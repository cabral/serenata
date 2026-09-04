"""Reading lot outcomes out of the dataset, and the exclusions that shape them.

The rule is tested over rows built by hand; this is the other half — whether
the rows a rule receives are the right ones. Every exclusion here is argued in
`docs/hypotheses/single_bid_in_segment.md`, and each has a notice in the
fixture package that exists to be left out.

It also checks the two statements of one definition against each other. The
population is defined in SQL twice: once in `serenata.classify.dataset` where
the classifier reads it, and once in `docs/hypotheses/single_bid_in_segment.sql`
so the measured base rate can be checked without running this code. Two
statements of one definition drift, so both run here over the same dataset.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pytest

from serenata.classify import classify_dataset
from serenata.classify.dataset import read_outcomes
from serenata.normalise import normalise_package

from .support import make_notice_package, notice_xml

HYPOTHESIS_SQL = Path("docs/hypotheses/single_bid_in_segment.sql")

#: A buyer, its country, and a supplier. The country is what puts a notice in a
#: market, so it is the one organisation field that matters here.
ORGANISATIONS = """
      <efac:Organizations>
        <efac:Organization>
          <efac:Company>
            <cac:PartyIdentification>
              <cbc:ID>ORG-0001</cbc:ID>
            </cac:PartyIdentification>
            <cac:PartyName>
              <cbc:Name languageID="ENG">EXAMPLE BODY</cbc:Name>
            </cac:PartyName>
            <cac:PostalAddress>
              <cac:Country>
                <cbc:IdentificationCode>{country}</cbc:IdentificationCode>
              </cac:Country>
            </cac:PostalAddress>
          </efac:Company>
        </efac:Organization>
      </efac:Organizations>"""


def body(*, procedure: str, cpv: str, system: str) -> str:
    """A notice body carrying exactly the fields the population query reads."""
    return f"""
  <cbc:IssueDate>2026-08-13+02:00</cbc:IssueDate>
  <cbc:ContractFolderID>FOLDER-0001</cbc:ContractFolderID>
  <cac:ContractingParty>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
    </cac:Party>
  </cac:ContractingParty>
  <cac:ProcurementProject>
    <cbc:Name languageID="ENG">EXAMPLE PROCUREMENT</cbc:Name>
  </cac:ProcurementProject>
  <cac:TenderingProcess>
    <cbc:ProcedureCode>{procedure}</cbc:ProcedureCode>
  </cac:TenderingProcess>
  <cac:ProcurementProjectLot>
    <cbc:ID>LOT-0001</cbc:ID>
    <cac:ProcurementProject>
      <cac:MainCommodityClassification>
        <cbc:ItemClassificationCode>{cpv}</cbc:ItemClassificationCode>
      </cac:MainCommodityClassification>
    </cac:ProcurementProject>
    <cac:TenderingProcess>
      <cac:ContractingSystem>
        <cbc:ContractingSystemTypeCode>{system}</cbc:ContractingSystemTypeCode>
      </cac:ContractingSystem>
    </cac:TenderingProcess>
  </cac:ProcurementProjectLot>"""


def result(bids: str | None) -> str:
    """A lot outcome. ``None`` withholds the count the way eForms withholds it."""
    if bids is None:
        statistics = """
          <efac:ReceivedSubmissionsStatistics>
            <efac:FieldsPrivacy>
              <efbc:FieldIdentifierCode>rec-sub-cou</efbc:FieldIdentifierCode>
              <cbc:ReasonCode>oth-int</cbc:ReasonCode>
            </efac:FieldsPrivacy>
            <efbc:StatisticsCode>unpublished</efbc:StatisticsCode>
            <efbc:StatisticsNumeric>-1</efbc:StatisticsNumeric>
          </efac:ReceivedSubmissionsStatistics>"""
    else:
        statistics = f"""
          <efac:ReceivedSubmissionsStatistics>
            <efbc:StatisticsCode>tenders</efbc:StatisticsCode>
            <efbc:StatisticsNumeric>{bids}</efbc:StatisticsNumeric>
          </efac:ReceivedSubmissionsStatistics>"""
    return f"""
      <efac:NoticeResult>
        <efac:LotResult>
          <cbc:ID>RES-0001</cbc:ID>
          <efac:TenderLot><cbc:ID>LOT-0001</cbc:ID></efac:TenderLot>{statistics}
        </efac:LotResult>
      </efac:NoticeResult>"""


def award(
    index: int,
    *,
    bids: str | None = "4",
    country: str = "SWE",
    procedure: str = "open",
    cpv: str = "45000000",
    system: str = "none",
) -> bytes:
    """One award notice, varying only what the population query looks at."""
    return notice_xml(
        root="ContractAwardNotice",
        notice_id=f"notice-{index:04d}",
        publication_id=f"{index:08d}-2026",
        body=body(procedure=procedure, cpv=cpv, system=system),
        extension=ORGANISATIONS.format(country=country) + result(bids),
    )


@pytest.fixture(scope="module")
def dataset(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A normalised dataset with one market of 60 lots, and the exclusions.

    Sixty because the rule will not compare against a market below fifty, so a
    smaller fixture could only ever test that it stays silent.
    """
    notices = {
        f"{index:08d}_2026.xml": award(index, bids="1" if index <= 3 else "4")
        for index in range(1, 61)
    }
    notices["00000101_2026.xml"] = award(101, bids=None)
    notices["00000102_2026.xml"] = award(102, bids="0")
    notices["00000103_2026.xml"] = award(103, procedure="neg-wo-call")
    notices["00000104_2026.xml"] = award(104, system="fa-wo-rc")

    archive = tmp_path_factory.mktemp("archive")
    package = archive / "202600157.tar.gz"
    package.write_bytes(make_notice_package(notices))
    root = tmp_path_factory.mktemp("dataset")
    normalise_package(package, root)
    return root


