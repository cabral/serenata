"""The eForms XML vocabulary, and how this project reads it safely.

Shared by the parse stage and the field survey. It lives at package root rather
than inside either of them because the prefix map is load-bearing for
constraint 2: the drop list in ``serenata.parse.personal_data`` is written in
these prefixes, and a second copy that drifted would silently stop matching the
paths it exists to reject. One map, one meaning.

Reading is streamed and refuses document type declarations, per ADR-0003.
"""

from __future__ import annotations

import re

#: The namespaces eForms notices are written in, and the prefixes the
#: specification uses for them. An element in an unlisted namespace keeps its
#: bare local name, which is visible in a path without a prefix.
EFORMS_PREFIXES = {
    "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2": "cac",
    "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2": "cbc",
    "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2": "ext",
    "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1": "efac",
    "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1": "efbc",
    "http://data.europa.eu/p27/eforms-ubl-extensions/1": "efext",
}

#: Notice types differ at the root (``ContractNotice``, ``ContractAwardNotice``,
#: …), so the root is normalised to this in every path. Without it, the same
#: field would appear under several paths.
ROOT = "notice"

#: A document type declaration must appear in the prolog, so the opening bytes
#: are enough to find one. Comfortably larger than any eForms prolog.
HEADER_BYTES = 8192

#: Bytes fed to the parser at a time once the header has been cleared.
CHUNK_BYTES = 1 << 16

#: Root namespaces that mark a document as eForms. The three UBL notice types
#: sit under the OASIS prefix; the business registration notice under the
#: Publications Office's own. Measured against OJ S 157/2026, where these cover
#: all 3,190 notices.
EFORMS_ROOT_NAMESPACES = (
    "urn:oasis:names:specification:ubl:schema:xsd:",
    "http://data.europa.eu/p27/",
)

#: The root element of a legacy TED notice, recognised so it can be refused
#: with a message that says why rather than as an unknown document.
LEGACY_ROOT = "TED_EXPORT"

_DOCTYPE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)


class NoticeRejected(ValueError):
    """A notice this project will not parse."""


def qualified_name(tag: str) -> str:
    """``cbc:IssueDate`` for a namespaced ElementTree tag."""
    if not tag.startswith("{"):
        return tag
    uri, _, local = tag[1:].partition("}")
    prefix = EFORMS_PREFIXES.get(uri)
    return f"{prefix}:{local}" if prefix else local


def namespace_of(tag: str) -> str:
    """The namespace URI of an ElementTree tag, or ``""`` if it has none."""
    if not tag.startswith("{"):
        return ""
    return tag[1:].partition("}")[0]


def reject_doctype(header: bytes) -> None:
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
