# SPDX-License-Identifier: AGPL-3.0-only
"""Byte-identical Parquet, which is constraint 4 made checkable.

A rerun is the only thing that can establish determinism, so these tests write
twice and compare bytes rather than asserting that the settings are set.

The awkward case is nulls in a sort key. Registry data is full of them by
design, "not provided" and "not applicable" being different facts, and
`None < "ROUSSEAU"` raises in Python. A sort that crashed on the first missing
role date would be discovered in session 3, on real data, at the worst moment.
"""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from crony_eu.parquet import ROW_GROUP_SIZE, WRITER, sort_key, write

SCHEMA = pa.schema(
    [
        pa.field("commune_code", pa.string()),
        pa.field("supplier_siren", pa.string()),
        pa.field("amount_eur", pa.decimal128(18, 2)),
        pa.field("role_end", pa.string()),
    ]
)

KEY = ("commune_code", "supplier_siren")


def rows() -> list[dict[str, object]]:
    """Obviously synthetic: impossible commune codes, reserved SIREN range."""
    from decimal import Decimal

    return [
        {
            "commune_code": "99002",
            "supplier_siren": "900000002",
            "amount_eur": Decimal("1200.00"),
            "role_end": None,
        },
        {
            "commune_code": "99001",
            "supplier_siren": "900000001",
            "amount_eur": Decimal("48200.50"),
            "role_end": "2024-03",
        },
        {
            "commune_code": "99001",
            "supplier_siren": "900000003",
            "amount_eur": Decimal("75.00"),
            "role_end": None,
        },
    ]


class TestSortKey:
    def test_nulls_do_not_raise(self) -> None:
        assert sort_key({"a": None}, ["a"]) < sort_key({"a": "x"}, ["a"])

    def test_nulls_group_together_and_come_first(self) -> None:
        keys = sorted(
            sort_key(row, ["a"]) for row in ({"a": "b"}, {"a": None}, {"a": "a"})
        )
        assert keys[0] == ((0, ""),), "a null sorted somewhere other than first"

    def test_a_missing_column_is_the_same_as_a_null(self) -> None:
        assert sort_key({}, ["a"]) == sort_key({"a": None}, ["a"])

    def test_mixed_types_in_one_column_do_not_raise(self) -> None:
        # DuckDB and a CSV reader disagree about whether a numeric-looking code
        # is an int; the sort must not be where that argument surfaces.
        assert sorted(sort_key(row, ["a"]) for row in ({"a": 2}, {"a": "10"}))


class TestWrite:
    def test_it_writes_every_row(self, tmp_path: Path) -> None:
        count = write(rows(), SCHEMA, tmp_path / "t.parquet", KEY)
        assert count == 3
        assert pq.read_table(tmp_path / "t.parquet").num_rows == 3

    def test_it_sorts_by_the_declared_key(self, tmp_path: Path) -> None:
        write(rows(), SCHEMA, tmp_path / "t.parquet", KEY)

        table = pq.read_table(tmp_path / "t.parquet")
        assert table.column("commune_code").to_pylist() == ["99001", "99001", "99002"]
        assert table.column("supplier_siren").to_pylist()[:2] == [
            "900000001",
            "900000003",
        ]

    def test_input_order_does_not_change_the_bytes(self, tmp_path: Path) -> None:
        # The real claim. Rows arrive from a DuckDB scan whose order is not
        # promised, so sorting before writing is what makes a rerun identical.
        write(rows(), SCHEMA, tmp_path / "a.parquet", KEY)
        write(list(reversed(rows())), SCHEMA, tmp_path / "b.parquet", KEY)

        assert (tmp_path / "a.parquet").read_bytes() == (
            tmp_path / "b.parquet"
        ).read_bytes()

    def test_a_rerun_is_byte_identical(self, tmp_path: Path) -> None:
        write(rows(), SCHEMA, tmp_path / "a.parquet", KEY)
        write(rows(), SCHEMA, tmp_path / "b.parquet", KEY)

        assert (tmp_path / "a.parquet").read_bytes() == (
            tmp_path / "b.parquet"
        ).read_bytes()

    def test_the_check_can_actually_fail(self, tmp_path: Path) -> None:
        # Two files compared byte for byte would also be equal if `write` wrote
        # nothing at all, or if every row were dropped.
        changed = rows()
        changed[0]["commune_code"] = "99009"
        write(rows(), SCHEMA, tmp_path / "a.parquet", KEY)
        write(changed, SCHEMA, tmp_path / "b.parquet", KEY)

        assert (tmp_path / "a.parquet").read_bytes() != (
            tmp_path / "b.parquet"
        ).read_bytes()

    def test_the_schema_is_declared_not_inferred(self, tmp_path: Path) -> None:
        # A slice where every `role_end` is null must still produce a string
        # column, or two slices of the same table would have different schemas
        # and DuckDB would refuse to read them together.
        sparse = [dict(row, role_end=None) for row in rows()]
        write(sparse, SCHEMA, tmp_path / "t.parquet", KEY)

        assert (
            pq.read_table(tmp_path / "t.parquet").schema.field("role_end").type
            == pa.string()
        )

    def test_an_unknown_key_in_a_row_is_ignored(self, tmp_path: Path) -> None:
        # Rows come from readers that carry more columns than a table declares.
        # The schema decides what is stored.
        noisy = [dict(row, scratch="not a column") for row in rows()]
        write(noisy, SCHEMA, tmp_path / "t.parquet", KEY)

        assert pq.read_table(tmp_path / "t.parquet").schema.names == SCHEMA.names

    def test_it_leaves_no_partial_file(self, tmp_path: Path) -> None:
        write(rows(), SCHEMA, tmp_path / "t.parquet", KEY)
        assert list(tmp_path.iterdir()) == [tmp_path / "t.parquet"]

    def test_it_creates_the_parent_directory(self, tmp_path: Path) -> None:
        write(rows(), SCHEMA, tmp_path / "deep" / "t.parquet", KEY)
        assert (tmp_path / "deep" / "t.parquet").is_file()

    def test_an_empty_table_is_still_written(self, tmp_path: Path) -> None:
        # A slice with no rows is an answer. A missing file is a question about
        # whether the stage ran.
        assert write([], SCHEMA, tmp_path / "t.parquet", KEY) == 0
        assert pq.read_table(tmp_path / "t.parquet").schema.names == SCHEMA.names


class TestPinnedSettings:
    @pytest.mark.parametrize(
        ("setting", "expected"),
        [
            ("compression", "zstd"),
            ("version", "2.6"),
            ("data_page_version", "2.0"),
        ],
    )
    def test_the_settings_that_change_every_byte_are_pinned(
        self, setting: str, expected: str
    ) -> None:
        # Not a tautology: this fails the moment someone edits WRITER without
        # realising that every checksum this project has ever recorded moves.
        assert WRITER[setting] == expected

    def test_the_row_group_size_is_fixed(self) -> None:
        assert ROW_GROUP_SIZE == 20_000

    def test_the_settings_reach_the_file(self, tmp_path: Path) -> None:
        write(rows(), SCHEMA, tmp_path / "t.parquet", KEY)
        metadata = pq.ParquetFile(tmp_path / "t.parquet").metadata
        assert metadata.row_group(0).column(0).compression == "ZSTD"
