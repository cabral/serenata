"""Turn one notice's parsed records into the model's rows.

Pure and offline: rows in, rows out, no clock and no filesystem. What arrives is
a `ParsedNotice` — values keyed by the element path they came from, grouped by
the repeatable container they belong to — and what leaves is one dictionary per
row of `serenata.normalise.model`.

Three things here are not mechanical, and each is a decision the model records
rather than a habit of this code.

**A repeated path is never resolved by picking one.** A `SET` column carries the
whole set; a `TEXT` column takes the notice's own language and says which it
took; and a `SCALAR` column meeting a repeat raises `RepeatedValue` rather than
choosing. That last case did not occur once in the 3,190 notices of OJ S
157/2026 — the columns where repetition was measured are `SET` or `TEXT` — so
raising reports model drift rather than rejecting ordinary data.

**Blocks pair on `Field.occurrence`.** A statistic's code and its number, a
location's country and its NUTS code, a buyer and its type: each pair sits in a
repeatable block, and two fields belong to the same block exactly when their
occurrence agrees down to that block's depth.

**Absence is recorded, never collapsed** (ADR-0006). Every non-structural
column carries a status beside it, and a value is only `present` when an
element carried one.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

from serenata.normalise.model import (
    FIELD_PRIVACY_TABLE,
    LOCATION_BLOCK,
    LOT_RESULT_STATISTIC_TABLE,
    ORGANISATION_ROLE_TABLE,
    PRIVACY_BLOCK,
    REALIZED_LOCATION_TABLE,
    ROLE_QUALIFIERS,
    ROLE_SOURCES,
    STATISTIC_BLOCKS,
    STATISTIC_COLUMNS,
    TABLES,
    Column,
    Kind,
    Status,
    Table,
)
from serenata.normalise.privacy import BLOCK_TARGETS, RECORD_TARGETS, Target, covers
from serenata.parse.records import Field, ParsedNotice, Record

#: Where the citable TED reference lives, relative to the notice record. Every
#: row carries it so a published flag can link to the notice it came from.
PUBLICATION_ID = (
    "ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension"
    "/efac:Publication/efbc:NoticePublicationID"
)

#: And the publication date the dataset is partitioned by. Taken from the
#: notice, never from the run clock (constraint 4).
PUBLICATION_DATE = PUBLICATION_ID.rsplit("/", 1)[0] + "/efbc:PublicationDate"

#: The partition a notice lands in when its publication date is missing or not
#: a year. Notices are partitioned so they can be found; one that cannot say
#: when it was published is still archived, and hiding it would be worse than
#: naming the gap.
UNKNOWN_YEAR = "unknown"

#: Which table a record kind's rows are scoped to, where a row names its scope.
SCOPE_TABLE = {
    "notice": "notice",
    "lot": "lot",
    "organisation": "organisation",
    "lot_result": "lot_result",
    "lot_tender": "lot_tender",
    "settled_contract": "settled_contract",
    "tendering_party": "tendering_party",
}

#: Where a privacy block names the field it withholds, relative to the block.
FIELD_IDENTIFIER = "efbc:FieldIdentifierCode"

#: Rows = one dictionary per row, keyed by table name.
Rows = dict[str, list[dict[str, Any]]]


class RepeatedValue(LookupError):
    """A column modelled as one value met a record carrying several.

    Either the notice is unusual or the model is wrong about that path, and
    both are worth knowing. What must not happen is the third option — quietly
    storing one of them — which is why this is raised rather than resolved.
    """


def _segments(path: str) -> list[str]:
    return path.split("/") if path else []


def _common_depth(left: str, right: str) -> int:
    """How many leading path segments two paths share."""
    depth = 0
    for one, other in zip(_segments(left), _segments(right), strict=False):
        if one != other:
            break
        depth += 1
    return depth


def _status_of(fields: Sequence[Field]) -> Status:
    if not fields:
        return Status.ABSENT
    if all(item.empty for item in fields):
        return Status.EMPTY
    return Status.PRESENT


def _blocks(record: Record, prefix: str) -> Iterator[tuple[int, tuple[Field, ...]]]:
    """Group a record's fields into the repeatable block ``prefix`` names.

    Yields ``(block ordinal, fields)`` in document order, the ordinal being the
    block's position among blocks of that kind in this record. Fields belong to
    the same block when their occurrence agrees down to the block's depth,
    which is what keeps a statistic's code with its own number rather than the
    next block's.
    """
    depth = len(_segments(prefix))
    grouped: dict[tuple[int, ...], list[Field]] = {}
    for item in record.fields:
        if not item.path.startswith(f"{prefix}/"):
            continue
        # Insertion order is document order: parse appends fields as elements
        # close, and dictionaries preserve that.
        grouped.setdefault(item.occurrence[:depth], []).append(item)
    for ordinal, fields in enumerate(grouped.values()):
        yield ordinal, tuple(fields)


def _relative(fields: Sequence[Field], prefix: str) -> dict[str, Field]:
    """A block's fields keyed by their path below ``prefix``.

    A path repeating inside one block would overwrite here. That is a model
    question rather than a silent loss: the blocks this is used for —
    statistics, locations, privacy — were measured carrying one of each.
    """
    cut = len(prefix) + 1
    return {item.path[cut:]: item for item in fields}


def _read(record: Record, column: Column, language: str | None) -> dict[str, Any]:
    """One column's value and its companions, read from ``record``."""
    fields = record.fields_at(column.path)
    status = _status_of(fields)
    cells: dict[str, Any] = {f"{column.name}_status": status.value}

    if column.kind is Kind.SET:
        cells[column.name] = [item.value for item in fields]
        return cells

    chosen: Field | None = None
    if column.kind is Kind.TEXT and len(fields) > 1:
        # Free text is published once per language — 77 notices carry two
        # titles, always in distinct languages, and in every one of the 37,498
        # measured the notice's own language is among them. Taking that one
        # keeps the choice a rule rather than a coin toss; the companion
        # records which language was taken, including when the fallback runs.
        chosen = next(
            (item for item in fields if item.attribute("languageID") == language),
            fields[0],
        )
    elif len(fields) > 1:
        raise RepeatedValue(
            f"{column.name} reads {column.path!r}, which occurs {len(fields)} "
            f"times in this {record.kind} record. A column that holds one value "
            "may not pick one of several; the model has to say which it means "
            "or carry the set (docs/data-model.md, ADR-0007)."
        )
    elif fields:
        chosen = fields[0]

    cells[column.name] = chosen.value if chosen is not None else None
    if column.currency:
        cells[f"{column.name}_currency"] = (
            chosen.attribute("currencyID") if chosen is not None else None
        )
    if column.kind is Kind.TEXT:
        cells[f"{column.name}_language"] = (
            chosen.attribute("languageID") if chosen is not None else None
        )
    return cells


