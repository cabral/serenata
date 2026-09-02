"""Read every notice in an archived daily package.

Members are streamed out of the tarball rather than extracted to disk. The
archive is read-only input: parse never writes back into it, because raw files
are ground truth (ADR-0002).
"""

from __future__ import annotations

import tarfile
from collections.abc import Iterator
from pathlib import Path
from xml.etree.ElementTree import ParseError

from serenata.eforms import NoticeRejected
from serenata.parse.notice import read_notice
from serenata.parse.records import ParsedNotice


class NoticeParseError(Exception):
    """A notice in an archived package could not be parsed.

    Carries the member it came from. TED names each member after the notice's
    own publication number (``00566631_2026.xml``), so the member identifies
    the notice even when the document is too damaged to read an identifier out
    of — which is the case where saying *which* notice failed matters most.
    """

    def __init__(self, member: str, reason: str) -> None:
        self.member = member
        self.reason = reason
        super().__init__(f"{member}: {reason}")


def parse_package(package: Path) -> Iterator[ParsedNotice]:
    """Yield the parsed form of every notice in ``package``, in archive order.

    Raises `NoticeParseError` on the first notice that cannot be parsed,
    naming it. Nothing is skipped silently: a stage that quietly dropped the
    notices it could not read would produce a dataset whose gaps are invisible,
    and a legacy-format package would parse to nothing at all with no signal.

    A caller that wants to survey a mixed or damaged package catches the error
    per notice and decides its own policy. This stage does not decide for it.
    """
    with tarfile.open(package, "r:gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".xml"):
                continue
            handle = archive.extractfile(member)
            if handle is None:  # pragma: no cover - a directory entry named .xml
                raise NoticeParseError(member.name, "member could not be read")
            try:
                # Streamed, not read whole: one notice in a real package is
                # 40 MB, 1,569 times the median (ADR-0003).
                yield read_notice(handle)
            except (ParseError, NoticeRejected) as exc:
                raise NoticeParseError(member.name, str(exc)) from exc
