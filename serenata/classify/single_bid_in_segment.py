"""A single bid in a market where single bids are rare.

The hypothesis is `docs/hypotheses/single_bid_in_segment.md`; the argument that
produced it is case 002, and case 001 is the version of this idea that was
rejected. Read the hypothesis before changing a threshold here:
both numbers below were chosen after measuring, and the file records what the
measurement could and could not distinguish.

**Why not simply flag a single bid.** Because 42.1% of the competitive,
non-framework lot results measured under version 1 received exactly one, so a
flag on that describes the European market rather than finding anything in it.
Single-bid rates ran from 6.5% to 78.2% across markets, and it is the distance from a
lot's own market that carries information.

**A flag is an anomaly, not an accusation** (constraint 3). A single bid is
lawful and ordinary, and usually means one supplier wanted the work.

This module is a pure function over rows. It reads no files, no clock, no
network, and no free text: given the same outcomes it returns the same flags in
the same order (constraint 4), and it reads only structured fields (constraint
5).
"""

from __future__ import annotations

from collections.abc import Iterable

from serenata.classify.records import Flag, LotOutcome, notice_url

#: This rule's name in a flag row, and the stem of its hypothesis file.
RULE = "single_bid_in_segment"

#: Bumped whenever the logic below changes what it flags — a threshold, the
#: segment definition, the population. Two runs that disagree can then be told
#: apart from two rules that disagree (ADR-0011).
RULE_VERSION = 2

#: The smallest market this rule will compare against. At 50 independent
#: Bernoulli observations a 15% rate has a standard error of about 5 points.
#: Lots may cluster within notices or buyers: this is a heuristic, not a
#: precision or anonymity guarantee. Version-2 remeasurement is pending.
SEGMENT_FLOOR = 50

#: A market where fewer than this share of comparable lots drew a single bid.
#: Roughly a third of the measured population's own rate. Expressed in whole
#: percent and compared by cross-multiplication, so the test is exact integer
#: arithmetic rather than a float comparison that could differ between runs.
SINGLE_BID_RATE_PERCENT = 15

#: What "one bid" means. Named because the rule is about this number and not
#: about scarcity in general: two bids in a market where everyone gets nine is
#: a different hypothesis, and would be a different case file.
SINGLE_BID = 1


def segment_counts(
    outcomes: Iterable[LotOutcome],
) -> dict[tuple[str, str], tuple[int, int]]:
    """``(country, division) -> (lot results, of which single bid)``.

    The baseline, computed from the dataset being classified rather than from a
    frozen reference table (ADR-0011). That makes the corpus an input to the
    rule, which is why both counts travel in every flag it produces.
    """
    counts: dict[tuple[str, str], tuple[int, int]] = {}
    for outcome in outcomes:
        size, singles = counts.get(outcome.segment, (0, 0))
        counts[outcome.segment] = (
            size + 1,
            singles + (1 if outcome.bids == SINGLE_BID else 0),
        )
    return counts


def is_rare(size: int, singles: int) -> bool:
    """Whether single bidding is unusual in a market of this shape.

    ``singles / size < SINGLE_BID_RATE_PERCENT / 100``, multiplied out. A market
    too small to have a rate is not rare, it is unmeasured, and the rule says
    nothing about the lots in it.
    """
    return size >= SEGMENT_FLOOR and singles * 100 < SINGLE_BID_RATE_PERCENT * size


def flags(outcomes: Iterable[LotOutcome]) -> list[Flag]:
    """Every lot outcome that received one bid where one bid is rare.

    Sorted by publication and position within it, so writing the result is
    byte-stable and two runs over the same dataset produce the same file.
    """
    population = list(outcomes)
    counts = segment_counts(population)

    found = []
    for outcome in population:
        if outcome.bids != SINGLE_BID:
            continue
        size, singles = counts[outcome.segment]
        if not is_rare(size, singles):
            continue
        found.append(
            Flag(
                source_publication_id=outcome.source_publication_id,
                source_notice_id=outcome.source_notice_id,
                source_url=notice_url(outcome.source_publication_id),
                publication_year=outcome.publication_year,
                rule=RULE,
                rule_version=RULE_VERSION,
                lot_result_ordinal=outcome.lot_result_ordinal,
                lot_ref=outcome.lot_ref,
                bids=outcome.bids,
                segment_country=outcome.country,
                segment_cpv_division=outcome.cpv_division,
                segment_size=size,
                segment_single_bids=singles,
            )
        )
    return sorted(found, key=lambda flag: flag.sort_key)
