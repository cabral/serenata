"""What a classifier reads, and what it writes.

Two records, and the distance between them is the whole stage. A `LotOutcome`
is a lot result reduced to the fields a rule may read — structured values,
already normalised, nothing free text (constraint 5). A `Flag` is one anomaly,
carrying the evidence for its own claim so that checking it does not mean
rerunning the pipeline — see `docs/adr/0011-flags-carry-their-own-baseline.md`.

**A flag is a statistical anomaly, never an accusation** (constraint 3). Nothing
in these records asserts wrongdoing, and nothing downstream may phrase them as
though they did: the row says what was measured and what it was compared
against, and the innocent explanations are in the classifier's hypothesis file.

**No floating point.** A segment's rate is carried as the two counts it was
computed from rather than as a quotient. The rate is one division away for
anyone who wants it, and a file with no float in it cannot differ between runs
by a rounding decision — which is one less thing standing between constraint 4
and a byte-identical rerun.
"""

from __future__ import annotations

from dataclasses import dataclass, fields

#: TED serves every notice at this address. The XML rather than the
#: human-readable page because it is the document the pipeline actually read:
#: a reader following a flag arrives at the bytes the flag came from, not at a
#: rendering of them. The same notice is readable at
#: ``/en/notice/-/detail/{publication id}``.
NOTICE_URL = "https://ted.europa.eu/en/notice/{publication_id}/xml"


@dataclass(frozen=True)
class LotOutcome:
    """One lot result, reduced to what a rule may read.

    Assembled by `serenata.classify.dataset` from the normalised tables. Every
    field here is a structured value or this project's own numbering; a rule
    that needs anything else needs a different case file, not a wider record.
    """

    source_publication_id: str
    source_notice_id: str
    publication_year: str
    #: Which lot result within the notice, and which lot it decided.
    lot_result_ordinal: int
    lot_ref: str
    #: Bids received. Read as a number by the rule, which is the rule's own act:
    #: the model stores it as published, because a withheld count is published
    #: as ``-1`` and casting it silently would make a deferral a quantity
    #: (ADR-0006). Outcomes carrying a withheld count never reach here.
    bids: int
    #: The market this outcome is compared against.
    country: str
    cpv_division: str
    #: The latest publication day in the corpus supersession was evaluated
    #: against (ADR-0013). Corrections published after it are not reflected,
    #: and a flag that did not say so would overstate how current it is.
    correction_cutoff: str

    @property
    def segment(self) -> tuple[str, str]:
        return self.country, self.cpv_division


@dataclass(frozen=True)
class Flag:
    """One anomaly, with the evidence that makes it checkable.

    Per ADR-0011 a flag carries the values the rule read *and* the baseline it
    compared them against, so a reader can disagree without rerunning anything:
    the row says one bid, in a market of this size where this many lots drew a
    single bid, and links the notice it came from.
    """

    source_publication_id: str
    source_notice_id: str
    source_url: str
    publication_year: str
    #: The rule that fired, and its own version. Bumped when the logic changes,
    #: so two runs that disagree can be told from two rules that disagree.
    rule: str
    rule_version: int
    lot_result_ordinal: int
    lot_ref: str
    #: The evidence: what was read, and what it was measured against.
    bids: int
    segment_country: str
    segment_cpv_division: str
    segment_size: int
    segment_single_bids: int
    #: The corpus this flag's supersession check saw, carried for the same
    #: reason as the baseline beside it: a reader can tell what it could and
    #: could not have known (ADR-0011, ADR-0013).
    correction_cutoff: str

    @property
    def sort_key(self) -> tuple[str, int]:
        """Publication, then position within it. Fixed, so a rerun matches."""
        return self.source_publication_id, self.lot_result_ordinal


#: The flag table's columns, in declaration order. Taken from the dataclass
#: rather than restated, so a field added to the record reaches the file.
FLAG_COLUMNS = tuple(field.name for field in fields(Flag))

#: Columns stored as integers. Everything else is a string, following the
#: normalised model's rule that values are stored as published — except that
#: these are not published values, they are this stage's own counting.
FLAG_INTEGERS = frozenset(
    {
        "rule_version",
        "lot_result_ordinal",
        "bids",
        "segment_size",
        "segment_single_bids",
    }
)


def notice_url(publication_id: str) -> str:
    """Where a reader checks the flag: the notice on TED, as XML."""
    return NOTICE_URL.format(publication_id=publication_id)
