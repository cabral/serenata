"""The normalise stage: what each table's rows say, and what they refuse to say.

Fixtures are built in memory and are obviously synthetic per
`tests/fixtures/README.md` — impossible publication numbers, `EXAMPLE BODY`,
`ORG-0001`. Nothing here touches the network; `tests/conftest.py` refuses a
socket if it tries.

The cases worth reading first are the ones that cost something to get wrong:
a withheld bid count must not read as a number, a sole trader's name must not
reach a row, and a column that meets several values must not pick one.
"""

from __future__ import annotations

import io
from typing import Any

import pytest

from serenata.normalise import Status, notice_rows, publication_year
from serenata.normalise.dataset import normalise_notices
from serenata.normalise.rows import RepeatedValue
from serenata.parse import ParsedNotice, read_notice

from .support import SYNTHETIC_NOTICE_ID, SYNTHETIC_PUBLICATION, notice_xml

ORGANISATIONS = """
      <efac:Organizations>
        <efac:Organization>
          <efac:Company>
            <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
            <cac:PartyName>
              <cbc:Name languageID="ENG">EXAMPLE BODY</cbc:Name>
            </cac:PartyName>
            <cac:PartyLegalEntity>
              <cbc:CompanyID>X0000001</cbc:CompanyID>
            </cac:PartyLegalEntity>
            <cac:PartyLegalEntity>
              <cbc:CompanyID>X0000002</cbc:CompanyID>
            </cac:PartyLegalEntity>
            <cac:PostalAddress>
              <cbc:CityName>EXAMPLE CITY</cbc:CityName>
            </cac:PostalAddress>
          </efac:Company>
        </efac:Organization>
        <efac:Organization>
          <efbc:NaturalPersonIndicator>true</efbc:NaturalPersonIndicator>
          <efac:Company>
            <cac:PartyIdentification><cbc:ID>ORG-0002</cbc:ID></cac:PartyIdentification>
            <cac:PartyName><cbc:Name>MUST-NEVER-APPEAR</cbc:Name></cac:PartyName>
            <cac:PartyLegalEntity>
              <cbc:CompanyID>MUST-NEVER-APPEAR</cbc:CompanyID>
            </cac:PartyLegalEntity>
          </efac:Company>
        </efac:Organization>
      </efac:Organizations>"""

RESULTS = """
      <efac:NoticeResult>
        <efac:LotResult>
          <cbc:ID>RES-0001</cbc:ID>
          <efac:TenderLot><cbc:ID>LOT-0001</cbc:ID></efac:TenderLot>
          <efac:LotTender><cbc:ID>TEN-0001</cbc:ID></efac:LotTender>
          <efac:LotTender><cbc:ID>TEN-0002</cbc:ID></efac:LotTender>
          <cbc:HigherTenderAmount currencyID="SEK">1000</cbc:HigherTenderAmount>
          <efac:ReceivedSubmissionsStatistics>
            <efbc:StatisticsCode>tenders</efbc:StatisticsCode>
            <efbc:StatisticsNumeric>3</efbc:StatisticsNumeric>
          </efac:ReceivedSubmissionsStatistics>
          <efac:ReceivedSubmissionsStatistics>
            <efac:FieldsPrivacy>
              <efbc:FieldIdentifierCode>rec-sub-cou</efbc:FieldIdentifierCode>
              <cbc:ReasonCode>oth-int</cbc:ReasonCode>
            </efac:FieldsPrivacy>
            <efbc:StatisticsCode>unpublished</efbc:StatisticsCode>
            <efbc:StatisticsNumeric>-1</efbc:StatisticsNumeric>
          </efac:ReceivedSubmissionsStatistics>
        </efac:LotResult>
        <efac:LotTender>
          <cbc:ID>TEN-0001</cbc:ID>
          <cac:LegalMonetaryTotal>
            <cbc:PayableAmount currencyID="EUR">500</cbc:PayableAmount>
          </cac:LegalMonetaryTotal>
        </efac:LotTender>
        <efac:TenderingParty>
          <cbc:ID>TPA-0001</cbc:ID>
          <efac:Tenderer>
            <cbc:ID>ORG-0002</cbc:ID>
            <efbc:GroupLeadIndicator>true</efbc:GroupLeadIndicator>
          </efac:Tenderer>
          <efac:Tenderer><cbc:ID>ORG-0003</cbc:ID></efac:Tenderer>
        </efac:TenderingParty>
        <efac:SettledContract>
          <cbc:ID>CON-0001</cbc:ID>
          <efac:LotTender><cbc:ID>TEN-0001</cbc:ID></efac:LotTender>
          <efac:LotTender><cbc:ID>TEN-0002</cbc:ID></efac:LotTender>
          <cac:SignatoryParty>
            <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
          </cac:SignatoryParty>
        </efac:SettledContract>
        <efac:FieldsPrivacy>
          <efbc:FieldIdentifierCode>not-val</efbc:FieldIdentifierCode>
          <cbc:ReasonCode>eo-int</cbc:ReasonCode>
        </efac:FieldsPrivacy>
      </efac:NoticeResult>"""

