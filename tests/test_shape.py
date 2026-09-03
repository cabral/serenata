"""The dataset-shape report: what it counts, and what it must never print.

`docs/dataset-shape.md` is generated from archived packages and is where this
repository's claims about its own output live — row counts, how populated each
column is, how many withheld sentinels there are, and how often a contact
address turned up in a field that is not a contact field. Before it existed
those numbers were measured by hand with scripts nobody committed.

Two properties matter more than the arithmetic. It is **deterministic**, or it
cannot be cited. And it reports **counts and never values**, because the leak it
measures is personal data: a report that printed what it found would publish the
thing it exists to warn about.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from serenata.survey import __main__ as survey_cli
from serenata.survey.shape import Shape, checksum, render, shape_package

from .support import sample_notices, sample_package


@pytest.fixture(scope="module")
def measured(tmp_path_factory: pytest.TempPathFactory) -> Shape:
    package = sample_package(tmp_path_factory.mktemp("archive"))
    shape = shape_package(package)
    shape.finish()
    return shape


class TestWhatItCounts:
    """Every number the report carries, over a package whose cases are known."""

    def test_it_counts_the_notices_it_could_and_could_not_use(
        self, measured: Shape
    ) -> None:
        assert measured.notices == 4
        # The legacy notice and the damaged one. A report that quietly counted
        # four notices from a six-member package would overstate its coverage.
        assert measured.unparsed == 2
        assert measured.unnormalised == 0

    def test_it_counts_rows_per_table(self, measured: Shape) -> None:
        assert measured.rows["notice"] == 4
        assert measured.rows["lot_result_statistic"] == 2
        assert measured.rows["realized_location"] == 2

    def test_no_table_has_rows_sharing_a_key(self, measured: Shape) -> None:
        assert measured.key_collisions == {}

    def test_it_finds_the_notice_uuid_that_is_not_unique(self, measured: Shape) -> None:
        assert measured.repeated_notice_ids == 1

    def test_it_finds_the_withheld_sentinels(self, measured: Shape) -> None:
        assert measured.sentinels["lot_tender.payable_amount"] == 1
        assert measured.sentinels["lot_result_statistic.statistic_value"] == 1

    def test_it_finds_addresses_in_fields_that_are_not_contact_fields(
        self, measured: Shape
    ) -> None:
        # The sample carries two: one in a city, one in a lot description. Only
        # the first is shaped like a person's own address.
        assert measured.contact_shaped["organisation.city"] == 1
        assert measured.personal_shaped["organisation.city"] == 1
        assert measured.contact_shaped["lot.description"] == 1
        assert measured.personal_shaped["lot.description"] == 0

    def test_it_reports_how_populated_a_column_is(self, measured: Shape) -> None:
        statuses = measured.statuses["lot_result_statistic.statistic_value"]
        assert statuses["present"] == 1
        assert statuses["withheld"] == 1


class TestWhatItMustNeverPrint:
    """A report that printed what it found would publish it."""

    def test_no_field_value_appears_in_the_document(self, measured: Shape) -> None:
        document = render(measured)
        for value in (
            "firstname.lastname@example.invalid",
            "office@example.invalid",
            "EXAMPLE BUYING BODY",
            "MUST-NEVER-APPEAR",
            "DROPPED-CONTACT-VALUE",
        ):
            assert value not in document, value

    def test_the_check_can_actually_fail(self) -> None:
        # Those values have to be in the sample for the assertion above to mean
        # anything.
        carried = b"".join(sample_notices().values()).decode()
        assert "firstname.lastname@example.invalid" in carried
        assert "EXAMPLE BUYING BODY" in carried


class TestItCanBeCited:
    """A measurement that moves between runs is not a citation."""

    def test_the_same_package_renders_the_same_document(self, tmp_path: Path) -> None:
        package = sample_package(tmp_path)
        first, second = shape_package(package), shape_package(package)
        first.finish()
        second.finish()
        assert render(first) == render(second)

    def test_it_records_what_it_measured(self, measured: Shape) -> None:
        document = render(measured)
        name, digest = measured.packages[0]
        assert name in document
        assert f"sha256:{digest}" in document
        assert len(digest) == 64

    def test_the_checksum_is_of_the_package(self, tmp_path: Path) -> None:
        package = sample_package(tmp_path)
        other = tmp_path / "other.tar.gz"
        other.write_bytes(package.read_bytes() + b"trailing")
        assert checksum(package) != checksum(other)

    def test_an_empty_measurement_still_renders(self) -> None:
        # Nothing measured is a legitimate answer, and a renderer that fell over
        # on it would be a renderer nobody could run on a fresh checkout.
        shape = Shape()
        shape.finish()
        document = render(shape)
        assert "No column in these packages carries the `-1` sentinel." in document
        assert "0 notices" in document.replace("**", "")


class TestTheCommand:
    """`python -m serenata.survey --report shape`."""

    def test_it_writes_the_report(self, tmp_path: Path, capsys) -> None:
        package = sample_package(tmp_path)
        output = tmp_path / "shape.md"

        code = survey_cli.main([str(package), "--report", "shape", "-o", str(output)])

        assert code == 0
        assert "# Dataset shape" in output.read_text(encoding="utf-8")
        assert "measured" in capsys.readouterr().err

    def test_the_default_report_is_still_the_field_survey(
        self, tmp_path: Path, capsys
    ) -> None:
        package = sample_package(tmp_path)
        assert survey_cli.main([str(package)]) == 0
        assert "# eForms field usage" in capsys.readouterr().out

    def test_a_package_with_no_eforms_notices_is_an_error(
        self, tmp_path: Path, capsys
    ) -> None:
        from .support import make_notice_package

        empty = tmp_path / "empty.tar.gz"
        empty.write_bytes(make_notice_package({"000001_2026.xml": b"<TED_EXPORT/>"}))

        assert survey_cli.main([str(empty), "--report", "shape"]) == 1
        assert "no eForms notices" in capsys.readouterr().err
