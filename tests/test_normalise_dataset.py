"""Writing the dataset: the schema, the layout, and the rerun.

The test that matters here is `TestRerunIdentity`. Constraint 4 says the same
input data and the same code produce the same bytes, and no static check can
establish that — only running the pipeline twice and comparing checksums can.
`tests/test_constraints.py` enforces the half a static check can see (no clock,
no unseeded randomness downstream of fetch); this is the other half, and it is
open-work #9, which was blocked until this stage wrote anything at all.

Everything runs offline against a package built in memory.
"""

from __future__ import annotations

import hashlib
import tarfile
from pathlib import Path

import duckdb
import pyarrow.parquet as pq
import pytest

from serenata.normalise import (
    PARTITION,
    TABLES,
    WRITER,
    Table,
    normalise_package,
    package_part,
    schema_of,
    table,
)

from .support import PACKAGE_PREFIX, make_notice_package, notice_xml
from .test_normalise import BODY, ORGANISATIONS, RESULTS

PACKAGE_ID = "202600157"


def package(directory: Path, count: int = 3, year: str = "2026") -> Path:
    """A daily package of synthetic notices, written to disk unfetched."""
    notices = {
        f"{index:08d}_2026.xml": notice_xml(
            publication_id=f"{index:08d}-2026",
            publication_date=f"{year}-08-17+02:00",
            body=BODY,
            extension=ORGANISATIONS + RESULTS,
        )
        for index in range(1, count + 1)
    }
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{PACKAGE_ID}.tar.gz"
    path.write_bytes(make_notice_package(notices))
    return path


def checksums(root: Path) -> dict[str, str]:
    """Every written file under ``root``, by relative path and content hash."""
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*.parquet"))
    }


class TestRerunIdentity:
    """Constraint 4, proved the only way it can be: by running it twice."""

    def test_two_runs_over_one_package_are_byte_identical(self, tmp_path: Path) -> None:
        source = package(tmp_path)
        first, second = tmp_path / "first", tmp_path / "second"

        normalise_package(source, first)
        normalise_package(source, second)

        assert checksums(first) == checksums(second)
        assert len(checksums(first)) == len(TABLES), "a table went unwritten"

    def test_rewriting_in_place_reproduces_the_same_bytes(self, tmp_path: Path) -> None:
        # The realistic case: a package renormalised into an existing dataset
        # after a code change that should not have moved anything.
        source = package(tmp_path)
        root = tmp_path / "dataset"
        normalise_package(source, root)
        before = checksums(root)
        normalise_package(source, root)
        assert checksums(root) == before

    def test_the_comparison_can_actually_fail(self, tmp_path: Path) -> None:
        # A checksum test passes vacuously if it compares nothing, or if the
        # writer ignores its input. Different data must give different bytes.
        one = tmp_path / "one"
        other = tmp_path / "other"
        normalise_package(package(tmp_path / "a", count=2), one)
        normalise_package(package(tmp_path / "b", count=3), other)
        assert checksums(one) != checksums(other)


class TestLayout:
    """Where a row lands, and what the file is called."""

    def test_rows_are_partitioned_by_the_notices_own_year(self, tmp_path: Path) -> None:
        result = normalise_package(package(tmp_path, year="2019"), tmp_path / "out")
        partitions = {path.parent.name for path in result.files}
        assert partitions == {f"{PARTITION}=2019"}

    def test_the_file_is_named_after_the_source_package(self, tmp_path: Path) -> None:
        result = normalise_package(package(tmp_path), tmp_path / "out")
        assert {path.name for path in result.files} == {f"{PACKAGE_ID}.parquet"}
        assert package_part(Path("data/2026/202600157.tar.gz")) == PACKAGE_ID

    def test_every_table_is_written_even_with_no_rows(self, tmp_path: Path) -> None:
        # An empty notice fills the notice tables and nothing else. A missing
        # file would make an empty table indistinguishable from a broken query.
        empty = tmp_path / "empty.tar.gz"
        empty.write_bytes(
            make_notice_package({"00000009_2026.xml": notice_xml()}, PACKAGE_PREFIX)
        )
        result = normalise_package(empty, tmp_path / "out")
        written = {path.parent.parent.name for path in result.files}
        assert written == {model.name for model in TABLES}
        lots = pq.read_table(tmp_path / "out" / "lot" / f"{PARTITION}=2026")
        assert lots.num_rows == 0
        assert lots.schema.names == list(schema_of(table("lot")).names)


