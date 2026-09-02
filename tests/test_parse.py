"""The parse stage: what it reads, what it refuses, and what it never records.

Fixtures are built in memory and are obviously synthetic per
`tests/fixtures/README.md` — impossible notice ids, `EXAMPLE BODY`, and values
like `DROPPED-CONTACT-VALUE` that could not be mistaken for a person's name.
Committing a real sample package is open-work #7, not this stage's job.

Nothing here touches the network; `tests/conftest.py` refuses a socket if it
tries.
"""

from __future__ import annotations

import io
import tarfile
from pathlib import Path
from xml.etree.ElementTree import ParseError

import pytest

from serenata.eforms import NoticeRejected
from serenata.parse import (
    NoticeParseError,
    ParsedNotice,
    parse_package,
    read_notice,
)

CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
EFAC = "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1"
EFBC = "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1"
EFEXT = "http://data.europa.eu/p27/eforms-ubl-extensions/1"

#: Deliberately not name-shaped: a fixture proving a contact is dropped must
#: not itself contain anything resembling a person.
CONTACT_VALUE = "DROPPED-CONTACT-VALUE"

LOT = "<cac:ProcurementProjectLot><cbc:ID>LOT-0001</cbc:ID></cac:ProcurementProjectLot>"


def organisation(
    *, local_id: str = "ORG-0001", natural_person: str | None = None
) -> str:
    indicator = (
        f"<efbc:NaturalPersonIndicator>{natural_person}</efbc:NaturalPersonIndicator>"
        if natural_person is not None
        else ""
    )
    return f"""
      <efac:Organization>
        {indicator}
        <efac:Company>
          <cac:PartyIdentification>
            <cbc:ID>{local_id}</cbc:ID>
          </cac:PartyIdentification>
          <cac:PartyName><cbc:Name>EXAMPLE BODY</cbc:Name></cac:PartyName>
          <cac:PartyLegalEntity>
            <cbc:CompanyID>X0000000</cbc:CompanyID>
          </cac:PartyLegalEntity>
          <cac:PostalAddress>
            <cbc:CityName>EXAMPLE CITY</cbc:CityName>
          </cac:PostalAddress>
          <cac:Contact>
            <cbc:Name>{CONTACT_VALUE}</cbc:Name>
            <cbc:ElectronicMail>{CONTACT_VALUE}</cbc:ElectronicMail>
          </cac:Contact>
        </efac:Company>
      </efac:Organization>"""


def eforms_notice(
    *,
    root: str = "ContractNotice",
    notice_id: str | None = "00000001-2026",
    organisations: str | None = None,
    results: str = "",
    lots: str = LOT,
    extra: str = "",
    beneficial_owner: bool = False,
) -> bytes:
    """A synthetic eForms notice carrying the containers the model names."""
    identifier = f"<cbc:ID>{notice_id}</cbc:ID>" if notice_id is not None else ""
    owner = (
        """
        <efac:UltimateBeneficialOwner>
          <cbc:FamilyName>MUST-NEVER-APPEAR</cbc:FamilyName>
          <cbc:ID>UBO-0001</cbc:ID>
        </efac:UltimateBeneficialOwner>"""
        if beneficial_owner
        else ""
    )
    orgs = organisation() if organisations is None else organisations
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<{root} xmlns="urn:oasis:names:specification:ubl:schema:xsd:{root}-2"
        xmlns:cac="{CAC}" xmlns:cbc="{CBC}" xmlns:ext="{EXT}"
        xmlns:efac="{EFAC}" xmlns:efbc="{EFBC}" xmlns:efext="{EFEXT}">
  {identifier}
  {lots}
  <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
    <efext:EformsExtension>
      <efac:Organizations>{orgs}{owner}</efac:Organizations>
      <efac:NoticeResult>{results}</efac:NoticeResult>
      {extra}
    </efext:EformsExtension>
  </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
