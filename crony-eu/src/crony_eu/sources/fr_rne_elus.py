# SPDX-License-Identifier: AGPL-3.0-only
"""Répertoire national des élus: who holds municipal office, and since when.

The seed side of the same-body check. Four files, two datasets:

- the **current** register, `elus-conseillers-municipaux-cm.csv` and
  `elus-maires-mai.csv`, refreshed after the March 2026 municipal elections
- the **pre-election** extract of the councils in office on 27 February 2026,
  which is how F1 establishes that someone held office when a contract was
  notified in a term that has since ended

Both are Licence Ouverte 2.0. Resource URLs are resolved through the
data.gouv.fr API rather than hardcoded, because they move: some SIRENE files
changed storage in February 2026 and the old links return 404.

**Three things the observed headers corrected**, recorded here and in
`crony-eu/docs/sources/france.md` because the specification predicted otherwise:

1. There are two columns nobody expected, `Code de la collectivité à statut
   particulier` and its label, for Paris, Lyon, Marseille and Corsica.
2. The conseillers file carries `Code nationalité`. The maires files do not.
3. **The maires files have no function column at all.** The function is the
   file. So `function_label` is read from the conseillers file and supplied as
   `Maire` for rows from a maires file, rather than left null, which would make
   a mayor indistinguishable from a councillor with no delegated function and
   quietly break F1's Code pénal 432-12 tag.

**Why DuckDB and not the `csv` module.** The conseillers file is 65MB and about
half a million rows. Read into Python dicts that is most of a gigabyte before a
byte is written, so the read, the date parsing, the hashing and the ordering all
happen in SQL and the result arrives as Arrow.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from crony_eu.http import SourceClient, download, read_manifest
from crony_eu.normalize import (
    DATE_SHAPES,
    EARLIEST_PLAUSIBLE_YEAR,
    IMPLAUSIBLE_RATE_LIMIT,
    TWO_DIGIT_YEAR,
)
from crony_eu.parquet import write_arrow
from crony_eu.paths import Layout
from crony_eu.sql import identity, plausible_date

SOURCE = "fr-rne-elus"

#: Recorded in every manifest entry. Both datasets publish under it.
LICENCE = "Licence Ouverte 2.0"

#: The data.gouv.fr dataset API. `/api/1/datasets/<slug>/` lists resources with
#: their current URLs, which is what makes this survive a storage migration.
API = "https://www.data.gouv.fr/api/1/datasets"

#: The mandate every one of these files describes. Mayor is a *function* held
#: within a municipal council seat, not a separate mandate, which is why a mayor
#: appears in both files and groups into one person below.
MANDATE = "conseiller_municipal"


@dataclass(frozen=True)
class SourceFile:
    """One published CSV, and what reading it means."""

    key: str
    dataset: str
    title: str
    snapshot_kind: str
    function_label: str | None

    @property
    def filename(self) -> str:
        return f"{self.key}.csv"


#: The four files phase 1 reads. `function_label` is the value to supply when
#: the file has no function column, which is the maires files (see above).
FILES: tuple[SourceFile, ...] = (
    SourceFile(
        key="cm_current",
        dataset="repertoire-national-des-elus-1",
        title="elus-conseillers-municipaux-cm.csv",
        snapshot_kind="current",
        function_label=None,
    ),
    SourceFile(
        key="maires_current",
        dataset="repertoire-national-des-elus-1",
        title="elus-maires-mai.csv",
        snapshot_kind="current",
        function_label="Maire",
    ),
    SourceFile(
        key="cm_pre_election",
        dataset="elections-municipales-2026-maires-et-conseillers-municipaux-sortants",
        title="mun2026-cm-sortants-20260227.csv",
        snapshot_kind="pre_election",
        function_label=None,
    ),
    SourceFile(
        key="maires_pre_election",
        dataset="elections-municipales-2026-maires-et-conseillers-municipaux-sortants",
        title="mun2026-maires-sortants-20260227.csv",
        snapshot_kind="pre_election",
        function_label="Maire",
    ),
)

#: Published column -> our name. Two published columns are deliberately not
#: read: the département and collectivity labels, which are lookups we do not
#: need and would have to keep in step with a renaming.
COLUMNS = {
    "Code du département": "departement_code",
    "Code de la commune": "commune_code",
    "Libellé de la commune": "commune_label",
    "Nom de l'élu": "surname_raw",
    "Prénom de l'élu": "given_raw",
    "Code sexe": "sex",
    "Date de naissance": "birth_date_raw",
    "Code de la catégorie socio-professionnelle": "csp_code",
    "Date de début du mandat": "mandate_start_raw",
    "Date de début de la fonction": "function_start_raw",
}

#: Present in the conseillers files only. Read when there, null when not.
OPTIONAL_COLUMNS = {
    "Libellé de la fonction": "function_label_raw",
    "Code nationalité": "nationality_code",
}

#: Every date column, by the name we give it. Named once because the strict
#: parse, the "which row was bad" report and the plausibility gate all walk the
#: same list.
DATE_COLUMNS = ("birth_date_raw", "mandate_start_raw", "function_start_raw")


def date_sql(column: str, pivot: str) -> str:
    """The published date in `column`, as a DATE, or NULL if it is unreadable.

    The shape decides the format. Trying formats in order does not work here:
    `%d/%m/%Y` accepts `03/04/71` and returns the year 71, which is how the
    first staging of the real register produced 520,240 rows with a birth year
    under 100 and mandates starting in the year 20 (see `normalize.py`).

    `pivot` is the snapshot's own date, and it supplies the century for the
    two-digit form: a register cannot publish a date that has not happened yet.
    """
    text = f"nullif(trim({column}), '')"
    branches = []
    for pattern, fmt in DATE_SHAPES:
        parsed = f"try_strptime({text}, '{fmt}')::DATE"
        if pattern == TWO_DIGIT_YEAR:
            parsed = (
                f"CASE WHEN {parsed} > DATE '{pivot}' "
                f"THEN ({parsed} - INTERVAL 100 YEAR)::DATE ELSE {parsed} END"
            )
        branches.append(f"WHEN regexp_full_match({text}, '{pattern}') THEN {parsed}")
    return f"CASE WHEN {text} IS NULL THEN NULL {' '.join(branches)} ELSE NULL END"


ELUS = pa.schema(
    [
        pa.field("elu_row_id", pa.string()),
        pa.field("elu_person_id", pa.string()),
        pa.field("source_file", pa.string()),
        pa.field("snapshot_kind", pa.string()),
        pa.field("mandate_type", pa.string()),
        pa.field("departement_code", pa.string()),
        pa.field("commune_code", pa.string()),
        pa.field("commune_label", pa.string()),
        pa.field("surname_raw", pa.string()),
        pa.field("given_raw", pa.string()),
        pa.field("sex", pa.string()),
        pa.field("birth_date", pa.date32()),
        pa.field("birth_ym", pa.string()),
        pa.field("csp_code", pa.string()),
        pa.field("mandate_start", pa.date32()),
        pa.field("function_label", pa.string()),
        pa.field("function_start", pa.date32()),
        pa.field("nationality_code", pa.string()),
        pa.field("dates_plausible", pa.bool_()),
        pa.field("retrieved_at", pa.string()),
    ]
)

ELU_PERSON = pa.schema(
    [
        pa.field("elu_person_id", pa.string()),
        pa.field("snapshot_kind", pa.string()),
        pa.field("mandate_type", pa.string()),
        pa.field("departement_code", pa.string()),
        pa.field("commune_code", pa.string()),
        pa.field("commune_label", pa.string()),
        pa.field("surname_raw", pa.string()),
        pa.field("given_raw", pa.string()),
        pa.field("sex", pa.string()),
        pa.field("birth_date", pa.date32()),
        pa.field("birth_ym", pa.string()),
        pa.field("csp_code", pa.string()),
        pa.field("mandate_start", pa.date32()),
        pa.field("function_labels", pa.string()),
        pa.field("function_count", pa.int32()),
        pa.field("is_maire", pa.bool_()),
        pa.field("source_file_count", pa.int32()),
        pa.field("dates_plausible", pa.bool_()),
        pa.field("retrieved_at", pa.string()),
    ]
)


class StageError(Exception):
    """A published file did not read the way this module says it reads."""


def resource_url(client: SourceClient, dataset: str, title: str) -> str:
    """The current URL of one resource, asked of the API rather than assumed."""
    payload = client.json(f"{API}/{dataset}/")
    for resource in payload.get("resources", []):
        if resource.get("title") == title:
            url: str = resource["url"]
            return url
    published = sorted(r.get("title", "") for r in payload.get("resources", []))
    raise StageError(
        f"{dataset} no longer publishes a resource titled {title!r}. "
        f"It lists: {published}"
    )


def fetch(client: SourceClient, layout: Layout, snapshot: str) -> list[dict[str, Any]]:
    """Download the four files into a raw snapshot. Safe to run twice.

    A file already recorded in the snapshot's manifest is skipped rather than
    refetched, which is what makes an interrupted run resumable and a repeated
    run cheap.
    """
    destination = layout.raw(SOURCE, snapshot)
    manifest = layout.manifest(SOURCE, snapshot)
    already = {entry["path"] for entry in read_manifest(manifest)}

    entries: list[dict[str, Any]] = []
    for published in FILES:
        if published.filename in already:
            continue
        url = resource_url(client, published.dataset, published.title)
        entries.append(
            download(
                client,
                url,
                destination / published.filename,
                manifest,
                licence=LICENCE,
            )
        )
    return entries


def _retrieved(manifest: Path) -> dict[str, str]:
    """filename -> retrieved_at, the one clock reading that reaches a row."""
    return {entry["path"]: entry["retrieved_at"] for entry in read_manifest(manifest)}


def _select(published: SourceFile, path: Path, retrieved_at: str, pivot: str) -> str:
    """The SQL that turns one published CSV into the `elus` columns.

    Read as VARCHAR throughout, so that DuckDB's own type sniffing cannot decide
    a commune code is an integer and drop the leading zero that makes it a
    commune code.
    """

    def as_date(column: str) -> str:
        return date_sql(column, pivot)

    plausible_row = " AND ".join(
        plausible_date(as_date(column), EARLIEST_PLAUSIBLE_YEAR, pivot)
        for column in DATE_COLUMNS
    )
    function_label = (
        f"'{published.function_label}'"
        if published.function_label is not None
        else "nullif(trim(function_label_raw), '')"
    )
    nationality = (
        "nullif(trim(nationality_code), '')" if _has_nationality(path) else "NULL"
    )

    # The identity of a function row, and of the person holding it. The person
    # id drops the two function fields and nothing else, so two rows for one
    # councillor who is also the mayor group together.
    person_parts = [
        f"'{published.snapshot_kind}'",
        f"'{MANDATE}'",
        "surname_raw",
        "given_raw",
        "birth_date_raw",
        "commune_code",
        "mandate_start_raw",
    ]
    row_parts = [
        f"'{published.key}'",
        *person_parts,
        function_label,
        "function_start_raw",
    ]

    return f"""
        SELECT
            {identity(row_parts)}                         AS elu_row_id,
            {identity(person_parts)}                      AS elu_person_id,
            '{published.key}'                             AS source_file,
            '{published.snapshot_kind}'                   AS snapshot_kind,
            '{MANDATE}'                                   AS mandate_type,
            nullif(trim(departement_code), '')            AS departement_code,
            nullif(trim(commune_code), '')                AS commune_code,
            nullif(trim(commune_label), '')               AS commune_label,
            nullif(trim(surname_raw), '')                 AS surname_raw,
            nullif(trim(given_raw), '')                   AS given_raw,
            nullif(trim(sex), '')                         AS sex,
            {as_date("birth_date_raw")}                   AS birth_date,
            strftime({as_date("birth_date_raw")}, '%Y-%m') AS birth_ym,
            nullif(trim(csp_code), '')                    AS csp_code,
            {as_date("mandate_start_raw")}                AS mandate_start,
            {function_label}                              AS function_label,
            {as_date("function_start_raw")}               AS function_start,
            {plausible_row}                               AS dates_plausible,
            {nationality}                                 AS nationality_code,
            '{retrieved_at}'                              AS retrieved_at
        FROM read_csv(
            '{path.as_posix()}',
            delim = ';', header = true, all_varchar = true,
            names = {_names(path)!r}
        )
    """


def _header(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return handle.readline().rstrip("\r\n").split(";")


def _names(path: Path) -> list[str]:
    """Our column names, positionally, for every column the file publishes.

    Positional rather than by lookup, because `read_csv(names = ...)` renames in
    order. A column we do not read keeps a placeholder name so the positions
    stay aligned.
    """
    mapping = {**COLUMNS, **OPTIONAL_COLUMNS}
    names = []
    for index, published in enumerate(_header(path)):
        names.append(mapping.get(published.strip(), f"unused_{index}"))
    return names


def _has_nationality(path: Path) -> bool:
    return "nationality_code" in _names(path)


def _check_dates(
    connection: duckdb.DuckDBPyConnection,
    published: SourceFile,
    path: Path,
    pivot: str,
) -> None:
    """Refuse a file this project cannot read, and only that.

    Two different problems arrive looking the same, and the difference decides
    whether staging stops.

    **A shape we cannot read** means the file changed. Staging stops: carrying
    nulls forward would let a flag read "no mandate recorded" where the truth is
    "we stopped understanding this column".

    **A readable date that is implausible** is usually a fact about the
    register, not about our reading of it. The real file has exactly one
    councillor whose birth year is in the 1000s, out of 511,225. Stopping for
    that would mean never staging France until a prefecture fixes a typo.

    **Unless there are too many of them**, and that is the case real data
    taught. Reading `03/04/71` with `%d/%m/%Y` put *every* row of both
    pre-election files in the first century. So the rate decides: above
    `IMPLAUSIBLE_RATE_LIMIT` the file is being read wrongly and staging stops;
    below it, the rows are marked `dates_plausible = false`, counted, and
    carried. Constraint 9 then does the rest, because an implausible date
    cannot establish an overlap and an `unknown` overlap cannot reach a packet.

    Every report carries the file, the column and a row number, never the value.
    """
    reader = (
        f"read_csv('{path.as_posix()}', delim = ';', header = true, "
        f"all_varchar = true, names = {_names(path)!r})"
    )
    for column in DATE_COLUMNS:
        if column == "function_start_raw" and published.function_label is not None:
            continue

        parsed = date_sql(column, pivot)
        believable = plausible_date("parsed", EARLIEST_PLAUSIBLE_YEAR, pivot)
        counted = connection.execute(
            f"""
            SELECT
                count(*) FILTER (raw IS NOT NULL),
                count(*) FILTER (raw IS NOT NULL AND parsed IS NULL),
                count(*) FILTER (
                    parsed IS NOT NULL AND NOT {believable}
                ),
                min(row_number) FILTER (
                    raw IS NOT NULL AND (parsed IS NULL OR NOT {believable})
                )
            FROM (
                SELECT row_number() OVER () AS row_number,
                       nullif(trim({column}), '') AS raw,
                       {parsed} AS parsed
                FROM {reader}
            )
            """
        ).fetchone()
        assert counted is not None, "an aggregate query always returns one row"
        present, unreadable, implausible, first = counted

        if unreadable:
            raise StageError(
                f"{published.filename}: column {column} matches none of the "
                f"published date shapes in {unreadable} of {present} rows, "
                f"first at data row {first}. Shapes read here are "
                f"{[pattern for pattern, _ in DATE_SHAPES]}. The value is not "
                "shown: it may be a person's birth date (CLAUDE.md, "
                "constraint 13)."
            )

        if present and implausible / present > IMPLAUSIBLE_RATE_LIMIT:
            share = 100 * implausible / present
            raise StageError(
                f"{published.filename}: column {column} reads as a date "
                f"outside {EARLIEST_PLAUSIBLE_YEAR}..{pivot} in {implausible} "
                f"of {present} rows ({share:.1f}%), first at data row {first}. "
                "Above "
                f"{IMPLAUSIBLE_RATE_LIMIT:.0%} that is this project reading the "
                "file wrongly rather than the register being surprising. The "
                "value is not shown (constraint 13)."
            )


def stage(layout: Layout, snapshot: str) -> dict[str, int]:
    """Read the raw snapshot into `elus.parquet` and `elu_person.parquet`.

    Offline, no clock, and byte-identical on a rerun: the ordering is by the row
    id, which is a hash of the fields that define the row and is therefore both
    unique and independent of the order DuckDB happened to scan in.
    """
    raw = layout.raw(SOURCE, snapshot)
    staged = layout.staged(SOURCE, snapshot)
    retrieved = _retrieved(layout.manifest(SOURCE, snapshot))

    missing = [f.filename for f in FILES if not (raw / f.filename).is_file()]
    if missing:
        raise StageError(
            f"{SOURCE}: snapshot {snapshot} is missing {missing}. Fetch it first."
        )

    connection = duckdb.connect()
    try:
        selects = []
        for published in FILES:
            path = raw / published.filename
            _check_dates(connection, published, path, snapshot)
            selects.append(
                _select(
                    published, path, retrieved.get(published.filename, ""), snapshot
                )
            )

        # A temp table rather than an Arrow table registered back into the
        # connection. Both tables below are derived from the same rows, and an
        # Arrow result handed back to DuckDB is a stream that is consumed once;
        # the second scan of it blocks. This also reads the four CSVs once
        # instead of twice, which at 130MB is the difference worth having.
        connection.execute(f"CREATE TEMP TABLE elus AS {' UNION ALL '.join(selects)}")

        # `to_arrow_table`, not `arrow()`: the latter returns a
        # RecordBatchReader, which is a stream that can be read once and which
        # `pq.write_table` will not take.
        elus = connection.execute(
            "SELECT * FROM elus ORDER BY elu_row_id"
        ).to_arrow_table()
        # Grouped by the fields the person id is built from, and nothing else.
        # `GROUP BY ALL` was wrong here: it also grouped by the descriptive
        # columns, so one councillor whose socio-professional code differed
        # between two published files became two rows sharing one
        # `elu_person_id`. One row in 994,761, and enough to fan out every join
        # downstream of it. The descriptive columns are reduced with `min()`,
        # which is a choice rather than a fact, and `source_file_count` says
        # when the sources disagreed about a person.
        people = connection.execute(
            """
            SELECT
                elu_person_id,
                snapshot_kind, mandate_type, commune_code,
                surname_raw, given_raw, birth_date, mandate_start,
                min(departement_code) AS departement_code,
                min(commune_label)    AS commune_label,
                min(sex)              AS sex,
                min(birth_ym)         AS birth_ym,
                min(csp_code)         AS csp_code,
                string_agg(DISTINCT function_label, ';' ORDER BY function_label)
                    AS function_labels,
                count(DISTINCT function_label)::INTEGER AS function_count,
                bool_or(function_label = 'Maire') AS is_maire,
                count(DISTINCT source_file)::INTEGER AS source_file_count,
                bool_and(dates_plausible) AS dates_plausible,
                min(retrieved_at) AS retrieved_at
            FROM elus
            GROUP BY
                elu_person_id, snapshot_kind, mandate_type, commune_code,
                surname_raw, given_raw, birth_date, mandate_start
            ORDER BY elu_person_id
            """
        ).to_arrow_table()
    finally:
        connection.close()

    return {
        "elus": write_arrow(elus, ELUS, staged / "elus.parquet"),
        "elu_person": write_arrow(people, ELU_PERSON, staged / "elu_person.parquet"),
    }
