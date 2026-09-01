"""The field survey: what it counts, what it refuses to count, and stability."""

from __future__ import annotations

import io
import tarfile
from xml.etree.ElementTree import ParseError

import pytest

from serenata.survey import __main__ as survey_cli
from serenata.survey.paths import (
    CHUNK_BYTES,
    ROOT,
    NoticeRejected,
    qualified_name,
    read_notice,
)
from serenata.survey.report import Survey, is_eforms, render, survey_package

CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
EFAC = "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1"


def notice_xml(
    *,
    root: str = "ContractNotice",
    subtype: str = "16",
    countries: tuple[str, ...] = ("DEU",),
    name: str = "EXAMPLE BODY",
    blank_deadline: bool = False,
) -> bytes:
    """A synthetic eForms notice, shaped like the real thing.

    Obviously synthetic per tests/fixtures/README.md: no real notice ID, and
    the only party name is EXAMPLE BODY.
    """
    parties = "".join(
        f'<cac:Country><cbc:IdentificationCode listName="country">{code}'
        "</cbc:IdentificationCode></cac:Country>"
        for code in countries
    )
    deadline = "" if blank_deadline else "2026-09-30+02:00"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<{root} xmlns="urn:oasis:names:specification:ubl:schema:xsd:{root}-2"
        xmlns:cac="{CAC}" xmlns:cbc="{CBC}" xmlns:efac="{EFAC}">
  <cbc:ID>00000001-2026</cbc:ID>
  <efac:NoticeSubType><cbc:SubTypeCode>{subtype}</cbc:SubTypeCode></efac:NoticeSubType>
  <cac:ContractingParty>
    <cac:Party>
      <cac:PartyName><cbc:Name>{name}</cbc:Name></cac:PartyName>
      <cac:PostalAddress>{parties}</cac:PostalAddress>
    </cac:Party>
  </cac:ContractingParty>
  <cac:TenderingProcess>
    <cbc:SubmissionDeadline>{deadline}</cbc:SubmissionDeadline>
  </cac:TenderingProcess>
