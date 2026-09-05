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

import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

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
from serenata.normalise.model import TABLES

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
    path = str(root / name).replace("'", "''")
    return f"read_parquet('{path}/**/*.parquet', hive_partitioning = true)"


def _eligible(root: Path) -> str:
    """The row-level eligibility the gate and the population share, minus the
    buyer country.

    Written once because the gate must never be narrower than the population it
    protects: a row the population reads and the gate skips is a duplicate
    nobody checks.
    """
    procedures = ", ".join(f"'{code}'" for code in COMPETITIVE_PROCEDURES)
    systems = ", ".join(f"'{code}'" for code in FRAMEWORK_SYSTEMS)
    return f"""
SELECT DISTINCT s.source_publication_id, s.lot_result_ordinal
FROM {_table(root, "lot_result_statistic")} s
JOIN {_table(root, "lot_result")} lr
  ON lr.source_publication_id = s.source_publication_id
 AND lr.ordinal = s.lot_result_ordinal
JOIN {_table(root, "lot")} l
  ON l.source_publication_id = s.source_publication_id
 AND l.lot_id = lr.lot_ref
JOIN {_table(root, "procedure")} p
  ON p.source_publication_id = s.source_publication_id
WHERE s.statistic_kind = 'received_submissions'
  AND s.statistic_code = 'tenders'
  AND s.statistic_code_status = 'present'
  AND s.statistic_value_status = 'present'
  AND regexp_full_match(s.statistic_value, '[+]?[0-9]+([.]0*)?')
  AND TRY_CAST(split_part(s.statistic_value, '.', 1) AS BIGINT) >= 1
  AND p.procedure_code_status = 'present'
  AND p.procedure_code IN ({procedures})
  AND l.cpv_code_status = 'present'
  AND NOT list_has_any(l.contracting_system_codes, [{systems}])
"""


def _duplicate_query(root: Path) -> str:
    """Check the keys this rule reads, returning a boolean, never record values.

    Structural duplicates (including overlaps across packages or years) are
    upstream errors, not extra observations. Distinct structural rows may also
    collide on a local join identifier or offer multiple tender counts for one
    outcome. Neither case has an authoritative row this reader can choose.

    The scan covers the publications the population draws from, and the tender
    check the lot results in it. A publication that contributes no lot outcome
    contributes to no segment either, so its duplicates cannot move a flag —
    and TED publishes such rows: one framework lot result in the archive
    carries its bid count four times, and validating whole tables let it stop
    every measurement over data the rule never reads. Eligibility deliberately
    stops short of the buyer country, so a publication cannot escape the check
    by carrying the very duplicate organisations that would exclude it.
    """
    inputs = {
        "procedure",
        "lot",
        "lot_result",
        "organisation",
        "organisation_role",
        "lot_result_statistic",
    }
    checks = [
        (table.name, table.key, "true") for table in TABLES if table.name in inputs
    ]
    checks.extend(
        [
            ("lot", ("source_publication_id", "lot_id"), "lot_id IS NOT NULL"),
            (
                "organisation",
                ("source_publication_id", "org_local_id"),
                "org_local_id IS NOT NULL",
            ),
            (
                "lot_result_statistic",
                ("source_publication_id", "lot_result_ordinal"),
                "statistic_kind = 'received_submissions' "
                "AND statistic_code = 'tenders' "
                "AND statistic_code_status = 'present' "
                "AND (source_publication_id, lot_result_ordinal) IN "
                "(SELECT source_publication_id, lot_result_ordinal FROM eligible)",
            ),
        ]
    )
    scope = "source_publication_id IN (SELECT source_publication_id FROM eligible)"
    duplicates = " UNION ALL ".join(
        f"SELECT 1 FROM {_table(root, table)} WHERE {condition} AND {scope} "
        f"GROUP BY {', '.join(key)} HAVING count(*) > 1"
        for table, key, condition in checks
    )
    return f"WITH eligible AS ({_eligible(root)}) SELECT EXISTS ({duplicates})"


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
-- Numeric values remain strings; parse already strips outer whitespace.
-- Accept optional +, ASCII digits and an optional dot with only zeros after it.
-- Check the entire string before discarding its zero fraction. Cast only the
-- integer part: casting decimals, even with TRY_CAST, can round nonzero tails.
-- TRY_CAST excludes BIGINT overflow; bids >= 1 excludes zero below.
WITH counted_statistics AS (
    SELECT *,
           CASE WHEN regexp_full_match(statistic_value, '[+]?[0-9]+([.]0*)?')
                THEN TRY_CAST(split_part(statistic_value, '.', 1) AS BIGINT)
           END AS bids
    FROM {_table(root, "lot_result_statistic")}
), buyer_country AS (
    SELECT r.source_publication_id,
           min(o.country_code) AS country
    FROM {_table(root, "organisation_role")} r
    LEFT JOIN {_table(root, "organisation")} o
      ON o.source_publication_id = r.source_publication_id
     AND o.org_local_id = r.org_ref
    WHERE r.role = 'buyer'
    GROUP BY 1
    HAVING count(DISTINCT o.country_code) = 1
       AND count(*) = count(*) FILTER (
           WHERE o.country_code_status = 'present'
             AND o.country_code IS NOT NULL AND o.country_code <> ''
       )
)
SELECT s.source_publication_id,
       s.source_notice_id,
       CAST(s.publication_year AS VARCHAR) AS publication_year,
       s.lot_result_ordinal,
       lr.lot_ref,
         s.bids,
       b.country,
       substr(l.cpv_code, 1, 2) AS cpv_division
