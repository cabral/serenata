"""Read a corrigendum link's parts out of the identifier TED published.

`efac:Changes/efbc:ChangedNoticeIdentifier` is the link from a corrigendum to
the notice it corrects. Two unrelated identifier namespaces share the column,
measured over 19,180 notices in `docs/correction-links.md`: 1,752 links carry an
eForms notice identifier with a two-digit version suffix, and 1,088 carry a
legacy TED publication number and year. There is no third shape in that corpus,
and `unknown` exists for the one that eventually appears rather than for a shape
already seen.

Which namespace a link used is recorded, not inferred at the point of use
(ADR-0013). Splitting the value here rather than in a query keeps the parse in
one place and keeps the two namespaces from being compared to each other, which
is what a naive join across them would do.

This is a string split over an archived value, not a resolution: whether the
target is in the corpus is a question for the classify stage, over the dataset.
"""

from __future__ import annotations

import re
from enum import StrEnum

#: An eForms notice identifier and the version of it being corrected. The
#: identifier matches `source_notice_id`; the suffix does not belong to it, and
#: leaving it attached is why a raw link resolves against nothing.
EFORMS_LINK = re.compile(
    r"(?P<target>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"
    r"-(?P<version>[0-9]{2})"
)

#: A legacy TED publication number and its year, the numbering that preceded
#: eForms. Measured first groups are four to six digits; the bound is wider than
#: that and still refuses a UUID or a free-form string. These carry no version.
TED_LEGACY_LINK = re.compile(r"(?P<target>[0-9]{1,8}-(?:19|20)[0-9]{2})")


class Namespace(StrEnum):
    """Which identifier namespace a correction link is written in."""

    #: An eForms notice identifier: joinable to `source_notice_id`.
    EFORMS = "eforms"
    #: A legacy TED publication number: no eForms notice carries this
    #: identifier, so a link in this namespace cannot resolve within a dataset
    #: built from eForms notices. Recorded rather than dropped — it is 38.3% of
    #: the links, and dropping it would understate how much goes unresolved.
    TED_LEGACY = "ted_legacy"
    #: A present link in neither namespace. Nothing in the measured corpus is
    #: `unknown`; it keeps an unrecognised shape visible instead of silently
    #: becoming an absent link.
    UNKNOWN = "unknown"


def parse_link(value: str | None) -> tuple[Namespace, str, str | None] | None:
    """Split ``value`` into its namespace, target identifier and version.

    Returns ``None`` when there is no link to split. An unrecognised shape
    keeps its whole value as the target, because the one thing that would be
    wrong is to report no link where TED published one.
    """
    if value is None or not value.strip():
        return None
    link = value.strip()
    if (eforms := EFORMS_LINK.fullmatch(link)) is not None:
        return Namespace.EFORMS, eforms["target"], eforms["version"]
    if (legacy := TED_LEGACY_LINK.fullmatch(link)) is not None:
        return Namespace.TED_LEGACY, legacy["target"], None
    return Namespace.UNKNOWN, link, None
