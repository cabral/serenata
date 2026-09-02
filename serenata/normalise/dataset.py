"""Write the model's rows as Parquet, the same bytes every time.

ADR-0001 chose Parquet queried with DuckDB and put byte-stability on this
stage: "Parquet output is only byte-stable if the writer makes it so — fixed
row ordering, fixed schema and writer settings, pinned writer version." That
sentence is this module's whole specification, and
`tests/test_normalise_dataset.py` is the proof, because a rerun is the only
thing that can establish it.

What makes a rerun identical:

- **Fixed row order.** Rows are sorted by their table's key before every write,
  with Python's stable sort, so ties keep document order rather than whatever
  order the notices arrived in.
- **Fixed schema.** Columns come from `serenata.normalise.model` in declaration
  order, with a type per column rather than one inferred from the values
  present in this particular package.
- **Fixed writer settings.** `WRITER` below, passed on every write.
- **Pinned writer version.** `uv.lock` pins pyarrow; the Parquet metadata
  records which version wrote a file, so upgrading pyarrow can change the bytes
  without changing a row. That is a dependency bump doing what a dependency
  bump does, and the rerun test will say so.
- **No clock.** The partition is the notice's publication year, and nothing
  else in a file comes from the runtime.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from serenata.normalise.model import TABLES, Kind, Table
from serenata.normalise.rows import UNKNOWN_YEAR, Rows, empty_rows, notice_rows
from serenata.parse import ParsedNotice, Unparsed, parse_package

#: Parquet writer settings, pinned. Changing any of them changes every byte the
#: pipeline has ever written, so they belong in one named place rather than at
#: each call site. zstd because it is deterministic and well supported; the 2.6
#: format and v2 data pages because they are what current readers expect.
WRITER: dict[str, Any] = {
    "compression": "zstd",
    "compression_level": 3,
    "version": "2.6",
    "data_page_version": "2.0",
    "use_dictionary": True,
    "write_statistics": True,
}

#: Rows per Parquet row group. Fixed, because the grouping is part of the file's
#: bytes: the same rows split differently are the same data and a different
#: checksum.
ROW_GROUP_SIZE = 20_000

#: The partition directory each table is written under, Hive-style, so DuckDB
#: reads `publication_year` as a column without being told to.
PARTITION = "publication_year"


def _arrow_type(table: Table, name: str) -> pa.DataType:
    """The stored type of one column.

    Values are stored as published, as strings. Casting is a decision with
    edge cases — a withheld amount is published as ``-1`` — and belongs to
    whoever queries, explicitly. Ordinals are the exception: they are this
    project's own numbering, not something a notice published.
    """
    if name == "ordinal" or name.endswith("_ordinal"):
        return pa.int32()
    for column in table.columns:
        if column.name == name and column.kind is Kind.SET:
            return pa.list_(pa.string())
    return pa.string()


def schema_of(table: Table) -> pa.Schema:
    """The Parquet schema for one table, in declaration order.

    Without `PARTITION`. A Hive-partitioned dataset keeps the partition value in
    the directory name, and a file that also carried it as a column would give
    every reader that discovers partitions two definitions of one field —
    pyarrow refuses to merge them, and DuckDB has to be told which to believe.
    The path says the year; a reader gets it back as a column.
    """
    return pa.schema(
        [
            (name, _arrow_type(table, name))
            for name in table.field_names()
            if name != PARTITION
        ]
    )


@dataclass
class Dataset:
    """Rows accumulated across notices, ready to be written.

    Held in memory for the length of one package. A daily package of 3,190
    notices produces about 90,000 rows, which is small; a caller normalising a
    year does it a package at a time, which is also how the partitions are
    written.
    """

    rows: Rows = field(default_factory=empty_rows)

    def add(self, produced: Rows) -> None:
        for name, rows in produced.items():
            self.rows[name].extend(rows)

    def counts(self) -> dict[str, int]:
        return {name: len(rows) for name, rows in self.rows.items()}

    def years(self) -> list[str]:
        """Every partition this dataset has rows for, in order.

        A dataset with no rows at all still names one, so that an empty package
        writes an empty table rather than nothing.
        """
        found = {
            row[PARTITION]
            for rows in self.rows.values()
            for row in rows
            if row.get(PARTITION)
        }
        return sorted(found) or [UNKNOWN_YEAR]

    def arrow(self, table: Table, year: str) -> pa.Table:
        """One year of one table's rows, sorted by its key, as an Arrow table."""
        rows = sorted(
            (row for row in self.rows[table.name] if row.get(PARTITION) == year),
            # A missing key sorts before any value rather than raising: keys are
            # present in every notice measured, and a notice that broke that
            # should still land somewhere findable.
            key=lambda row: tuple(_sort_key(row.get(name)) for name in table.key),
        )
        schema = schema_of(table)
        columns = [
            pa.array([row.get(name) for row in rows], type=schema.field(name).type)
            for name in schema.names
        ]
        return pa.Table.from_arrays(columns, schema=schema)


