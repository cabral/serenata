"""The rule itself: what fires, what does not, and why.

`docs/hypotheses/single_bid_in_segment.md` is the argument; this is the part a
test can hold. The rule is a pure function over rows, so everything here is
built in memory: no files, no dataset, no pipeline.

The negative cases matter more than the positive one. A single bid is lawful,
ordinary and — measured over five publication days — the outcome of 42.1% of
competitive non-framework lot results, so a rule that fired on one bid would be
describing the market. Each test below is one of the ways this rule declines to.
"""

from __future__ import annotations

from serenata.classify.records import LotOutcome
from serenata.classify.single_bid_in_segment import (
    RULE,
    RULE_VERSION,
    SEGMENT_FLOOR,
    SINGLE_BID_RATE_PERCENT,
    flags,
    is_rare,
    segment_counts,
)


def outcome(
    index: int,
    bids: int,
    *,
    country: str = "SWE",
    division: str = "45",
) -> LotOutcome:
    """One lot outcome, identified by its position so flags are traceable."""
    return LotOutcome(
        source_publication_id=f"{index:08d}-2026",
        source_notice_id=f"notice-{index:04d}",
        publication_year="2026",
        lot_result_ordinal=0,
        lot_ref="LOT-0001",
        bids=bids,
        country=country,
        cpv_division=division,
    )


def market(
    size: int,
    singles: int,
    *,
    country: str = "SWE",
    division: str = "45",
    start: int = 1,
) -> list[LotOutcome]:
    """``size`` outcomes in one market, ``singles`` of which drew one bid."""
    return [
        outcome(
            start + index,
            bids=1 if index < singles else 4,
            country=country,
            division=division,
        )
        for index in range(size)
    ]


class TestTheBaseline:
    """The segment counts a flag is measured against."""

    def test_it_counts_lot_results_and_single_bids_per_market(self) -> None:
        counts = segment_counts(market(10, 2) + market(5, 5, country="FIN", start=100))
        assert counts == {("SWE", "45"): (10, 2), ("FIN", "45"): (5, 5)}

    def test_a_market_below_the_floor_is_unmeasured_not_rare(self) -> None:
        # Zero single bids out of 49 is the lowest rate there is, and the rule
        # still says nothing: the market is too small to have a baseline.
        assert not is_rare(SEGMENT_FLOOR - 1, 0)
        assert is_rare(SEGMENT_FLOOR, 0)

    def test_the_threshold_is_exact_at_the_boundary(self) -> None:
        # 15 of 100 is not below 15%. Integer arithmetic, so this is a fact
        # rather than a floating-point coincidence.
        assert not is_rare(100, SINGLE_BID_RATE_PERCENT)
        assert is_rare(100, SINGLE_BID_RATE_PERCENT - 1)


class TestWhatFires:
    def test_one_bid_in_a_market_where_one_bid_is_rare(self) -> None:
        found = flags(market(100, 5))

        assert len(found) == 5
        first = found[0]
        assert first.rule == RULE
        assert first.rule_version == RULE_VERSION
        assert first.bids == 1
        assert (first.segment_country, first.segment_cpv_division) == ("SWE", "45")
        assert (first.segment_size, first.segment_single_bids) == (100, 5)

    def test_flags_are_ordered_by_publication_and_position(self) -> None:
        found = flags(list(reversed(market(100, 5))))
        assert [flag.source_publication_id for flag in found] == sorted(
            flag.source_publication_id for flag in found
        )

    def test_each_market_is_judged_on_its_own_rate(self) -> None:
        # Same bid count, two markets: rare in one, ordinary in the other.
        population = market(100, 5) + market(100, 60, country="ROU", start=1000)
        found = flags(population)

        assert {flag.segment_country for flag in found} == {"SWE"}
        assert len(found) == 5


class TestWhatDoesNotFire:
    """Every one of these is a lot that received exactly one bid."""

    def test_not_when_the_market_is_too_small(self) -> None:
        assert flags(market(SEGMENT_FLOOR - 1, 1)) == []

    def test_not_when_single_bidding_is_ordinary_there(self) -> None:
        # 42.1% is roughly the measured European rate for this population.
        assert flags(market(100, 42)) == []

    def test_not_when_the_market_is_exactly_at_the_threshold(self) -> None:
        assert flags(market(100, SINGLE_BID_RATE_PERCENT)) == []

    def test_not_for_a_lot_that_drew_several_bids(self) -> None:
        found = flags(market(100, 5))
        assert all(flag.bids == 1 for flag in found)

    def test_a_market_of_only_single_bids_flags_nothing(self) -> None:
        # The degenerate case the rule must not invert: every lot drew one bid,
        # so one bid is exactly what this market does.
        assert flags(market(100, 100)) == []


class TestItIsAPureFunction:
    def test_the_same_input_gives_the_same_flags(self) -> None:
        population = market(100, 5)
        assert flags(population) == flags(population)

    def test_it_does_not_consume_or_reorder_its_input(self) -> None:
        population = market(100, 5)
        before = list(population)
        flags(population)
        assert population == before

    def test_an_empty_population_is_not_an_error(self) -> None:
        assert flags([]) == []
