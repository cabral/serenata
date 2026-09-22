# SPDX-License-Identifier: AGPL-3.0-only
"""Données essentielles de la commande publique: who bought what, from whom.

The money side of the same-body check. One consolidated file, republished from
the ~10,900 resources the buying platforms publish separately, by
`decp-processing` (https://github.com/ColinMaudry/decp-processing) under the
Licence Ouverte 2.0.

**This is a consolidation, not the register itself**, and that distinction has
to survive into the provenance of anything built on it. Two consequences the
rest of this module is shaped by:

- `sourceDataset` and `sourceFile` name the platform each row came from, and
  they are staged rather than dropped, because "which platform published this"
  is the first question anyone checking a finding asks.
- the `acheteur_*` and `titulaire_*` geography, category and population columns
  are **enrichment added by the consolidator**, not fields a buyer declared.
  They are staged into their own columns, marked as derived in
  `crony-eu/docs/sources/france.md`, and a case packet that cites one has to
  cite the consolidator for it. The buyer declared a SIRET; the commune code
  beside it is somebody's join.

The enrichment is also what removes SIRENE from this session. The work order
asked for a SIRENE stock ingestion to map a buyer SIREN to a commune code; the
consolidated file already carries `acheteur_commune_code`, so the stock is not
fetched. What SIRENE was also going to supply, the supplier's *catégorie
juridique* for F1's exclusion list, is a separate question answered in
`stage()`'s report rather than assumed here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from crony_eu.http import SourceClient, download, read_manifest
from crony_eu.normalize import (
    EARLIEST_PLAUSIBLE_YEAR,
    IMPLAUSIBLE_RATE_LIMIT,
    LA_POSTE_SIREN,
)
from crony_eu.parquet import write_arrow, write_batches
from crony_eu.paths import Layout
from crony_eu.sql import digits_only, identity, plausible_date, siret_valid

SOURCE = "fr-decp"

#: Recorded in every manifest entry. The dataset publishes under `lov2`.
LICENCE = "Licence Ouverte 2.0"

#: The data.gouv.fr dataset API, as for the élus: resource URLs move, and the
#: static.data.gouv.fr path carries a publication timestamp that changes daily.
API = "https://www.data.gouv.fr/api/1/datasets"

DATASET = "donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire"

#: Published resource title -> the name it is stored under in the snapshot.
#:
#: `schema.json` is archived beside the data on purpose. It is the publisher's
#: own statement of what the columns are on the day the file was fetched, it
#: costs 24KB, and it is the only way a later reader can tell a column this
#: project misread from a column the publisher changed.
FILES: tuple[tuple[str, str], ...] = (
    ("decp.parquet", "decp.parquet"),
    ("schema.json", "schema.json"),
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
    """Download the consolidated file and its schema. Safe to run twice.

    A file already recorded in the snapshot's manifest is skipped rather than
    refetched. At 247MB that is not a nicety: it is what makes an interrupted
    run resumable without asking data.gouv.fr for the whole thing again.
    """
    destination = layout.raw(SOURCE, snapshot)
    manifest = layout.manifest(SOURCE, snapshot)
    already = {entry["path"] for entry in read_manifest(manifest)}

    entries: list[dict[str, Any]] = []
    for title, stored in FILES:
        if stored in already:
            continue
        url = resource_url(client, DATASET, title)
        entries.append(
            download(client, url, destination / stored, manifest, licence=LICENCE)
        )
    return entries


#: The published columns this project stages, in the order they are hashed into
#: `decp_row_id`. Enrichment columns are deliberately **not** in the key: a row
#: is identified by what the buyer published, so the consolidator recomputing a
#: commune code does not change the identity of the contract underneath it.
#:
#: `titulaire_typeIdentifiant` is in the list because the real file needs it. On
#: the 2026-09-19 snapshot, 218 pairs of rows are identical on every other
#: published field and differ only in the case of that value (`SIRET` against
#: `Siret`), which without it makes 218 pairs of contracts share an id.
IDENTITY_COLUMNS: tuple[str, ...] = (
    "uid",
    "id",
    "modification_id",
    "acheteur_id",
    "titulaire_id",
    "titulaire_typeIdentifiant",
    "objet",
    "montant",
    "dateNotification",
    "datePublicationDonnees",
    "procedure",
    "nature",
    "dureeMois",
    "offresRecues",
    "lieuExecution_code",
    "codeCPV",
    "idAccordCadre",
    "typeGroupementOperateurs",
    "sourceDataset",
    "sourceFile",
)

#: Published supplier identifier type -> the value staged. The published column
#: carries case and punctuation variants of the same few types, and a join that
#: filtered on `= 'SIRET'` would silently lose the 227 rows spelled otherwise.
ID_TYPES = {
    "SIRET": "SIRET",
    "TVA": "TVA",
    "TVA_INTRACOMMUNAUTAIRE": "TVA",
    "HORS_UE": "HORS_UE",
    "UE": "UE",
    "IREP": "IREP",
    "RIDET": "RIDET",
    "TAHITI": "TAHITI",
    "FRWF": "FRWF",
}

#: The buyer category, as the consolidator classifies it, that phase 1 treats as
#: a commune. Phase 1 covers communes only; `Groupement de communes` and the
#: rest are phase 2 and are staged but not mapped.
COMMUNE_CATEGORY = "Commune"


#: Staged column -> whether the buyer declared it or the consolidator computed
#: it. ADR-0007 requires the two to be cited apart in an export, so the split is
#: data a later stage reads rather than a paragraph a later reader has to
#: remember. `crony-eu/tests/test_sources_fr_decp.py` pins that every column in
#: `CONTRACTS` appears here exactly once, so a new column cannot arrive without
#: someone deciding which kind of fact it is.
#:
#: `identity` is the third value and it is neither: those columns are this
#: project's own, computed from the published fields and carrying no claim about
#: the world.
DECLARED = "declared"
DERIVED = "derived"
IDENTITY = "identity"

ATTRIBUTE_ORIGIN: dict[str, str] = {
    "decp_row_id": IDENTITY,
    "buyer_assertion_id": IDENTITY,
    "uid": DECLARED,
    "contract_id": DECLARED,
    "modification_id": DECLARED,
    "is_latest_version": IDENTITY,
    "published_as_current": DECLARED,
    "buyer_siret": DECLARED,
    "buyer_siren": IDENTITY,
    "buyer_siret_valid": IDENTITY,
    "buyer_label": DECLARED,
    # The two ADR-0007 was written about. `acheteur_categorie` is the
    # consolidator's classification of the buyer and `acheteur_commune_code` its
    # join from the SIRET; the buyer declared neither.
    "buyer_category": DERIVED,
    "buyer_commune_code": DERIVED,
    "buyer_departement_code": DERIVED,
    "supplier_id_raw": DECLARED,
    "supplier_id_type_raw": DECLARED,
    "supplier_id_type": IDENTITY,
    "supplier_siret": IDENTITY,
    "supplier_siren": IDENTITY,
    "supplier_siret_valid": IDENTITY,
    "supplier_has_siren": IDENTITY,
    "supplier_label": DECLARED,
    "supplier_size_category": DERIVED,
    "supplier_activity_code": DERIVED,
    "supplier_commune_code": DERIVED,
    "supplier_departement_code": DERIVED,
    "subject": DECLARED,
    "cpv_code": DECLARED,
    "nature": DECLARED,
    "procedure": DECLARED,
    "duration_months": DECLARED,
    "offers_received": DECLARED,
    "framework_id": DECLARED,
    "consortium_type": DECLARED,
    "execution_place_code": DECLARED,
    "amount_eur": DECLARED,
    "amount_rationalised_eur": DERIVED,
    "amount_anomaly": DERIVED,
    "date_notification": DECLARED,
    "date_published": DECLARED,
    "dates_plausible": IDENTITY,
    "source_dataset": DECLARED,
    "source_file": DECLARED,
    "source_url": IDENTITY,
    "retrieved_at": IDENTITY,
}


def derived_columns() -> tuple[str, ...]:
    """The columns an export has to attribute to the consolidator."""
    return tuple(
        sorted(name for name, origin in ATTRIBUTE_ORIGIN.items() if origin == DERIVED)
    )


CONTRACTS = pa.schema(
    [
        pa.field("decp_row_id", pa.string()),
        pa.field("buyer_assertion_id", pa.string()),
        pa.field("uid", pa.string()),
        pa.field("contract_id", pa.string()),
        pa.field("modification_id", pa.int32()),
        pa.field("is_latest_version", pa.bool_()),
        pa.field("published_as_current", pa.bool_()),
        pa.field("buyer_siret", pa.string()),
        pa.field("buyer_siren", pa.string()),
        pa.field("buyer_siret_valid", pa.bool_()),
        pa.field("buyer_label", pa.string()),
        pa.field("buyer_category", pa.string()),
        pa.field("buyer_commune_code", pa.string()),
        pa.field("buyer_departement_code", pa.string()),
        pa.field("supplier_id_raw", pa.string()),
        pa.field("supplier_id_type_raw", pa.string()),
        pa.field("supplier_id_type", pa.string()),
        pa.field("supplier_siret", pa.string()),
        pa.field("supplier_siren", pa.string()),
        pa.field("supplier_siret_valid", pa.bool_()),
        pa.field("supplier_has_siren", pa.bool_()),
        pa.field("supplier_label", pa.string()),
        pa.field("supplier_size_category", pa.string()),
        pa.field("supplier_activity_code", pa.string()),
        pa.field("supplier_commune_code", pa.string()),
        pa.field("supplier_departement_code", pa.string()),
        pa.field("subject", pa.string()),
        pa.field("cpv_code", pa.string()),
        pa.field("nature", pa.string()),
        pa.field("procedure", pa.string()),
        pa.field("duration_months", pa.int32()),
        pa.field("offers_received", pa.int32()),
        pa.field("framework_id", pa.string()),
        pa.field("consortium_type", pa.string()),
        pa.field("execution_place_code", pa.string()),
        pa.field("amount_eur", pa.decimal128(18, 2)),
        pa.field("amount_rationalised_eur", pa.decimal128(18, 2)),
        pa.field("amount_anomaly", pa.string()),
        pa.field("date_notification", pa.date32()),
        pa.field("date_published", pa.date32()),
        pa.field("dates_plausible", pa.bool_()),
        pa.field("source_dataset", pa.string()),
        pa.field("source_file", pa.string()),
        pa.field("source_url", pa.string()),
        pa.field("retrieved_at", pa.string()),
    ]
)

#: buyer SIREN -> the commune it buys for. One row per (SIREN, commune code),
#: never one per SIREN, because on the real file four SIRENs carry more than one
#: commune code and one of them carries sixteen. Collapsing that to a single
#: value would invent a fact; `commune_code_count` shows it instead.
COMMUNE_BUYERS = pa.schema(
    [
        pa.field("buyer_siren", pa.string()),
        pa.field("commune_code", pa.string()),
        pa.field("departement_code", pa.string()),
        pa.field("buyer_label", pa.string()),
        pa.field("commune_code_count", pa.int32()),
        pa.field("siret_count", pa.int32()),
        pa.field("contract_count", pa.int32()),
        pa.field("retrieved_at", pa.string()),
    ]
)


def _id_type_sql() -> str:
    """The published identifier type, spelled one way.

    The column carries `SIRET`, `Siret` and `siret`, and `HORS_UE` next to
    `HORS-UE` and `HORS UE`. A join filtering on `= 'SIRET'` would quietly drop
    the 227 rows spelled otherwise, which is the sort of loss that looks like a
    data gap rather than a bug.

    A type this project has no name for passes through under its own, upper
    cased. The real file carries `FRW`, `RCI` and `AUTRE`, which are nobody's
    idea of an identifier scheme and are not SIRETs, and inventing a mapping for
    them would be worse than carrying them as they came.
    """
    trimmed = "trim(titulaire_typeIdentifiant)"
    normalised = f"upper(replace(replace({trimmed}, '-', '_'), ' ', '_'))"
    branches = " ".join(
        f"WHEN {normalised} = '{published}' THEN '{staged}'"
        for published, staged in ID_TYPES.items()
    )
    return f"CASE {branches} ELSE nullif({normalised}, '') END"


def _select(path: Path, retrieved_at: str, url: str, pivot: str) -> str:
    """The SQL that turns the consolidated file into the staged columns.

    `url` and `retrieved_at` come from the snapshot's manifest and are copied on
    to every row. That is a lot of identical strings, and Parquet dictionary
    encodes them to almost nothing; what it buys is a row that carries its own
    provenance, so an export citing one attribute does not have to go back to a
    manifest to find out where it came from (constraint 2).
    """
    buyer_siret = digits_only("acheteur_id", 14)
    supplier_type = _id_type_sql()
    published_siret = digits_only("titulaire_id", 14)
    supplier_siret = f"CASE WHEN {supplier_type} = 'SIRET' THEN {published_siret} END"
    notified = "dateNotification"
    plausible = plausible_date(notified, EARLIEST_PLAUSIBLE_YEAR, pivot)

    # What a buyer verification binds to. `decp_row_id` deliberately hashes only
    # the published fields, so it does not change when the consolidator
    # recomputes a commune code, which is exactly why it cannot bind a check to
    # the values that check examined. This one hashes the asserted enrichment
    # with the snapshot, so a changed assertion cannot reuse an old review.
    buyer_assertion = identity(
        [
            f"'{pivot}'",
            buyer_siret,
            "nullif(trim(acheteur_categorie), '')",
            "nullif(trim(acheteur_commune_code), '')",
        ]
    )

    return f"""
        SELECT
            {identity(IDENTITY_COLUMNS)}                  AS decp_row_id,
            {buyer_assertion}                             AS buyer_assertion_id,
            nullif(trim(uid), '')                         AS uid,
            nullif(trim(id), '')                          AS contract_id,
            CAST(modification_id AS INTEGER)              AS modification_id,
            coalesce(modification_id, 0) = max(coalesce(modification_id, 0))
                OVER (PARTITION BY uid, titulaire_id)     AS is_latest_version,
            donneesActuelles                              AS published_as_current,

            {buyer_siret}                                 AS buyer_siret,
            substr({buyer_siret}, 1, 9)                   AS buyer_siren,
            {siret_valid(buyer_siret, LA_POSTE_SIREN)}    AS buyer_siret_valid,
            nullif(trim(acheteur_nom), '')                AS buyer_label,
            nullif(trim(acheteur_categorie), '')          AS buyer_category,
            nullif(trim(acheteur_commune_code), '')       AS buyer_commune_code,
            nullif(trim(acheteur_departement_code), '')   AS buyer_departement_code,

            nullif(trim(titulaire_id), '')                AS supplier_id_raw,
            nullif(trim(titulaire_typeIdentifiant), '')   AS supplier_id_type_raw,
            {supplier_type}                               AS supplier_id_type,
            {supplier_siret}                              AS supplier_siret,
            substr({supplier_siret}, 1, 9)                AS supplier_siren,
            {siret_valid(supplier_siret, LA_POSTE_SIREN)} AS supplier_siret_valid,
            {supplier_siret} IS NOT NULL                  AS supplier_has_siren,
            nullif(trim(titulaire_nom), '')               AS supplier_label,
            nullif(trim(titulaire_categorie), '')         AS supplier_size_category,
            nullif(trim(titulaire_activite_code), '')     AS supplier_activity_code,
            nullif(trim(titulaire_commune_code), '')      AS supplier_commune_code,
            nullif(trim(titulaire_departement_code), '')  AS supplier_departement_code,

            nullif(trim(objet), '')                       AS subject,
            nullif(trim(codeCPV), '')                     AS cpv_code,
            nullif(trim(nature), '')                      AS nature,
            nullif(trim(procedure), '')                   AS procedure,
            CAST(dureeMois AS INTEGER)                    AS duration_months,
            CAST(offresRecues AS INTEGER)                 AS offers_received,
            nullif(trim(idAccordCadre), '')               AS framework_id,
            nullif(trim(typeGroupementOperateurs), '')    AS consortium_type,
            nullif(trim(lieuExecution_code), '')          AS execution_place_code,
            CAST(montant AS DECIMAL(18, 2))               AS amount_eur,
            CAST(montant_rationalise AS DECIMAL(18, 2))   AS amount_rationalised_eur,
            nullif(trim(montant_anomalie), '')            AS amount_anomaly,
            {notified}                                    AS date_notification,
            datePublicationDonnees                        AS date_published,
            {plausible}                                   AS dates_plausible,
            nullif(trim(sourceDataset), '')               AS source_dataset,
            nullif(trim(sourceFile), '')                  AS source_file,
            '{url}'                                       AS source_url,
            '{retrieved_at}'                              AS retrieved_at
        FROM read_parquet('{path.as_posix()}')
    """


def _check_notification_dates(
    connection: duckdb.DuckDBPyConnection, path: Path, pivot: str
) -> tuple[int, int]:
    """Refuse a file this project cannot read, and only that.

    The same rule the élus register taught, applied to the other side of the
    join. A notification date outside the believable window is either the
    register carrying a typo or this project reading the column wrongly, and the
    rate is what tells them apart: on the 2026-09-19 snapshot 928 rows of
    3,281,288 (0.028%) fall before 1900, which is a platform's empty date
    landing on `0001-01-01` rather than a misread column.

    A date this project cannot believe still matters downstream, because
    constraint 9 says an overlap it cannot establish is `unknown` and an
    `unknown` overlap cannot reach a case packet. So these rows are marked and
    carried, never dropped, and the counts go into the report.
    """
    believable = plausible_date("dateNotification", EARLIEST_PLAUSIBLE_YEAR, pivot)
    counted = connection.execute(
        f"""
        SELECT count(*), count(*) FILTER (NOT {believable})
        FROM read_parquet('{path.as_posix()}')
        """
    ).fetchone()
    assert counted is not None, "an aggregate query always returns one row"
    total, implausible = counted

    if total and implausible / total > IMPLAUSIBLE_RATE_LIMIT:
        share = 100 * implausible / total
        raise StageError(
            f"decp.parquet: dateNotification falls outside "
            f"{EARLIEST_PLAUSIBLE_YEAR}..{pivot} in {implausible} of {total} "
            f"rows ({share:.1f}%). Above {IMPLAUSIBLE_RATE_LIMIT:.0%} that is "
            "this project reading the file wrongly rather than a platform "
            "publishing a bad date."
        )
    return int(total), int(implausible)


def stage(layout: Layout, snapshot: str) -> dict[str, int]:
    """Read the raw snapshot into three tables. Offline, and clock-free.

    - `contract_versions.parquet`: every published row, one per contract version
      per titulaire per lot.
    - `contracts.parquet`: the rows at the latest version of each contract.
    - `commune_buyers.parquet`: buyer SIREN -> the commune it buys for.

    **The latest version is chosen by `modification_id`, not by the published
    `donneesActuelles` flag**, and the difference is not small. On the
    2026-09-19 snapshot the flag is true on 2,114,178 rows and every one of them
    does carry the highest modification for its contract, so the flag is never
    wrong. It is absent: 70,277 (contract, titulaire) groups have no row flagged
    at all, 43,726 of them because the flag is false on every row including the
    highest-numbered one, and 26,551 because the whole group has no
    modification_id and no flag. Filtering on the flag would have dropped every
    one of those contracts out of `contracts.parquet` without a word.

    Ordering is by `decp_row_id`, which is a hash of the published fields and is
    therefore unique and independent of the order DuckDB scanned in.
    """
    raw = layout.raw(SOURCE, snapshot)
    staged = layout.staged(SOURCE, snapshot)
    source = raw / "decp.parquet"
    if not source.is_file():
        raise StageError(
            f"{SOURCE}: snapshot {snapshot} is missing decp.parquet. Fetch it first."
        )

    entries = {
        entry["path"]: entry
        for entry in read_manifest(layout.manifest(SOURCE, snapshot))
    }
    published = entries.get("decp.parquet", {})

    connection = duckdb.connect()
    try:
        total, implausible = _check_notification_dates(connection, source, snapshot)
        select = _select(
            source,
            published.get("retrieved_at", ""),
            published.get("url", ""),
            snapshot,
        )
        connection.execute(f"CREATE TEMP TABLE versions AS {select}")

        duplicated = connection.execute(
            "SELECT count(*) - count(DISTINCT decp_row_id) FROM versions"
        ).fetchone()
        assert duplicated is not None
        if duplicated[0]:
            raise StageError(
                f"decp.parquet: {duplicated[0]} rows share a decp_row_id with "
                "another row. The id is a hash of every published field staged "
                "here, so this means the publisher now emits rows this project "
                "cannot tell apart, and every count keyed on the id is wrong "
                "until IDENTITY_COLUMNS covers whatever distinguishes them."
            )

        written = {
            "contract_versions": write_batches(
                connection.execute(
                    "SELECT * FROM versions ORDER BY decp_row_id"
                ).to_arrow_reader(),
                CONTRACTS,
                staged / "contract_versions.parquet",
            ),
            "contracts": write_batches(
                connection.execute(
                    "SELECT * FROM versions WHERE is_latest_version "
                    "ORDER BY decp_row_id"
                ).to_arrow_reader(),
                CONTRACTS,
                staged / "contracts.parquet",
            ),
        }

        # One row per (SIREN, commune code). `commune_code_count` carries the
        # ambiguity rather than resolving it: four SIRENs on the real file map to
        # more than one commune, and one of them maps to sixteen.
        buyers = connection.execute(
            f"""
            SELECT
                buyer_siren,
                buyer_commune_code                  AS commune_code,
                min(buyer_departement_code)         AS departement_code,
                min(buyer_label)                    AS buyer_label,
                CAST(count(DISTINCT buyer_commune_code)
                     OVER (PARTITION BY buyer_siren) AS INTEGER)
                                                    AS commune_code_count,
                CAST(count(DISTINCT buyer_siret) AS INTEGER)   AS siret_count,
                CAST(count(DISTINCT uid) AS INTEGER)           AS contract_count,
                min(retrieved_at)                   AS retrieved_at
            FROM versions
            WHERE buyer_category = '{COMMUNE_CATEGORY}'
              AND buyer_siren IS NOT NULL
              AND buyer_commune_code IS NOT NULL
            GROUP BY buyer_siren, buyer_commune_code
            ORDER BY buyer_siren, commune_code
            """
        ).to_arrow_table()
        written["commune_buyers"] = write_arrow(
            buyers, COMMUNE_BUYERS, staged / "commune_buyers.parquet"
        )

        _write_report(connection, layout, snapshot, total, implausible)
    finally:
        connection.close()

    return written


def _write_report(
    connection: duckdb.DuckDBPyConnection,
    layout: Layout,
    snapshot: str,
    total: int,
    implausible: int,
) -> Path:
    """Aggregates about the snapshot, written where a person can read them.

    Counts, shares and contract ids. No buyer name, no supplier name, no row
    content: constraint 13 says an agent session looks at real data through
    schemas and counts, and a report it writes has to be the same shape or the
    constraint only holds while nobody opens the file.

    The amount outliers are the exception that proves it. The work order asks
    for the top 0.1% by amount, and they are listed by contract id precisely so
    that checking one means opening the source notice rather than reading a
    description out of this file.
    """

    def one(sql: str) -> tuple[Any, ...]:
        """One aggregate row, which an aggregate query always returns."""
        row = connection.execute(sql).fetchone()
        assert row is not None, "an aggregate query always returns one row"
        return row

    published, latest = one(
        "SELECT count(*), count(*) FILTER (is_latest_version) FROM versions"
    )
    buyers = one(
        f"""
        SELECT count(*) FILTER (buyer_commune_code IS NOT NULL),
               count(DISTINCT buyer_siren)
                   FILTER (buyer_category = '{COMMUNE_CATEGORY}'),
               count(DISTINCT buyer_commune_code)
                   FILTER (buyer_category = '{COMMUNE_CATEGORY}'),
               count(*) FILTER (buyer_siret_valid)
        FROM versions
        """
    )
    suppliers = one(
        """
        SELECT count(*) FILTER (supplier_has_siren),
               count(*) FILTER (supplier_siret_valid),
               count(*) FILTER (
                   supplier_siret IS NOT NULL AND NOT supplier_siret_valid),
               count(DISTINCT supplier_siren)
        FROM versions
        """
    )
    versions = one(
        """
        SELECT count(*) FILTER (published_as_current),
               (SELECT count(*) FROM (
                    SELECT uid, supplier_id_raw FROM versions GROUP BY 1, 2
                    HAVING count(*) FILTER (published_as_current) = 0)),
               count(*) FILTER (published_as_current IS NULL)
        FROM versions
        """
    )
    notified = one(
        "SELECT min(date_notification), max(date_notification) FROM versions"
    )
    pairs = one(
        """
        SELECT count(*) FROM (
            SELECT DISTINCT buyer_commune_code, supplier_siren
            FROM versions
            WHERE is_latest_version AND buyer_category = 'Commune'
              AND buyer_commune_code IS NOT NULL AND supplier_siren IS NOT NULL)
        """
    )

    (cutoff,) = one(
        "SELECT quantile_cont(amount_eur, 0.999) FROM versions "
        "WHERE is_latest_version AND amount_eur IS NOT NULL"
    )
    outliers = connection.execute(
        f"""
        SELECT DISTINCT uid FROM versions
        WHERE is_latest_version AND amount_eur >= {cutoff}
        ORDER BY uid
        """
    ).fetchall()

    vocabularies = {
        column: {
            str(value): count
            for value, count in connection.execute(
                f"SELECT {column}, count(*) FROM versions GROUP BY 1 ORDER BY 2 DESC"
            ).fetchall()
        }
        for column in ("buyer_category", "supplier_id_type", "supplier_size_category")
    }

    report = {
        "source": SOURCE,
        "snapshot": snapshot,
        "rows_published": published,
        "rows_latest_version": latest,
        "notification_date": {
            "earliest": str(notified[0]),
            "latest": str(notified[1]),
            "implausible_rows": implausible,
            "implausible_share": round(implausible / total, 6) if total else 0.0,
        },
        "buyers": {
            "rows_with_commune_code": buyers[0],
            "rows_with_commune_code_share": round(buyers[0] / published, 6),
            "rows_with_valid_siret_share": round(buyers[3] / published, 6),
            "distinct_commune_buyer_sirens": buyers[1],
            "distinct_communes_buying": buyers[2],
        },
        "suppliers": {
            "rows_with_siren_share": round(suppliers[0] / published, 6),
            "rows_with_valid_siret_share": round(suppliers[1] / published, 6),
            "rows_with_siret_failing_checksum": suppliers[2],
            "distinct_supplier_sirens": suppliers[3],
        },
        "versions": {
            "rows_published_as_current": versions[0],
            "groups_with_no_row_flagged_current": versions[1],
            "rows_with_no_flag_at_all": versions[2],
        },
        "commune_supplier_pairs": pairs[0],
        "amount_outliers": {
            "quantile": 0.999,
            "threshold_eur": float(cutoff) if cutoff is not None else None,
            "contract_count": len(outliers),
            "contract_uids": [uid for (uid,) in outliers],
        },
        "vocabularies": vocabularies,
    }

    destination = layout.reports() / f"{SOURCE}-{snapshot}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return destination


#: Staged table -> the schema it is written with. `crony doctor` compares what is
#: on disk against this, so a table staged by older code is reported as stale
#: rather than discovered as a missing-column error three stages later.
TABLES: dict[str, pa.Schema] = {
    "contracts": CONTRACTS,
    "contract_versions": CONTRACTS,
    "commune_buyers": COMMUNE_BUYERS,
}
