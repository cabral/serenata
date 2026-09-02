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

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import IO, cast
from xml.etree.ElementTree import Element, ParseError, XMLPullParser

#: The namespaces eForms notices are written in, and the prefixes the
#: specification uses for them. An element in an unlisted namespace keeps its
#: bare local name, which is visible in the report as a path without a prefix.
EFORMS_PREFIXES = {
    "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2": "cac",
    "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2": "cbc",
    "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2": "ext",
    "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1": "efac",
    "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1": "efbc",
    "http://data.europa.eu/p27/eforms-ubl-extensions/1": "efext",
}

#: Notice types differ at the root (``ContractNotice``, ``ContractAwardNotice``,
#: …), so the root is normalised to this and recorded separately. Without it,
#: the same field would appear as several paths and look rarer than it is.
ROOT = "notice"

#: A document type declaration must appear in the prolog, so the opening bytes
#: are enough to find one. Comfortably larger than any eForms prolog.
HEADER_BYTES = 8192

#: Bytes fed to the parser at a time once the header has been cleared.
CHUNK_BYTES = 1 << 16

_DOCTYPE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)

_COUNTRY_CODE_SUFFIX = "/cac:Country/cbc:IdentificationCode"
_SUBTYPE = "cbc:SubTypeCode"


class NoticeRejected(ValueError):
    """A notice this survey will not parse."""


@dataclass(frozen=True)
class NoticeShape:
    """What one notice carries, without carrying any of its values."""

    root_type: str
    subtype: str | None
    countries: frozenset[str] = field(default_factory=frozenset)
    valued_paths: frozenset[str] = field(default_factory=frozenset)
    empty_paths: frozenset[str] = field(default_factory=frozenset)


def qualified_name(tag: str) -> str:
    """``cbc:IssueDate`` for a namespaced ElementTree tag."""
    if not tag.startswith("{"):
        return tag
    uri, _, local = tag[1:].partition("}")
    prefix = EFORMS_PREFIXES.get(uri)
    return f"{prefix}:{local}" if prefix else local


def _reject_doctype(header: bytes) -> None:
    """Refuse a notice carrying a document type declaration (ADR-0003).

    eForms is validated against an XSD and no notice needs a DTD; none of the
    3,190 notices in OJ S 157/2026 carries one. Refusing them closes internal
    entity expansion, the one attack the standard library's parser is still
    open to, without taking on a dependency to do it.
    """
    if _DOCTYPE.search(header):
        raise NoticeRejected(
            "notice carries a document type declaration; eForms notices are "
            "schema-validated and do not need one (ADR-0003)"
        )


def read_notice(source: IO[bytes]) -> NoticeShape:
    """Describe one eForms notice by the paths it populates.

    Reads ``source`` as a stream, discarding each element once its path has
    been recorded, so cost tracks the deepest element rather than the whole
    document.
    """
    parser: XMLPullParser[Element[str]] = XMLPullParser(events=("start", "end"))

    header = source.read(HEADER_BYTES)
    _reject_doctype(header)

    root_type: str | None = None
    subtype: str | None = None
    countries: set[str] = set()
    valued: set[str] = set()
    empty: set[str] = set()
    open_elements: list[Element[str]] = []
    path: list[str] = []

    def drain() -> None:
        nonlocal root_type, subtype
        # read_events() is typed for every event kind it could be asked for;
        # subscribing to start and end alone means the payload is an Element.
        events = cast("Iterator[tuple[str, Element[str]]]", parser.read_events())
        for event, element in events:
            name = qualified_name(element.tag)
            if event == "start":
                if root_type is None:
                    root_type = name
                path.append(ROOT if not path else name)
                open_elements.append(element)
                continue

            here = "/".join(path)
            text = (element.text or "").strip()
            (valued if text else empty).add(here)

            if text and name == _SUBTYPE and subtype is None:
                subtype = text
            if text and here.endswith(_COUNTRY_CODE_SUFFIX):
                countries.add(text)

            path.pop()
            open_elements.pop()
            # Release the element and unhook it from its parent, so a finished
            # subtree is not held for the length of the document.
            element.clear()
            if open_elements:
                open_elements[-1].remove(element)

    chunk = header
    while chunk:
        parser.feed(chunk)
        drain()
        chunk = source.read(CHUNK_BYTES)

    parser.close()
    drain()

    if root_type is None:
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