class TestSchema:
    """What the columns are, and what they are not."""

    def test_values_are_stored_as_published(self, tmp_path: Path) -> None:
        normalise_package(package(tmp_path), tmp_path / "out")
        tenders = pq.read_table(tmp_path / "out" / "lot_tender")
        assert tenders.schema.field("payable_amount").type == "string"
        assert tenders.column("payable_amount").to_pylist()[0] == "500"

    def test_a_set_column_is_a_list(self, tmp_path: Path) -> None:
        normalise_package(package(tmp_path), tmp_path / "out")
        lots = pq.read_table(tmp_path / "out" / "lot")
        codes = lots.schema.field("contracting_system_codes")
        assert codes.type.value_type == "string"
        assert str(codes.type).startswith("list<")
        assert lots.column("contracting_system_codes").to_pylist()[0] == [
            "none",
            "fa-wo-rc",
        ]

    def test_ordinals_are_numbers(self, tmp_path: Path) -> None:
        normalise_package(package(tmp_path), tmp_path / "out")
        organisations = pq.read_table(tmp_path / "out" / "organisation")
        assert organisations.schema.field("ordinal").type == "int32"

    @pytest.mark.parametrize("model", TABLES, ids=lambda t: t.name)
    def test_the_schema_covers_every_column_and_companion(self, model: Table) -> None:
        expected = [name for name in model.field_names() if name != PARTITION]
        assert list(schema_of(model).names) == expected

    @pytest.mark.parametrize("model", TABLES, ids=lambda t: t.name)
    def test_the_partition_is_not_also_a_column(self, model: Table) -> None:
        # Two definitions of one field is what a Hive reader refuses to merge.
        assert PARTITION not in schema_of(model).names

    def test_the_writer_settings_are_pinned(self) -> None:
        # Not a style check: these settings are in every byte the project has
        # written, so changing one silently invalidates every checksum
        # published against the old ones.
        assert WRITER == {
            "compression": "zstd",
            "compression_level": 3,
            "version": "2.6",
            "data_page_version": "2.0",
            "use_dictionary": True,
            "write_statistics": True,
        }


class TestOrdering:
    """Rows are sorted before every write, never left in scan order."""

    def test_rows_come_out_in_key_order(self, tmp_path: Path) -> None:
        source = package(tmp_path, count=5)
        # Reverse the archive so document order and key order disagree; a
        # writer relying on scan order would reproduce the tar's order.
        reversed_package = tmp_path / "reversed.tar.gz"
        with tarfile.open(source) as reading:
            members = list(reading.getmembers())
            with tarfile.open(reversed_package, "w:gz") as writing:
                for member in reversed(members):
                    handle = reading.extractfile(member)
                    assert handle is not None
                    member.mtime = 0
                    writing.addfile(member, handle)

        normalise_package(reversed_package, tmp_path / "out")
        notices = pq.read_table(tmp_path / "out" / "notice")
        published = notices.column("source_publication_id").to_pylist()
        assert published == sorted(published)


class TestDuckDBCanQueryIt:
    """ADR-0001's other half: the dataset is queried with DuckDB, not by us."""

    def test_a_query_reads_the_partitioned_dataset(self, tmp_path: Path) -> None:
        root = tmp_path / "out"
        normalise_package(package(tmp_path, count=4), root)
        connection = duckdb.connect()
        rows = connection.sql(
            "SELECT count(*) AS notices, count(DISTINCT publication_year) AS years "
            f"FROM read_parquet('{root}/notice/**/*.parquet', hive_partitioning=true)"
        ).fetchone()
        assert rows == (4, 1)

    def test_a_withheld_bid_count_is_visible_as_withheld(self, tmp_path: Path) -> None:
        # The query a single-bid classifier will write, and the reason the
        # status column exists: reading the number alone finds a -1.
        root = tmp_path / "out"
        normalise_package(package(tmp_path), root)
        connection = duckdb.connect()
        counts = connection.sql(
            "SELECT statistic_value_status, count(*) FROM read_parquet("
            f"'{root}/lot_result_statistic/**/*.parquet', hive_partitioning=true) "
            "GROUP BY 1 ORDER BY 1"
        ).fetchall()
        assert counts == [("present", 3), ("withheld", 3)]