def _computed(column: Column, value: Any, status: Status) -> dict[str, Any]:
    """A column the builder fills rather than reading from a path."""
    return {column.name: value, f"{column.name}_status": status.value}


def _identity_of(notice: ParsedNotice) -> dict[str, Any]:
    """What every row carries, whichever record it was built from."""
    return {
        "source_notice_id": notice.notice_id,
        "source_publication_id": _publication_id(notice),
        "publication_year": publication_year(notice),
    }


def _notice_record(notice: ParsedNotice) -> Record:
    return notice.of_kind("notice")[0]


def _publication_id(notice: ParsedNotice) -> str | None:
    return _notice_record(notice).value(PUBLICATION_ID)


def publication_year(notice: ParsedNotice) -> str:
    """The partition this notice's rows land in, from its publication date."""
    published = _notice_record(notice).value(PUBLICATION_DATE) or ""
    year = published[:4]
    return year if year.isdigit() else UNKNOWN_YEAR


def _notice_language(notice: ParsedNotice) -> str | None:
    return _notice_record(notice).value("cbc:NoticeLanguageCode")


def _record_rows(
    table: Table, notice: ParsedNotice, language: str | None
) -> Iterator[dict[str, Any]]:
    """Rows for a table whose every row is one parse record."""
    for record in notice.of_kind(table.record):
        withheld = {
            target.column
            for target in _withheld_in(record)
            if target.table == table.name
        }
        row: dict[str, Any] = {}
        for column in table.columns:
            if column.structural:
                continue
            if column.kind is Kind.COMPUTED:
                if column.name == "root_element":
                    row |= _computed(column, notice.root_element, Status.PRESENT)
                continue
            row |= _read(record, column, language)
            if column.name in withheld:
                row[f"{column.name}_status"] = Status.WITHHELD.value
        yield _identity_of(notice) | {"ordinal": record.ordinal} | row


