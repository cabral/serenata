# SPDX-License-Identifier: AGPL-3.0-only
"""The buyer check, and the two facts it refuses to collapse into one.

ADR-0007 Amendment 1 turned one question into two because they fail differently.
"The registry did not corroborate this buyer" blocks a packet. "Nobody can
establish what commune code this establishment carried in 2019" does not, because
no source records it, and blocking on it would have cost every packet while
recording nothing.

So the tests that matter here are about keeping them apart, keeping
`not_established` out of `true`, and keeping an old decision from surviving a
change in what it was decided about.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crony_eu.match import buyer_verification as bv
from crony_eu.paths import Layout
from fakes import siret

BUYER = siret("21740010")


@pytest.fixture
def layout(outside_repo: Path) -> Layout:
    made = Layout(outside_repo)
    made.create()
    return made


def assertion(commune: str = "74010", buyer: str = BUYER) -> bv.Assertion:
    return bv.Assertion(
        buyer_assertion_id="assertion-1",
        decp_snapshot="2026-09-19",
        buyer_siret=buyer,
        asserted_category="Commune",
        asserted_commune_code=commune,
    )


def evidence(**overrides: object) -> bv.Evidence:
    fields: dict[str, object] = {
        "resolved": True,
        "evidence_sha256": "a" * 64,
        "source_url": "https://recherche-entreprises.api.gouv.invalid/search",
        "retrieved_at": "2026-09-22T09:00:00+00:00",
        "siren": BUYER[:9],
        "nature_juridique": "7210",
        "commune_code": "74010",
        "state": "A",
    }
    fields.update(overrides)
    return bv.Evidence(**fields)  # type: ignore[arg-type]


class TestAssessTheFourConditions:
    def test_all_four_holding_proposes_corroborated(self) -> None:
        got = bv.assess(assertion(), evidence())
        assert got.identity_corroborated == bv.TRUE
        assert got.blocking_reason is None

    def test_a_siret_in_a_different_legal_unit_is_refused(self) -> None:
        got = bv.assess(assertion(), evidence(siren="999999999"))
        assert got.identity_corroborated == bv.FALSE
        assert got.blocking_reason == bv.WRONG_LEGAL_UNIT

    def test_a_legal_unit_that_is_not_a_commune_is_refused(self) -> None:
        # A syndicat mixte or an EPCI buying for a commune is a different body,
        # and phase 1 covers communes.
        got = bv.assess(assertion(), evidence(nature_juridique="7346"))
        assert got.identity_corroborated == bv.FALSE
        assert got.blocking_reason == bv.NOT_A_COMMUNE

    def test_a_disagreeing_commune_code_is_refused(self) -> None:
        got = bv.assess(assertion(commune="74010"), evidence(commune_code="74011"))
        assert got.identity_corroborated == bv.FALSE
        assert got.blocking_reason == bv.COMMUNE_DISAGREES

    def test_evidence_that_did_not_resolve_is_unknown_not_false(self) -> None:
        # "The registry has nothing" and "the registry disagrees" are different
        # facts about a buyer and a reviewer has to tell them apart.
        got = bv.assess(assertion(), evidence(resolved=False, siren=None))
        assert got.identity_corroborated == bv.UNKNOWN
        assert got.blocking_reason == bv.NOT_RESOLVED

    def test_no_evidence_at_all_is_unknown(self) -> None:
        got = bv.assess(assertion(), None)
        assert got.identity_corroborated == bv.UNKNOWN
        assert got.blocking_reason == bv.NO_EVIDENCE

    def test_a_closed_establishment_still_corroborates(self) -> None:
        # Amendment 1: a current closure does not disqualify a contract that
        # predates it, and no window is enforced from the dates at all.
        got = bv.assess(assertion(), evidence(state="F"))
        assert got.identity_corroborated == bv.TRUE


class TestHistoricalGeographyIsNeverEstablished:
    def test_even_a_perfect_match_leaves_it_not_established(self) -> None:
        # INSEE overwrites an establishment's commune code forward whenever the
        # Code officiel geographique changes, closed establishments included, so
        # there is no historical value anywhere to compare against. `assess`
        # cannot return `established` and this is the test that says so.
        assert bv.assess(assertion(), evidence()).historical_geography == (
            bv.NOT_ESTABLISHED
        )

    @pytest.mark.parametrize(
        "case",
        [
            {},
            {"state": "F"},
            {"resolved": False},
            {"commune_code": "74011"},
        ],
    )
    def test_no_input_produces_established(self, case: dict[str, object]) -> None:
        got = bv.assess(assertion(), evidence(**case))
        assert got.historical_geography != bv.ESTABLISHED


class TestWhatBlocksAPacket:
    def test_a_corroborated_identity_with_no_history_does_not_block(self) -> None:
        # The whole point of the amendment. Before it, this blocked every packet.
        decision = {
            "identity_corroborated": bv.TRUE,
            "historical_geography": bv.NOT_ESTABLISHED,
        }
        assert bv.blocks_a_packet(decision) is None

    @pytest.mark.parametrize("identity", [bv.FALSE, bv.UNKNOWN, "", None])
    def test_anything_but_a_corroborated_identity_blocks(
        self, identity: object
    ) -> None:
        decision = {
            "identity_corroborated": identity,
            "historical_geography": bv.NOT_ESTABLISHED,
        }
        assert bv.blocks_a_packet(decision) is not None

    def test_contradicted_geography_blocks(self) -> None:
        decision = {
            "identity_corroborated": bv.TRUE,
            "historical_geography": bv.CONTRADICTED,
        }
        reason = bv.blocks_a_packet(decision)
        assert reason is not None
        assert "contradicted" in reason


class TestTheLogIsAppendOnly:
    def queued(self, **overrides: object) -> dict[str, object]:
        given = evidence()
        return {
            "verification_id": bv.verification_id("assertion-1", given.evidence_sha256),
            "assertion": assertion(),
            "evidence": given,
            "assessment": bv.assess(assertion(), given),
            **overrides,
        }

    def decide(self, verdict: str = bv.TRUE, note: str | None = None) -> dict:
        return bv.record(
            self.queued(),
            identity_corroborated=verdict,
            historical_geography=bv.NOT_ESTABLISHED,
            decided_by="maintainer",
            note=note,
        )

    def test_the_first_decision_is_revision_one(self, layout: Layout) -> None:
        bv.append(layout, [self.decide()])
        assert [row["revision"] for row in bv.read(layout)] == [1]

    def test_a_second_decision_supersedes_without_erasing(self, layout: Layout) -> None:
        bv.append(layout, [self.decide(bv.TRUE)])
        bv.append(layout, [self.decide(bv.FALSE, note="checked the annuaire")])

        everything = bv.read(layout)
        assert [row["revision"] for row in everything] == [1, 2]
        assert [row["identity_corroborated"] for row in everything] == [
            bv.TRUE,
            bv.FALSE,
        ]

        current = bv.latest(layout)
        assert len(current) == 1
        assert current[0]["identity_corroborated"] == bv.FALSE

    def test_history_answers_what_we_believed_then(self, layout: Layout) -> None:
        bv.append(layout, [self.decide(bv.TRUE)])
        bv.append(layout, [self.decide(bv.FALSE)])
        identifier = str(bv.read(layout)[0]["verification_id"])

        told = bv.history(layout, identifier)
        assert [row["revision"] for row in told] == [1, 2]
        # A packet built on revision 1 is findable and withdrawable precisely
        # because revision 1 is still on disk (constraint 11).
        assert told[0]["identity_corroborated"] == bv.TRUE

    def test_ordering_uses_revisions_and_not_a_clock(self, layout: Layout) -> None:
        # The handoff asks for deterministic ordering without wall-clock
        # timestamps, so there is no field here to sort by time.
        bv.append(layout, [self.decide()])
        assert "decided_at" not in bv.read(layout)[0]
        assert set(bv.SCHEMA.names).isdisjoint({"decided_at", "timestamp"})

    def test_writing_twice_gives_the_same_bytes(self, layout: Layout) -> None:
        bv.append(layout, [self.decide()])
        first = bv.path(layout).read_bytes()
        # A rebuild from the same rows is byte-identical (constraint 4).
        rows = bv.read(layout)
        from crony_eu.parquet import write

        write(rows, bv.SCHEMA, bv.path(layout), key=("verification_id", "revision"))
        assert bv.path(layout).read_bytes() == first


class TestTheIdIsBoundToItsInputs:
    def test_changed_evidence_gets_a_new_id(self) -> None:
        # A review cannot be reused when the registry answers differently.
        first = bv.verification_id("assertion-1", "a" * 64)
        second = bv.verification_id("assertion-1", "b" * 64)
        assert first != second

    def test_a_changed_assertion_gets_a_new_id(self) -> None:
        # Nor when the consolidator changes its claim.
        first = bv.verification_id("assertion-1", "a" * 64)
        second = bv.verification_id("assertion-2", "a" * 64)
        assert first != second

    def test_a_decided_verification_leaves_the_queue(self, layout: Layout) -> None:
        identifier = bv.verification_id("assertion-1", "a" * 64)
        rows = [{"verification_id": identifier}]
        assert bv.pending(layout, rows) == [identifier]

        given = evidence()
        bv.append(
            layout,
            [
                bv.record(
                    {
                        "verification_id": identifier,
                        "assertion": assertion(),
                        "evidence": given,
                        "assessment": bv.assess(assertion(), given),
                    },
                    identity_corroborated=bv.TRUE,
                    historical_geography=bv.NOT_ESTABLISHED,
                    decided_by="maintainer",
                )
            ],
        )
        assert bv.pending(layout, rows) == []

    def test_new_evidence_puts_it_back_in_the_queue(self, layout: Layout) -> None:
        old = bv.verification_id("assertion-1", "a" * 64)
        given = evidence()
        bv.append(
            layout,
            [
                bv.record(
                    {
                        "verification_id": old,
                        "assertion": assertion(),
                        "evidence": given,
                        "assessment": bv.assess(assertion(), given),
                    },
                    identity_corroborated=bv.TRUE,
                    historical_geography=bv.NOT_ESTABLISHED,
                    decided_by="maintainer",
                )
            ],
        )
        fresh = bv.verification_id("assertion-1", "b" * 64)
        assert bv.pending(layout, [{"verification_id": fresh}]) == [fresh]


class TestRecordRefusesNonsense:
    def queued(self) -> dict[str, object]:
        given = evidence()
        return {
            "verification_id": "v1",
            "assertion": assertion(),
            "evidence": given,
            "assessment": bv.assess(assertion(), given),
        }

    def test_an_unknown_identity_value_is_refused(self) -> None:
        with pytest.raises(ValueError, match="identity_corroborated"):
            bv.record(
                self.queued(),
                identity_corroborated="probably",
                historical_geography=bv.NOT_ESTABLISHED,
                decided_by="maintainer",
            )

    def test_an_unknown_geography_value_is_refused(self) -> None:
        with pytest.raises(ValueError, match="historical_geography"):
            bv.record(
                self.queued(),
                identity_corroborated=bv.TRUE,
                historical_geography="probably",
                decided_by="maintainer",
            )

    def test_a_decision_keeps_the_evidence_it_was_made_on(self) -> None:
        written = bv.record(
            self.queued(),
            identity_corroborated=bv.TRUE,
            historical_geography=bv.NOT_ESTABLISHED,
            decided_by="maintainer",
        )
        assert written["evidence_sha256"] == "a" * 64
        assert written["evidence_retrieved_at"] == "2026-09-22T09:00:00+00:00"
        assert written["evidence_url"].startswith("https://")


class TestTheQueue:
    """Joining what DECP asserts to what the registry answered.

    One row per buyer assertion, each carrying a proposal. The join is a LEFT
    one on purpose: a buyer nobody fetched evidence for still has to appear, as
    `unknown`, rather than vanishing from a queue that would then look finished.
    """

    def build(
        self,
        layout: Layout,
        contracts: list[dict[str, object]],
        responses: list[tuple[str, dict[str, object]]],
    ) -> None:
        from crony_eu.sources import fr_decp
        from crony_eu.sources import fr_entreprises_api as api
        from fakes import write_decp

        write_decp(layout.raw(fr_decp.SOURCE, "2026-09-19") / "decp.parquet", contracts)
        fr_decp.stage(layout, "2026-09-19")

        import hashlib
        import json

        from crony_eu.http import append_manifest

        raw = layout.raw(api.SOURCE, "2026-09-22")
        raw.mkdir(parents=True, exist_ok=True)
        for value, body in responses:
            ask = api.Ask("siret", value)
            text = json.dumps(body)
            (raw / ask.filename).write_text(text, encoding="utf-8")
            append_manifest(
                layout.manifest(api.SOURCE, "2026-09-22"),
                {
                    "source": api.SOURCE,
                    "url": f"{api.ENDPOINT}?q={value}",
                    "path": ask.filename,
                    "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "bytes": len(text),
                    "retrieved_at": "2026-09-22T09:00:00+00:00",
                    "licence": api.LICENCE,
                    "status": 200,
                },
            )
        api.stage(layout, "2026-09-22")

    def test_a_matching_buyer_is_queued_as_corroborated(self, layout: Layout) -> None:
        from fakes import api_establishment, api_response, api_unit, decp_row

        self.build(
            layout,
            [decp_row(acheteur_id=BUYER, acheteur_commune_code="74010")],
            [
                (
                    BUYER,
                    api_response(
                        [
                            api_unit(
                                unit_siren=BUYER[:9],
                                nature_juridique="7210",
                                establishments=[
                                    api_establishment(
                                        establishment_siret=BUYER, commune="74010"
                                    )
                                ],
                            )
                        ]
                    ),
                )
            ],
        )
        queued = bv.queue(layout, "2026-09-19", "2026-09-22", "74")
        assert len(queued) == 1
        assert queued[0]["assessment"].identity_corroborated == bv.TRUE
        assert queued[0]["assessment"].historical_geography == bv.NOT_ESTABLISHED

    def test_a_disagreeing_commune_is_queued_as_refused(self, layout: Layout) -> None:
        from fakes import api_establishment, api_response, api_unit, decp_row

        self.build(
            layout,
            [decp_row(acheteur_id=BUYER, acheteur_commune_code="74010")],
            [
                (
                    BUYER,
                    api_response(
                        [
                            api_unit(
                                unit_siren=BUYER[:9],
                                nature_juridique="7210",
                                establishments=[
                                    api_establishment(
                                        establishment_siret=BUYER, commune="74099"
                                    )
                                ],
                            )
                        ]
                    ),
                )
            ],
        )
        queued = bv.queue(layout, "2026-09-19", "2026-09-22", "74")
        assert queued[0]["assessment"].identity_corroborated == bv.FALSE
        assert queued[0]["assessment"].blocking_reason == bv.COMMUNE_DISAGREES

    def test_a_buyer_with_no_evidence_is_queued_as_unknown(
        self, layout: Layout
    ) -> None:
        # The LEFT join earning itself: a buyer nobody asked about still appears,
        # because a queue that hid it would look finished when it was not.
        from fakes import api_response, api_unit, decp_row

        other = siret("21740011")
        self.build(
            layout,
            [
                decp_row(uid="A", acheteur_id=BUYER, acheteur_commune_code="74010"),
                decp_row(uid="B", acheteur_id=other, acheteur_commune_code="74011"),
            ],
            [(BUYER, api_response([api_unit(unit_siren=BUYER[:9])]))],
        )
        queued = bv.queue(layout, "2026-09-19", "2026-09-22", "74")

        # Both are `unknown`, and for different reasons that a reviewer has to
        # be able to tell apart: one buyer was asked about and the registry
        # returned nothing usable, the other was never asked about at all.
        assert {str(row["assessment"].identity_corroborated) for row in queued} == {
            bv.UNKNOWN
        }
        assert sorted(
            str(row["assessment"].blocking_reason) for row in queued
        ) == sorted([bv.NO_EVIDENCE, bv.NOT_RESOLVED])

    def test_every_queued_row_carries_its_binding(self, layout: Layout) -> None:
        from fakes import api_establishment, api_response, api_unit, decp_row

        self.build(
            layout,
            [decp_row(acheteur_id=BUYER, acheteur_commune_code="74010")],
            [
                (
                    BUYER,
                    api_response(
                        [
                            api_unit(
                                unit_siren=BUYER[:9],
                                nature_juridique="7210",
                                establishments=[
                                    api_establishment(establishment_siret=BUYER)
                                ],
                            )
                        ]
                    ),
                )
            ],
        )
        row = bv.queue(layout, "2026-09-19", "2026-09-22", "74")[0]
        assert row["verification_id"] == bv.verification_id(
            row["assertion"].buyer_assertion_id, row["evidence"].evidence_sha256
        )


class TestTheQueueIsScoped:
    def test_a_buyer_outside_the_departement_is_not_queued(
        self, layout: Layout
    ) -> None:
        # The LEFT join that keeps an un-fetched buyer visible would, unscoped,
        # queue every commune buyer in France as unknown.
        from fakes import api_response, decp_row

        TestTheQueue().build(
            layout,
            [
                decp_row(uid="IN", acheteur_id=BUYER, acheteur_commune_code="74010"),
                decp_row(
                    uid="OUT",
                    acheteur_id=siret("21930001"),
                    acheteur_commune_code="93001",
                ),
            ],
            [(BUYER, api_response([]))],
        )
        queued = bv.queue(layout, "2026-09-19", "2026-09-22", "74")
        assert [row["assertion"].buyer_siret for row in queued] == [BUYER]
