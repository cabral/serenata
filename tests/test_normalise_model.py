"""The executable model, checked against the document that is the contract.

`docs/data-model.md` is what a classifier author, a reviewer or a journalist
reads; `serenata/normalise/model.py` is what actually builds the columns. Two
descriptions of the same thing drift, and the drift is invisible in review
because nobody diffs a table against a dataclass. So the tests here derive their
assertions from the document, the way `tests/test_personal_data.py` derives its
own from `docs/personal-data.md`.

What is checked: every table exists in both, every column exists in both, and
where both give a source path the two paths are the same element. Constraint 2
gets its own check — a column mapping to a path the drop list rejects would be a
violation introduced in a dataclass, where no reader of the document would see
it.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from serenata.normalise.model import (
    ROLE_QUALIFIERS,
    ROLE_SOURCES,
    TABLES,
    Column,
    Kind,
    Table,
)
from serenata.parse.personal_data import is_dropped

MODEL_DOC = Path(__file__).resolve().parent.parent / "docs" / "data-model.md"
USAGE_DOC = Path(__file__).resolve().parent.parent / "docs" / "field-usage.md"

EXT = (
    "notice/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension"
)

#: A table row citing a column and the element path it reads.
_ROW = re.compile(r"^\|\s*`([\w_]+)`\s*\|\s*`([^`]+)`\s*\|", re.M)

#: A field-usage row: presence, countries, max occurrences per record, path.
_USAGE_ROW = re.compile(
    r"^\|\s*[\d.]+%\s*\|\s*\d+\s*\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|", re.M
)


def expand(path: str) -> str:
    """Resolve the document's shorthands into a literal element path."""
    path = path.replace("<org>", f"{EXT}/efac:Organizations/efac:Organization")
    return path.replace("<ext>", EXT)


def documented() -> dict[str, str]:
    """Every ``### `table``` section of the model document, keyed by table."""
    sections = re.split(r"^### `", MODEL_DOC.read_text(encoding="utf-8"), flags=re.M)
    return {
        section.split("`", 1)[0]: section.split("`", 1)[1].split("\n### ")[0]
        for section in sections[1:]
    }


def measured_cardinality() -> dict[str, int]:
    """path -> the most times it occurred inside one record, as measured."""
    text = USAGE_DOC.read_text(encoding="utf-8")
    return {path: int(times) for times, path in _USAGE_ROW.findall(text)}


def absolute(table: Table, path: str) -> str:
    """The document-style path for a column's container-relative one."""
    return f"{table.container}/{path}"


class TestTheDocumentAndTheCodeAgree:
    """A column exists in both places or in neither."""

    def test_every_table_has_a_section(self) -> None:
        missing = [table.name for table in TABLES if table.name not in documented()]
        assert not missing, (
            f"tables built with no section in data-model.md: {missing}. "
            "The document is the contract; a table nobody documented is a "
            "column set nobody agreed to."
        )

    def test_every_documented_table_is_built(self) -> None:
        built = {table.name for table in TABLES}
        extra = [name for name in documented() if name not in built]
        assert not extra, (
            f"data-model.md documents tables the model does not build: {extra}."
        )

    @pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
    def test_every_column_is_documented(self, table: Table) -> None:
        section = documented()[table.name]
        undocumented = [
            column.name
            for column in table.columns
            if not column.structural and f"`{column.name}`" not in section
        ]
        assert not undocumented, (
            f"{table.name} builds columns data-model.md never mentions: {undocumented}."
        )

    @pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
    def test_documented_columns_are_built(self, table: Table) -> None:
        # The role table's first column is a role value rather than a column
        # name; its own test below covers it.
        if table.name == "organisation_role":
            return
        built = {column.name for column in table.columns}
        missing = [
            name
            for name, _path in _ROW.findall(documented()[table.name])
            if name not in built
        ]
        assert not missing, (
            f"data-model.md gives {table.name} columns the model does not "
            f"build: {missing}."
        )

    @pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
    def test_source_paths_match(self, table: Table) -> None:
        """Where both name a source element, it is the same element."""
        for name, path in _ROW.findall(documented()[table.name]):
            column = next((c for c in table.columns if c.name == name), None)
            # A computed column's source is described in prose — the notice's
            # root element, a block read from two records — and the document
            # is where that description belongs.
            if column is None or column.kind is Kind.COMPUTED:
                continue
            assert absolute(table, column.path) == expand(path), (
                f"{table.name}.{name} reads {absolute(table, column.path)!r} "
                f"but data-model.md documents {expand(path)!r}."
            )

    def test_the_path_check_can_actually_fail(self) -> None:
        # Passing vacuously is the failure mode of a test that parses a
        # document: prove it matched rows for a table with plain columns.
        notice = next(table for table in TABLES if table.name == "notice")
        rows = _ROW.findall(documented()["notice"])
        assert len(rows) > 10, f"only parsed {len(rows)} rows for notice"
        assert absolute(notice, notice.column("issue_date").path) == (
            "notice/cbc:IssueDate"
        )


