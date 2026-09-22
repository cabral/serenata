# SPDX-License-Identifier: AGPL-3.0-only
"""`crony review`, driven by scripted keypresses.

The work order asks for "the review loop driven by scripted keypresses", and the
screen takes its `input` and `print` as arguments so that it can be. Every record
here is generated: this is the one command that shows real names, and the only
place it runs on real data is the maintainer's terminal.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from crony_eu.match import buyer_verification as bv
from crony_eu.match import candidates, judgments, review
from crony_eu.paths import Layout
from fakes import (
    api_establishment,
    api_response,
    api_unit,
    siret,
    slice_elu,
    slice_officer,
    stage_slice,
)

BUYER = siret("21740010")


@pytest.fixture
def layout(outside_repo: Path) -> Layout:
    made = Layout(outside_repo)
    made.create()
    return made


class Script:
    """Keypresses in, screen out."""

    def __init__(self, *keys: str) -> None:
        self._keys: Iterator[str] = iter(keys)
        self.screen: list[str] = []

    def ask(self, prompt: str) -> str:
        self.screen.append(prompt)
        try:
            return next(self._keys)
        except StopIteration as error:
            raise EOFError from error

    def say(self, line: str) -> None:
        self.screen.append(line)

    @property
    def text(self) -> str:
        return "\n".join(self.screen)


def one_candidate(layout: Layout, **officer: object) -> str:
    stage_slice(layout, [slice_elu()], [slice_officer(**officer)])
    candidates.run(layout, "74")
    return str(judgments.latest(layout)[0]["judgment_id"])


class TestPeople:
    @pytest.mark.parametrize(
        ("key", "status"),
        [
            ("c", judgments.CONFIRMED),
            ("r", judgments.REJECTED),
            ("a", judgments.AMBIGUOUS),
        ],
    )
    def test_a_key_records_its_status(
        self, layout: Layout, key: str, status: str
    ) -> None:
        identifier = one_candidate(layout)
        script = Script(key)
        tally = review.review_people(
            layout, "74", "maintainer", ask=script.ask, say=script.say
        )
        assert tally.decided == {status: 1}
        latest = judgments.history(layout, identifier)[-1]
        assert latest["status"] == status
        assert latest["decided_by"] == "maintainer"

    def test_a_note_travels_with_the_decision(self, layout: Layout) -> None:
        identifier = one_candidate(layout)
        script = Script("n", "same birth month, different commune", "r")
        review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        assert judgments.history(layout, identifier)[-1]["note"] == (
            "same birth month, different commune"
        )

    def test_input_closing_during_a_note_keeps_the_sitting_going(
        self, layout: Layout
    ) -> None:
        one_candidate(layout)
        script = Script("n")
        tally = review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        # The note read hits end of input, records nothing, and the next prompt
        # reads end of input too, which is a quit.
        assert tally.stopped and not tally.decided

    def test_skip_leaves_it_pending(self, layout: Layout) -> None:
        identifier = one_candidate(layout)
        script = Script("s")
        tally = review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        assert tally.skipped == 1
        assert judgments.history(layout, identifier)[-1]["status"] == judgments.PENDING

    def test_quit_stops_and_decides_nothing(self, layout: Layout) -> None:
        one_candidate(layout)
        script = Script("q")
        tally = review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        assert tally.stopped and not tally.decided

    def test_closed_input_is_a_quit_not_a_crash(self, layout: Layout) -> None:
        one_candidate(layout)
        script = Script()
        tally = review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        assert tally.stopped

    def test_an_unknown_key_asks_again(self, layout: Layout) -> None:
        one_candidate(layout)
        script = Script("z", "c")
        tally = review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        assert "keys: c r a n s q" in script.text
        assert tally.decided == {judgments.CONFIRMED: 1}

    def test_a_decided_candidate_is_not_shown_again(self, layout: Layout) -> None:
        one_candidate(layout)
        review.review_people(layout, "74", "m", ask=Script("c").ask, say=print)
        script = Script()
        tally = review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        assert tally.shown == 0
        assert "0 pending" in script.text

    def test_the_screen_shows_both_sides_and_the_missing_dates(
        self, layout: Layout
    ) -> None:
        one_candidate(layout)
        script = Script("s")
        review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        text = script.text
        assert "ELU" in text and "OFFICER" in text
        assert "NOMDEXEMPLE" in text
        # The dates cannot establish an overlap, and the screen says why.
        assert "publishes no role dates" in text
        assert "annuaire-entreprises.data.gouv.fr/entreprise/" in text
        assert "never confirms a match on its own" in text

    def test_a_collision_is_announced(self, layout: Layout) -> None:
        stage_slice(
            layout,
            [slice_elu(commune_code="74010"), slice_elu(commune_code="74011")],
            [slice_officer()],
        )
        candidates.run(layout, "74")
        script = Script("s", "s")
        review.review_people(layout, "74", "m", ask=script.ask, say=script.say)
        assert "key collision" in script.text

    def test_nothing_matched_yet_names_the_command(self, layout: Layout) -> None:
        with pytest.raises(review.ReviewError, match="crony match fr --scope dep:74"):
            review.review_people(layout, "74", "m", ask=Script().ask, say=print)


class TestSample:
    def test_the_same_seed_draws_the_same_sample(self) -> None:
        ids = [f"id{n:03d}" for n in range(200)]
        assert review.sample_ids(ids, 10, 1) == review.sample_ids(ids, 10, 1)
        assert review.sample_ids(ids, 10, 1) != review.sample_ids(ids, 10, 2)

    def test_input_order_does_not_change_the_sample(self) -> None:
        # The flag's precision figure is recomputed from the same draw, which is
        # only possible if the draw does not depend on how the ids arrived.
        ids = [f"id{n:03d}" for n in range(200)]
        assert review.sample_ids(ids, 10, 1) == review.sample_ids(
            list(reversed(ids)), 10, 1
        )

    def test_a_sample_larger_than_the_population_is_all_of_it(self) -> None:
        assert sorted(review.sample_ids(["a", "b"], 5, 1)) == ["a", "b"]

    def test_the_screen_says_how_far_through_the_sample(self, layout: Layout) -> None:
        one_candidate(layout)
        script = Script("c")
        review.review_people(
            layout, "74", "m", ask=script.ask, say=script.say, sample=5, seed=1
        )
        assert "sample of 5 with seed 1: 0 already decided, 1 to go" in script.text


class TestBuyers:
    def stage(self, layout: Layout, commune: str = "74010") -> None:
        body = api_response(
            [
                api_unit(
                    unit_siren=BUYER[:9],
                    nature_juridique="7210",
                    establishments=[
                        api_establishment(establishment_siret=BUYER, commune=commune)
                    ],
                )
            ]
        )
        stage_slice(
            layout, [slice_elu()], [slice_officer()], buyer=BUYER, buyer_body=body
        )

    def test_c_records_a_corroborated_identity_and_no_history(
        self, layout: Layout
    ) -> None:
        self.stage(layout)
        script = Script("c")
        tally = review.review_buyers(layout, "74", "m", ask=script.ask, say=script.say)
        assert tally.decided == {bv.TRUE: 1}
        decision = bv.latest(layout)[0]
        assert decision["identity_corroborated"] == bv.TRUE
        # Amendment 1: never rewritten as true.
        assert decision["historical_geography"] == bv.NOT_ESTABLISHED
        assert bv.blocks_a_packet(decision) is None

    def test_c_is_refused_when_a_mechanical_check_failed(self, layout: Layout) -> None:
        # DECP asserts 74010, the registry answers 74099. A person cannot
        # corroborate what the evidence does not.
        self.stage(layout, commune="74099")
        script = Script("c", "r")
        tally = review.review_buyers(layout, "74", "m", ask=script.ask, say=script.say)
        assert "refused" in script.text
        assert tally.decided == {bv.FALSE: 1}
        assert bv.latest(layout)[0]["identity_corroborated"] == bv.FALSE

    def test_contradicted_geography_needs_a_note(self, layout: Layout) -> None:
        self.stage(layout)
        script = Script("x", "", "c", "n", "prefectoral merger act", "c")
        review.review_buyers(layout, "74", "m", ask=script.ask, say=script.say)
        assert "needs a note" in script.text
        decision = bv.latest(layout)[0]
        assert decision["historical_geography"] == bv.CONTRADICTED
        assert decision["note"] == "prefectoral merger act"
        # And a contradicted geography blocks the packet even with a
        # corroborated identity.
        assert bv.blocks_a_packet(decision) is not None

    def test_there_is_no_key_for_established(self, layout: Layout) -> None:
        # No approved source can establish historical geography, and a person's
        # recollection is not an official source.
        assert bv.ESTABLISHED not in review.BUYER_KEYS.values()
        self.stage(layout)
        script = Script("e", "q")
        review.review_buyers(layout, "74", "m", ask=script.ask, say=script.say)
        assert "keys: c r u x n s q" in script.text

    def test_the_screen_says_what_the_standard_does_not_establish(
        self, layout: Layout
    ) -> None:
        self.stage(layout)
        script = Script("s")
        review.review_buyers(layout, "74", "m", ask=script.ask, say=script.say)
        assert "consolidator's join" in script.text
        assert "never as true" in script.text

    def test_a_decided_buyer_leaves_the_queue(self, layout: Layout) -> None:
        self.stage(layout)
        review.review_buyers(layout, "74", "m", ask=Script("u").ask, say=print)
        assert review.buyers_queue(layout, "74") == []

    def test_skip_quit_and_an_unknown_key(self, layout: Layout) -> None:
        self.stage(layout)
        script = Script("z", "s")
        tally = review.review_buyers(layout, "74", "m", ask=script.ask, say=script.say)
        assert tally.skipped == 1
        script = Script("q")
        assert review.review_buyers(
            layout, "74", "m", ask=script.ask, say=script.say
        ).stopped

    def test_no_evidence_staged_names_the_command(self, layout: Layout) -> None:
        with pytest.raises(review.ReviewError, match="crony fetch fr-entreprises-api"):
            review.buyers_queue(layout, "74")
