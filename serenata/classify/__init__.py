"""Stage 4: hypothesis classifiers over the normalised dataset.

One module per classifier. A classifier may not merge without its file in
``docs/hypotheses/``: a written, falsifiable hypothesis citing its
risk-indicator source, tests, and base rates measured on real historical
data. Classifiers read structured fields only (no free text, no NLP), run
offline, and are deterministic. Their output is statistical anomalies with
possible innocent explanations — never accusations.

Each rule is a pure function over rows. `serenata.classify.dataset` is the only
part that touches a file: it reads the outcomes a rule may speak about and
writes back the flags it returned, each carrying the baseline it was measured
against (`docs/adr/0011-flags-carry-their-own-baseline.md`).
"""

from pathlib import Path

from serenata.classify import single_bid_in_segment
from serenata.classify.dataset import (
    Classified,
    default_flag_root,
    read_outcomes,
    write_flags,
)
from serenata.classify.records import Flag, LotOutcome, notice_url

#: Every rule that runs, in the order they run. A module reaches this list only
#: with a hypothesis file beside it; `tests/test_constraints.py` is what makes
#: that true rather than customary.
RULES = (single_bid_in_segment,)

__all__ = [
    "RULES",
    "Classified",
    "Flag",
    "LotOutcome",
    "classify_dataset",
    "default_flag_root",
    "notice_url",
    "read_outcomes",
    "single_bid_in_segment",
    "write_flags",
]


def classify_dataset(dataset: Path, root: Path) -> list[Classified]:
    """Run every rule over ``dataset`` and write its flags under ``root``.

    The outcomes are read once and handed to each rule, because reading them is
    the expensive half and a rule may not mutate what it is given.
    """
    outcomes = read_outcomes(dataset)
    results = []
    for rule in RULES:
        found = rule.flags(outcomes)
        files = write_flags(found, root, rule=rule.RULE)
        results.append(
            Classified(
                rule=rule.RULE,
                rule_version=rule.RULE_VERSION,
                outcomes=len(outcomes),
                flags=len(found),
                files=tuple(files),
            )
        )
    return results
