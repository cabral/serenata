# SPDX-License-Identifier: AGPL-3.0-only
"""F1, one generated scenario per branch the work order lists for session 5.

"An élu found only in the pre-election extract; a mandate starting after the
notification date; a role starting after the notification date; a role ended
before it; a role with no dates at all; an excluded legal category; the 432-12
tag set and not set; a consortium supplier; a contract with several versions; a
key collision; a supplier with forty contracts to one commune counting once in
the pair denominator." Each is here, and so is every packet gate.

Every name is invented, and F1's output is a statistical anomaly with possible
innocent explanations, never an accusation. The tests assert counts and columns,
not conclusions about anyone.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest
from crony_eu.flags import base_rates
from crony_eu.flags import f1_same_body as f1
from crony_eu.match import buyer_verification as bv
from crony_eu.match import candidates, judgments
from crony_eu.paths import Layout
from fakes import (
    api_establishment,
    api_response,
    api_unit,
    decp_row,
    set_roles,
    siret,
    slice_elu,
    slice_officer,
    stage_slice,
)

SUPPLIER = siret("81230001")
BUYER = siret("21740010")
NOTIFIED = date(2024, 5, 14)


@pytest.fixture
def layout(outside_repo: Path) -> Layout:
    made = Layout(outside_repo)
    made.create()
    return made


def contract(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "acheteur_id": BUYER,
        "acheteur_commune_code": "74010",
        "titulaire_id": SUPPLIER,
        "dateNotification": NOTIFIED,
        "montant": 120000.0,
    }
    fields.update(overrides)
    return decp_row(**fields)


def flag(layout: Layout) -> list[dict[str, object]]:
    candidates.run(layout, "74")
    f1.run(layout, "74")
    _, run = f1.current_run(layout, "74")
    return [dict(row) for row in pq.read_table(run / "hits.parquet").to_pylist()]


def run_directory(layout: Layout) -> Path:
    return f1.current_run(layout, "74")[1]


class TestConditions:
    """The pure functions, one branch each."""

    def test_a_current_mandate_covers_a_later_date(self) -> None:
        assert (
            f1.mandate_overlap("current", date(2026, 3, 22), None, date(2026, 5, 1))
            == f1.TRUE
        )

    def test_a_mandate_starting_after_the_date_is_unknown_not_false(self) -> None:
        # The register cannot show earlier terms, so it cannot show someone was
        # out of office; the spec gives `unknown` when neither can be established.
        got = f1.mandate_overlap("current", date(2026, 3, 22), None, date(2024, 5, 14))
        assert got == f1.UNKNOWN

    def test_a_pre_election_mandate_covers_up_to_the_new_council(self) -> None:
        start, new = date(2020, 5, 18), date(2026, 3, 22)
        assert (
            f1.mandate_overlap("pre_election", start, new, date(2024, 5, 14)) == f1.TRUE
        )
        assert (
            f1.mandate_overlap("pre_election", start, new, date(2026, 4, 1))
            == f1.UNKNOWN
        )

    def test_a_pre_election_mandate_without_a_new_council_is_unknown(self) -> None:
        got = f1.mandate_overlap(
            "pre_election", date(2020, 5, 18), None, date(2024, 5, 14)
        )
        assert got == f1.UNKNOWN

    def test_no_notification_date_is_unknown(self) -> None:
        assert f1.mandate_overlap("current", date(2020, 1, 1), None, None) == f1.UNKNOWN
        assert f1.role_overlap("role_start", date(2020, 1, 1), None, None) == f1.UNKNOWN

    def test_a_role_starting_after_the_date_is_false(self) -> None:
        got = f1.role_overlap("role_start", date(2025, 1, 1), None, date(2024, 5, 14))
        assert got == f1.FALSE

    def test_a_role_ended_before_the_date_is_false(self) -> None:
        got = f1.role_overlap(
            "role_start", date(2019, 1, 1), date(2023, 1, 1), date(2024, 5, 14)
        )
        assert got == f1.FALSE

    def test_a_role_with_no_dates_at_all_is_unknown(self) -> None:
        assert f1.role_overlap("absent", None, None, date(2024, 5, 14)) == f1.UNKNOWN

    def test_a_filing_date_is_not_a_role_start(self) -> None:
        # The case the whole role-date gate exists for.
        got = f1.role_overlap("filing_date", date(2019, 1, 1), None, date(2024, 5, 14))
        assert got == f1.UNKNOWN

    def test_an_open_role_covers_the_date(self) -> None:
        got = f1.role_overlap("role_start", date(2019, 1, 1), None, date(2024, 5, 14))
        assert got == f1.TRUE

    @pytest.mark.parametrize(
        ("code", "out"),
        [
            ("5515", True),
            ("5615", True),
            ("5415", True),
            ("4110", True),
            ("7210", True),
            ("5710", False),
            ("5599", False),
            (None, False),
        ],
    )
    def test_the_exclusion_list(self, code: str | None, out: bool) -> None:
        # 5599 is where an SPL sits, and it cannot be excluded by category.
        assert f1.excluded(code) is out

    def test_the_432_12_tag_needs_all_three(self) -> None:
        cap = f1.ARTICLE_432_12_ANNUAL_CAP
        assert f1.possible_432_12_exception(3500, "Maire", cap) is True
        assert f1.possible_432_12_exception(3501, "Maire", cap) is False
        assert f1.possible_432_12_exception(3500, None, cap) is False
        assert f1.possible_432_12_exception(3500, "Maire", cap + 1) is False
        assert f1.possible_432_12_exception(3500, "Maire", None) is False

    @pytest.mark.parametrize(
        "labels",
        [
            "Maire",
            "Maire délégué",
            "1er adjoint au Maire",
            "Maire;3ème adjoint au Maire",
        ],
    )
    def test_the_functions_the_tag_covers(self, labels: str) -> None:
        assert f1.holds_a_432_12_function(labels)


class TestScenarios:
    """Generated slices, end to end through matching and the flag."""

    def test_a_current_councillor_is_a_hit_with_its_overlaps(
        self, layout: Layout
    ) -> None:
        stage_slice(
            layout,
            [slice_elu(mandate_start="2020-05-18")],
            [slice_officer()],
            contracts=[contract()],
        )
        (hit,) = flag(layout)
        assert hit["mandate_overlap"] == f1.TRUE
        # The company API carries no role dates, and the flag says so.
        assert hit["role_overlap"] == f1.UNKNOWN
        assert hit["match_status"] == "unconfirmed"
        assert hit["calibration"] == "uncalibrated"
        assert hit["packet_eligible"] is False

    def test_an_elu_found_only_in_the_pre_election_extract(
        self, layout: Layout
    ) -> None:
        stage_slice(
            layout,
            [slice_elu(surname="AUTRENOM", mandate_start="2026-03-22")],
            [slice_officer()],
            pre_election=[slice_elu(mandate_start="20/05/18")],
            contracts=[contract()],
        )
        hits = flag(layout)
        assert [(h["elu_snapshot_kind"], h["mandate_overlap"]) for h in hits] == [
            ("pre_election", f1.TRUE)
        ]

    def test_a_mandate_starting_after_the_notification(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu(mandate_start="2026-03-22")],
            [slice_officer()],
            contracts=[contract()],
        )
        assert flag(layout)[0]["mandate_overlap"] == f1.UNKNOWN

    @pytest.mark.parametrize(
        ("start", "end", "expected"),
        [
            (date(2025, 1, 1), None, f1.FALSE),
            (date(2019, 1, 1), date(2023, 1, 1), f1.FALSE),
            (date(2019, 1, 1), None, f1.TRUE),
            (None, None, f1.UNKNOWN),
        ],
    )
    def test_role_dates_when_a_source_has_them(
        self, layout: Layout, start: date | None, end: date | None, expected: str
    ) -> None:
        stage_slice(layout, [slice_elu()], [slice_officer()], contracts=[contract()])
        set_roles(layout, start, end)
        assert flag(layout)[0]["role_overlap"] == expected

    def test_an_excluded_legal_category_is_reported_and_not_flagged(
        self, layout: Layout
    ) -> None:
        stage_slice(
            layout,
            [slice_elu()],
            [slice_officer()],
            contracts=[contract()],
            supplier_category="5515",
        )
        assert flag(layout) == []
        excluded = pq.read_table(run_directory(layout) / "excluded.parquet").to_pylist()
        assert [row["supplier_legal_category"] for row in excluded] == ["5515"]
        # And the excluded supplier is not in the denominator either.
        assert pq.read_table(run_directory(layout) / "pairs.parquet").num_rows == 0

    def test_the_432_12_tag_is_set(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu(function_label="Maire")],
            [slice_officer()],
            contracts=[contract(montant=9000.0)],
            populations=[("74010", "COM", "PMUN", 900)],
        )
        (hit,) = flag(layout)
        assert hit["possible_432_12_exception"] is True
        assert hit["yearly_total_eur"] == Decimal("9000.00")

    def test_the_432_12_tag_is_not_set_over_the_yearly_cap(
        self, layout: Layout
    ) -> None:
        # Two contracts in one year, each under the cap, together over it.
        stage_slice(
            layout,
            [slice_elu(function_label="Maire")],
            [slice_officer()],
            contracts=[
                contract(uid="A", montant=9000.0),
                contract(uid="B", montant=9000.0),
            ],
            populations=[("74010", "COM", "PMUN", 900)],
        )
        hits = flag(layout)
        assert {h["possible_432_12_exception"] for h in hits} == {False}
        assert {h["yearly_total_eur"] for h in hits} == {Decimal("18000.00")}

    def test_a_consortium_gives_each_supplier_its_own_pair(
        self, layout: Layout
    ) -> None:
        other = siret("81230002")
        stage_slice(
            layout,
            [slice_elu()],
            [slice_officer()],
            contracts=[contract(uid="C"), contract(uid="C", titulaire_id=other)],
            other_suppliers={other: []},
        )
        flag(layout)
        pairs = pq.read_table(run_directory(layout) / "pairs.parquet").to_pylist()
        assert sorted(row["supplier_siren"] for row in pairs) == sorted(
            [SUPPLIER[:9], other[:9]]
        )

    def test_only_the_latest_version_of_a_contract_counts(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu()],
            [slice_officer()],
            contracts=[
                contract(uid="V", modification_id=0, montant=100.0),
                contract(uid="V", modification_id=1, montant=200.0),
            ],
        )
        (hit,) = flag(layout)
        assert hit["amount_eur"] == Decimal("200.00")

    def test_a_key_collision_is_carried(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu(commune_code="74010"), slice_elu(commune_code="74011")],
            [slice_officer()],
            contracts=[contract()],
        )
        hits = flag(layout)
        assert hits and all(hit["key_collision"] for hit in hits)

    def test_forty_contracts_are_one_pair(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu()],
            [slice_officer()],
            contracts=[contract(uid=f"U{n:02d}") for n in range(40)],
        )
        hits = flag(layout)
        assert len(hits) == 40
        pairs = pq.read_table(run_directory(layout) / "pairs.parquet").to_pylist()
        assert len(pairs) == 1
        assert pairs[0]["contracts"] == 40
        (band,) = [
            row
            for row in base_rates.table(layout, run_directory(layout))
            if row["pairs"]
        ]
        assert (band["pairs"], band["candidate_pairs"]) == (1, 1)

    def test_an_implausible_notification_date_gives_unknown_overlaps(
        self, layout: Layout
    ) -> None:
        # A platform's empty date lands on 0001-01-01. Staging marks it
        # implausible, and the flag reads it as no date at all rather than as a
        # date two thousand years before any mandate.
        # Out-of-scope plausible rows keep the file under the stage's 1% rule,
        # which would otherwise, rightly, refuse a file that is all bad dates.
        filler = [
            contract(uid=f"OUT{n}", acheteur_commune_code="93001") for n in range(150)
        ]
        stage_slice(
            layout,
            [slice_elu(mandate_start="2020-05-18")],
            [slice_officer()],
            contracts=[contract(dateNotification=date(1, 1, 1)), *filler],
        )
        (hit,) = flag(layout)
        assert hit["date_notification"] is None
        assert hit["mandate_overlap"] == f1.UNKNOWN
        assert hit["yearly_total_eur"] is None

    def test_a_rejected_judgment_is_not_a_hit(self, layout: Layout) -> None:
        stage_slice(layout, [slice_elu()], [slice_officer()], contracts=[contract()])
        candidates.run(layout, "74")
        (row,) = judgments.latest(layout)
        judgments.decide(layout, str(row["judgment_id"]), judgments.REJECTED, "m")
        f1.run(layout, "74")
        assert pq.read_table(run_directory(layout) / "hits.parquet").num_rows == 0


class TestGates:
    """Packet eligibility is every gate at once; each is a column of its own."""

    def everything_true(self, layout: Layout, monkeypatch: pytest.MonkeyPatch) -> dict:
        body = api_response(
            [
                api_unit(
                    unit_siren=BUYER[:9],
                    nature_juridique="7210",
                    establishments=[api_establishment(establishment_siret=BUYER)],
                )
            ]
        )
        stage_slice(
            layout,
            [slice_elu(mandate_start="2020-05-18")],
            [slice_officer()],
            contracts=[contract()],
            buyer=BUYER,
            buyer_body=body,
        )
        set_roles(layout, date(2019, 1, 1), None)
        candidates.run(layout, "74")
        (row,) = judgments.latest(layout)
        judgments.decide(layout, str(row["judgment_id"]), judgments.CONFIRMED, "m")
        (queued,) = bv.queue(layout, "2026-09-19", "2026-09-22", "74")
        bv.append(
            layout,
            [
                bv.record(
                    queued,
                    identity_corroborated=bv.TRUE,
                    historical_geography=bv.NOT_ESTABLISHED,
                    decided_by="m",
                )
            ],
        )
        monkeypatch.setattr(f1, "CALIBRATION", "2026-10-01")
        f1.run(layout, "74")
        (hit,) = pq.read_table(run_directory(layout) / "hits.parquet").to_pylist()
        return dict(hit)

    def test_every_gate_passing_makes_a_packet_eligible_hit(
        self, layout: Layout, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hit = self.everything_true(layout, monkeypatch)
        assert hit["packet_eligible"] is True
        # Snapshot corroboration: identity true, geography never rewritten.
        assert hit["historical_geography"] == bv.NOT_ESTABLISHED
        assert hit["calibration"] == "2026-10-01"

    def test_uncalibrated_blocks_even_when_everything_else_passes(
        self, layout: Layout, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        hit = self.everything_true(layout, monkeypatch)
        monkeypatch.setattr(f1, "CALIBRATION", None)
        f1.run(layout, "74")
        (again,) = pq.read_table(run_directory(layout) / "hits.parquet").to_pylist()
        assert hit["packet_eligible"] and not again["packet_eligible"]
        assert again["gate_calibrated"] is False

    def test_a_non_diffusible_supplier_is_not_redistributable(
        self, layout: Layout
    ) -> None:
        stage_slice(
            layout,
            [slice_elu()],
            [slice_officer()],
            contracts=[contract()],
            supplier_diffusion="P",
        )
        (hit,) = flag(layout)
        assert hit["gate_redistributable"] is False

    def test_an_unreviewed_buyer_is_not_verified(self, layout: Layout) -> None:
        stage_slice(layout, [slice_elu()], [slice_officer()], contracts=[contract()])
        (hit,) = flag(layout)
        assert hit["buyer_identity_corroborated"] == bv.UNKNOWN
        assert hit["gate_buyer_verified"] is False

    def test_a_decision_on_older_evidence_does_not_carry_over(
        self, layout: Layout, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self.everything_true(layout, monkeypatch)
        # The registry now answers differently: re-archive the buyer's evidence.
        from crony_eu.sources import fr_entreprises_api as api
        from fakes import archive_api

        archive_api(
            layout,
            [
                (
                    api.Ask("siret", BUYER),
                    api_response(
                        [
                            api_unit(
                                unit_siren=BUYER[:9],
                                nature_juridique="7210",
                                establishments=[
                                    api_establishment(
                                        establishment_siret=BUYER, state="F"
                                    )
                                ],
                            )
                        ]
                    ),
                )
            ],
        )
        f1.run(layout, "74")
        (hit,) = pq.read_table(run_directory(layout) / "hits.parquet").to_pylist()
        assert hit["buyer_identity_corroborated"] == bv.UNKNOWN
        assert hit["packet_eligible"] is False


class TestBaseRate:
    def test_wilson_is_bounded_and_empty_is_none(self) -> None:
        assert base_rates.wilson(0, 0) is None
        low, high = base_rates.wilson(0, 10) or (None, None)
        assert low == 0.0 and 0 < high < 0.35
        low, high = base_rates.wilson(10, 10) or (None, None)
        assert 0.65 < low < 1 and high == 1.0

    def test_wilson_matches_a_known_value(self) -> None:
        # 20 of 100 at z = 1.96, worked by hand: centre 0.211098, margin 0.077733,
        # so 0.133365 to 0.288831.
        low, high = base_rates.wilson(20, 100) or (0.0, 0.0)
        assert round(low, 4) == 0.1334 and round(high, 4) == 0.2888

    def test_losses_are_counted_per_gate_and_not_netted(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu(mandate_start="2020-05-18")],
            [slice_officer()],
            contracts=[contract()],
        )
        flag(layout)
        (row,) = [
            r for r in base_rates.table(layout, run_directory(layout)) if r["pairs"]
        ]
        # One pair, failing four gates, is counted under all four.
        assert row["candidate_pairs"] == 1
        assert row["lost_judgment_not_confirmed"] == 1
        assert row["lost_role_overlap_not_true"] == 1
        assert row["lost_buyer_not_corroborated"] == 1
        assert row["lost_uncalibrated"] == 1
        assert row["lost_mandate_overlap_unknown"] == 0
        assert row["geography_not_established_pairs"] == 1

    def test_the_bands_come_out_in_band_order(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu()],
            [slice_officer()],
            contracts=[contract(), contract(uid="Z", acheteur_commune_code="74011")],
            populations=[
                ("74010", "COM", "PMUN", 60000),
                ("74011", "COM", "PMUN", 300),
            ],
        )
        flag(layout)
        bands = [row["band"] for row in base_rates.table(layout, run_directory(layout))]
        assert bands == ["up to 500", "above 50,000"]

    def test_precision_reads_the_seeded_sample(self, layout: Layout) -> None:
        stage_slice(layout, [slice_elu()], [slice_officer()], contracts=[contract()])
        flag(layout)
        assert base_rates.precision(layout, "74").reviewed == 0
        (row,) = judgments.latest(layout)
        judgments.decide(layout, str(row["judgment_id"]), judgments.CONFIRMED, "m")
        measured = base_rates.precision(layout, "74")
        assert (measured.reviewed, measured.confirmed, measured.estimate) == (1, 1, 1.0)
        assert measured.seed == base_rates.PRECISION_SEED

    def test_the_report_goes_to_the_data_directory_and_not_the_spec(
        self, layout: Layout
    ) -> None:
        stage_slice(layout, [slice_elu()], [slice_officer()], contracts=[contract()])
        flag(layout)
        body = base_rates.report(layout, "74")
        assert (layout.reports() / "f1-base-rate-dep-74.json").is_file()
        assert body["status"].startswith("uncalibrated")
        assert body["query"].endswith("f1_base_rate.sql")

    def test_a_base_rate_needs_a_flag_run_for_the_current_inputs(
        self, layout: Layout
    ) -> None:
        stage_slice(layout, [slice_elu()], [slice_officer()], contracts=[contract()])
        candidates.run(layout, "74")
        with pytest.raises(FileNotFoundError, match="crony flag F1"):
            base_rates.report(layout, "74")


class TestDeterminism:
    def test_the_same_inputs_give_the_same_bytes(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu()],
            [slice_officer()],
            contracts=[contract(uid=f"U{n}") for n in range(5)],
        )
        flag(layout)
        first = (run_directory(layout) / "hits.parquet").read_bytes()
        f1.run(layout, "74")
        assert (run_directory(layout) / "hits.parquet").read_bytes() == first

    def test_a_new_decision_is_a_new_run(self, layout: Layout) -> None:
        stage_slice(layout, [slice_elu()], [slice_officer()], contracts=[contract()])
        flag(layout)
        before = run_directory(layout)
        (row,) = judgments.latest(layout)
        judgments.decide(layout, str(row["judgment_id"]), judgments.CONFIRMED, "m")
        assert run_directory(layout) != before


class TestRefusals:
    def test_missing_candidates_names_the_command(self, layout: Layout) -> None:
        stage_slice(layout, [slice_elu()], [slice_officer()], contracts=[contract()])
        with pytest.raises(f1.FlagError, match="crony match fr --scope dep:74"):
            f1.run(layout, "74")

    def test_missing_staged_data_names_the_command(self, layout: Layout) -> None:
        with pytest.raises(f1.FlagError, match="crony fetch"):
            f1.run(layout, "74")
