# SPDX-License-Identifier: AGPL-3.0-only
"""Session 4: the key, the candidates, and the log of what a person decided.

The work order's list for this session, in order: normalisation properties (in
`test_normalize.py`), key collision detection, append-only semantics and
latest-wins, history returned in order, a confirm followed by a reject leaving
both rows readable. Every name is invented; `NOMDEXEMPLE` is not a French surname
and nothing here could be mistaken for a finding.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow.parquet as pq
import pytest
from crony_eu.match import candidates, judgments, keys
from crony_eu.paths import Layout
from fakes import (
    Elu,
    api_officer,
    api_response,
    api_unit,
    decp_row,
    siret,
    write_decp,
    write_rne_snapshot,
)

SUPPLIER = siret("81230001")


@pytest.fixture
def layout(outside_repo: Path) -> Layout:
    made = Layout(outside_repo)
    made.create()
    return made


class TestKeys:
    def test_a_key_is_surname_given_and_month(self) -> None:
        assert keys.build("Nomdexemple", "Jean-Pierre", "1971-04") == (
            "NOMDEXEMPLE|JEANPIERRE|1971-04"
        )

    @pytest.mark.parametrize(
        ("surname", "given", "month"),
        [(None, "A", "1971-04"), ("A", None, "1971-04"), ("A", "B", None)],
    )
    def test_a_missing_part_builds_no_key(
        self, surname: str | None, given: str | None, month: str | None
    ) -> None:
        # Matching on less than the rule is not matching under the rule.
        assert keys.build(surname, given, month) is None

    def test_the_two_registers_spellings_meet(self) -> None:
        # Mixed case and accents on the élu side, capitals on the officer side.
        elu = keys.elu_keys("Nomdéxemple", "Élodie", "1971-04")
        officer = keys.officer_keys("NOMDEXEMPLE", None, "ELODIE MARIE", "1971-04")
        assert {k.value for k in elu} == {k.value for k in officer}

    def test_an_officer_gets_a_key_per_distinct_surname(self) -> None:
        got = keys.officer_keys("NOMDEXEMPLE", "AUTRENOM", "JEAN", "1971-04")
        assert [(k.variant, k.value) for k in got] == [
            (keys.BIRTH, "NOMDEXEMPLE|JEAN|1971-04"),
            (keys.USAGE, "AUTRENOM|JEAN|1971-04"),
        ]

    def test_equal_birth_and_usage_names_give_one_key(self) -> None:
        # 931 of the 1,366 real `BIRTH (USAGE)` officers.
        got = keys.officer_keys("NOMDEXEMPLE", "NOMDEXEMPLE", "JEAN", "1971-04")
        assert [k.variant for k in got] == [keys.BIRTH]

    def test_an_elu_surname_with_a_marriage_marker_is_taken_whole(self) -> None:
        # As specified: the élu side has one variant. 810 élus nationally carry
        # EP, NEE or VEUVE inside their surname and match nobody under this
        # rule. Handling them is a new rule id, not an edit.
        got = keys.elu_keys("NOMDEXEMPLE EPOUSE AUTRENOM", "Jean", "1971-04")
        assert [k.value for k in got] == ["NOMDEXEMPLE EPOUSE AUTRENOM|JEAN|1971-04"]


class TestJudgmentsLog:
    def candidate(self, elu: str = "e1", officer: str = "o1") -> dict[str, object]:
        return {
            "judgment_id": judgments.judgment_id(keys.RULE_ID, elu, officer),
            "rule_id": keys.RULE_ID,
            "elu_person_id": elu,
            "officer_row_id": officer,
            "siren": SUPPLIER[:9],
        }

    def test_a_candidate_enters_as_pending_from_the_program(
        self, layout: Layout
    ) -> None:
        assert judgments.enter(layout, [self.candidate()], "run-1") == 1
        row = judgments.latest(layout)[0]
        assert row["status"] == judgments.PENDING
        assert row["decided_by"] == judgments.MACHINE
        assert row["revision"] == 1

    def test_entering_twice_adds_nothing(self, layout: Layout) -> None:
        judgments.enter(layout, [self.candidate()], "run-1")
        assert judgments.enter(layout, [self.candidate()], "run-2") == 0
        assert len(judgments.history(layout, str(self.candidate()["judgment_id"]))) == 1

    def test_re_entering_never_supersedes_a_person(self, layout: Layout) -> None:
        # The one thing this log exists to prevent.
        judgments.enter(layout, [self.candidate()], "run-1")
        identifier = str(self.candidate()["judgment_id"])
        judgments.decide(layout, identifier, judgments.CONFIRMED, "maintainer")
        judgments.enter(layout, [self.candidate()], "run-2")
        assert judgments.latest(layout)[0]["status"] == judgments.CONFIRMED

    def test_a_confirm_then_a_reject_leaves_both_readable(self, layout: Layout) -> None:
        judgments.enter(layout, [self.candidate()], "run-1")
        identifier = str(self.candidate()["judgment_id"])
        judgments.decide(layout, identifier, judgments.CONFIRMED, "maintainer")
        judgments.decide(
            layout, identifier, judgments.REJECTED, "maintainer", note="homonym"
        )

        told = judgments.history(layout, identifier)
        assert [row["status"] for row in told] == [
            judgments.PENDING,
            judgments.CONFIRMED,
            judgments.REJECTED,
        ]
        assert [row["revision"] for row in told] == [1, 2, 3]
        assert judgments.latest(layout)[0]["status"] == judgments.REJECTED
        assert judgments.latest(layout)[0]["note"] == "homonym"

    def test_a_decision_copies_what_it_is_about_from_the_log(
        self, layout: Layout
    ) -> None:
        judgments.enter(layout, [self.candidate("e9", "o9")], "run-1")
        identifier = str(self.candidate("e9", "o9")["judgment_id"])
        written = judgments.decide(layout, identifier, judgments.CONFIRMED, "m")
        assert (written["elu_person_id"], written["officer_row_id"]) == ("e9", "o9")
        assert written["rule_id"] == keys.RULE_ID

    def test_pending_is_not_a_decision_a_person_makes(self, layout: Layout) -> None:
        judgments.enter(layout, [self.candidate()], "run-1")
        with pytest.raises(ValueError, match="only ever the program"):
            judgments.decide(
                layout, str(self.candidate()["judgment_id"]), judgments.PENDING, "m"
            )

    def test_an_unknown_judgment_cannot_be_decided(self, layout: Layout) -> None:
        with pytest.raises(KeyError):
            judgments.decide(layout, "nope", judgments.CONFIRMED, "m")

    def test_a_new_rule_is_a_new_judgment(self) -> None:
        # ADR-0003: a rule change does not revalue old decisions.
        assert judgments.judgment_id("FR-NAME-BIRTHYM-v1", "e", "o") != (
            judgments.judgment_id("FR-NAME-BIRTHYM-v2", "e", "o")
        )

    def test_no_clock_in_the_log(self) -> None:
        assert "decided_at" not in judgments.SCHEMA.names


class TestCandidates:
    """The builder over generated staged data, end to end and offline."""

    def stage(
        self,
        layout: Layout,
        elus: list[Elu],
        officers: list[dict[str, object]],
        *,
        buyer_commune: str = "74010",
        supplier: str = SUPPLIER,
    ) -> None:
        import hashlib
        import json

        from crony_eu.http import append_manifest
        from crony_eu.sources import fr_decp, fr_entreprises_api, fr_rne_elus

        write_decp(
            layout.raw(fr_decp.SOURCE, "2026-09-19") / "decp.parquet",
            [decp_row(acheteur_commune_code=buyer_commune, titulaire_id=supplier)],
        )
        fr_decp.stage(layout, "2026-09-19")

        write_rne_snapshot(layout.root, "2026-09-16", cm_current=elus)
        fr_rne_elus.stage(layout, "2026-09-16")

        api = fr_entreprises_api
        ask = api.Ask("siren", supplier[:9])
        text = json.dumps(
            api_response([api_unit(unit_siren=supplier[:9], officers=officers)])
        )
        raw = layout.raw(api.SOURCE, "2026-09-22")
        raw.mkdir(parents=True, exist_ok=True)
        (raw / ask.filename).write_text(text, encoding="utf-8")
        append_manifest(
            layout.manifest(api.SOURCE, "2026-09-22"),
            {
                "source": api.SOURCE,
                "url": f"{api.ENDPOINT}?q={ask.value}",
                "path": ask.filename,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "bytes": len(text),
                "retrieved_at": "2026-09-22T09:00:00+00:00",
                "licence": api.LICENCE,
                "status": 200,
            },
        )
        api.stage(layout, "2026-09-22")

    def elu(self, **overrides: str) -> Elu:
        fields = {
            "commune_code": "74010",
            "departement_code": "74",
            "surname": "NOMDEXEMPLE",
            "given": "Jean",
            "birth_date": "1971-04-03",
        }
        fields.update(overrides)
        return Elu(**fields)

    def test_equal_keys_make_a_candidate(self, layout: Layout) -> None:
        self.stage(
            layout,
            [self.elu()],
            [api_officer(surname="NOMDEXEMPLE", given="JEAN", birth="1971-04")],
        )
        found, report = candidates.build(layout, "74")
        assert len(found) == 1
        assert found[0]["surname_variant"] == keys.BIRTH
        assert found[0]["key_collision"] is False
        assert report.candidates == 1

    def test_a_usage_name_match_says_so(self, layout: Layout) -> None:
        # Measured in session 4: which variant élus match like, split by sex.
        self.stage(
            layout,
            [self.elu(surname="AUTRENOM", sex="F")],
            [
                api_officer(
                    surname="NOMDEXEMPLE (AUTRENOM)", given="JEAN", birth="1971-04"
                )
            ],
        )
        found, report = candidates.build(layout, "74")
        assert [row["surname_variant"] for row in found] == [keys.USAGE]
        assert report.by_variant_and_sex == {"usage/F": 1}

    def test_a_different_birth_month_is_not_a_candidate(self, layout: Layout) -> None:
        self.stage(
            layout,
            [self.elu(birth_date="1971-05-03")],
            [api_officer(surname="NOMDEXEMPLE", given="JEAN", birth="1971-04")],
        )
        assert candidates.build(layout, "74")[0] == []

    def test_an_elu_outside_the_scope_is_not_matched(self, layout: Layout) -> None:
        self.stage(
            layout,
            [self.elu(commune_code="93001", departement_code="93")],
            [api_officer(surname="NOMDEXEMPLE", given="JEAN", birth="1971-04")],
        )
        assert candidates.build(layout, "74")[0] == []

    def test_one_key_in_two_communes_is_a_collision(self, layout: Layout) -> None:
        self.stage(
            layout,
            [self.elu(commune_code="74010"), self.elu(commune_code="74011")],
            [api_officer(surname="NOMDEXEMPLE", given="JEAN", birth="1971-04")],
        )
        found, report = candidates.build(layout, "74")
        assert len(found) == 2
        assert all(row["key_collision"] for row in found)
        assert {row["elu_communes_for_key"] for row in found} == {2}
        assert report.collisions == 2

    def test_run_writes_candidates_and_enters_them_pending(
        self, layout: Layout
    ) -> None:
        self.stage(
            layout,
            [self.elu()],
            [api_officer(surname="NOMDEXEMPLE", given="JEAN", birth="1971-04")],
        )
        report = candidates.run(layout, "74")
        assert report.entered_pending == 1

        written = pq.read_table(layout.candidates("74")).to_pylist()
        assert len(written) == 1
        assert judgments.latest(layout)[0]["status"] == judgments.PENDING
        assert judgments.latest(layout)[0]["run_id"]

        # And a rerun decides nothing and enters nothing new.
        assert candidates.run(layout, "74").entered_pending == 0

        import json

        report = json.loads(
            (layout.reports() / "candidates-dep-74.json").read_text(encoding="utf-8")
        )
        assert report["candidates"] == 1
        assert report["rule_id"] == keys.RULE_ID
        # Aggregates only: no name in the report (constraint 13).
        assert "NOMDEXEMPLE" not in json.dumps(report)

    def test_rebuilding_gives_the_same_bytes(self, layout: Layout) -> None:
        self.stage(
            layout,
            [self.elu()],
            [api_officer(surname="NOMDEXEMPLE", given="JEAN", birth="1971-04")],
        )
        candidates.run(layout, "74")
        first = layout.candidates("74").read_bytes()
        candidates.run(layout, "74")
        assert layout.candidates("74").read_bytes() == first

    def test_missing_staged_data_names_the_command(self, layout: Layout) -> None:
        with pytest.raises(candidates.CandidateError, match="crony fetch fr-rne-elus"):
            candidates.build(layout, "74")


class TestRunId:
    def test_the_same_inputs_give_the_same_id(self, layout: Layout) -> None:
        from crony_eu.http import append_manifest
        from crony_eu.run import run_id

        append_manifest(
            layout.manifest("fr-decp", "2026-09-19"),
            {"path": "decp.parquet", "sha256": "a" * 64},
        )
        first = run_id(layout, [("fr-decp", "2026-09-19")])
        assert run_id(layout, [("fr-decp", "2026-09-19")]) == first

    def test_changed_bytes_change_the_id(self, layout: Layout) -> None:
        from crony_eu.http import append_manifest
        from crony_eu.run import run_id

        append_manifest(
            layout.manifest("fr-decp", "2026-09-19"),
            {"path": "decp.parquet", "sha256": "a" * 64},
        )
        before = run_id(layout, [("fr-decp", "2026-09-19")])
        append_manifest(
            layout.manifest("fr-decp", "2026-09-19"),
            {"path": "schema.json", "sha256": "b" * 64},
        )
        assert run_id(layout, [("fr-decp", "2026-09-19")]) != before

    def test_input_order_does_not_matter(self, layout: Layout) -> None:
        from crony_eu.run import run_id

        pairs = [("fr-decp", "2026-09-19"), ("fr-rne-elus", "2026-09-16")]
        assert run_id(layout, pairs) == run_id(layout, list(reversed(pairs)))