BODY = """
  <cbc:IssueDate>2026-08-13+02:00</cbc:IssueDate>
  <cbc:ContractFolderID>FOLDER-0001</cbc:ContractFolderID>
  <cac:ContractingParty>
    <cac:ContractingPartyType><cbc:PartyTypeCode>body-pl</cbc:PartyTypeCode></cac:ContractingPartyType>
    <cac:ContractingActivity><cbc:ActivityTypeCode>gen-pub</cbc:ActivityTypeCode></cac:ContractingActivity>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID>ORG-0001</cbc:ID></cac:PartyIdentification>
    </cac:Party>
  </cac:ContractingParty>
  <cac:ContractingParty>
    <cac:ContractingPartyType><cbc:PartyTypeCode>ra</cbc:PartyTypeCode></cac:ContractingPartyType>
    <cac:Party>
      <cac:PartyIdentification><cbc:ID>ORG-0003</cbc:ID></cac:PartyIdentification>
    </cac:Party>
  </cac:ContractingParty>
  <cac:ProcurementProject>
    <cbc:Name languageID="ENG">EXAMPLE PROCUREMENT</cbc:Name>
    <cbc:Name languageID="FRA">EXEMPLE DE MARCHE</cbc:Name>
    <cbc:Description></cbc:Description>
    <cac:RealizedLocation>
      <cac:Address>
        <cac:Country><cbc:IdentificationCode>SWE</cbc:IdentificationCode></cac:Country>
      </cac:Address>
    </cac:RealizedLocation>
    <cac:RealizedLocation>
      <cac:Address>
        <cac:Country><cbc:IdentificationCode>FIN</cbc:IdentificationCode></cac:Country>
        <cbc:CountrySubentityCode>FI1B</cbc:CountrySubentityCode>
      </cac:Address>
    </cac:RealizedLocation>
  </cac:ProcurementProject>
  <cac:ProcurementProjectLot>
    <cbc:ID>LOT-0001</cbc:ID>
    <cac:TenderingProcess>
      <cac:ContractingSystem>
        <cbc:ContractingSystemTypeCode>none</cbc:ContractingSystemTypeCode>
      </cac:ContractingSystem>
      <cac:ContractingSystem>
        <cbc:ContractingSystemTypeCode>fa-wo-rc</cbc:ContractingSystemTypeCode>
      </cac:ContractingSystem>
    </cac:TenderingProcess>
    <cac:TenderingTerms>
      <cac:AppealTerms>
        <cac:AppealReceiverParty>
          <cac:PartyIdentification><cbc:ID>ORG-0003</cbc:ID></cac:PartyIdentification>
        </cac:AppealReceiverParty>
      </cac:AppealTerms>
    </cac:TenderingTerms>
  </cac:ProcurementProjectLot>"""