class TestFailuresAreCounted:
    """A run that lost notices must not look like a run that had none."""

    def test_an_unreadable_member_is_reported_not_skipped(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.tar.gz"
        broken.write_bytes(
            make_notice_package(
                {
                    "00000001_2026.xml": notice_xml(),
                    "00000002_2026.xml": b"<not-a-notice/>",
                }
            )
        )
        result = normalise_package(broken, tmp_path / "out")
        assert result.notices == 1
        assert len(result.unparsed) == 1
        assert "00000002_2026.xml" in result.unparsed[0].member
        assert "unparsed" in result.describe()

    def test_a_clean_run_describes_what_it_wrote(self, tmp_path: Path) -> None:
        result = normalise_package(package(tmp_path), tmp_path / "out")
        assert result.unparsed == ()
        assert result.unnormalised == ()
        assert "3 notices" in result.describe()
        assert result.rows["notice"] == 3


class TestEdges:
    """The cases a daily package does not contain but a year of them will."""

    def test_a_notice_the_model_cannot_map_is_named_and_counted(
        self, tmp_path: Path
    ) -> None:
        repeated = BODY.replace(
            "<cbc:IssueDate>2026-08-13+02:00</cbc:IssueDate>",
            "<cbc:IssueDate>2026-08-13+02:00</cbc:IssueDate>"
            "<cbc:IssueDate>2026-08-14+02:00</cbc:IssueDate>",
        )
        source = tmp_path / "mixed.tar.gz"
        source.write_bytes(
            make_notice_package(
                {
                    "00000001_2026.xml": notice_xml(publication_id="00000001-2026"),
                    "00000002_2026.xml": notice_xml(
                        publication_id="00000002-2026", body=repeated
                    ),
                }
            )
        )
        result = normalise_package(source, tmp_path / "out")
        assert result.notices == 2
        assert len(result.unnormalised) == 1
        assert "issue_date" in result.unnormalised[0].reason
        assert "unnormalised" in result.describe()
        # The notice that did map is still written: one bad notice does not
        # cost the rest of the package.
        assert result.rows["notice"] == 1

    def test_a_notice_without_a_publication_still_lands_somewhere(
        self, tmp_path: Path
    ) -> None:
        # No publication block at all: the key is missing, and the row sorts
        # first rather than the write failing.
        document = notice_xml()
        stripped = document.replace(
            document[
                document.index(b"<efac:Publication>") : document.index(
                    b"</efac:Publication>"
                )
                + len(b"</efac:Publication>")
            ],
            b"",
        )
        source = tmp_path / "anonymous.tar.gz"
        source.write_bytes(make_notice_package({"00000001_2026.xml": stripped}))
        result = normalise_package(source, tmp_path / "out")
        assert result.rows["notice"] == 1
        notices = pq.read_table(tmp_path / "out" / "notice")
        assert notices.column("source_publication_id").to_pylist() == [None]
        assert {path.parent.name for path in result.files} == {f"{PARTITION}=unknown"}

    def test_a_package_named_without_a_known_suffix_still_names_its_file(
        self,
    ) -> None:
        assert package_part(Path("202600157.tgz")) == "202600157"
        assert package_part(Path("202600157.tar")) == "202600157"

    def test_asking_for_a_table_or_column_that_does_not_exist_says_so(self) -> None:
        with pytest.raises(KeyError):
            table("not_a_table")
        with pytest.raises(KeyError):
            table("notice").column("not_a_column")
