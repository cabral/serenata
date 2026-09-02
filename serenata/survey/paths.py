"""Element paths present in an eForms notice.

eForms permits far more fields than any notice uses, and usage varies by member
state. This module reports what a notice actually carries, so the data model can
be designed against observed usage rather than the specification's optionality.

Paths are reported as namespace-prefixed element paths
(``notice/cac:ProcurementProject/cbc:Name``) rather than eForms BT codes.
BT codes are what the specification names fields by, but mapping an element path
to its BT code needs the eForms SDK, which this offline survey does not carry.
Element paths are what is observable in the XML, and they are unambiguous.

Nothing here reads a field's *value* into its output. The survey counts
presence, which is all the data model needs and all constraint 2 permits — some
of these elements can carry a natural person's name.

Notices are parsed as a stream and discarded element by element. That is not
premature: one real notice in OJ S 157/2026 is 40 MB, 1,569 times the median,
and reading a whole tree cost four times the file's own size. Streaming also
bounds what a document with deeply amplified entities could cost, and a document
type declaration is refused outright — see ADR-0003.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import IO
from xml.etree.ElementTree import ParseError

from serenata.eforms import (
    CHUNK_BYTES,
    EFORMS_PREFIXES,
    HEADER_BYTES,
    ROOT,
    NoticeRejected,
    PrologGuard,
    qualified_name,
    stream_elements,
)

#: Re-exported so this module stays the survey's single entry point for the
#: vocabulary. The definitions live in ``serenata.eforms`` because the parse
#: stage needs the identical prefix map — see that module.
__all__ = [
    "CHUNK_BYTES",
    "EFORMS_PREFIXES",
    "HEADER_BYTES",
    "ROOT",
    "NoticeRejected",
    "NoticeShape",
    "PrologGuard",
    "qualified_name",
    "read_notice",
    "stream_elements",
]

_COUNTRY_CODE_SUFFIX = "/cac:Country/cbc:IdentificationCode"
_SUBTYPE = "cbc:SubTypeCode"


@dataclass(frozen=True)
class NoticeShape:
    """What one notice carries, without carrying any of its values."""

    root_type: str
    subtype: str | None
    countries: frozenset[str] = field(default_factory=frozenset)
    valued_paths: frozenset[str] = field(default_factory=frozenset)
    empty_paths: frozenset[str] = field(default_factory=frozenset)


def read_notice(source: IO[bytes]) -> NoticeShape:
    """Describe one eForms notice by the paths it populates.

    Reads ``source`` as a stream, discarding each element once its path has
    been recorded, so cost tracks the deepest element rather than the whole
    document. The walk itself is `serenata.eforms.stream_elements`, shared with
    the parse stage; what is counted here is this module's own.
    """
    root_type: str | None = None
    subtype: str | None = None
    countries: set[str] = set()
    valued: set[str] = set()
    empty: set[str] = set()
    path: list[str] = []

    for event, name, element in stream_elements(source):
        if event == "start":
            if root_type is None:
                root_type = name
            path.append(ROOT if not path else name)
            continue

        here = "/".join(path)
        text = (element.text or "").strip()
        (valued if text else empty).add(here)

        if text and name == _SUBTYPE and subtype is None:
            subtype = text
        if text and here.endswith(_COUNTRY_CODE_SUFFIX):
            countries.add(text)

        path.pop()

    if root_type is None:  # pragma: no cover - stream_elements raises first
        raise ParseError("no root element")

    return NoticeShape(
        root_type=root_type,
        subtype=subtype,
        countries=frozenset(countries),
        valued_paths=frozenset(valued),
        # A path that holds a value somewhere is not "empty"; containers and
        # genuinely blank elements are what remain.
        empty_paths=frozenset(empty - valued),
    )