def notice(**kwargs: Any) -> ParsedNotice:
    """Parse a synthetic notice carrying the fixture above unless told otherwise."""
    document = notice_xml(
        body=kwargs.pop("body", BODY),
        extension=kwargs.pop("extension", ORGANISATIONS + RESULTS),
        **kwargs,
    )
    return read_notice(io.BytesIO(document))


def rows(table: str, **kwargs: Any) -> list[dict[str, Any]]:
    return notice_rows(notice(**kwargs))[table]


def only(table: str, **kwargs: Any) -> dict[str, Any]:
    found = rows(table, **kwargs)
    assert len(found) == 1, f"expected one {table} row, got {len(found)}"
    return found[0]


class TestIdentity:
    """Every row says which publication it came from."""

    def test_every_row_carries_the_publication_and_the_notice(self) -> None:
        produced = notice_rows(notice())
        assert produced["notice"], "the fixture produced no rows at all"
        for name, table_rows in produced.items():
            for row in table_rows:
                assert row["source_publication_id"] == SYNTHETIC_PUBLICATION, name
                assert row["source_notice_id"] == SYNTHETIC_NOTICE_ID, name
                assert row["publication_year"] == "2026", name

    def test_the_partition_comes_from_the_notice(self) -> None:
        assert publication_year(notice(publication_date="2019-01-01+01:00")) == "2019"

    def test_a_notice_without_a_readable_date_is_still_partitioned(self) -> None:
        # Dropping it would be worse: a notice that cannot say when it was
        # published is still archived, and the partition names the gap.
        assert publication_year(notice(publication_date="")) == "unknown"
        assert publication_year(notice(publication_date="not-a-date")) == "unknown"

    def test_the_notice_row_carries_its_root_element(self) -> None:
        row = only("notice", root="ContractAwardNotice")
        assert row["root_element"] == "ContractAwardNotice"
        assert row["root_element_status"] == Status.PRESENT


class TestAbsenceIsRecorded:
    """ADR-0006: four causes of a missing value, four different statuses."""

    def test_a_value_that_is_there_is_present(self) -> None:
        row = only("notice")
        assert row["issue_date"] == "2026-08-13+02:00"
        assert row["issue_date_status"] == Status.PRESENT

    def test_a_blank_element_is_empty_not_absent(self) -> None:
        row = only("procedure")
        assert row["description"] == ""
        assert row["description_status"] == Status.EMPTY

    def test_a_missing_element_is_absent(self) -> None:
        row = only("notice")
        assert row["changed_notice_id"] is None
        assert row["changed_notice_id_status"] == Status.ABSENT

    def test_a_withheld_statistic_is_not_a_number(self) -> None:
        # The failure this whole design exists to prevent: a publisher's lawful
        # deferral read as a bid count of -1.
        statistics = rows("lot_result_statistic")
        withheld = [r for r in statistics if r["statistic_code"] == "unpublished"]
        assert len(withheld) == 1
        assert withheld[0]["statistic_value"] == "-1"
        assert withheld[0]["statistic_value_status"] == Status.WITHHELD
        assert withheld[0]["statistic_code_status"] == Status.WITHHELD

    def test_a_published_statistic_keeps_its_code_and_number(self) -> None:
        statistics = rows("lot_result_statistic")
        counted = [r for r in statistics if r["statistic_code"] == "tenders"]
        assert len(counted) == 1
        assert counted[0]["statistic_value"] == "3"
        assert counted[0]["statistic_value_status"] == Status.PRESENT
        assert counted[0]["statistic_kind"] == "received_submissions"


class TestConstraintTwo:
    """A sole trader's identifying values never reach a row."""

    def test_a_natural_person_keeps_only_the_key(self) -> None:
        organisations = rows("organisation")
        person = [r for r in organisations if r["is_natural_person"] == "true"]
        assert len(person) == 1
        assert person[0]["org_local_id"] == "ORG-0002"
        assert person[0]["name"] is None
        assert person[0]["name_status"] == Status.ABSENT
        assert person[0]["company_ids"] == []

    def test_nothing_in_any_row_carries_the_suppressed_value(self) -> None:
        produced = notice_rows(notice())
        for table_rows in produced.values():
            for row in table_rows:
                for value in row.values():
                    values = value if isinstance(value, list) else [value]
                    assert "MUST-NEVER-APPEAR" not in [
                        v for v in values if isinstance(v, str)
                    ]


