"""Read lot outcomes out of the normalised dataset, and write flags back.

The only part of the classify stage that touches a file. Rules are pure
functions over rows (`serenata.classify.single_bid_in_segment`); this module
gets them their rows and stores what they return.

Reading is DuckDB over the Parquet ADR-0001 chose, which is the arrangement
that ADR anticipated: "classifiers will move it when they need SQL". The
population query below is the one in
`docs/hypotheses/single_bid_in_segment.sql`, which exists so the measurement
in the hypothesis can be checked without running this code.
`tests/test_classify_dataset.py` runs both over the same dataset and fails if
they disagree, because two statements of one definition drift.

Writing follows the normalise stage's rules exactly, and imports its settings
rather than restating them: sorted rows, a fixed schema, pinned writer options,
partitioned by publication year, no clock anywhere (ADR-0011, constraint 4).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from serenata.classify.records import (
    FLAG_COLUMNS,
    FLAG_INTEGERS,
    Flag,
    LotOutcome,
)
from serenata.normalise.dataset import PARTITION, ROW_GROUP_SIZE, WRITER

#: Procedure types where several bids are the expectation. Negotiation without
#: a prior call for competition is excluded: one bid there is the procedure
#: working as designed, not a surprise (BT-105).
COMPETITIVE_PROCEDURES = (
    "open",
    "restricted",
    "comp-dial",
    "comp-tend",
    "innovation",
    "neg-w-call",
)

#: Framework agreements and dynamic purchasing systems, excluded. Competition
#: under a framework happens at call-off, which the award notice does not
#: report; the Commission's own single-bidder indicator excludes them for the
#: same reason (BT-765).
FRAMEWORK_SYSTEMS = ("fa-wo-rc", "fa-w-rc", "fa-mix", "dps-list", "dps-nlist")


def _table(root: Path, name: str) -> str:
    return f"read_parquet('{root / name}/**/*.parquet', hive_partitioning = true)"


def population_query(root: Path) -> str:
    """The lot outcomes a rule may speak about, as SQL over the dataset.

    Every exclusion is argued in the hypothesis. In short: a withheld bid count
    is not a number, no bids is not one bid, a procedure with no call for
    competition is not expected to draw several, and a framework's competition
    is not in this notice.

    The buyer join stays inside one publication. Organisation identifiers are
    scoped to their notice, and joining them across notices is entity
    resolution — milestone 3, and not assumed here.
    """
    procedures = ", ".join(f"'{code}'" for code in COMPETITIVE_PROCEDURES)
    systems = ", ".join(f"'{code}'" for code in FRAMEWORK_SYSTEMS)
    return f"""
WITH buyer_country AS (
    SELECT r.source_publication_id,
           any_value(o.country_code) AS country
    FROM {_table(root, "organisation_role")} r
    JOIN {_table(root, "organisation")} o
      ON o.source_publication_id = r.source_publication_id
     AND o.org_local_id = r.org_ref
    WHERE r.role = 'buyer'
      AND o.country_code_status = 'present'
    GROUP BY 1
)
SELECT s.source_publication_id,
       s.source_notice_id,
       CAST(s.publication_year AS VARCHAR) AS publication_year,
       s.lot_result_ordinal,
       lr.lot_ref,
       CAST(s.statistic_value AS BIGINT) AS bids,
       b.country,
       substr(l.cpv_code, 1, 2) AS cpv_division
FROM {_table(root, "lot_result_statistic")} s
JOIN {_table(root, "lot_result")} lr
  ON lr.source_publication_id = s.source_publication_id
 AND lr.ordinal = s.lot_result_ordinal
JOIN {_table(root, "lot")} l
  ON l.source_publication_id = s.source_publication_id
 AND l.lot_id = lr.lot_ref
JOIN {_table(root, "procedure")} p
  ON p.source_publication_id = s.source_publication_id
JOIN buyer_country b
  ON b.source_publication_id = s.source_publication_id
WHERE s.statistic_kind = 'received_submissions'
  AND s.statistic_code = 'tenders'
  AND s.statistic_value_status = 'present'
  AND TRY_CAST(s.statistic_value AS BIGINT) >= 1
  AND p.procedure_code_status = 'present'
  AND p.procedure_code IN ({procedures})
  AND l.cpv_code_status = 'present'
  AND NOT list_has_any(l.contracting_system_codes, [{systems}])
ORDER BY s.source_publication_id, s.lot_result_ordinal
"""


def read_outcomes(root: Path) -> list[LotOutcome]:
    """Every lot outcome in the normalised dataset a rule may speak about.

    Ordered by publication and position, so the list a rule receives does not
    depend on how DuckDB happened to scan the files.
    """
    connection = duckdb.connect()
    try:
        rows = connection.sql(population_query(root)).fetchall()
    finally:
        connection.close()
    return [
        LotOutcome(
            source_publication_id=str(publication),
            source_notice_id=str(notice),
            publication_year=str(year),
            lot_result_ordinal=int(ordinal),
            lot_ref=str(lot_ref),
            bids=int(bids),
            country=str(country),
            cpv_division=str(division),
        )
        for publication, notice, year, ordinal, lot_ref, bids, country, division in rows
    ]


def flag_schema() -> pa.Schema:
    """The flag table's Parquet schema, without the partition column.

    A Hive-partitioned dataset keeps the partition in the directory name; a
    file that also carried it would give a reader two definitions of one field.
    """
    return pa.schema(
        [
            (name, pa.int32() if name in FLAG_INTEGERS else pa.string())
            for name in FLAG_COLUMNS
            if name != PARTITION
        ]
    )


def write_flags(flags: Iterable[Flag], root: Path, *, rule: str) -> list[Path]:
    """Write ``flags`` under ``root``, one file per rule per year.

    Naming the file after the rule lets a rerun replace its own output in place
    and lets two rules sit side by side in a partition. A year with no flags is
    still written, with its schema, so a query returns no rows rather than
    failing to find a file.
    """
    ordered = sorted(flags, key=lambda flag: flag.sort_key)
    schema = flag_schema()
    names = [name for name in FLAG_COLUMNS if name != PARTITION]

    by_year: dict[str, list[Flag]] = {}
    for flag in ordered:
        by_year.setdefault(flag.publication_year, []).append(flag)

    written: list[Path] = []
    for year, rows in sorted(by_year.items()):
        directory = root / "flag" / f"{PARTITION}={year}"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{rule}.parquet"
        pq.write_table(
            pa.table(
                {name: [getattr(flag, name) for flag in rows] for name in names},
                schema=schema,
            ),
            path,
            row_group_size=ROW_GROUP_SIZE,
            **WRITER,
        )
        written.append(path)
    return written


@dataclass(frozen=True)
class Classified:
    """What one classifier run produced."""

    rule: str
    rule_version: int
    outcomes: int
    flags: int
    files: tuple[Path, ...]

    def describe(self) -> str:
        share = 100 * self.flags / self.outcomes if self.outcomes else 0.0
        return (
            f"{self.rule} v{self.rule_version}: {self.flags:,} flags "
            f"from {self.outcomes:,} lot outcomes ({share:.2f}%)"
        )


def default_flag_root() -> Path:
    """Where flags are written unless the caller says otherwise.

    Beside the normalised dataset, under the same gitignored `data/`: flags are
    derived and rebuildable from the archive and the code that made them.
    """
    return Path("data") / "flags"