def _role_rows(notice: ParsedNotice) -> list[dict[str, Any]]:
    """One row per organisation reference: which organisation played which role.

    A role is an edge because an organisation is a buyer in one notice and a
    supplier in another. The reference and its qualifiers are paired on
    `Field.occurrence` down to the block they share, so the largest measured
    notice — 163 buyers — keeps each buyer's type with that buyer.

    One row per *reference*, not per distinct organisation: six notices in
    OJ S 157/2026 name the same organisation as buyer in two contracting-party
    blocks carrying different type codes. Collapsing those would have to choose
    one of the two descriptions, so both are kept and ``block_ordinal`` tells
    them apart.
    """
    rows: list[dict[str, Any]] = []
    columns = {column.name: column for column in ORGANISATION_ROLE_TABLE.columns}

    for role, (kind, path) in ROLE_SOURCES.items():
        qualifiers = ROLE_QUALIFIERS.get(role, ())
        for record in notice.of_kind(kind):
            for block_ordinal, reference in enumerate(record.fields_at(path)):
                row = _identity_of(notice) | {
                    "role": role,
                    "scope_table": SCOPE_TABLE[kind],
                    "scope_ordinal": record.ordinal,
                    "block_ordinal": block_ordinal,
                }
                row |= _computed(
                    columns["org_ref"],
                    reference.value,
                    Status.EMPTY if reference.empty else Status.PRESENT,
                )
                for name, qualifier_path in qualifiers:
                    depth = _common_depth(path, qualifier_path)
                    block = reference.occurrence[:depth]
                    found = [
                        item
                        for item in record.fields_at(qualifier_path)
                        if item.occurrence[:depth] == block
                    ]
                    row |= _computed(
                        columns[name],
                        found[0].value if found else None,
                        _status_of(found),
                    )
                for name in ("buyer_type_code", "buyer_activity_code", "is_group_lead"):
                    if name not in row:
                        # A qualifier belongs to one role; on every other role's
                        # rows the column is not merely empty, it does not
                        # apply. Recorded `absent` until the notice-subtype
                        # rules make `not_applicable` derivable (ADR-0006).
                        row |= _computed(columns[name], None, Status.ABSENT)
                rows.append(row)
    return rows


def _location_rows(notice: ParsedNotice) -> Iterator[dict[str, Any]]:
    """One row per place of performance, for the notice and for each lot.

    `cac:RealizedLocation` repeats — a lot was measured naming 59 country codes
    — so country and NUTS code are rows here rather than columns that could
    hold one location each, and each row keeps the pairing the block gives.
    """
    columns = {column.name: column for column in REALIZED_LOCATION_TABLE.columns}
    sources = (("procedure", "notice"), ("lot", "lot"))
    paths = {
        "country_code": "cac:Address/cac:Country/cbc:IdentificationCode",
        "nuts_code": "cac:Address/cbc:CountrySubentityCode",
    }
    for scope_table, kind in sources:
        for record in notice.of_kind(kind):
            for ordinal, fields in _blocks(record, LOCATION_BLOCK):
                inside = _relative(fields, LOCATION_BLOCK)
                row = _identity_of(notice) | {
                    "scope_table": scope_table,
                    "scope_ordinal": record.ordinal,
                    "block_ordinal": ordinal,
                }
                for name, path in paths.items():
                    found = inside.get(path)
                    row |= _computed(
                        columns[name],
                        found.value if found is not None else None,
                        _status_of([found] if found is not None else []),
                    )
                yield row


def _withheld_in_block(fields: Sequence[Field], block: str) -> set[str]:
    """Which columns of a statistics block its own privacy blocks withhold.

    Scoped by containment: a privacy block *inside* a statistics block is about
    that block, which is what keeps one withheld count from marking the other
    eleven a lot result can carry.

    Which of the block's two columns it names is the code's job to say, and
    `rec-sub-cou` (the number) and `rec-sub-typ` (the code) say it. Where a code
    is missing or `serenata.normalise.privacy` cannot place it, both columns are
    marked, which is the conservative direction and was this function's only
    behaviour before the SDK mapping existed. Both blocks measured withheld in
    OJ S 157/2026 carry both codes, so the mapping confirms what containment
    already said there rather than changing it.
    """
    cut = len(block) + 1
    inside = [item.path[cut:] for item in fields]
    if not any(path.startswith(f"{PRIVACY_BLOCK}/") for path in inside):
        return set()
    codes = {
        item.value
        for item in fields
        if item.path[cut:] == f"{PRIVACY_BLOCK}/{FIELD_IDENTIFIER}"
    }
    if codes and all(code in BLOCK_TARGETS for code in codes):
        return {target.column for code in codes for target in BLOCK_TARGETS[code]}
    return {name for name, _path in STATISTIC_COLUMNS}


def _statistic_rows(notice: ParsedNotice) -> Iterator[dict[str, Any]]:
    """One row per statistics block of a lot result.

    The bid count lives here, and so does the reason this table exists: a
    publisher may withhold it, and a withheld count is published as the code
    ``unpublished`` with the number ``-1``. Two blocks in OJ S 157/2026 are
    exactly that. A classifier reading the number without the status would read
    a lawful deferral as a negative bid count.
    """
    columns = {column.name: column for column in LOT_RESULT_STATISTIC_TABLE.columns}
    for record in notice.of_kind("lot_result"):
        for block, kind in STATISTIC_BLOCKS.items():
            for ordinal, fields in _blocks(record, block):
                inside = _relative(fields, block)
                withheld = _withheld_in_block(fields, block)
                row = _identity_of(notice) | {
                    "lot_result_ordinal": record.ordinal,
                    "statistic_kind": kind,
                    "block_ordinal": ordinal,
                }
                for name, path in STATISTIC_COLUMNS:
                    found = inside.get(path)
                    status = _status_of([found] if found is not None else [])
                    if name in withheld:
                        status = Status.WITHHELD
                    row |= _computed(
                        columns[name],
                        found.value if found is not None else None,
                        status,
                    )
                yield row


