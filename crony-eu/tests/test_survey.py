# SPDX-License-Identifier: AGPL-3.0-only
"""The table the choice of département is made from.

Every number here decides something, so each one is checked against a slice
small enough to count by hand. Two of them are checked because the first version
of this module got them wrong on the real data and the mistakes were invisible:
a sum inflated by a join fanout, and three cities reading as zero.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crony_eu import survey
from crony_eu.paths import Layout
from crony_eu.sources import fr_decp, fr_insee_pop, fr_rne_elus
from fakes import Elu, decp_row, write_decp, write_populations, write_rne_snapshot

SNAPSHOT = "2026-09-19"
ELUS_SNAPSHOT = "2026-09-16"


@pytest.fixture
def layout(outside_repo: Path) -> Layout:
    made = Layout(outside_repo)
    made.create()
    return made


def build(
    layout: Layout,
    contracts: list[dict[str, object]],
    populations: list,
    elus: list[Elu] | None = None,
) -> None:
    """Stage all three sources from generated fixtures."""
    write_decp(layout.raw(fr_decp.SOURCE, SNAPSHOT) / "decp.parquet", contracts)
    fr_decp.stage(layout, SNAPSHOT)

    write_populations(
        layout.raw(fr_insee_pop.SOURCE, SNAPSHOT) / fr_insee_pop.STORED, populations
    )
    fr_insee_pop.stage(layout, SNAPSHOT)

    write_rne_snapshot(layout.root, ELUS_SNAPSHOT, cm_current=elus or [])
    fr_rne_elus.stage(layout, ELUS_SNAPSHOT)


class TestDepartementOf:
    def test_a_metropolitan_code_takes_two_digits(self) -> None:
        assert survey.departement_of("'93001'").startswith("CASE")

    @pytest.mark.parametrize(
        ("commune", "expected"),
        [("93001", "93"), ("01234", "01"), ("97401", "974"), ("98411", "984")],
    )
    def test_it_splits_where_insee_splits(self, commune: str, expected: str) -> None:
        import duckdb

        sql = survey.departement_of(f"'{commune}'")
        assert duckdb.connect().execute(f"SELECT {sql}").fetchone()[0] == expected


class TestDepartements:
    def test_population_is_not_multiplied_by_the_contracts(
        self, layout: Layout
    ) -> None:
        # The bug this test exists for: joining commune to contract and elu
        # before aggregating fans each commune row out, and `sum(population)`
        # then counts it once per contract. On the real data that reported the
        # Nord as 53 billion inhabitants.
        contracts = [
            decp_row(uid=f"U{n}", acheteur_commune_code="93001") for n in range(7)
        ]
        build(
            layout,
            contracts,
            [("93001", "COM", "PMUN", 1200)],
            elus=[
                Elu(commune_code="93001", departement_code="93", surname="UNDEUX"),
                Elu(commune_code="93001", departement_code="93", surname="TROISQUATRE"),
            ],
        )

        rows, _ = survey.departements(layout)
        found = {row["departement_code"]: row for row in rows}
        assert found["93"]["population"] == 1200
        assert found["93"]["communes"] == 1
        assert found["93"]["contracts"] == 7
        assert found["93"]["people"] == 2

    def test_pairs_count_a_supplier_once_however_many_contracts_it_won(
        self, layout: Layout
    ) -> None:
        contracts = [
            decp_row(uid=f"U{n}", acheteur_commune_code="93001") for n in range(5)
        ]
        build(layout, contracts, [("93001", "COM", "PMUN", 1200)])
        rows, _ = survey.departements(layout)
        assert {row["departement_code"]: row["pairs"] for row in rows}["93"] == 1

    def test_the_432_12_column_counts_only_communes_over_the_line(
        self, layout: Layout
    ) -> None:
        contracts = [
            decp_row(uid="A", acheteur_commune_code="93001"),
            decp_row(uid="B", acheteur_commune_code="93002"),
        ]
        build(
            layout,
            contracts,
            [("93001", "COM", "PMUN", 1200), ("93002", "COM", "PMUN", 9000)],
        )
        rows, _ = survey.departements(layout)
        found = {row["departement_code"]: row for row in rows}["93"]
        assert found["pairs"] == 2
        assert found["pairs_above_432_12"] == 1

    def test_a_departement_that_bought_nothing_still_has_a_row(
        self, layout: Layout
    ) -> None:
        build(
            layout,
            [decp_row(acheteur_commune_code="93001")],
            [("93001", "COM", "PMUN", 1200), ("12001", "COM", "PMUN", 800)],
        )
        rows, _ = survey.departements(layout)
        found = {row["departement_code"]: row for row in rows}
        assert found["12"]["pairs"] == 0
        assert found["12"]["communes"] == 1


class TestBands:
    def test_the_3500_line_falls_between_two_bands(self, layout: Layout) -> None:
        build(
            layout,
            [
                decp_row(uid="A", acheteur_commune_code="93001"),
                decp_row(uid="B", acheteur_commune_code="93002"),
            ],
            [("93001", "COM", "PMUN", 3499), ("93002", "COM", "PMUN", 3500)],
        )
        bands = {row["band"]: row["pairs"] for row in survey.pairs_by_band(layout)}
        assert bands["500 to 3,499"] == 1
        assert bands["3,500 to 9,999"] == 1

    def test_a_scope_cuts_the_bands_to_one_departement(self, layout: Layout) -> None:
        build(
            layout,
            [
                decp_row(uid="A", acheteur_commune_code="93001"),
                decp_row(uid="B", acheteur_commune_code="12001"),
            ],
            [("93001", "COM", "PMUN", 1200), ("12001", "COM", "PMUN", 1200)],
        )
        cut = survey.pairs_by_band(layout, "93")
        assert sum(int(row["pairs"]) for row in cut) == 1


class TestPairsOutsideTheCommuneList:
    def test_an_arrondissement_buyer_is_counted_and_not_lost(
        self, layout: Layout
    ) -> None:
        # Paris buys under 75112, which INSEE publishes as an ARM and not a COM.
        # Without this count the survey shows Paris as a commune that bought
        # nothing, which is a wrong number wearing the clothes of a small slice.
        build(
            layout,
            [
                decp_row(uid="A", acheteur_commune_code="93001"),
                decp_row(uid="B", acheteur_commune_code="75112"),
                decp_row(uid="C", acheteur_commune_code="99999"),
            ],
            [("93001", "COM", "PMUN", 1200), ("75112", "ARM", "PMUN", 150000)],
        )
        counted = survey.pairs_outside_the_commune_list(layout)
        assert counted == {
            "on_a_commune": 1,
            "on_an_arrondissement": 1,
            "on_no_published_code": 1,
        }


class TestRefusals:
    def test_a_missing_source_names_the_command_that_fixes_it(
        self, layout: Layout
    ) -> None:
        with pytest.raises(survey.SurveyError, match="crony fetch fr-decp"):
            survey.departements(layout)