</{root}>""".encode()


def make_package(members: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name, body in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(body)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def write_package(tmp_path, members: dict[str, bytes], name="202600157.tar.gz"):
    path = tmp_path / name
    path.write_bytes(make_package(members))
    return path


class TestQualifiedName:
    def test_it_uses_the_eforms_prefix_for_a_known_namespace(self):
        assert qualified_name(f"{{{CBC}}}IssueDate") == "cbc:IssueDate"

    def test_an_unknown_namespace_falls_back_to_the_bare_local_name(self):
        assert qualified_name("{http://example.invalid/x}Thing") == "Thing"

    def test_an_unnamespaced_tag_is_unchanged(self):
        assert qualified_name("Thing") == "Thing"


class TestReadNotice:
    def test_it_normalises_the_varying_root_so_paths_compare(self):
        award = read_notice(io.BytesIO(notice_xml(root="ContractAwardNotice")))
        contract = read_notice(io.BytesIO(notice_xml(root="ContractNotice")))

        assert award.root_type == "ContractAwardNotice"
        assert contract.root_type == "ContractNotice"
        # The same field must not look rarer merely because notice types differ.
        assert f"{ROOT}/cbc:ID" in award.valued_paths & contract.valued_paths

    def test_it_records_paths_that_carry_a_value(self):
        shape = read_notice(io.BytesIO(notice_xml()))
        assert (
            f"{ROOT}/cac:TenderingProcess/cbc:SubmissionDeadline" in shape.valued_paths
        )

    def test_a_blank_element_is_empty_not_valued(self):
        shape = read_notice(io.BytesIO(notice_xml(blank_deadline=True)))
        path = f"{ROOT}/cac:TenderingProcess/cbc:SubmissionDeadline"

        assert path in shape.empty_paths
        assert path not in shape.valued_paths

    def test_containers_are_empty_not_valued(self):
        shape = read_notice(io.BytesIO(notice_xml()))
        assert f"{ROOT}/cac:ContractingParty" in shape.empty_paths

    def test_it_reads_the_notice_subtype(self):
        assert read_notice(io.BytesIO(notice_xml(subtype="29"))).subtype == "29"

    def test_it_collects_every_country_the_notice_names(self):
        shape = read_notice(io.BytesIO(notice_xml(countries=("DEU", "FRA"))))
        assert shape.countries == frozenset({"DEU", "FRA"})

    def test_it_carries_no_field_values_into_its_output(self):
        # Constraint 2: the survey counts presence. A party name must not be
        # reachable from the result, even though the parser walked past it.
        shape = read_notice(io.BytesIO(notice_xml(name="EXAMPLE BODY")))
        rendered = repr(shape)

        assert "EXAMPLE BODY" not in rendered
        assert f"{ROOT}/cac:ContractingParty/cac:Party/cac:PartyName/cbc:Name" in (
            shape.valued_paths
        )


class TestDoctypeIsRefused:
    """ADR-0003: refusing a DTD closes internal entity expansion.

    The only attack the standard library's parser is still open to, and none of
    the 3,190 real notices in OJ S 157/2026 carries a document type declaration.
    """

    BOMB = b"""<?xml version="1.0"?><!DOCTYPE lolz [
      <!ENTITY a "AAAAAAAAAA">
      <!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
      <!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">
    ]><ContractNotice><cbc:ID xmlns:cbc="x">&c;</cbc:ID></ContractNotice>"""

    def test_an_amplifying_notice_is_refused_before_it_expands(self):
        with pytest.raises(NoticeRejected, match="document type declaration"):
            read_notice(io.BytesIO(self.BOMB))

    def test_a_plain_doctype_is_refused_too(self):
        xml = b'<?xml version="1.0"?><!DOCTYPE r><r>ok</r>'
        with pytest.raises(NoticeRejected, match="ADR-0003"):
            read_notice(io.BytesIO(xml))

    def test_an_ordinary_notice_is_not_refused(self):
        assert read_notice(io.BytesIO(notice_xml())).root_type == "ContractNotice"

    def test_a_refused_notice_is_counted_not_fatal(self, tmp_path):
        # One bad document must not abort a 3,000-notice run.
        package = write_package(
            tmp_path,
            {
                "d/00000001_2026.xml": notice_xml(),
                "d/00000002_2026.xml": self.BOMB,
            },
        )
        survey = survey_package(package)

        assert survey.notices == 1
        assert survey.unreadable == 1
        assert "1 members could not be read" in render(survey)

    def test_malformed_xml_is_counted_not_fatal(self, tmp_path):
        package = write_package(
            tmp_path,
            {
                "d/00000001_2026.xml": notice_xml(),
                "d/00000002_2026.xml": b"<unclosed>",
            },
        )
        survey = survey_package(package)

        assert survey.notices == 1
        assert survey.unreadable == 1


class TestStreaming:
    def test_a_notice_larger_than_one_chunk_parses_correctly(self):
        # The real archive holds a 40 MB notice; correctness must not depend on
        # a document fitting in a single read.
        filler = "".join(
            f"<cac:AdditionalDocumentReference><cbc:ID>D{i}</cbc:ID>"
            "</cac:AdditionalDocumentReference>"
            for i in range(4000)
        )
        xml = notice_xml().replace(
            b"</cac:TenderingProcess>",
            f"</cac:TenderingProcess>{filler}".encode(),
        )
        assert len(xml) > CHUNK_BYTES, "fixture must span more than one chunk"

        shape = read_notice(io.BytesIO(xml))

        assert f"{ROOT}/cbc:ID" in shape.valued_paths
        assert f"{ROOT}/cac:AdditionalDocumentReference/cbc:ID" in shape.valued_paths

    def test_a_document_with_no_root_is_a_parse_error(self):
        with pytest.raises(ParseError):
            read_notice(io.BytesIO(b""))


class TestIsEforms:
    @pytest.mark.parametrize(
        ("name", "expected"),
        [
            ("20260817_157/00566631_2026.xml", True),
            ("20260817_157/123456_2022.xml", False),
            ("20260817_157/notanumber_2026.xml", False),
        ],
    )
    def test_eforms_filenames_carry_eight_digits(self, name, expected):
        assert is_eforms(name) is expected


class TestSurveyPackage:
    def test_it_counts_notices_and_their_shapes(self, tmp_path):
        package = write_package(
            tmp_path,
            {
                "20260817_157/00000001_2026.xml": notice_xml(),
                "20260817_157/00000002_2026.xml": notice_xml(
                    root="ContractAwardNotice"
                ),
            },
        )
        survey = survey_package(package)

        assert survey.notices == 2
        assert survey.root_types["ContractNotice"] == 1
        assert survey.root_types["ContractAwardNotice"] == 1
        assert survey.valued[f"{ROOT}/cbc:ID"] == 2

    def test_legacy_ted_notices_are_counted_not_silently_dropped(self, tmp_path):
        package = write_package(
            tmp_path,
            {
                "20260817_157/00000001_2026.xml": notice_xml(),
                "20260817_157/123456_2022.xml": b"<TED_EXPORT/>",
            },
        )
        survey = survey_package(package)

        assert survey.notices == 1
        assert survey.skipped_legacy == 1

    def test_non_xml_members_are_ignored(self, tmp_path):
        package = write_package(
            tmp_path,
            {
                "20260817_157/00000001_2026.xml": notice_xml(),
                "20260817_157/README.txt": b"not a notice",
            },
        )
        assert survey_package(package).notices == 1

    def test_several_packages_accumulate_into_one_survey(self, tmp_path):
        first = write_package(
            tmp_path, {"d/00000001_2026.xml": notice_xml()}, "a.tar.gz"
        )
        second = write_package(
            tmp_path, {"d/00000002_2026.xml": notice_xml()}, "b.tar.gz"
        )

        survey = Survey()
        survey_package(first, into=survey)
        survey_package(second, into=survey)

        assert survey.notices == 2
        assert survey.packages == ["a.tar.gz", "b.tar.gz"]

    def test_presence_is_the_share_of_notices_carrying_a_value(self, tmp_path):
        package = write_package(
            tmp_path,
            {
                "d/00000001_2026.xml": notice_xml(),
                "d/00000002_2026.xml": notice_xml(blank_deadline=True),
            },
        )
        survey = survey_package(package)

        assert (
            survey.presence(f"{ROOT}/cac:TenderingProcess/cbc:SubmissionDeadline")
            == 0.5
        )
        assert survey.presence(f"{ROOT}/cbc:ID") == 1.0

    def test_presence_of_an_unseen_path_is_zero(self):
        assert Survey().presence("notice/nothing") == 0.0

    def test_a_path_records_the_countries_that_populate_it(self, tmp_path):
        package = write_package(
            tmp_path,
            {
                "d/00000001_2026.xml": notice_xml(countries=("DEU",)),
                "d/00000002_2026.xml": notice_xml(countries=("FRA",)),
            },
        )
        survey = survey_package(package)

        assert survey.path_countries[f"{ROOT}/cbc:ID"] == {"DEU", "FRA"}


class TestRender:
    def test_the_report_is_byte_identical_across_runs(self, tmp_path):
        # Constraint 4. The data model cites these numbers; a report that
        # changed between runs would be worse than no report.
        package = write_package(
            tmp_path,
            {
                "d/00000001_2026.xml": notice_xml(countries=("DEU", "FRA")),
                "d/00000002_2026.xml": notice_xml(root="ContractAwardNotice"),
            },
        )
        assert render(survey_package(package)) == render(survey_package(package))

    def test_it_carries_no_timestamp(self, tmp_path):
        package = write_package(tmp_path, {"d/00000001_2026.xml": notice_xml()})
        document = render(survey_package(package))

        assert "2026-09" not in document.split("## Field usage")[0].replace(
            "202600157", ""
        ), "provenance is the package and its checksum, never a generation clock"

    def test_it_carries_the_ted_attribution(self, tmp_path):
        # Reuse of TED data is conditioned on acknowledging the source
        # (Commission Decision 2011/833/EU). Generated, not pasted, so that
        # regenerating the report cannot quietly drop the acknowledgement.
        package = write_package(tmp_path, {"d/00000001_2026.xml": notice_xml()})
        document = render(survey_package(package))

        assert "© European Union" in document
        assert "2011/833/EU" in document
        assert "ted.europa.eu" in document

    def test_it_reports_what_was_surveyed(self, tmp_path):
        package = write_package(
            tmp_path,
            {
                "d/00000001_2026.xml": notice_xml(),
                "d/123456_2022.xml": b"<TED_EXPORT/>",
            },
        )
        document = render(survey_package(package))

        assert "1 eForms notices" in document
        assert "1 legacy TED schema notices skipped" in document
        assert "202600157.tar.gz" in document

    def test_it_separates_populated_paths_from_never_populated_ones(self, tmp_path):
        package = write_package(
            tmp_path, {"d/00000001_2026.xml": notice_xml(blank_deadline=True)}
        )
        document = render(survey_package(package))
        usage, never = document.split("## Never populated")

        assert "cbc:ID" in usage
        assert "cbc:SubmissionDeadline" in never

    def test_an_empty_survey_renders_without_dividing_by_zero(self):
        document = render(Survey())
        assert "0 eForms notices" in document


class TestCli:
    def test_it_writes_a_report_and_exits_zero(self, tmp_path, capsys):
        package = write_package(tmp_path, {"d/00000001_2026.xml": notice_xml()})
        out = tmp_path / "field-usage.md"

        code = survey_cli.main([str(package), "-o", str(out)])

        assert code == 0
        assert "# eForms field usage" in out.read_text(encoding="utf-8")

    def test_without_an_output_path_it_prints_the_report(self, tmp_path, capsys):
        package = write_package(tmp_path, {"d/00000001_2026.xml": notice_xml()})

        assert survey_cli.main([str(package)]) == 0
        assert "# eForms field usage" in capsys.readouterr().out

    def test_a_missing_package_is_an_error(self, tmp_path, capsys):
        code = survey_cli.main([str(tmp_path / "absent.tar.gz")])

        assert code == 2
        assert "no such package" in capsys.readouterr().err

    def test_a_package_with_no_eforms_notices_is_an_error(self, tmp_path, capsys):
        package = write_package(tmp_path, {"d/123456_2022.xml": b"<TED_EXPORT/>"})

        assert survey_cli.main([str(package)]) == 1
        assert "no eForms notices" in capsys.readouterr().err

    def test_packages_are_surveyed_in_sorted_order(self, tmp_path):
        # A shell glob's order must not change the report.
        b = write_package(tmp_path, {"d/00000002_2026.xml": notice_xml()}, "b.tar.gz")
        a = write_package(tmp_path, {"d/00000001_2026.xml": notice_xml()}, "a.tar.gz")
        out = tmp_path / "report.md"

        survey_cli.main([str(b), str(a), "-o", str(out)])

        document = out.read_text(encoding="utf-8")
        assert document.index("a.tar.gz") < document.index("b.tar.gz")
