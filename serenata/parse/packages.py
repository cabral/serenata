"""Read every notice in an archived daily package.

The stage does not decide what a caller should do about a notice it cannot
read, and it does not hide that there was one. Both halves matter, and an
exception cannot deliver them together: raising from inside a generator closes
it, so every notice after the first bad one would be lost — silently, since the
caller that caught the error would see iteration end normally. That is the
invisible gap this module exists to prevent, so failures are yielded rather
than raised.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import ParseError

from serenata.eforms import NoticeRejected
from serenata.packages import notice_members
from serenata.parse.notice import read_notice
from serenata.parse.records import ParsedNotice


@dataclass(frozen=True)
class Unparsed:
    """A member of a package that could not be read into records.

    Carries the member it came from. TED names each member after the notice's
    own publication number (``00566631_2026.xml``), so the member identifies
    the notice even when the document is too damaged to read an identifier out
    of — which is the case where saying *which* notice failed matters most.
    """

    member: str
    reason: str


#: What one member of a package becomes: records, or a reason it did not.
#: Yielding a union rather than raising is what lets a run continue past a bad
#: notice without the failure going unseen — a caller has to look at what it
#: was handed, and cannot mistake a truncated run for a complete one.
Outcome = ParsedNotice | Unparsed


def parse_package(package: Path) -> Iterator[Outcome]:
    """Yield an outcome for every notice in ``package``, in archive order.

    A notice that cannot be parsed yields `Unparsed` and the run continues, so
    one damaged document does not cost the other 3,189. A legacy-format package
    yields an `Unparsed` for each of its notices rather than nothing at all,
    which would look exactly like an empty package.

    A caller that wants to stop on the first failure checks the type and stops;
    one that wants to count them counts. Neither can end up with a partial
    dataset without having been told.
    """
    for name, handle in notice_members(package):
        try:
            # Streamed, not read whole: one notice in a real package is
            # 40 MB, 1,569 times the median (ADR-0003).
            yield read_notice(handle)
        except (ParseError, NoticeRejected) as exc:
            yield Unparsed(member=name, reason=str(exc))