def _privacy_blocks(record: Record) -> Iterator[tuple[str, int, dict[str, Field]]]:
    """Every `efac:FieldsPrivacy` block in a record, with where it sits.

    Yields ``(scope path, block ordinal, fields below the block)``. The scope
    path is relative to the record and is empty when the block qualifies the
    record itself; it is what says a block inside `efac:DecisionReason` is about
    the decision reason and not about the whole lot result.
    """
    scopes: dict[str, None] = {}
    for item in record.fields:
        head, marker, _ = item.path.partition(PRIVACY_BLOCK + "/")
        if marker:
            scopes[head.rstrip("/")] = None
    for scope_path in scopes:
        prefix = f"{scope_path}/{PRIVACY_BLOCK}" if scope_path else PRIVACY_BLOCK
        for ordinal, fields in _blocks(record, prefix):
            yield scope_path, ordinal, _relative(fields, prefix)


def _withheld_in(record: Record) -> set[Target]:
    """The columns this record's privacy blocks mark non-public.

    A publisher withholds a field by publishing a placeholder in it — an amount
    as ``-1`` — and naming it by code here. `serenata.normalise.privacy` turns
    the code into a column, from the eForms SDK's own field definitions, and
    refuses the codes it cannot place rather than marking something adjacent.
    The value stays exactly as published; only the status changes (ADR-0006).
    """
    found: set[Target] = set()
    for scope_path, _ordinal, inside in _privacy_blocks(record):
        code = inside.get(FIELD_IDENTIFIER)
        if code is None:
            continue
        for target in RECORD_TARGETS.get(code.value, ()):
            if covers(scope_path, target):
                found.add(target)
    return found


def _privacy_rows(notice: ParsedNotice) -> Iterator[dict[str, Any]]:
    """One row per field a publisher marked withheld or deferred.

    The block is scoped to the element it sits inside, which is finer than the
    record: measured inside `efac:ReceivedSubmissionsStatistics`,
    `efac:FrameworkAgreementValues` and `efac:NoticeResult`, among others. The
    row keeps that path so the scope is not lost.
    """
    columns = {column.name: column for column in FIELD_PRIVACY_TABLE.columns}
    for record in notice.records:
        for scope_path, ordinal, inside in _privacy_blocks(record):
            row = _identity_of(notice) | {
                "scope_table": SCOPE_TABLE[record.kind],
                "scope_ordinal": record.ordinal,
                "scope_path": scope_path,
                "block_ordinal": ordinal,
            }
            for name, path in (
                ("field_identifier_code", FIELD_IDENTIFIER),
                ("reason_code", "cbc:ReasonCode"),
                ("publication_date", "efbc:PublicationDate"),
            ):
                found = inside.get(path)
                row |= _computed(
                    columns[name],
                    found.value if found is not None else None,
                    _status_of([found] if found is not None else []),
                )
            yield row


#: Tables whose rows are a block inside a record rather than a record, and so
#: are built by the functions above rather than column by column.
_BUILT_FROM_BLOCKS = frozenset(
    {
        ORGANISATION_ROLE_TABLE.name,
        REALIZED_LOCATION_TABLE.name,
        LOT_RESULT_STATISTIC_TABLE.name,
        FIELD_PRIVACY_TABLE.name,
    }
)


def empty_rows() -> Rows:
    """One empty list per table, so every table is written even with no rows."""
    return {table.name: [] for table in TABLES}


def notice_rows(notice: ParsedNotice) -> Rows:
    """Every row one notice contributes, keyed by table.

    Raises `RepeatedValue` if a column modelled as holding one value meets a
    record that repeats its path.
    """
    language = _notice_language(notice)
    rows = empty_rows()
    for table in TABLES:
        if table.record and table.name not in _BUILT_FROM_BLOCKS:
            rows[table.name] = list(_record_rows(table, notice, language))
    rows[ORGANISATION_ROLE_TABLE.name] = _role_rows(notice)
    rows[REALIZED_LOCATION_TABLE.name] = list(_location_rows(notice))
    rows[LOT_RESULT_STATISTIC_TABLE.name] = list(_statistic_rows(notice))
    rows[FIELD_PRIVACY_TABLE.name] = list(_privacy_rows(notice))
    return rows
