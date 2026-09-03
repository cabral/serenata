"""The whole pipeline, over a package, in the shape TED publishes one.

Every other test in this suite builds its notices inside the test that reads
them, which keeps a fixture and its assertion in one file and means **nothing
exercised a package end to end**. The figures this repository quotes about real
data were measured by hand against a local archive that CI cannot see, and
nothing would say when they stopped being true.

This is the other half: `data/sample/` is a committed package of six synthetic
notices, packed here into the archive layout and run through
`parse` → `normalise` → Parquet → DuckDB with no special casing. It is small
enough to read in a review — which matters, because a fixture nobody checks
proves nothing — and it carries the cases that cost something:

- a withheld bid count, published as the code `unpublished` with the number -1;
- a withheld amount, published as -1;
- two notices sharing a UUID under different publication numbers;
- an organisation flagged as a natural person, and a beneficial owner subtree;
- a legacy TED notice, refused rather than guessed at;
- a damaged document, which must not cost the other five.

What it is not is a real package. Real notices carry contact names and e-mail
addresses in 99.9% of cases (`docs/personal-data.md`), so committing one would
put personal data in a public repository to test that we remove personal data.
The sample is synthetic and structurally faithful instead, and
`docs/known-issues.md` says plainly which figures that leaves unverified.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import duckdb
import pytest

from serenata.normalise import TABLES, normalise_package
from serenata.packages import notice_members
from serenata.parse import Unparsed, is_dropped, parse_package

from .support import PACKAGE_PREFIX, SAMPLE, sample_notices, sample_package

#: Values the sample carries where a person's data would be. None may reach a
#: record, a row, or a Parquet file.
NEVER = ("MUST-NEVER-APPEAR", "DROPPED-CONTACT-VALUE")


@pytest.fixture(scope="module")
def package(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return sample_package(tmp_path_factory.mktemp("archive"))


@pytest.fixture(scope="module")
def dataset(package: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("dataset")
    normalise_package(package, root)
    return root


def query(dataset: Path, sql: str) -> list[tuple]:
    """Run SQL over the dataset the way a classifier author would."""
    connection = duckdb.connect()
    for table in TABLES:
        connection.sql(
            f"CREATE VIEW {table.name} AS SELECT * FROM read_parquet("
            f"'{dataset}/{table.name}/**/*.parquet', hive_partitioning = true)"
        )
    return connection.sql(sql).fetchall()


class TestTheArchiveLayer:
    """A package is read from the tarball, without extracting it first."""

    def test_every_notice_is_a_member(self, package: Path) -> None:
        members = [name for name, _handle in notice_members(package)]
        assert len(members) == 6
        assert all(name.startswith(f"{PACKAGE_PREFIX}/") for name in members)

    def test_the_sample_is_small_enough_to_read(self) -> None:
        # The rule this fixture exists under: if a reviewer cannot read it,
        # it is not a fixture, it is a binary nobody checks.
        total = sum(path.stat().st_size for path in SAMPLE.rglob("*.xml"))
        assert total < 64 * 1024, f"the sample has grown to {total} bytes"


class TestParsingTheSample:
    """Four eForms notices parse; two are refused, by name."""

    def test_the_run_survives_what_it_cannot_read(self, package: Path) -> None:
        outcomes = list(parse_package(package))
        parsed = [o for o in outcomes if not isinstance(o, Unparsed)]
        refused = {
            o.member.rsplit("/", 1)[-1]: o.reason
            for o in outcomes
            if isinstance(o, Unparsed)
        }

        assert len(parsed) == 4
        assert set(refused) == {"000005_2026.xml", "00000006_2026.xml"}
        assert "legacy" in refused["000005_2026.xml"]
        # A damaged document is named. Losing it silently would leave a gap
        # nobody could see, which is the failure this shape prevents.
        assert refused["00000006_2026.xml"]

    def test_no_dropped_path_reaches_a_record(self, package: Path) -> None:
        for outcome in parse_package(package):
            if isinstance(outcome, Unparsed):
                continue
            for record in outcome.records:
                for item in record.fields:
                    absolute = f"notice/{item.path}"
                    assert not is_dropped(absolute), absolute


class TestConstraintTwoEndToEnd:
    """The values that must never be stored, checked where they would land."""

    def test_nothing_forbidden_survives_into_a_record(self, package: Path) -> None:
        for outcome in parse_package(package):
            if isinstance(outcome, Unparsed):
                continue
            for record in outcome.records:
                for item in record.fields:
                    assert item.value not in NEVER, f"{record.kind}/{item.path}"

    def test_nothing_forbidden_survives_into_the_written_dataset(
        self, dataset: Path
    ) -> None:
        # Read the bytes rather than the rows: a value that reached a file is a
        # value that reached disk, whichever column it hid in.
        for path in dataset.rglob("*.parquet"):
            body = path.read_bytes()
            for forbidden in NEVER:
                assert forbidden.encode() not in body, path.name

    def test_the_check_can_actually_fail(self) -> None:
        # Prove the sample still carries the values this is looking for; a
        # fixture that lost them would make the assertions above vacuous.
        carried = b"".join(sample_notices().values())
        for forbidden in NEVER:
            assert forbidden.encode() in carried

    def test_a_natural_person_keeps_only_an_opaque_key(self, dataset: Path) -> None:
        rows = query(
            dataset,
            "SELECT org_local_id, name, name_status FROM organisation "
            "WHERE is_natural_person = 'true'",
        )
        assert rows == [("ORG-0005", None, "absent")]


class TestTheDatasetItProduces:
    """What a classifier author would find, asked the way they would ask."""

    def test_every_table_is_written(self, dataset: Path) -> None:
        written = {path.parent.parent.name for path in dataset.rglob("*.parquet")}
        assert written == {table.name for table in TABLES}

    def test_every_key_is_unique(self, dataset: Path) -> None:
        # The gate that would have caught the notice UUID: run it over every
        # table rather than the one someone thought to check.
        collisions = {}
        for table in TABLES:
            key = ", ".join(table.key)
            rows = query(
                dataset,
                f"SELECT count(*), count(DISTINCT ({key})) FROM {table.name}",
            )
            total, distinct = rows[0]
            if total != distinct:
                collisions[table.name] = (total, distinct)
        assert not collisions, f"tables with duplicate keys: {collisions}"

    def test_one_notice_uuid_covers_two_publications(self, dataset: Path) -> None:
        rows = query(
            dataset,
            "SELECT source_notice_id, count(*) FROM notice "
            "GROUP BY 1 HAVING count(*) > 1",
        )
        assert rows == [("00000000-0000-0000-0000-000000000002", 2)], (
            "the sample no longer carries the duplicate-UUID case, which is the "
            "reason every table is keyed on the publication"
        )

    def test_a_withheld_bid_count_is_not_a_number(self, dataset: Path) -> None:
        rows = query(
            dataset,
            "SELECT statistic_code, statistic_value, statistic_value_status "
            "FROM lot_result_statistic ORDER BY statistic_code",
        )
        assert rows == [
            ("tenders", "2", "present"),
            ("unpublished", "-1", "withheld"),
        ]

    def test_a_withheld_amount_reads_withheld_and_keeps_what_was_published(
        self, dataset: Path
    ) -> None:
        # TEN-0002 publishes `-1` and a `win-ten-val` privacy block. The eForms
        # SDK says that code names `cbc:PayableAmount`, so the status carries
        # the deferral and the value stays exactly as published — a classifier
        # reading the status cannot mistake it for a negative sum of money.
        rows = query(
            dataset,
            "SELECT payable_amount, payable_amount_currency, payable_amount_status "
            "FROM lot_tender ORDER BY tender_id",
        )
        assert rows == [("500", "EUR", "present"), ("-1", "SEK", "withheld")]

    def test_a_privacy_block_says_what_it_qualifies(self, dataset: Path) -> None:
        rows = query(
            dataset,
            "SELECT scope_table, field_identifier_code FROM field_privacy "
            "ORDER BY field_identifier_code",
        )
        assert rows == [
            ("notice", "not-val"),
            ("lot_result", "rec-sub-cou"),
            ("lot_result", "rec-sub-typ"),
            ("lot_tender", "win-ten-val"),
        ]

    def test_repeated_paths_arrive_as_sets(self, dataset: Path) -> None:
        assert query(
            dataset,
            "SELECT contracting_system_codes FROM lot "
            "WHERE lot_id = 'LOT-0001' AND source_publication_id = "
            "'00000001-2026'",
        ) == [(["none", "none"],)]
        assert query(dataset, "SELECT tender_refs FROM settled_contract") == [
            (["TEN-0001", "TEN-0002"],)
        ]

    def test_free_text_arrives_in_the_notices_own_language(self, dataset: Path) -> None:
        rows = query(
            dataset,
            "SELECT title, title_language FROM procedure "
            "WHERE source_publication_id = '00000001-2026'",
        )
        assert rows == [("EXAMPLE PROCUREMENT OF NOTHING", "ENG")]

    def test_a_place_of_performance_is_a_row(self, dataset: Path) -> None:
        rows = query(
            dataset,
            "SELECT country_code, nuts_code, nuts_code_status FROM realized_location "
            "ORDER BY block_ordinal",
        )
        assert rows == [("SWE", None, "absent"), ("FIN", "FI1B", "present")]


class TestRerunIdentityOverTheSample:
    """Constraint 4, over a package rather than over a notice built in place."""

    def test_two_runs_are_byte_identical(self, package: Path, tmp_path: Path) -> None:
        def digest(root: Path) -> dict[str, str]:
            return {
                str(path.relative_to(root)): hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
                for path in sorted(root.rglob("*.parquet"))
            }

        first, second = tmp_path / "first", tmp_path / "second"
        normalise_package(package, first)
        normalise_package(package, second)
        assert digest(first) == digest(second)
        assert len(digest(first)) == len(TABLES)


class TestTheSampleDocumentsItself:
    """A fixture whose README stops matching it is a fixture nobody can use."""

    def test_every_notice_is_described(self) -> None:
        readme = (SAMPLE / "README.md").read_text(encoding="utf-8")
        undescribed = [name for name in sample_notices() if name not in readme]
        assert not undescribed, (
            f"data/sample/README.md does not mention {undescribed}. It says what "
            "each notice is for; a member it never mentions is one nobody knows "
            "the purpose of."
        )