class TestTheRoleTable:
    """Roles are edges, and each one's reference path is documented."""

    def test_every_role_is_documented(self) -> None:
        section = documented()["organisation_role"]
        for role, (_kind, path) in ROLE_SOURCES.items():
            assert f"`{role}`" in section, f"role {role} is undocumented"
            assert expand_in(section, path), (
                f"the reference path for {role} is not in data-model.md: {path}"
            )

    def test_every_qualifier_is_documented(self) -> None:
        section = documented()["organisation_role"]
        for qualifiers in ROLE_QUALIFIERS.values():
            for name, _path in qualifiers:
                assert f"`{name}`" in section, f"{name} is undocumented"

    def test_qualifiers_belong_to_a_role_that_exists(self) -> None:
        assert set(ROLE_QUALIFIERS) <= set(ROLE_SOURCES)


def expand_in(section: str, relative: str) -> bool:
    """Whether ``section`` cites a path ending in this record-relative one."""
    return any(
        expand(cited).endswith(relative)
        for cited in re.findall(r"`((?:notice/|<ext>/|<org>/)[^`]+)`", section)
    )


class TestTheModelObeysTheDropList:
    """Constraint 2: person-carrying fields get no column, not a nullable one."""

    def test_no_column_reads_a_dropped_path(self) -> None:
        offending = [
            f"{table.name}.{column.name}"
            for table in TABLES
            for column in table.columns
            if column.path and is_dropped(absolute(table, column.path))
        ]
        assert not offending, (
            f"columns reading paths the drop list rejects: {offending}. "
            "Fields that can name a natural person get no column at all "
            "(CLAUDE.md constraint 2, docs/personal-data.md)."
        )

    def test_no_role_reads_a_dropped_path(self) -> None:
        offending = [
            role for role, (_kind, path) in ROLE_SOURCES.items() if is_dropped(path)
        ]
        assert not offending, f"roles reading dropped paths: {offending}"


class TestCompanionColumns:
    """ADR-0006 and ADR-0007: what sits beside a value, and where."""

    @pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
    def test_every_non_structural_column_has_a_status(self, table: Table) -> None:
        names = table.field_names()
        missing = [
            column.name
            for column in table.columns
            if not column.structural and f"{column.name}_status" not in names
        ]
        assert not missing, (
            f"{table.name} has columns without a status companion: {missing}. "
            "Absence is recorded beside the value, uniformly (ADR-0006)."
        )

    @pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
    def test_structural_columns_have_no_status(self, table: Table) -> None:
        names = table.field_names()
        extra = [
            column.name
            for column in table.columns
            if column.structural and f"{column.name}_status" in names
        ]
        assert not extra, (
            f"{table.name} gives a status to structural columns: {extra}. "
            "A key is how a row is addressed, not something a notice provided."
        )

    def test_amount_columns_carry_a_currency(self) -> None:
        amounts = [
            f"{table.name}.{column.name}"
            for table in TABLES
            for column in table.columns
            if column.name.endswith("_amount") and not column.currency
        ]
        assert not amounts, (
            f"amount columns without a currency companion: {amounts}. An "
            "amount without one is a number, not a sum of money."
        )

    def test_every_column_reading_an_amount_carries_a_currency(self) -> None:
        # The check above matches on the column's *name*, so a money column
        # called something else would slip past it. This matches on the source
        # element instead: eForms names every monetary element `…Amount`, so a
        # column reading one and carrying no currency is the same defect under
        # a different name.
        missing = [
            f"{table.name}.{column.name}"
            for table in TABLES
            for column in table.columns
            if column.path.endswith("Amount") and not column.currency
        ]
        assert not missing, (
            f"columns reading a monetary element without a currency companion: "
            f"{missing}"
        )

    def test_that_check_can_actually_fail(self) -> None:
        # Both currency checks are only worth having if a money column without
        # a companion is expressible.
        offender = Column("some_value", "cbc:SomethingAmount")
        assert offender.path.endswith("Amount")
        assert not offender.currency
        assert "some_value_currency" not in offender.companions

    def test_set_columns_are_named_plurally(self) -> None:
        singular = [
            f"{table.name}.{column.name}"
            for table in TABLES
            for column in table.columns
            if column.kind is Kind.SET and not column.name.endswith("s")
        ]
        assert not singular, (
            f"set columns with singular names: {singular}. A column holding "
            "every value says so in its name (ADR-0007)."
        )