</{root}>""".encode()


def parse(document: bytes) -> ParsedNotice:
    return read_notice(io.BytesIO(document))


def write_package(directory: Path, members: dict[str, bytes]) -> Path:
    package = directory / "202600157.tar.gz"
    with tarfile.open(package, "w:gz") as archive:
        for name, body in members.items():
            info = tarfile.TarInfo(f"20260817_157/{name}")
            info.size = len(body)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(body))
    return package


class TestFormatDispatch:
    """The document says what it is; the filename only claims."""

    @pytest.mark.parametrize(
        "root",
        ["ContractNotice", "ContractAwardNotice", "PriorInformationNotice"],
    )
    def test_it_reads_every_eforms_root_seen_in_a_real_package(self, root: str) -> None:
        assert parse(eforms_notice(root=root)).root_element == root

    def test_it_reads_the_business_registration_notice_namespace(self) -> None:
        # This one sits under the Publications Office's own namespace rather
        # than the OASIS UBL one; both are eForms.
        document = eforms_notice().replace(
            b"urn:oasis:names:specification:ubl:schema:xsd:ContractNotice-2",
            b"http://data.europa.eu/p27/eforms-business-registration-information-notice/1",
        )
        assert parse(document).root_element == "ContractNotice"

    def test_a_legacy_notice_is_refused_with_a_reason(self) -> None:
        with pytest.raises(NoticeRejected) as raised:
            parse(b"<?xml version='1.0'?><TED_EXPORT><FORM/></TED_EXPORT>")
        message = str(raised.value)
        assert "legacy" in message.lower()
        assert "docs/personal-data.md" in message, (
            "refusing has to say where the work that lifts it is written down"
        )

    def test_an_unrecognised_root_is_refused(self) -> None:
        with pytest.raises(NoticeRejected, match="unrecognised"):
            parse(b"<?xml version='1.0'?><SomethingElse/>")

    def test_the_root_decides_not_the_filename(self, tmp_path: Path) -> None:
        # A six-digit name is the legacy convention, but this document is
        # eForms and parses; open-work #4 asks for exactly this.
        package = write_package(tmp_path, {"123456_2022.xml": eforms_notice()})
        assert len(list(parse_package(package))) == 1


class TestRefusalsFromAdr0003:
    """Streamed, and no document type declarations."""

    def test_a_document_type_declaration_is_refused(self) -> None:
        document = eforms_notice().replace(
            b"<ContractNotice", b"<!DOCTYPE ContractNotice><ContractNotice", 1
        )
        with pytest.raises(NoticeRejected, match="document type declaration"):
            parse(document)

    def test_malformed_xml_raises(self) -> None:
        # Truncated mid-document, so the root is valid eForms and it is the
        # parser rather than the dispatch that rejects it.
        truncated = eforms_notice()[: -len("</ContractNotice>") - 20]
        with pytest.raises(ParseError):
            parse(truncated)


class TestConstraintTwo:
    """Person-carrying fields never reach a record."""

    def test_contact_values_are_never_recorded(self) -> None:
        notice = parse(eforms_notice())
        recorded = [item.value for record in notice.records for item in record.fields]
        assert CONTACT_VALUE not in recorded
        assert not any("cac:Contact" in item for item in _paths(notice))

    def test_a_beneficial_owner_subtree_is_never_recorded(self) -> None:
        notice = parse(eforms_notice(beneficial_owner=True))
        recorded = [item.value for record in notice.records for item in record.fields]
        assert "MUST-NEVER-APPEAR" not in recorded
        assert not any("UltimateBeneficialOwner" in item for item in _paths(notice))

    def test_the_organisation_name_survives_when_it_is_not_a_person(self) -> None:
        # The drop must not be so broad it removes the dataset's whole point.
        organisations = parse(eforms_notice()).of_kind("organisation")
        assert organisations[0].value("efac:Company/cac:PartyName/cbc:Name") == (
            "EXAMPLE BODY"
        )


class TestNaturalPersonSuppression:
    """A sole trader's company data is a private individual's personal data."""

    def test_identifying_values_go_when_the_indicator_is_true(self) -> None:
        notice = parse(eforms_notice(organisations=organisation(natural_person="true")))
        org = notice.of_kind("organisation")[0]
        assert org.value("efac:Company/cac:PartyName/cbc:Name") is None
        assert org.value("efac:Company/cac:PartyLegalEntity/cbc:CompanyID") is None
        assert org.value("efac:Company/cac:PostalAddress/cbc:CityName") is None

    def test_the_opaque_key_survives_so_the_record_is_anonymised_not_deleted(
        self,
    ) -> None:
        notice = parse(eforms_notice(organisations=organisation(natural_person="true")))
        org = notice.of_kind("organisation")[0]
        assert org.value("efac:Company/cac:PartyIdentification/cbc:ID") == "ORG-0001"

    def test_an_explicit_false_does_not_suppress(self) -> None:
        notice = parse(
            eforms_notice(organisations=organisation(natural_person="false"))
        )
        org = notice.of_kind("organisation")[0]
        assert org.value("efac:Company/cac:PartyName/cbc:Name") == "EXAMPLE BODY"

    def test_an_absent_indicator_is_not_a_false_one(self) -> None:
        # It is absent from about 90% of real notices. Treating absent as
        # "false" would be a guess; treating it as "true" would empty the
        # dataset. Parse does neither, and open-work #11 owns the gap.
        notice = parse(eforms_notice(organisations=organisation()))
        org = notice.of_kind("organisation")[0]
        assert org.value("efbc:NaturalPersonIndicator") is None
        assert org.value("efac:Company/cac:PartyName/cbc:Name") == "EXAMPLE BODY"


class TestRecords:
    """Containers become records; references stay fields."""

    def test_containers_become_records_with_ordinals(self) -> None:
        notice = parse(
            eforms_notice(
                organisations=organisation(local_id="ORG-0001")
                + organisation(local_id="ORG-0002")
            )
        )
        organisations = notice.of_kind("organisation")
        assert [record.ordinal for record in organisations] == [0, 1]
        assert (
            organisations[1].value("efac:Company/cac:PartyIdentification/cbc:ID")
            == "ORG-0002"
        )

    def test_a_nested_reference_is_a_field_not_a_record(self) -> None:
        # efac:LotResult/efac:LotTender names the winning tender; only
        # efac:NoticeResult/efac:LotTender is a tender in its own right.
        notice = parse(
            eforms_notice(
                results="""
                <efac:LotResult>
                  <cbc:ID>RES-0001</cbc:ID>
                  <efac:LotTender><cbc:ID>TEN-0001</cbc:ID></efac:LotTender>
                </efac:LotResult>
                <efac:LotTender><cbc:ID>TEN-0001</cbc:ID></efac:LotTender>"""
            )
        )
        assert len(notice.of_kind("lot_tender")) == 1
        result = notice.of_kind("lot_result")[0]
        assert result.value("efac:LotTender/cbc:ID") == "TEN-0001"

    def test_every_record_carries_the_source_notice_id(self) -> None:
        notice = parse(eforms_notice())
        assert notice.notice_id == "00000001-2026"
        assert notice.records
        assert all(record.notice_id == "00000001-2026" for record in notice.records)

    def test_a_notice_without_an_identifier_is_refused(self) -> None:
        with pytest.raises(NoticeRejected, match="cbc:ID"):
            parse(eforms_notice(notice_id=None))

    def test_a_blank_leaf_is_recorded_as_empty_not_missing(self) -> None:
        # No notice in OJ S 157/2026 carries one — 0 blank leaves in 897,471 —
        # but the schema permits it and ADR-0006 gives it a distinct status,
        # so the parser has to be able to produce one.
        notice = parse(
            eforms_notice(
                lots="<cac:ProcurementProjectLot><cbc:ID></cbc:ID>"
                "</cac:ProcurementProjectLot>"
            )
        )
        lot = notice.of_kind("lot")[0]
        assert lot.fields[0].path == "cbc:ID"
        assert lot.fields[0].empty is True
        assert lot.fields[0].value == ""

    def test_a_container_is_not_recorded_as_a_blank_field(self) -> None:
        # Structure is not a missing value: cac:PartyName holds cbc:Name and
        # must not appear as an empty field of its own.
        notice = parse(eforms_notice())
        assert "efac:Company/cac:PartyName" not in _paths(notice)


class TestDeterminism:
    """Constraint 4: the same notice yields the same records."""

    def test_reparsing_gives_identical_records(self) -> None:
        document = eforms_notice(
            organisations=organisation(local_id="ORG-0001")
            + organisation(local_id="ORG-0002")
        )
        assert parse(document) == parse(document)

    def test_records_are_frozen(self) -> None:
        record = parse(eforms_notice()).records[0]
        with pytest.raises(AttributeError):
            record.kind = "tampered"  # type: ignore[misc]


class TestPackages:
    """Reading an archived package, and failing loudly when one cannot be read."""

    def test_it_reads_every_notice_in_a_package(self, tmp_path: Path) -> None:
        package = write_package(
            tmp_path,
            {
                "00000001_2026.xml": eforms_notice(notice_id="00000001-2026"),
                "00000002_2026.xml": eforms_notice(notice_id="00000002-2026"),
            },
        )
        assert [notice.notice_id for notice in parse_package(package)] == [
            "00000001-2026",
            "00000002-2026",
        ]

    def test_a_bad_notice_fails_loudly_naming_the_member(self, tmp_path: Path) -> None:
        package = write_package(
            tmp_path,
            {"00000003_2026.xml": eforms_notice()[:-40]},
        )
        with pytest.raises(NoticeParseError) as raised:
            list(parse_package(package))
        assert raised.value.member.endswith("00000003_2026.xml")

    def test_a_legacy_package_is_not_silently_empty(self, tmp_path: Path) -> None:
        # The failure this guards: a 2023 package yielding zero notices and no
        # error, which looks exactly like a package with nothing in it.
        package = write_package(tmp_path, {"123456_2022.xml": b"<TED_EXPORT/>"})
        with pytest.raises(NoticeParseError, match="legacy"):
            list(parse_package(package))

    def test_non_xml_members_are_skipped(self, tmp_path: Path) -> None:
        package = write_package(
            tmp_path,
            {"README.txt": b"not a notice", "00000001_2026.xml": eforms_notice()},
        )
        assert len(list(parse_package(package))) == 1


def _paths(notice: ParsedNotice) -> set[str]:
    return {item.path for record in notice.records for item in record.fields}
