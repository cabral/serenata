"""Which column a publisher withheld, from the code they published.

eForms does not omit a withheld value — it **publishes a placeholder** and says
elsewhere that the field is non-public. An amount arrives as ``-1``, a bid count
as the code ``unpublished`` with the number ``-1``. Measured in OJ S 157/2026:
74 tender payable amounts, 44 notice total amounts, 11 highest and 11 lowest
tender amounts, among 215 privacy blocks in all. A classifier that read those
as numbers would treat a lawful deferral as a negative sum of money, and the
single-bid classifier would read a withheld count as a low one.

`efac:FieldsPrivacy` names its target with a code — ``win-ten-val``,
``rec-sub-cou`` — and the code alone does not say which element it means. This
module supplies that, by joining `sdk_privacy.PRIVACY_FIELDS`, which is the
eForms SDK's own answer, onto the columns of `serenata.normalise.model`. The
result is what lets `rows.py` mark a column `withheld` rather than `present`
(ADR-0006, ADR-0008).

**It refuses more than it accepts, and the refusals are the point.** Two things
make a code unusable here, and guessing past either would mark the wrong column
non-public:

- **A predicate that mattered.** The SDK identifies a field by an XPath that may
  carry one; ``pro-acc`` and ``dir-awa-jus`` are the same element, told apart
  only by ``@listName``. This project's paths carry no predicates (ADR-0005), so
  where stripping one merges two SDK fields the code is refused. The generator
  records which fields collide, so this is read from the SDK rather than
  guessed.
- **No column.** Most withholdable fields are not in this model — the notice's
  total amount and the framework-agreement values among them. A code naming one
  has nothing to mark.

Eleven of the SDK's 47 codes survive both tests. `UNUSABLE` keeps the rest with
the reason, so `docs/data-model.md` can state the coverage instead of implying
it is complete.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import NamedTuple

from serenata.eforms import ROOT
from serenata.normalise.model import (
    LOT_RESULT_STATISTIC_TABLE,
    STATISTIC_BLOCKS,
    STATISTIC_COLUMNS,
    TABLES,
)
from serenata.normalise.sdk_privacy import PRIVACY_FIELDS
from serenata.parse.records import CONTAINERS

#: An XPath predicate — `cac:Foo[cbc:Bar/@listName='x']/cbc:Baz`. Stripped to
#: reach this project's path vocabulary; where that loses a distinction the SDK
#: was making, `PrivacyField.shares_path_with` says so and the code is refused.
PREDICATE = re.compile(r"\[[^\]]*\]")


class Target(NamedTuple):
    """A column a privacy code names, and the element it reads."""

    table: str
    column: str
    #: The column's source path, relative to the record. `rows.py` checks the
    #: privacy block sits at or above it before marking anything.
    path: str


def _stripped(xpath: str) -> str:
    """`/*/a/b[pred]/c` in this project's path vocabulary: `notice/a/b/c`."""
    return ROOT + PREDICATE.sub("", xpath)[2:]


def _locate(absolute: str) -> tuple[str, str]:
    """Which record kind an absolute path falls in, and its path within it."""
    container = max(
        (path for path in CONTAINERS if absolute.startswith(f"{path}/")),
        key=len,
        default="",
    )
    if container:
        return CONTAINERS[container], absolute[len(container) + 1 :]
    return "notice", absolute[len(ROOT) + 1 :]


def _record_columns() -> dict[tuple[str, str], list[Target]]:
    """(record kind, path) -> the columns reading it, for record-built tables."""
    found: dict[tuple[str, str], list[Target]] = defaultdict(list)
    for table in TABLES:
        if not table.record:
            continue
        for column in table.columns:
            if not column.structural and column.path:
                found[table.record, column.path].append(
                    Target(table.name, column.name, column.path)
                )
    return dict(found)


def _block_columns() -> dict[tuple[str, str], list[Target]]:
    """The same, for columns that are a block within a record rather than a row.

    Only the statistics blocks: no privacy code in the SDK names a place of
    performance, so `realized_location` needs nothing here.
    """
    return {
        ("lot_result", f"{block}/{path}"): [
            Target(LOT_RESULT_STATISTIC_TABLE.name, name, path)
        ]
        for block in STATISTIC_BLOCKS
        for name, path in STATISTIC_COLUMNS
    }


def _resolve() -> tuple[
    dict[str, tuple[Target, ...]], dict[str, tuple[Target, ...]], dict[str, str]
]:
    """Join the SDK's withheld fields onto this model's columns."""
    by_code: dict[str, list[tuple[str, str, tuple[str, ...]]]] = defaultdict(list)
    for field in PRIVACY_FIELDS:
        by_code[field.code].append(
            (field.field_id, field.xpath, field.shares_path_with)
        )

    records, blocks = _record_columns(), _block_columns()
    record_targets: dict[str, tuple[Target, ...]] = {}
    block_targets: dict[str, tuple[Target, ...]] = {}
    unusable: dict[str, str] = {}

    for code, fields in sorted(by_code.items()):
        shared = sorted({other for *_, sharers in fields for other in sharers})
        if shared:
            unusable[code] = (
                "the SDK tells its field apart from "
                f"{', '.join(shared)} by an XPath predicate, which this "
                "model's paths do not carry (ADR-0005)"
            )
            continue

        where = {_locate(_stripped(xpath)) for _, xpath, _ in fields}
        in_records = [records[key] for key in where if key in records]
        in_blocks = [blocks[key] for key in where if key in blocks]
        if len(in_records) + len(in_blocks) != len(where):
            unusable[code] = "no column in this model reads " + ", ".join(
                sorted(f"{kind}/{path}" for kind, path in where)
            )
            continue
        if in_records and in_blocks:
            unusable[code] = "its fields land in both a record and a block table"
            continue

        found = tuple(
            sorted({target for group in in_records + in_blocks for target in group})
        )
        if in_blocks:
            block_targets[code] = found
        else:
            record_targets[code] = found

    return record_targets, block_targets, unusable


#: Code -> the columns of a record-built table it withholds.
#: Code -> the columns of a block table it withholds, scoped by the block the
#: privacy element sits in rather than by the record.
#: Code -> why this model cannot act on it.
RECORD_TARGETS, BLOCK_TARGETS, UNUSABLE = _resolve()

#: Every code the SDK defines, whether or not it resolves here. A code outside
#: this set is one the vendored table has never heard of, which is a different
#: fact from one it knows and cannot place.
KNOWN_CODES = frozenset(RECORD_TARGETS) | frozenset(BLOCK_TARGETS) | frozenset(UNUSABLE)


def covers(scope_path: str, target: Target) -> bool:
    """Whether a privacy block at ``scope_path`` can be naming ``target``.

    A block sits at or above the field it withholds — inside
    `efac:DecisionReason` for the decision reason code, at the record root for a
    tender's payable amount. A block somewhere else names something this row
    does not hold, and marking on the code alone would withhold the wrong
    column.
    """
    if not scope_path:
        return True
    return target.path == scope_path or target.path.startswith(f"{scope_path}/")
