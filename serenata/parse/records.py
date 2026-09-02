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


class AmbiguousField(LookupError):
    """A path asked for as a single value occurs more than once."""


@dataclass(frozen=True)
class Field:
    """One element's value, and whether it carried one.

    ``path`` is relative to the record's container, so a field of an
    organisation reads ``efac:Company/cac:PartyName/cbc:Name`` — the same form
    `serenata.parse.personal_data` suppresses against.

    ``empty`` distinguishes an element that was present and blank from one that
    carried a value, which ADR-0006 needs and a plain empty string cannot say.
    A container that holds other elements is structure, not a blank value, and
    produces no field — unless it also carries text of its own, which nothing
    in the surveyed package does but which would otherwise vanish silently.
    The exception is an element that becomes a `Record`: it has no field of its
    own to hold stray text, so text there is not represented. That case is the
    six paths in `CONTAINERS`, is structurally meaningless in eForms, and was
    measured at zero occurrences.

    ``attributes`` keeps the element's own attributes in document order. They
    are not decoration: ``currencyID`` is what makes an amount a sum of money
    rather than a number, and `docs/data-model.md` promises amounts are stored
    "as published, with their currency". ``listName`` says which code list a
    coded value belongs to, and without it the value is ambiguous across lists.

    ``occurrence`` is the sibling index of every element along ``path``, from
    the record's container down. It is what keeps repeated blocks apart: a lot
    result carries several ``efac:ReceivedSubmissionsStatistics``, each with a
    code and a number, and two fields belong to the same block exactly when
    their occurrence agrees up to that block's depth. Without it the bid count
    and the statistic it counts cannot be paired, which would leave the
    single-bid classifier reading an unknown quantity.
    """

    path: str
    value: str
    empty: bool
    attributes: tuple[tuple[str, str], ...] = ()
    occurrence: tuple[int, ...] = ()

    def attribute(self, name: str) -> str | None:
        """The value of one attribute, or ``None`` if the element lacks it."""
        for key, value in self.attributes:
            if key == name:
                return value
        return None


@dataclass(frozen=True)
class Record:
    """One instance of a repeatable container, or the notice itself.

    ``ordinal`` is the container's position among all containers of its kind in
    the notice, counted in document order — not its position among its
    immediate siblings. The distinction matters when a notice carries more than
    one ``ext:UBLExtension``: organisations in the second continue the
    numbering rather than restarting. Document order within the notice is what
    makes ``(notice_id, kind, ordinal)`` a stable key; it deliberately says
    nothing about which parent a record hung from, because the model does not
    yet carry that either.
    """

    kind: str
    ordinal: int
    notice_id: str
    fields: tuple[Field, ...]

    def value(self, path: str) -> str | None:
        """The single value at ``path``, or ``None`` if there is no such field.

        Raises `AmbiguousField` when ``path`` occurs more than once — which is
        ordinary in eForms, not exotic: 97% of lot records and 73% of lot
        results in OJ S 157/2026 repeat at least one path. Returning the first
        of several silently would hand a caller one arbitrary value out of a
        set, and a classifier reading an arbitrary award criterion or bid count
        is the failure this project cannot afford. Use `values` where repeats
        are expected.

        ``None`` means the field is not here at all. A field that was present
        and blank is a `Field` with ``empty`` set and an empty ``value``, which
        is a different fact — see ADR-0006.
        """
        found = self.values(path)
        if not found:
            return None
        if len(found) > 1:
            raise AmbiguousField(
                f"{path!r} occurs {len(found)} times in this {self.kind} "
                f"record; use values() and pair them on Field.occurrence"
            )
        return found[0]

    def values(self, path: str) -> tuple[str, ...]:
        """Every value at ``path``, in document order."""
        return tuple(field.value for field in self.fields if field.path == path)

    def fields_at(self, path: str) -> tuple[Field, ...]:
        """Every field at ``path``, in document order, with their occurrences."""
        return tuple(field for field in self.fields if field.path == path)


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