class TestWhatTheRuleIsGiven:
    def test_it_reads_one_outcome_per_lot_result(self, dataset: Path) -> None:
        outcomes = read_outcomes(dataset)
        assert len(outcomes) == 60

    def test_every_outcome_carries_its_market_and_its_count(
        self, dataset: Path
    ) -> None:
        first = read_outcomes(dataset)[0]
        assert (first.country, first.cpv_division) == ("SWE", "45")
        assert first.bids == 1
        assert first.lot_ref == "LOT-0001"
        assert first.publication_year == "2026"

    def test_outcomes_arrive_in_a_fixed_order(self, dataset: Path) -> None:
        published = [
            outcome.source_publication_id for outcome in read_outcomes(dataset)
        ]
        assert published == sorted(published)


class TestWhatIsLeftOut:
    """Four notices in the fixture exist only to be excluded."""

    def test_a_withheld_count_is_not_read_as_a_number(self, dataset: Path) -> None:
        # Published as -1 under a privacy declaration. Reading it would make a
        # lawful deferral a negative bid count (ADR-0006).
        assert "00000101-2026" not in self.published(dataset)

    def test_no_bids_is_not_one_bid(self, dataset: Path) -> None:
        assert "00000102-2026" not in self.published(dataset)

    def test_a_procedure_with_no_call_for_competition(self, dataset: Path) -> None:
        # One bid after no call for competition is the procedure working.
        assert "00000103-2026" not in self.published(dataset)

    def test_a_framework_lot(self, dataset: Path) -> None:
        # Competition under a framework happens at call-off, which this notice
        # does not report.
        assert "00000104-2026" not in self.published(dataset)

    @staticmethod
    def published(dataset: Path) -> set[str]:
        return {outcome.source_publication_id for outcome in read_outcomes(dataset)}


class TestTheTwoStatementsOfThePopulationAgree:
    """The classifier's SQL and the hypothesis's SQL define one thing twice."""

    def test_they_select_the_same_lot_outcomes(self, dataset: Path) -> None:
        connection = duckdb.connect()
        try:
            documented = connection.sql(self.documented_population(dataset)).fetchall()
        finally:
            connection.close()

        assert documented, "the fixture must exercise the query, not just parse it"
        assert {(row[0], row[1]) for row in documented} == {
            (outcome.source_publication_id, outcome.lot_result_ordinal)
            for outcome in read_outcomes(dataset)
        }

    @staticmethod
    def documented_population(dataset: Path) -> str:
        """The hypothesis's own SQL, pointed at the fixture instead of `data/`.

        Read from the committed file rather than restated, so a change to the
        published query that nobody mirrored in the code fails here.
        """
        sql = HYPOTHESIS_SQL.read_text(encoding="utf-8")
        sql = sql.replace("data/normalised/", f"{dataset}/")
        # Everything up to the reporting queries: the views, and then a select
        # of the population itself.
        views = sql.split("-- 1.")[0]
        return (
            views + "SELECT source_publication_id, lot_result_ordinal FROM population"
        )


class TestTheStageEndToEnd:
    def test_it_flags_the_single_bids_in_a_market_where_they_are_rare(
        self, dataset: Path, tmp_path: Path
    ) -> None:
        results = classify_dataset(dataset, tmp_path)

        assert len(results) == 1
        assert results[0].rule == "single_bid_in_segment"
        assert results[0].outcomes == 60
        # Three of sixty is 5%, below the threshold, in a market of exactly 60.
        assert results[0].flags == 3

    def test_it_writes_the_flags_it_reports(
        self, dataset: Path, tmp_path: Path
    ) -> None:
        results = classify_dataset(dataset, tmp_path)
        written = [path for path in tmp_path.rglob("*.parquet")]

        assert written and list(results[0].files) == written

    def test_the_summary_says_what_a_reader_needs(
        self, dataset: Path, tmp_path: Path
    ) -> None:
        described = classify_dataset(dataset, tmp_path)[0].describe()
        assert re.search(r"single_bid_in_segment v\d+: 3 flags", described)
        assert "60 lot outcomes" in described
        assert "5.00%" in described
