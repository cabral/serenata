"""An invented market, run through the real rule.

The flag explainer needs a flag to show, and the project has none it may show.
So the page shows one produced the only honest way available: by giving the real
classifier a market that does not exist and printing what it returns. Nothing
here is a finding. Every identifier says SYNTHETIC, the country is ``XX`` (a
code ISO 3166 reserves for users) and the CPV division is ``00`` (which the
vocabulary does not have), so no reader can mistake a row for a real notice.

Running the rule, rather than writing out what it would return, is the point:
the example cannot describe a rule the code no longer implements, because it is
the code's own output. `verdict` restates the rule's decision in the four
outcomes the page explains, and `tests/test_site.py` holds it to the rule.
"""

from __future__ import annotations

from dataclasses import dataclass

from serenata.classify import single_bid_in_segment as rule
from serenata.classify.records import Flag, LotOutcome

#: Marks every synthetic identifier, so a test can prove none is missing it.
SYNTHETIC = "SYNTHETIC"

COUNTRY = "XX"
DIVISION = "00"

#: What the rule is told a lot drew when it is not a single bid.
COMPETITIVE_BIDS = 3


@dataclass(frozen=True)
class Case:
    """One invented market and what the real rule made of it."""

    label: str
    size: int
    singles: int
    flags: tuple[Flag, ...]


def market(size: int, singles: int) -> list[LotOutcome]:
    """``size`` invented lot outcomes, ``singles`` of which drew exactly one bid."""
    return [
        LotOutcome(
            source_publication_id=f"{SYNTHETIC}-PUBLICATION-{number:03d}",
            source_notice_id=f"{SYNTHETIC}-NOTICE-{number:03d}",
            publication_year="XXXX",
            lot_result_ordinal=0,
            lot_ref=f"{SYNTHETIC}-LOT-{number:03d}",
            bids=rule.SINGLE_BID if number <= singles else COMPETITIVE_BIDS,
            country=COUNTRY,
            cpv_division=DIVISION,
            correction_cutoff="XXXX-XX-XX",
        )
        for number in range(1, size + 1)
    ]


def run(label: str, size: int, singles: int) -> Case:
    return Case(label, size, singles, tuple(rule.flags(market(size, singles))))


def cases() -> tuple[Case, ...]:
    """The markets the page walks through, chosen to sit on each side of each edge.

    The first is the market the explorer starts in. The rest are the ways the
    rule stays silent: a market under the floor, a market where one bid is
    ordinary, and a market exactly on the rate limit, where the comparison is
    strict and the rule is still silent.
    """
    limit = rule.SEGMENT_FLOOR * 2
    on_the_limit = limit * rule.SINGLE_BID_RATE_PERCENT // 100
    return (
        run("A market where one bid is rare", 60, 6),
        run("A market below the floor", rule.SEGMENT_FLOOR - 10, 2),
        run("A market where one bid is ordinary", 60, 21),
        run("Exactly on the rate limit", limit, on_the_limit),
        run("One lot under the rate limit", limit, on_the_limit - 1),
    )


def example_flag() -> Flag:
    """The flag the page shows in full: the first the invented market produces."""
    found = cases()[0].flags
    if not found:
        raise AssertionError("the invented market no longer produces a flag")
    return found[0]


def verdict(bids: int, size: int, singles: int) -> str:
    """Why the rule does or does not flag a lot, in the four outcomes the page names.

    ``size`` is the lot's market and ``singles`` the lots in it that drew one
    bid, the lot itself included. The order is the rule's own: the lot is looked
    at only if it drew one bid, and its market only if it is large enough.
    """
    if bids != rule.SINGLE_BID:
        return "not-single"
    if size < rule.SEGMENT_FLOOR:
        return "below-floor"
    if not rule.is_rare(size, singles):
        return "ordinary"
    return "flagged"