class TestKeys:
    """Every table is keyed on the identifier that is actually unique."""

    @pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
    def test_the_key_leads_with_the_publication(self, table: Table) -> None:
        assert table.key[0] == "source_publication_id", (
            f"{table.name} is keyed on {table.key[0]!r}. The notice UUID is "
            "not unique — two repeat within one publication day — so the "
            "publication is the key."
        )

    @pytest.mark.parametrize("table", TABLES, ids=lambda t: t.name)
    def test_every_key_column_exists(self, table: Table) -> None:
        names = table.field_names()
        missing = [name for name in table.key if name not in names]
        assert not missing, f"{table.name} is keyed on columns it lacks: {missing}"


class TestColumnsMatchMeasuredCardinality:
    """A column's shape is a claim about the data, and the data was measured.

    This is the gate that did not exist when the model was written, and its
    absence is why the model shipped saying a lot carries one contracting-system
    code when 8,028 of 8,624 lots carry two. `docs/field-usage.md` now reports
    how many times each path occurs inside a single record, so the claim is
    checkable rather than assumed.

    Only paths this project has actually seen are checked. A column whose path
    appears in no surveyed notice is a different problem, and
    `tests/test_data_model.py` is where it is caught.
    """

    def columns_with_measurements(self, kind: Kind) -> list[tuple[str, str, int]]:
        measured = measured_cardinality()
        return [
            (f"{table.name}.{column.name}", absolute(table, column.path), times)
            for table in TABLES
            for column in table.columns
            if column.kind is kind
            and column.path
            and (times := measured.get(absolute(table, column.path))) is not None
        ]

    def test_scalar_columns_read_paths_that_never_repeat(self) -> None:
        repeating = [
            f"{name} reads {path} (seen {times} times in one record)"
            for name, path, times in self.columns_with_measurements(Kind.SCALAR)
            if times > 1
        ]
        assert not repeating, (
            f"columns holding one value whose path repeats: {repeating}. The "
            "model has to carry the set, name which occurrence it means, or "
            "become a table of its own (ADR-0007). Storing one of several is "
            "storing an arbitrary one."
        )

    def test_set_columns_read_paths_that_do_repeat(self) -> None:
        singular = [
            f"{name} reads {path} (never seen more than {times} in one record)"
            for name, path, times in self.columns_with_measurements(Kind.SET)
            if times <= 1
        ]
        assert not singular, (
            f"set columns whose path never repeats: {singular}. A list column "
            "for a path that holds one value costs every reader an unnest for "
            "nothing; either the measurement moved or the column should be "
            "scalar."
        )

    def test_enough_columns_were_measured(self) -> None:
        # The gate is worthless if the report stopped carrying the column and
        # every lookup started returning nothing.
        scalars = self.columns_with_measurements(Kind.SCALAR)
        sets = self.columns_with_measurements(Kind.SET)
        assert len(scalars) > 40, f"only matched {len(scalars)} scalar columns"
        assert len(sets) >= 5, f"only matched {len(sets)} set columns"
        assert len(measured_cardinality()) > 400