class TestRepeatedValues:
    """ADR-0007: carried as a set, as a row, or by language — never picked."""

    def test_a_repeated_code_becomes_a_set(self) -> None:
        row = only("lot")
        assert row["contracting_system_codes"] == ["none", "fa-wo-rc"]
        assert row["contracting_system_codes_status"] == Status.PRESENT

    def test_an_absent_set_is_empty_and_says_so(self) -> None:
        # The second organisation carries no registration number at all — an
        # empty list, and a status saying the path was never there.
        row = rows("organisation")[1]
        assert row["company_ids"] == []
        assert row["company_ids_status"] == Status.ABSENT

    def test_repeated_references_are_all_kept(self) -> None:
        assert only("lot_result")["winning_tender_refs"] == ["TEN-0001", "TEN-0002"]
        assert only("settled_contract")["tender_refs"] == ["TEN-0001", "TEN-0002"]
        assert rows("organisation")[0]["company_ids"] == ["X0000001", "X0000002"]

    def test_free_text_takes_the_notices_own_language(self) -> None:
        row = only("procedure")
        assert row["title"] == "EXAMPLE PROCUREMENT"
        assert row["title_language"] == "ENG"

    def test_another_notice_language_takes_the_other_rendering(self) -> None:
        row = only("procedure", language="FRA")
        assert row["title"] == "EXEMPLE DE MARCHE"
        assert row["title_language"] == "FRA"

    def test_a_language_the_notice_does_not_offer_falls_back_to_the_first(
        self,
    ) -> None:
        row = only("procedure", language="SWE")
        assert row["title"] == "EXAMPLE PROCUREMENT"
        assert row["title_language"] == "ENG"

    def test_a_scalar_column_refuses_to_pick_one_of_several(self) -> None:
        repeated = BODY.replace(
            "<cbc:IssueDate>2026-08-13+02:00</cbc:IssueDate>",
            "<cbc:IssueDate>2026-08-13+02:00</cbc:IssueDate>"
            "<cbc:IssueDate>2026-08-14+02:00</cbc:IssueDate>",
        )
        with pytest.raises(RepeatedValue) as raised:
            notice_rows(notice(body=repeated))
        assert "issue_date" in str(raised.value)
        assert "cbc:IssueDate" in str(raised.value)

    def test_a_notice_that_does_not_map_is_named_rather_than_dropped(self) -> None:
        repeated = BODY.replace(
            "<cbc:IssueDate>2026-08-13+02:00</cbc:IssueDate>",
            "<cbc:IssueDate>2026-08-13+02:00</cbc:IssueDate>"
            "<cbc:IssueDate>2026-08-14+02:00</cbc:IssueDate>",
        )
        dataset, refused = normalise_notices([notice(), notice(body=repeated)])
        assert len(refused) == 1
        assert refused[0].notice_id == SYNTHETIC_NOTICE_ID
        assert "issue_date" in refused[0].reason
        # The good notice still made it: one bad notice does not cost the rest.
        assert len(dataset.rows["notice"]) == 1


class TestAmounts:
    """An amount without its currency is a number, not a sum of money."""

    def test_the_currency_travels_with_the_amount(self) -> None:
        assert only("lot_tender")["payable_amount"] == "500"
        assert only("lot_tender")["payable_amount_currency"] == "EUR"
        assert only("lot_result")["highest_tender_amount_currency"] == "SEK"

    def test_an_absent_amount_has_no_currency(self) -> None:
        row = only("lot_result")
        assert row["lowest_tender_amount"] is None
        assert row["lowest_tender_amount_currency"] is None
        assert row["lowest_tender_amount_status"] == Status.ABSENT