def _sort_key(value: Any) -> tuple[int, str]:
    """Order values of mixed presence deterministically."""
    if value is None:
        return (0, "")
    if isinstance(value, int):
        # Ordinals are small and non-negative; zero-padding keeps 2 before 10.
        return (1, f"{value:012d}")
    return (1, str(value))


def write_dataset(dataset: Dataset, root: Path, *, part: str) -> list[Path]:
    """Write every table under ``root``, partitioned by publication year.

    ``part`` names the file within a partition and is the source package's
    identifier, so a package can be rewritten in place and two packages
    covering the same year sit side by side without a generated name.

    A table with no rows is still written, with its schema, so a query against
    an empty table returns no rows rather than failing to find a file.
    """
    written: list[Path] = []
    years = dataset.years()
    for table in TABLES:
        for year in years:
            directory = root / table.name / f"{PARTITION}={year}"
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{part}.parquet"
            pq.write_table(
                dataset.arrow(table, year),
                path,
                row_group_size=ROW_GROUP_SIZE,
                **WRITER,
            )
            written.append(path)
    return written


@dataclass(frozen=True)
class Normalised:
    """What one package became.

    ``unparsed`` and ``unnormalised`` are counted rather than hidden: a run that
    lost notices must not look like a run that had none. `Unparsed` comes from
    the parse stage; `Unnormalised` is a notice parse read and this stage could
    not map, which is a model question and is named as one.
    """

    package: Path
    notices: int
    unparsed: tuple[Unparsed, ...]
    unnormalised: tuple[Unnormalised, ...]
    rows: dict[str, int]
    files: tuple[Path, ...]

    def describe(self) -> str:
        total = sum(self.rows.values())
        parts = [f"{self.package.name}: {self.notices} notices, {total} rows"]
        if self.unparsed:
            parts.append(f"{len(self.unparsed)} unparsed")
        if self.unnormalised:
            parts.append(f"{len(self.unnormalised)} unnormalised")
        return ", ".join(parts)


@dataclass(frozen=True)
class Unnormalised:
    """A notice this stage could not map into the model, and why."""

    notice_id: str
    reason: str


def normalise_notices(
    notices: Iterable[ParsedNotice],
) -> tuple[Dataset, list[Unnormalised]]:
    """Accumulate rows for every notice, collecting the ones that do not map."""
    dataset = Dataset()
    refused: list[Unnormalised] = []
    for notice in notices:
        try:
            dataset.add(notice_rows(notice))
        except LookupError as exc:
            refused.append(Unnormalised(notice_id=notice.notice_id, reason=str(exc)))
    return dataset, refused


def normalise_package(package: Path, root: Path) -> Normalised:
    """Parse one archived package and write its rows under ``root``.

    Offline and deterministic: the archive is read-only input, the partition
    comes from each notice's publication date, and rerunning over the same
    package writes the same bytes.
    """
    dataset = Dataset()
    unparsed: list[Unparsed] = []
    unnormalised: list[Unnormalised] = []
    notices = 0

    for outcome in parse_package(package):
        if isinstance(outcome, Unparsed):
            unparsed.append(outcome)
            continue
        notices += 1
        try:
            dataset.add(notice_rows(outcome))
        except LookupError as exc:
            unnormalised.append(
                Unnormalised(notice_id=outcome.notice_id, reason=str(exc))
            )

    files = write_dataset(dataset, root, part=package_part(package))
    return Normalised(
        package=package,
        notices=notices,
        unparsed=tuple(unparsed),
        unnormalised=tuple(unnormalised),
        rows=dataset.counts(),
        files=tuple(files),
    )


def default_dataset_root() -> Path:
    """Where the normalised dataset lives unless the caller says otherwise.

    Beside the raw archive, under the same gitignored `data/`: the dataset is
    derived and rebuildable, and committing it would put a 4 MB artefact per
    publication day into the history of a repository people clone to read.
    """
    return Path("data") / "normalised"


def package_part(package: Path) -> str:
    """The file name a package's rows are written under, without a suffix.

    ``202600157.tar.gz`` becomes ``202600157``: the TED package identifier,
    which is what the archive names the file after and is stable across runs.
    """
    name = package.name
    for suffix in (".tar.gz", ".tgz"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return package.stem