FROM counted_statistics s
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
    AND s.statistic_code_status = 'present'
  AND s.statistic_value_status = 'present'
    AND s.bids >= 1
  AND p.procedure_code_status = 'present'
  AND p.procedure_code IN ({procedures})
  AND l.cpv_code_status = 'present'
  AND NOT list_has_any(l.contracting_system_codes, [{systems}])
ORDER BY s.source_publication_id, s.lot_result_ordinal
"""


def read_outcomes(root: Path) -> list[LotOutcome]:
    """Every lot outcome in the normalised dataset a rule may speak about.

    Ordered by publication and position, so the list a rule receives does not
    depend on how DuckDB happened to scan the files. Duplicate input keys reject
    the whole run rather than multiplying the denominator. Input files must
    remain unchanged throughout validation and reading.
    """
    connection = duckdb.connect()
    try:
        if connection.sql(_duplicate_query(root)).fetchone() == (True,):
            raise ValueError("duplicate classifier input keys")
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

    A successful run replaces this rule's complete output, including removing
    obsolete years. Empty input removes this rule's files and returns no paths;
    no empty partition is invented. Other rule files are never removed.

    Stage every file before replacing any old output, so a serialization failure
    leaves the previous run intact. Each replacement is atomic, but the whole
    multi-year run is not a transaction: interruption during replacement can
    leave mixed generations. Obsolete files are removed only after all new
    files are installed. Concurrent writers to the same rule are unsupported.
    """
    if re.fullmatch(r"[a-z][a-z0-9_]*", rule) is None:
        raise ValueError("invalid flag rule name")
    ordered = sorted(flags, key=lambda flag: flag.sort_key)
    if any(flag.rule != rule for flag in ordered):
        raise ValueError("flag rule does not match writer rule")
    if any(
        re.fullmatch(r"[0-9]{4}|unknown", flag.publication_year) is None
        for flag in ordered
    ):
        raise ValueError("invalid flag publication year")
    schema = flag_schema()
    names = [name for name in FLAG_COLUMNS if name != PARTITION]

    by_year: dict[str, list[Flag]] = {}
    for flag in ordered:
        by_year.setdefault(flag.publication_year, []).append(flag)

    obsolete = set((root / "flag").glob(f"{PARTITION}=*/{rule}.parquet"))
    written: list[Path] = []
    if by_year:
        root.mkdir(parents=True, exist_ok=True)
        # Outside flag/ and without a .parquet suffix: readers cannot discover
        # staged files. Same filesystem as the destination for atomic replace.
        with TemporaryDirectory(prefix=".flags-", dir=root) as temporary:
            staged: list[tuple[Path, Path]] = []
            for year, rows in sorted(by_year.items()):
                pending = Path(temporary) / f"{year}.tmp"
                path = root / "flag" / f"{PARTITION}={year}" / f"{rule}.parquet"
                pq.write_table(
                    pa.table(
                        {
                            name: [getattr(flag, name) for flag in rows]
                            for name in names
                        },
                        schema=schema,
                    ),
                    pending,
                    row_group_size=ROW_GROUP_SIZE,
                    **WRITER,
                )
                staged.append((pending, path))
            for pending, path in staged:
                path.parent.mkdir(parents=True, exist_ok=True)
                pending.replace(path)
                written.append(path)
    for path in sorted(obsolete.difference(written)):
        path.unlink()
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