class TestRoles:
    """An organisation's role is an edge, and its qualifiers stay with it."""

    def roles(self, name: str) -> list[dict[str, Any]]:
        return [r for r in rows("organisation_role") if r["role"] == name]

    def test_each_buyer_keeps_its_own_type_and_activity(self) -> None:
        buyers = {r["org_ref"]: r for r in self.roles("buyer")}
        assert set(buyers) == {"ORG-0001", "ORG-0003"}
        assert buyers["ORG-0001"]["buyer_type_code"] == "body-pl"
        assert buyers["ORG-0001"]["buyer_activity_code"] == "gen-pub"
        assert buyers["ORG-0003"]["buyer_type_code"] == "ra"
        # The second contracting party carries no activity: absent, not the
        # first buyer's value leaking across the block boundary.
        assert buyers["ORG-0003"]["buyer_activity_code"] is None
        assert buyers["ORG-0003"]["buyer_activity_code_status"] == Status.ABSENT

    def test_a_group_lead_stays_with_the_tenderer_it_qualifies(self) -> None:
        tenderers = {r["org_ref"]: r for r in self.roles("tenderer")}
        assert tenderers["ORG-0002"]["is_group_lead"] == "true"
        assert tenderers["ORG-0003"]["is_group_lead"] is None

    def test_a_role_says_which_record_referenced_it(self) -> None:
        appeal = self.roles("appeal_receiver")
        assert [r["scope_table"] for r in appeal] == ["lot"]
        assert appeal[0]["org_ref"] == "ORG-0003"
        signatory = self.roles("contract_signatory")
        assert [r["scope_table"] for r in signatory] == ["settled_contract"]

    def test_a_qualifier_of_another_role_is_absent_not_blank(self) -> None:
        appeal = self.roles("appeal_receiver")[0]
        assert appeal["buyer_type_code"] is None
        assert appeal["buyer_type_code_status"] == Status.ABSENT

    def test_role_rows_are_keyed_uniquely(self) -> None:
        produced = rows("organisation_role")
        keys = {
            (r["role"], r["scope_table"], r["scope_ordinal"], r["block_ordinal"])
            for r in produced
        }
        assert len(keys) == len(produced)


class TestBlocks:
    """A repeatable block becomes rows, and the pairing inside it survives."""

    def test_each_place_of_performance_is_a_row(self) -> None:
        locations = rows("realized_location")
        assert [r["country_code"] for r in locations] == ["SWE", "FIN"]
        assert [r["block_ordinal"] for r in locations] == [0, 1]
        assert locations[0]["nuts_code"] is None
        assert locations[0]["nuts_code_status"] == Status.ABSENT
        assert locations[1]["nuts_code"] == "FI1B"
        assert {r["scope_table"] for r in locations} == {"procedure"}

    def test_a_privacy_block_says_what_it_sits_inside(self) -> None:
        privacy = rows("field_privacy")
        scopes = {r["scope_path"].rsplit("/", 1)[-1]: r for r in privacy}
        assert set(scopes) == {
            "efac:NoticeResult",
            "efac:ReceivedSubmissionsStatistics",
        }
        assert scopes["efac:NoticeResult"]["field_identifier_code"] == "not-val"
        assert scopes["efac:NoticeResult"]["reason_code"] == "eo-int"
        assert scopes["efac:NoticeResult"]["scope_table"] == "notice"
        statistics = scopes["efac:ReceivedSubmissionsStatistics"]
        assert statistics["scope_table"] == "lot_result"
        assert statistics["field_identifier_code"] == "rec-sub-cou"

    def test_a_notice_with_no_privacy_block_produces_no_rows(self) -> None:
        assert rows("field_privacy", extension=ORGANISATIONS) == []


class TestEveryTableIsProduced:
    """The fixture exercises all twelve tables rather than the easy nine."""

    def test_the_fixture_fills_every_table(self) -> None:
        produced = notice_rows(notice())
        empty = sorted(name for name, table_rows in produced.items() if not table_rows)
        assert not empty, (
            f"the fixture produces no rows for {empty}; a table with no test "
            "data is a table with no test."
        )
