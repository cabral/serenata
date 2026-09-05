"""The eForms XML vocabulary and shared guarded reader.

Shared by the parse stage and the field survey. It lives at package root rather
than inside either of them because the prefix map is load-bearing for
constraint 2: the drop list in ``serenata.parse.personal_data`` is written in
these prefixes, and a second copy that drifted would silently stop matching the
paths it exists to reject. One map, one meaning.

Reading is streamed and refuses document type declarations, per ADR-0003.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import IO, cast
from xml.etree.ElementTree import Element, ParseError, XMLPullParser

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

#: Size of the first read, not a limit on the prolog scan.
HEADER_BYTES = 8192

#: Bytes fed to the parser at a time once the header has been cleared.
CHUNK_BYTES = 1 << 16

#: UBL names a document type's namespace after the document itself, so
#: ``ContractNotice`` lives in ``…:xsd:ContractNotice-2``. Requiring that
#: agreement is what keeps a UBL ``Invoice`` — same prefix, same schema family,
#: not a notice — from being read as one.
UBL_PREFIX = "urn:oasis:names:specification:ubl:schema:xsd:"

#: eForms notice namespaces outside UBL. Measured against OJ S 157/2026; a new
#: one is refused by name, which makes adding it a one-line change rather than
#: a silent acceptance of whatever arrives.
EFORMS_NOTICE_NAMESPACES = frozenset(
    {"http://data.europa.eu/p27/eforms-business-registration-information-notice/1"}
)

#: Collect this many opening bytes (or EOF) before feeding the parser, even
#: when read() returns short. UTF-16/32 signatures contain NUL or a non-ASCII
#: BOM; an ASCII-compatible XML document starts with '<' or XML whitespace,
#: optionally preceded by a UTF-8 BOM. This is not full UTF-8 validation.
_ENCODING_BYTES = 4
_XML_STARTS = (b"<", b" ", b"\t", b"\r", b"\n", b"\xef\xbb\xbf")

#: ``<!DOCTYPE`` minus one, so a declaration split across two reads is still
#: seen: the tail of one chunk is prepended to the next before scanning.
_DOCTYPE_OVERLAP = len("<!DOCTYPE") - 1

#: The root element of a legacy TED notice, recognised so it can be refused
#: with a message that says why rather than as an unknown document.
LEGACY_ROOT = "TED_EXPORT"

_DOCTYPE = re.compile(rb"<!DOCTYPE", re.IGNORECASE)


class NoticeRejected(ValueError):
    """A notice this project will not parse."""


class NotEForms(NoticeRejected):
    """A document whose own root element says it is not an eForms notice.

    Separate from the rest of `NoticeRejected` because the two are different
    facts about a package, with different work behind them: this one is a
    format nobody has written a mapping for, the others are documents that are
    damaged or unsafe to read. A caller that folded them together would report
    a package of legacy notices as unreadable, and send someone looking for a
    corruption that is not there.
    """

    def __init__(self, root: str, message: str) -> None:
        super().__init__(message)
        #: The root element's local name, without its namespace.
        self.root = root
        #: Whether the document is a legacy TED notice rather than something
        #: this project has never seen. Legacy notices are open-work #3; the
        #: rest are a package carrying something unexpected.
        self.legacy = root == LEGACY_ROOT


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


def is_eforms_root(tag: str) -> bool:
    """Whether this root element belongs to an eForms notice.

    Checked against the namespace the document declares rather than against a
    prefix of it. A prefix match accepts every UBL document there is — an
    ``Invoice`` and an ``Order`` share the notice types' namespace family — and
    those parse into records that look like a notice and are not one.
    """
    namespace = namespace_of(tag)
    local = tag.rpartition("}")[2]
    if namespace.startswith(UBL_PREFIX):
        return local.endswith("Notice") and namespace == f"{UBL_PREFIX}{local}-2"
    return namespace in EFORMS_NOTICE_NAMESPACES


def accept_eforms_root(tag: str, *, because: str) -> None:
    """Raise `NotEForms` unless this root element opens an eForms notice.

    Every reader of a package asks the same question of every member, and each
    one used to answer it for itself — parse from the root namespace, the
    survey from the filename. A name is a claim and a package mixes formats, so
    the two disagreed by construction: an eForms notice delivered under a
    legacy-style name was parsed by one and counted as legacy by the other.
    One test, in the vocabulary that owns it.

    ``because`` says what *this* reader cannot do with such a document, which
    is the part that differs — refusing to parse a legacy notice and refusing
    to measure one are the same refusal for different reasons, and a message
    that named neither would be no use to whoever hits it.
    """
    if is_eforms_root(tag):
        return
    root = tag.rpartition("}")[2]
    described = (
        "legacy TED notice"
        if root == LEGACY_ROOT
        else f"unrecognised notice root element {root!r}"
    )
    raise NotEForms(root, f"{described}: {because}")


class PrologGuard:
    """Check the opening encoding signature, then scan the prolog for DTDs.

    The XML specification allows a DTD only before the root element. For
    ASCII-compatible markup, scanning chunks with overlap until the root opens
    catches the marker even behind long comments or across reads (ADR-0003).
    UTF-16/32 would hide that marker, with or without a BOM, so the opening
    signature must be checked before any bytes reach the parser.
    """

    def __init__(self) -> None:
        self._tail = b""
        self._scanning = True
        self._started = False

    def check(self, chunk: bytes) -> None:
        """Check before feeding; first chunk must contain at least 4 bytes or EOF."""
        if not self._started:
            self._started = True
            prefix = chunk[:_ENCODING_BYTES]
            if b"\x00" in prefix or not prefix.startswith(_XML_STARTS):
                raise NoticeRejected(
                    "notice lacks an ASCII-compatible XML prefix (UTF-8 is "
                    "supported); this project refuses encodings it cannot scan "
                    "for a document type declaration (ADR-0003)"
                )
        if not self._scanning:
            return
        window = self._tail + chunk
        if _DOCTYPE.search(window):
            raise NoticeRejected(
                "notice carries a document type declaration; eForms notices are "
                "schema-validated and do not need one (ADR-0003)"
            )
        self._tail = window[-_DOCTYPE_OVERLAP:]

    def root_started(self) -> None:
        """Stop scanning: nothing after the root element can declare a DTD."""
        self._scanning = False
        self._tail = b""


def stream_elements(source: IO[bytes]) -> Iterator[tuple[str, str, Element[str]]]:
    """Yield ``(event, qualified name, element)`` for one notice, streaming.

    The mechanics both readers need and neither should own: feeding the parser
    in chunks, refusing a document type declaration across the whole prolog,
    and releasing each element once the consumer has seen it close. What a
    reader does with the events — count paths, build records — is its own.

    **An element is not valid after its end event.** It is cleared and unhooked
    from its parent as soon as the consumer resumes. This releases completed
    subtrees, but does not impose a memory limit on parser buffers, large text
    or attributes, nesting, or values retained by consumers. Read what you need
    while you have it.
    """
    parser: XMLPullParser[Element[str]] = XMLPullParser(events=("start", "end"))
    guard = PrologGuard()
    open_elements: list[Element[str]] = []
    seen_root = False

    def drain() -> Iterator[tuple[str, str, Element[str]]]:
        nonlocal seen_root
        # read_events() is typed for every event kind it could be asked for;
        # subscribing to start and end alone means the payload is an Element.
        events = cast("Iterator[tuple[str, Element[str]]]", parser.read_events())
        for event, element in events:
            name = qualified_name(element.tag)
            if event == "start":
                if not seen_root:
                    seen_root = True
                    guard.root_started()
                open_elements.append(element)
                yield event, name, element
                continue
            yield event, name, element
            open_elements.pop()
            # Release the element and unhook it from its parent, so a finished
            # subtree is not held for the length of the document.
            element.clear()
            if open_elements:
                open_elements[-1].remove(element)

    chunk = source.read(HEADER_BYTES)
    # A binary stream may return fewer bytes than requested. Do not let Expat
    # see a partial BOM or encoding signature before the guard can check it.
    while 0 < len(chunk) < _ENCODING_BYTES:
        more = source.read(_ENCODING_BYTES - len(chunk))
        if not more:
            break
        chunk += more
    while chunk:
        guard.check(chunk)
        parser.feed(chunk)
        yield from drain()
        chunk = source.read(CHUNK_BYTES)

    parser.close()
    yield from drain()

    if not seen_root:
        raise ParseError("no root element")
