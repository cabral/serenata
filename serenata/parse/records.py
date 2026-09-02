"""The typed intermediate records the parse stage produces.

Parse does not build the relational model — that is normalise's job, against
`docs/data-model.md`. What it produces is the notice's structure with its
personal data already gone: values keyed by the element path they came from,
grouped by the repeatable container they belong to.

Keying values by their element path is not a shortcut. ADR-0005 makes the path
the provenance vocabulary, so an intermediate record that carries paths carries
provenance without a second mechanism, and normalise maps path to column.
"""

from __future__ import annotations

from dataclasses import dataclass

from serenata.eforms import ROOT

#: The eForms extension prefix every ``efac:``/``efbc:`` path passes through.
EXTENSION = (
    f"{ROOT}/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension"
)

#: Container element path -> record kind, for the repeatable containers of
#: `docs/data-model.md`. Everything outside one of these belongs to the notice.
#:
#: Matched on the **exact** path, which is what keeps a reference from becoming
#: a record: ``efac:LotResult/efac:LotTender`` names the winning tender and is a
#: field of the lot result, while ``efac:NoticeResult/efac:LotTender`` is the
#: tender itself. The two differ only in their path, so the path is what decides.
CONTAINERS: dict[str, str] = {
    f"{ROOT}/cac:ProcurementProjectLot": "lot",
    f"{EXTENSION}/efac:Organizations/efac:Organization": "organisation",
    f"{EXTENSION}/efac:NoticeResult/efac:LotResult": "lot_result",
    f"{EXTENSION}/efac:NoticeResult/efac:LotTender": "lot_tender",
    f"{EXTENSION}/efac:NoticeResult/efac:SettledContract": "settled_contract",
    f"{EXTENSION}/efac:NoticeResult/efac:TenderingParty": "tendering_party",
}

#: The kind given to everything that is not inside a container above.
NOTICE = "notice"


@dataclass(frozen=True)
class Field:
    """One element's value, and whether it carried one.

    ``path`` is relative to the record's container, so a field of an
    organisation reads ``efac:Company/cac:PartyName/cbc:Name`` — the same form
    `serenata.parse.personal_data` suppresses against.

    ``empty`` distinguishes an element that was present and blank from one that
    carried a value, which ADR-0006 needs and a plain empty string cannot say.
    Only leaf elements become fields; a container that holds other elements is
    structure, not a blank value.
    """

    path: str
    value: str
    empty: bool


@dataclass(frozen=True)
class Record:
    """One instance of a repeatable container, or the notice itself.

    ``ordinal`` is the container's position among its siblings, counted in
    document order, so two organisations in one notice stay distinguishable
    without inventing an identifier for them.
    """

    kind: str
    ordinal: int
    notice_id: str
    fields: tuple[Field, ...]

    def value(self, path: str) -> str | None:
        """The value at ``path``, or ``None`` if this record has no such field.

        ``None`` means the field is not here at all. A field that was present
        and blank is a `Field` with ``empty`` set and an empty ``value``, which
        is a different fact — see ADR-0006.
        """
        for field in self.fields:
            if field.path == path:
                return field.value
        return None


@dataclass(frozen=True)
class ParsedNotice:
    """Every record read out of one notice.

    ``records`` always begins with the notice-level record and continues in the
    order containers closed, which is document order for a notice's siblings.
    Deterministic, per constraint 4: the same notice yields the same records in
    the same order.
    """

    notice_id: str
    root_element: str
    records: tuple[Record, ...]

    def of_kind(self, kind: str) -> tuple[Record, ...]:
        """Every record of one kind, in document order."""
        return tuple(record for record in self.records if record.kind == kind)
