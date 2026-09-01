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
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from xml.etree.ElementTree import Element, fromstring

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


def walk(element: Element, prefix: str = "") -> Iterator[tuple[str, bool]]:
    """Yield ``(path, has_value)`` for the element and everything beneath it."""
    here = f"{prefix}/{qualified_name(element.tag)}" if prefix else ROOT
    yield here, bool((element.text or "").strip())
    for child in element:
        yield from walk(child, here)


def _first_text(root: Element, local_name: str) -> str | None:
    for element in root.iter():
        if qualified_name(element.tag).split(":")[-1] == local_name:
            text = (element.text or "").strip()
            if text:
                return text
    return None


def _country_codes(root: Element) -> frozenset[str]:
    """Country codes named anywhere in the notice.

    This is the countries a notice *names*, not a single attributed buyer
    country: a notice can name several organisations in several states. It is
    enough to answer the question the data model needs — whether a field is used
    across the union or only in some member states — and claiming more would
    require resolving which organisation is the buyer.
    """
    codes = set()
    for element in root.iter():
        if qualified_name(element.tag) != "cac:Country":
            continue
        for child in element:
            if qualified_name(child.tag) == "cbc:IdentificationCode":
                text = (child.text or "").strip()
                if text:
                    codes.add(text)
    return frozenset(codes)


def read_notice(xml: bytes) -> NoticeShape:
    """Describe one eForms notice by the paths it populates."""
    root = fromstring(xml)

    valued: set[str] = set()
    empty: set[str] = set()
    for path, has_value in walk(root):
        (valued if has_value else empty).add(path)

    return NoticeShape(
        root_type=qualified_name(root.tag),
        subtype=_first_text(root, "SubTypeCode"),
        countries=_country_codes(root),
        valued_paths=frozenset(valued),
        # A path that holds a value somewhere is not "empty"; containers and
        # genuinely blank elements are what remain.
        empty_paths=frozenset(empty - valued),
    )
