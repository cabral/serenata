"""The flag record and the file it is written to.

[ADR-0011](../docs/adr/0011-flags-carry-their-own-baseline.md) decided two
things and these tests hold both. A flag carries the evidence for its own
claim, so that checking one does not mean rerunning the pipeline. And the
baseline it was measured against travels in the row, because that baseline is
computed from the dataset being classified and a reader has to be able to see
which dataset that was.

Constraint 4 applies to flags exactly as it applies to the normalised dataset:
the same rows written twice are the same bytes. `TestRerunsAreIdentical` is the
only thing that can establish it.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pyarrow.parquet as pq

from serenata.classify.dataset import flag_schema, write_flags
from serenata.classify.records import FLAG_COLUMNS, Flag, notice_url
from serenata.classify.single_bid_in_segment import RULE, flags
from serenata.normalise import PARTITION

from .test_classify_single_bid import market


def written(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.parquet"))
    }


class TestAFlagCarriesItsEvidence:
    """ADR-0011: a row nobody can check without rerunning is not a flag."""

    def test_it_names_the_notice_and_where_to_read_it(self) -> None:
        flag = flags(market(100, 1))[0]

        assert flag.source_publication_id == "00000001-2026"
        assert flag.source_notice_id == "notice-0001"
        assert flag.source_url == notice_url("00000001-2026")
        assert flag.source_url.startswith("https://ted.europa.eu/")

    def test_it_names_the_rule_and_its_version(self) -> None:
        flag = flags(market(100, 1))[0]
        assert (flag.rule, flag.rule_version) == (RULE, 1)

    def test_it_carries_the_values_the_rule_read(self) -> None:
        flag = flags(market(100, 1))[0]
        assert (flag.bids, flag.lot_ref, flag.lot_result_ordinal) == (1, "LOT-0001", 0)

    def test_it_carries_the_baseline_it_was_compared_against(self) -> None:
        # The point of the ADR. Without these two numbers the row says "one
        # bid", which is true of 42.1% of the population and interesting in
        # none of them.
        flag = flags(market(100, 1))[0]
        assert (flag.segment_country, flag.segment_cpv_division) == ("SWE", "45")
        assert (flag.segment_size, flag.segment_single_bids) == (100, 1)

    def test_the_baseline_moves_with_the_dataset_and_the_row_shows_it(self) -> None:
        # The cost ADR-0011 accepted, made visible: the same lot in a bigger
        # dataset carries a different baseline rather than silently changing
        # its mind.
        small = flags(market(100, 1))[0]
        large = flags(market(200, 2))[0]

        assert small.segment_size != large.segment_size
        assert (small.source_publication_id, small.bids) == (
            large.source_publication_id,
            large.bids,
        )

    def test_no_column_is_a_float(self) -> None:
        # A rate is carried as the counts it came from. Nothing in a flag file
        # can differ between runs by a rounding decision.
        assert not any("float" in str(field.type) for field in flag_schema())


class TestTheFileItIsWrittenTo:
    def test_it_writes_one_file_per_rule_and_year(self, tmp_path: Path) -> None:
        paths = write_flags(flags(market(100, 3)), tmp_path, rule=RULE)

        assert [path.relative_to(tmp_path).as_posix() for path in paths] == [
            f"flag/{PARTITION}=2026/{RULE}.parquet"
        ]

    def test_every_field_of_the_record_reaches_the_file(self, tmp_path: Path) -> None:
        # The schema is derived from the dataclass, so a field added to the
        # record and forgotten here would be a column nobody wrote.
        write_flags(flags(market(100, 3)), tmp_path, rule=RULE)
        table = pq.read_table(
            tmp_path / "flag" / f"{PARTITION}=2026" / f"{RULE}.parquet"
        )

        assert table.column_names == [
            name for name in FLAG_COLUMNS if name != PARTITION
        ]
        assert table.num_rows == 3

    def test_rows_are_written_in_a_fixed_order(self, tmp_path: Path) -> None:
        write_flags(list(reversed(flags(market(100, 3)))), tmp_path, rule=RULE)
        table = pq.read_table(
            tmp_path / "flag" / f"{PARTITION}=2026" / f"{RULE}.parquet"
        )

        published = table.column("source_publication_id").to_pylist()
        assert published == sorted(published)

    def test_a_year_with_no_flags_writes_nothing_rather_than_an_empty_year(
        self, tmp_path: Path
    ) -> None:
        # There is no year to write: the partition comes from the flags, and a
        # run that flagged nothing has no year to name.
        assert write_flags([], tmp_path, rule=RULE) == []

    def test_flags_from_two_years_land_in_two_partitions(self, tmp_path: Path) -> None:
        found = flags(market(100, 2))
        older = Flag(**{**found[0].__dict__, "publication_year": "2025"})
        paths = write_flags([older, found[1]], tmp_path, rule=RULE)

        assert {path.parent.name for path in paths} == {
            f"{PARTITION}=2025",
            f"{PARTITION}=2026",
        }


class TestRerunsAreIdentical:
    """Constraint 4, for flags. ADR-0011 puts byte-stability on this stage too.

    Only a rerun can establish it, so this writes the same flags twice into two
    directories and compares checksums, the way the normalise stage's own rerun
    test does.
    """

    def test_the_same_flags_produce_the_same_bytes(self, tmp_path: Path) -> None:
        found = flags(market(100, 5))
        first, second = tmp_path / "first", tmp_path / "second"
        write_flags(found, first, rule=RULE)
        write_flags(found, second, rule=RULE)

        assert written(first) == written(second)

    def test_input_order_does_not_reach_the_bytes(self, tmp_path: Path) -> None:
        found = flags(market(100, 5))
        first, second = tmp_path / "first", tmp_path / "second"
        write_flags(found, first, rule=RULE)
        write_flags(list(reversed(found)), second, rule=RULE)

        assert written(first) == written(second)

    def test_different_flags_produce_different_bytes(self, tmp_path: Path) -> None:
        # The guard against a comparison that passes by comparing nothing.
        first, second = tmp_path / "first", tmp_path / "second"
        write_flags(flags(market(100, 5)), first, rule=RULE)
        write_flags(flags(market(100, 6)), second, rule=RULE)

        assert written(first) != written(second)
