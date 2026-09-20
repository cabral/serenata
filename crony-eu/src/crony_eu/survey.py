# SPDX-License-Identifier: AGPL-3.0-only
"""What each département would give phase 1, measured before one is picked.

Phase 1 runs on one département (`crony-eu/docs/work-order-phase-1.md`), and the
work order has the maintainer choosing it before session 1. Choosing it from the
staged data instead means the choice can be defended: the slice that produces
forty candidate pairs and the slice that produces four thousand look identical
on a map, and only one of them can measure a base rate.

This reads the three staged sources and nothing else. It makes no network call,
takes no clock reading and writes no file unless asked, because its whole job is
to put a table in front of a person who then decides.

**Every column here is a count.** Constraint 12 says an aggregate is not
automatically person-free, and the smallest cell in this table is a whole
département, so the counts are safe at this grain and would not be at commune
grain. `crony survey communes` does not exist for that reason.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import duckdb

from crony_eu.paths import Layout
from crony_eu.sources import fr_decp, fr_insee_pop, fr_rne_elus

#: Population bands, by the lower bound of each, copied from the band list in
#: `crony-eu/docs/flags/F1-same-body.md` rather than chosen here.
#:
#: **Every bound is inclusive at the top.** Code pénal art. 432-12 gives its
#: exception in communes of "3 500 habitants au plus", 3,500 or fewer, so a
#: commune of exactly 3,500 is inside the exception and not above it. The first
#: version of this module banded at `>= 3500` and put it above, which disagreed
#: with the flag spec by one inhabitant. Two communes sit exactly on the line.
BANDS: tuple[tuple[int, str], ...] = (
    (0, "up to 500"),
    (501, "501 to 3,500"),
    (3_501, "3,501 to 10,000"),
    (10_001, "10,001 to 50,000"),
    (50_001, "above 50,000"),
)

#: The population at or below which art. 432-12's exception can apply.
ARTICLE_432_12_CEILING = 3_500


class SurveyError(Exception):
    """A source the survey needs has not been staged."""


@dataclass(frozen=True)
class Staged:
    """Which snapshot of each source the survey read."""

    decp: str
    populations: str
    elus: str

    def as_dict(self) -> dict[str, str]:
        return {
            fr_decp.SOURCE: self.decp,
            fr_insee_pop.SOURCE: self.populations,
            fr_rne_elus.SOURCE: self.elus,
        }


def _latest(layout: Layout, source: str, table: str) -> tuple[str, str]:
    """The newest staged snapshot of one source, and the path to one table."""
    for snapshot in reversed(layout.snapshots(source)):
        path = layout.staged(source, snapshot) / f"{table}.parquet"
        if path.is_file():
            return snapshot, path.as_posix()
    raise SurveyError(
        f"{source} has no staged {table}.parquet. Run `crony fetch {source}` "
        f"and `crony stage {source}` first."
    )


def _band_sql(column: str) -> str:
    """The population band of a commune, as a CASE over `BANDS`."""
    branches = " ".join(
        f"WHEN {column} >= {lower} THEN '{label}'"
        for lower, label in reversed(BANDS)
        if lower
    )
    return (
        f"CASE WHEN {column} IS NULL THEN 'unknown' {branches} ELSE '{BANDS[0][1]}' END"
    )


#: The département a commune code belongs to. Overseas codes are three digits
#: and metropolitan ones two, which is the only rule needed here: checked
#: against INSEE's own département list on the 2023 vintage, this derivation
#: produces exactly its 100 codes and no others, in both directions.
#:
#: It is derived rather than read from a column because only one of the three
#: sources publishes one, and that column is empty for the 6,988 overseas rows
#: (`crony-eu/docs/sources/france.md`). Deriving it from the commune code makes
#: the three sources agree, and it is what lets the survey show overseas
#: départements that `--scope dep:` cannot currently reach.
def departement_of(column: str) -> str:
    return (
        f"CASE WHEN starts_with({column}, '97') OR starts_with({column}, '98') "
        f"THEN substr({column}, 1, 3) ELSE substr({column}, 1, 2) END"
    )


def _connect(layout: Layout) -> tuple[duckdb.DuckDBPyConnection, Staged]:
    """A connection with the three staged sources registered as views."""
    decp_snapshot, contracts = _latest(layout, fr_decp.SOURCE, "contracts")
    pop_snapshot, populations = _latest(layout, fr_insee_pop.SOURCE, "populations")
    elus_snapshot, people = _latest(layout, fr_rne_elus.SOURCE, "elu_person")

    connection = duckdb.connect()
    connection.execute(f"CREATE VIEW contracts AS SELECT * FROM '{contracts}'")
    connection.execute(
        f"CREATE VIEW communes AS SELECT geo_code AS commune_code, population "
        f"FROM '{populations}' WHERE geo_object = 'COM' "
        f"AND measure = '{fr_insee_pop.LEGAL_MEASURE}'"
    )
    connection.execute(
        f"CREATE VIEW arrondissements AS SELECT geo_code, population "
        f"FROM '{populations}' WHERE geo_object = 'ARM' "
        f"AND measure = '{fr_insee_pop.LEGAL_MEASURE}'"
    )
    connection.execute(f"CREATE VIEW people AS SELECT * FROM '{people}'")
    return connection, Staged(decp_snapshot, pop_snapshot, elus_snapshot)


def departements(layout: Layout) -> tuple[list[dict[str, Any]], Staged]:
    """One row per département: what a phase 1 slice there would have to work on.

    The columns are chosen to answer one question, which is whether a slice can
    produce a measurable rate. `pairs` is F1's denominator, `people_with_birth_key`
    is how much of the élu side can be matched at all, and `pairs_above_432_12`
    is how many of those pairs sit in a commune **above** the 3,500-inhabitant
    line, so a commune of exactly 3,500 is not counted: art. 432-12's exception
    covers it.
    """
    connection, staged = _connect(layout)
    try:
        rows = connection.execute(
            f"""
            WITH commune AS (
                SELECT commune_code, population,
                       {departement_of("commune_code")} AS departement_code
                FROM communes
            ),
            -- Each measure is aggregated to one row per departement *before*
            -- anything is joined. Joining first and aggregating after fans the
            -- commune rows out across contracts and elus, which leaves the
            -- distinct counts right and every sum multiplied by the fan. The
            -- first version of this query did exactly that and reported the
            -- population of the Nord as 53 billion.
            territory AS (
                SELECT departement_code,
                       count(*)         AS communes,
                       sum(population)  AS population
                FROM commune GROUP BY departement_code
            ),
            contract AS (
                SELECT DISTINCT buyer_commune_code AS commune_code, supplier_siren, uid
                FROM contracts
                WHERE buyer_category = '{fr_decp.COMMUNE_CATEGORY}'
                  AND buyer_commune_code IS NOT NULL
            ),
            bought AS (
                SELECT k.departement_code,
                       count(DISTINCT t.commune_code)   AS communes_buying,
                       count(DISTINCT t.uid)            AS contracts,
                       count(DISTINCT t.supplier_siren) AS suppliers
                FROM contract t JOIN commune k USING (commune_code)
                GROUP BY k.departement_code
            ),
            paired AS (
                SELECT k.departement_code,
                       count(*)                               AS pairs,
                       count(*) FILTER (
                           k.population > {ARTICLE_432_12_CEILING}) AS pairs_above
                FROM (SELECT DISTINCT commune_code, supplier_siren
                      FROM contract WHERE supplier_siren IS NOT NULL) p
                JOIN commune k USING (commune_code)
                GROUP BY k.departement_code
            ),
            elected AS (
                SELECT k.departement_code,
                       count(DISTINCT e.elu_person_id)  AS people,
                       count(DISTINCT e.elu_person_id)
                           FILTER (e.birth_ym IS NOT NULL) AS people_with_birth_key
                FROM people e JOIN commune k USING (commune_code)
                WHERE e.snapshot_kind = 'current'
                GROUP BY k.departement_code
            )
            SELECT
                t.departement_code,
                t.communes,
                t.population,
                coalesce(b.communes_buying, 0)        AS communes_buying,
                coalesce(b.contracts, 0)              AS contracts,
                coalesce(b.suppliers, 0)              AS suppliers,
                coalesce(p.pairs, 0)                  AS pairs,
                coalesce(p.pairs_above, 0)            AS pairs_above_432_12,
                coalesce(e.people, 0)                 AS people,
                coalesce(e.people_with_birth_key, 0)  AS people_with_birth_key
            FROM territory t
            LEFT JOIN bought b USING (departement_code)
            LEFT JOIN paired p USING (departement_code)
            LEFT JOIN elected e USING (departement_code)
            ORDER BY t.departement_code
            """
        ).fetchall()
        names = [description[0] for description in connection.description or []]
    finally:
        connection.close()

    return [dict(zip(names, row, strict=True)) for row in rows], staged


def pairs_by_band(layout: Layout, scope: str | None = None) -> list[dict[str, Any]]:
    """Distinct (commune, supplier) pairs per population band.

    F1's denominator, cut the way its base rate has to be cut. A rate pooled
    over a commune of four hundred and one of four hundred thousand describes
    neither, and the 3,500 line inside these bands is the one art. 432-12 turns
    on.
    """
    connection, _ = _connect(layout)
    where = ""
    if scope is not None:
        where = f"WHERE {departement_of('commune_code')} = '{scope}'"
    try:
        rows = connection.execute(
            f"""
            WITH commune AS (
                SELECT commune_code, population, {_band_sql("population")} AS band
                FROM communes {where}
            ),
            pair AS (
                SELECT DISTINCT buyer_commune_code AS commune_code, supplier_siren
                FROM contracts
                WHERE buyer_category = '{fr_decp.COMMUNE_CATEGORY}'
                  AND buyer_commune_code IS NOT NULL AND supplier_siren IS NOT NULL
            )
            SELECT
                c.band,
                count(DISTINCT c.commune_code)                  AS communes,
                count(DISTINCT p.commune_code)                  AS communes_buying,
                count(p.supplier_siren)                         AS pairs
            FROM commune c
            LEFT JOIN pair p USING (commune_code)
            GROUP BY c.band
            """
        ).fetchall()
        names = [description[0] for description in connection.description or []]
    finally:
        connection.close()

    order = {label: index for index, (_, label) in enumerate(BANDS)}
    listed = [dict(zip(names, row, strict=True)) for row in rows]
    return sorted(listed, key=lambda row: order.get(str(row["band"]), len(order)))


def write_report(layout: Layout, rows: list[dict[str, Any]], staged: Staged) -> Any:
    """Keep the table beside the staged data, so a choice can be rechecked."""
    destination = layout.reports() / "survey-departements.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {"staged": staged.as_dict(), "departements": rows},
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return destination


def pairs_outside_the_commune_list(layout: Layout) -> dict[str, int]:
    """Pairs whose buyer code is not one of INSEE's communes, and why.

    The bands are cut against INSEE's `COM` rows, and three cities do not buy
    under one. Paris, Lyon and Marseille purchase under **arrondissement
    municipal** codes (`75112`, not `75056`), which INSEE publishes as `ARM`.
    Left alone, the survey reports Paris as one commune with zero contracts and
    zero pairs, which is not a small slice; it is a wrong number that looks like
    a small slice.

    So the pairs that fall outside are counted and shown rather than dropped.
    On the 2026-09-19 snapshot: 305,426 land on a commune, 10,779 on an
    arrondissement, and 2,377 on a code INSEE does not publish at all, of which
    2,118 are Mayotte, which this vintage excludes by construction.

    Phase 1 covers communes in one metropolitan département, so none of this
    blocks it. It does mean a slice of `dep:75`, `dep:69` or `dep:13` would be
    measuring the wrong thing, and that is worth knowing before picking one
    rather than after.
    """
    connection, _ = _connect(layout)
    try:
        counted = connection.execute(
            f"""
            WITH pair AS (
                SELECT DISTINCT buyer_commune_code AS code, supplier_siren
                FROM contracts
                WHERE buyer_category = '{fr_decp.COMMUNE_CATEGORY}'
                  AND buyer_commune_code IS NOT NULL AND supplier_siren IS NOT NULL
            )
            SELECT
                count(*) FILTER (code IN (SELECT commune_code FROM communes)),
                count(*) FILTER (code IN (SELECT geo_code FROM arrondissements)),
                count(*) FILTER (
                    code NOT IN (SELECT commune_code FROM communes)
                    AND code NOT IN (SELECT geo_code FROM arrondissements))
            FROM pair
            """
        ).fetchone()
        assert counted is not None, "an aggregate query always returns one row"
    finally:
        connection.close()
    return {
        "on_a_commune": int(counted[0]),
        "on_an_arrondissement": int(counted[1]),
        "on_no_published_code": int(counted[2]),
    }
