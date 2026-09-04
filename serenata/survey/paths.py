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
    NotEForms,
    NoticeRejected,
    PrologGuard,
    accept_eforms_root,
    qualified_name,
    stream_elements,
)
from serenata.parse.records import CONTAINERS

#: Re-exported so this module stays the survey's single entry point for the
#: vocabulary. The definitions live in ``serenata.eforms`` because the parse
#: stage needs the identical prefix map — see that module.
__all__ = [
    "CHUNK_BYTES",
    "CONTAINERS",
    "EFORMS_PREFIXES",
    "HEADER_BYTES",
    "ROOT",
    "NotEForms",
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
    #: ``(path, times)`` — the most times a path occurred inside a single
    #: record of this notice. Sorted, so the shape is comparable and the
    #: report it feeds is deterministic.
    max_per_record: tuple[tuple[str, int], ...] = ()


def read_notice(source: IO[bytes]) -> NoticeShape:
    """Describe one eForms notice by the paths it populates.

    Reads ``source`` as a stream, discarding each element once its path has
    been recorded, so cost tracks the deepest element rather than the whole
    document. The walk itself is `serenata.eforms.stream_elements`, shared with
    the parse stage; what is counted here is this module's own.

    Raises `NotEForms` for a document whose root says it is not an eForms
    notice — the same test the parse stage applies, so a member cannot be a
    notice to one stage and not to the other.

    Two things are counted. **Presence** — which paths carry a value — is what
    the data model was first written against. **Cardinality** is what it turned
    out to need as well: how many times a path occurs inside a single record,
    which is the difference between a column that can hold one value and one
    that has to hold a set. A model written against presence alone will give a
    scalar column to a path that repeats, and then quietly store one arbitrary
    value of several.
    """
    root_type: str | None = None
    subtype: str | None = None
    countries: set[str] = set()
    valued: set[str] = set()
    empty: set[str] = set()
    #: Each open element's full path, so the path is not rejoined per event.
    joined: list[str] = []
    #: ``(container path, depth, counts)`` per open record. Counting within the
    #: record rather than the notice is the whole point: a notice carries eight
    #: lots, and it is what a *lot* repeats that decides the lot table's columns.
    open_records: list[tuple[str, int, dict[str, int]]] = []
    notice_counts: dict[str, int] = {}
    maxima: dict[str, int] = {}

    def fold(counts: dict[str, int]) -> None:
        for path, count in counts.items():
            if count > maxima.get(path, 0):
                maxima[path] = count

    for event, name, element in stream_elements(source):
        if event == "start":
            if root_type is None:
                accept_eforms_root(
                    element.tag,
                    because=(
                        "the paths this survey counts are the eForms "
                        "vocabulary, so measuring another format against them "
                        "would report field usage for fields that are not the "
                        "ones being counted (open-work #3)"
                    ),
                )
                root_type = name
            step = ROOT if not joined else name
            here = f"{joined[-1]}/{step}" if joined else step
            joined.append(here)
            if here in CONTAINERS:
                open_records.append((here, len(joined), {}))
            continue

        here = joined[-1]
        text = (element.text or "").strip()
        (valued if text else empty).add(here)

        if text and name == _SUBTYPE and subtype is None:
            subtype = text
        if text and here.endswith(_COUNTRY_CODE_SUFFIX):
            countries.add(text)

        if open_records and open_records[-1][1] == len(joined):
            # The record this element opened is closing: fold its counts before
            # counting the element itself, which belongs to the enclosing one.
            fold(open_records.pop()[2])
        counts = open_records[-1][2] if open_records else notice_counts
        counts[here] = counts.get(here, 0) + 1

        joined.pop()

    fold(notice_counts)

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
        max_per_record=tuple(sorted(maxima.items())),
    )
