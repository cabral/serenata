"""Read one archived notice into typed intermediate records.

Streamed, and refusing document type declarations, per ADR-0003:
`serenata.survey.paths` is the reference this follows rather than improves on.
One real notice in OJ S 157/2026 is 40 MB, so reading a whole tree is not an
option; each element is discarded once its value has been taken.

The *element* is discarded, not the value. A notice's records are returned
together, because every record carries the notice identifier and that is not
known until `notice/cbc:ID` has been read — so the records cannot be emitted as
they close. Memory is therefore bounded by one notice's extracted values rather
than by its XML: 89 MB peak across the 3,190-notice package, against the
survey's 4.3 MB for keeping only counts.

Constraint 2 is enforced here, because here is where the values first exist.
A path the drop list rejects is never read into a record, and an organisation
flagged as a natural person loses the values that identify it. What the parser
cannot avoid is materialising the text of the element it is closing — that is
expat's behaviour, not a choice this module makes. What it can guarantee, and
does, is that no such text is ever copied into a record or held after the
element is cleared.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import IO, cast
from xml.etree.ElementTree import Element, ParseError, XMLPullParser

from serenata.eforms import (
    CHUNK_BYTES,
    HEADER_BYTES,
    LEGACY_ROOT,
    ROOT,
    NoticeRejected,
    PrologGuard,
    is_eforms_root,
    qualified_name,
)
from serenata.parse.personal_data import (
    NATURAL_PERSON_INDICATOR,
    is_dropped_path,
    suppressed_for_natural_person,
)
from serenata.parse.records import CONTAINERS, NOTICE, Field, ParsedNotice, Record

#: Where the notice's own identifier sits. Present in every notice surveyed,
#: and required: it is the key every record carries back to its source.
NOTICE_ID_PATH = f"{ROOT}/cbc:ID"


@dataclass
class _Open:
    """A container element being filled while its subtree is read."""

    kind: str
    path: str
    ordinal: int
    depth: int
    fields: list[Field] = field(default_factory=list)


def _accept_root(tag: str, name: str) -> str:
    """Confirm the document is an eForms notice, from its root element.

    Dispatching on the root rather than the filename is deliberate: a package
    mixes formats and a name is a claim, while the root namespace is the
    document saying what it is.
    """
    if is_eforms_root(tag):
        return name
    if name == LEGACY_ROOT:
        raise NoticeRejected(
            "legacy TED notice. The mapping from legacy elements into the data "
            "model has not been measured — no archived package contains a "
            "legacy notice — so parsing one would be a guess about which "
            "fields can name a person. See docs/personal-data.md and "
            "docs/data-model.md; open-work #3 is the work that lifts this."
        )
    raise NoticeRejected(f"unrecognised notice root element {name!r}")


#: ``efbc:NaturalPersonIndicator`` is an ``xs:boolean``, whose lexical space is
#: {true, false, 1, 0} — so a publisher writing ``1`` is saying the same thing
#: as one writing ``true``. Only these two forms are read as a denial.
_NOT_A_NATURAL_PERSON = frozenset({"false", "0"})


def _is_natural_person(fields: list[Field]) -> bool:
    """Whether this organisation is a sole trader, per its own indicator.

    An **absent** indicator is "not provided", never "false" (ADR-0006), and it
    is not this function's job to guess — open-work #11 is where that gap is
    answered. A **present** one is read the other way about: anything that is
    not an explicit denial suppresses. Matching only ``true`` would have let a
    notice written with ``1`` keep a sole trader's name, national registration
    number and address, and docs/personal-data.md's instruction is to err
    toward dropping — a value we cannot read is not a denial.
    """
    for item in fields:
        if item.path == NATURAL_PERSON_INDICATOR:
            return item.value.strip().lower() not in _NOT_A_NATURAL_PERSON
    return False


def _finish(pending: _Open, notice_id: str) -> Record:
    fields = pending.fields
    if pending.kind == "organisation" and _is_natural_person(fields):
        # The organisation is a private individual trading in their own name:
        # the name, registration identifier and addresses are that person's
        # personal data. The opaque intra-notice key is kept, so the record is
        # anonymised rather than deleted. See docs/personal-data.md.
        fields = [
            item for item in fields if not suppressed_for_natural_person(item.path)
        ]
    return Record(
        kind=pending.kind,
        ordinal=pending.ordinal,
        notice_id=notice_id,
        fields=tuple(fields),
    )


def read_notice(source: IO[bytes]) -> ParsedNotice:
    """Read one eForms notice into its intermediate records.

    Raises `NoticeRejected` for a notice this project will not parse — a
    document type declaration, a legacy TED or unrecognised root, or a notice
    with no identifier — and `ParseError` for malformed XML. Nothing is
    skipped silently: a caller that cannot use a notice is told which and why.
    """
    parser: XMLPullParser[Element[str]] = XMLPullParser(events=("start", "end"))

    guard = PrologGuard()

    root_element: str | None = None
    notice_id: str | None = None
    path: list[str] = []
    #: ``path`` joined, one entry per depth, so the element path is not rebuilt
    #: on every start and end event. This loop runs about 1.7 million times per
    #: package; joining there is the difference between a minute and less.
    joined: list[str] = []
    #: Sibling index of each element on ``path``, so a repeated block's fields
    #: can be told apart. See ``Field.occurrence``.
    indices: list[int] = []
    #: Per open element, how many children of each name it has seen.
    child_counts: list[dict[str, int]] = []
    has_children: list[bool] = []
    open_elements: list[Element[str]] = []
    notice_fields: list[Field] = []
    open_containers: list[_Open] = []
    finished: list[_Open] = []
    seen: Counter[str] = Counter()

    def drain() -> None:
        nonlocal root_element, notice_id
        # read_events() is typed for every event kind it could be asked for;
        # subscribing to start and end alone means the payload is an Element.
        events = cast("Iterator[tuple[str, Element[str]]]", parser.read_events())
        for event, element in events:
            name = qualified_name(element.tag)

            if event == "start":
                if root_element is None:
                    root_element = _accept_root(element.tag, name)
                    guard.root_started()
                step = ROOT if not path else name
                if child_counts:
                    counts = child_counts[-1]
                    index = counts.get(step, 0)
                    counts[step] = index + 1
                else:
                    index = 0
                path.append(step)
                here = f"{joined[-1]}/{step}" if joined else step
                joined.append(here)
                indices.append(index)
                child_counts.append({})
                has_children.append(False)
                if len(has_children) > 1:
                    has_children[-2] = True
                open_elements.append(element)
                kind = CONTAINERS.get(here)
                if kind is not None:
                    open_containers.append(
                        _Open(
                            kind=kind,
                            path=here,
                            ordinal=seen[here],
                            depth=len(path),
                        )
                    )
                    seen[here] += 1
                continue

            here = joined[-1]
            had_children = has_children.pop()

            if open_containers and open_containers[-1].path == here:
                finished.append(open_containers.pop())
            elif not is_dropped_path(here, path):
                # Checked before the value is read, not after: a dropped field
                # must never be constructed, only to be removed downstream.
                text = (element.text or "").strip()
                # A leaf always becomes a field, blank or not. An element with
                # children does not — it is structure — unless it also carries
                # text of its own, which no notice in the surveyed package does
                # and which would otherwise be dropped without a trace.
                if not had_children or text:
                    inner = open_containers[-1] if open_containers else None
                    base = inner.path if inner else ROOT
                    depth = inner.depth if inner else 1
                    target = inner.fields if inner else notice_fields
                    target.append(
                        Field(
                            path=here[len(base) + 1 :],
                            value=text,
                            empty=not text,
                            attributes=tuple(
                                (qualified_name(key), value)
                                for key, value in element.attrib.items()
                            ),
                            occurrence=tuple(indices[depth:]),
                        )
                    )
                    if here == NOTICE_ID_PATH and text and notice_id is None:
                        notice_id = text

            path.pop()
            joined.pop()
            indices.pop()
            child_counts.pop()
            open_elements.pop()
            # Release the element and unhook it from its parent, so a finished
            # subtree is not held for the length of the document.
            element.clear()
            if open_elements:
                open_elements[-1].remove(element)

    chunk = source.read(HEADER_BYTES)
    while chunk:
        guard.check(chunk)
        parser.feed(chunk)
        drain()
        chunk = source.read(CHUNK_BYTES)

    parser.close()
    drain()

    if root_element is None:
        raise ParseError("no root element")
    if notice_id is None:
        raise NoticeRejected(
            f"notice carries no {NOTICE_ID_PATH}; every record has to trace "
            "back to a source notice and this one cannot be identified"
        )

    records = [
        Record(
            kind=NOTICE, ordinal=0, notice_id=notice_id, fields=tuple(notice_fields)
        ),
        *(_finish(pending, notice_id) for pending in finished),
    ]
    return ParsedNotice(
        notice_id=notice_id, root_element=root_element, records=tuple(records)
    )
