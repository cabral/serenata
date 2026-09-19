# SPDX-License-Identifier: AGPL-3.0-only
"""Write a staged table as Parquet, the same bytes every time.

Constraint 4 says a rerun over the same inputs produces identical output, and
Parquet is only byte-stable if the writer makes it so. Four things make it so,
and all four are here rather than at each call site, because a setting that
differs between two writers is a difference nobody sees until a checksum moves.

- **Fixed row order.** Rows are sorted by the table's key before writing, with
  Python's stable sort, so ties keep the order they arrived in rather than
  whatever order a dict iteration or a DuckDB scan produced.
- **Fixed schema.** Columns and their types come from the caller's declared
  schema, in declaration order, never inferred from the values that happen to be
  present in this slice.
- **Fixed writer settings.** `WRITER` below, passed on every write.
- **Pinned writer version.** `uv.lock` pins pyarrow, and Parquet records which
  version wrote a file, so a pyarrow upgrade can change the bytes without
  changing a row. That is a dependency bump behaving like one, and the rerun
  test will say so rather than letting it pass unnoticed.

This is a deliberate copy of the arrangement in the repository's other project
(`serenata/normalise/dataset.py`), not an import of it: ADR-0014 says nothing in
Crony depends on Serenata, and a shared module would be a dependency in the
direction that record forbids.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

#: Parquet writer settings, pinned. Changing any of them changes every byte this
#: project has ever written. zstd because it is deterministic and widely read;
#: the 2.6 format and v2 data pages because that is what current readers expect.
WRITER: dict[str, Any] = {
    "compression": "zstd",
    "compression_level": 3,
    "version": "2.6",
    "data_page_version": "2.0",
    "use_dictionary": True,
    "write_statistics": True,
}

#: Rows per row group. Fixed, because the grouping is part of the file's bytes:
#: the same rows split differently are the same data and a different checksum.
ROW_GROUP_SIZE = 20_000


def sort_key(row: Mapping[str, Any], columns: Sequence[str]) -> tuple[Any, ...]:
    """A comparable key that survives nulls and mixed types.

    A staged table has nullable columns by design ("not provided" and "not
    applicable" are different facts, and both are common in registry data), and
    `None < str` raises. Each part becomes a pair: a presence flag first, so
    nulls group together and sort before values, then the value rendered as a
    string so that an int and a str in one column cannot raise either.
    """
    key: list[Any] = []
    for column in columns:
        value = row.get(column)
        key.append((1, str(value)) if value is not None else (0, ""))
    return tuple(key)


def write_arrow(table: pa.Table, schema: pa.Schema, destination: Path) -> int:
    """Write an already-ordered Arrow table with the pinned settings.

    The row-based `write` below sorts in Python, which is right for a few
    thousand rows and wrong for the Répertoire national des élus: half a million
    councillors as Python dicts is most of a gigabyte before anything is
    written. Those tables are read, transformed and **ordered by DuckDB**, and
    arrive here as Arrow.

    So the sort is the caller's job, and it is not optional. Order by a key that
    is unique, so that no tie is left for the query planner to break however it
    likes on the day. `crony-eu/tests/test_sources_fr_rne_elus.py` stages the
    same fixture twice and compares bytes, which is the only thing that can
    establish that the caller did it.
    """
    # Selected by name before casting. `Table.cast` matches positionally and
    # raises on a different order, which makes the declared schema a contract
    # about the column list and an accident about the order of a SELECT.
    stored = table.select(list(schema.names)).cast(schema)

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    pq.write_table(stored, partial, row_group_size=ROW_GROUP_SIZE, **WRITER)
    os.replace(partial, destination)
    return int(stored.num_rows)


def write(
    rows: Iterable[Mapping[str, Any]],
    schema: pa.Schema,
    destination: Path,
    key: Sequence[str],
) -> int:
    """Write `rows` to `destination` as Parquet. Returns the row count.

    Written to a `.partial` and renamed, so an interrupted write leaves no file
    that a later stage would read as complete.
    """
    ordered = sorted(rows, key=lambda row: sort_key(row, key))
    table = pa.Table.from_pylist(
        [{name: row.get(name) for name in schema.names} for row in ordered],
        schema=schema,
    )

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    pq.write_table(table, partial, row_group_size=ROW_GROUP_SIZE, **WRITER)
    os.replace(partial, destination)
    return int(table.num_rows)


def write_batches(
    batches: Iterator[pa.RecordBatch], schema: pa.Schema, destination: Path
) -> int:
    """Stream an already-ordered sequence of batches out, with the same bytes.

    `write_arrow` needs the whole table in memory, which is fine for a million
    élus and not for DECP: 3.28 million contract versions with a free-text
    subject on each is a couple of gigabytes of Arrow before a byte is written.

    **Row groups are cut here, not where the batches happen to end.** The
    incoming batch sizes come from whatever DuckDB's scan produced, and they are
    not part of this project's contract; the row group size is. So rows are
    accumulated and flushed in `ROW_GROUP_SIZE` blocks, and the file is
    identical to what `write_arrow` would have produced from the same rows in
    the same order.

    Ordering remains the caller's job, exactly as it is there.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")

    written = 0
    pending: list[pa.RecordBatch] = []
    waiting = 0

    def flush(writer: pq.ParquetWriter, everything: bool) -> None:
        nonlocal pending, waiting, written
        while waiting >= ROW_GROUP_SIZE or (everything and waiting):
            block = pa.Table.from_batches(pending, schema=schema)
            group = block.slice(0, ROW_GROUP_SIZE)
            writer.write_table(group, row_group_size=ROW_GROUP_SIZE)
            written += group.num_rows
            rest = block.slice(group.num_rows)
            waiting = rest.num_rows
            pending = rest.to_batches() if waiting else []

    with pq.ParquetWriter(partial, schema, **WRITER) as writer:
        for batch in batches:
            pending.append(batch.select(list(schema.names)).cast(schema))
            waiting += batch.num_rows
            flush(writer, everything=False)
        flush(writer, everything=True)

    os.replace(partial, destination)
    return written
