"""Withheld fields: turning a publisher's privacy code into a column.

eForms publishes a placeholder rather than omitting a withheld value — an
amount as `-1`, a bid count as the code `unpublished` with the number `-1` —
and names what it withheld with a code in `efac:FieldsPrivacy`. Until the code
could be resolved to a column, a withheld amount read `present` with the value
`-1`, and every classifier reading an amount had to remember to exclude it by
hand. ADR-0006 exists so that forgetting is impossible; this is the half that
was missing.

`serenata/normalise/sdk_privacy.py` is the eForms SDK's own answer to which
field a code names, vendored so the stage stays offline (ADR-0008), and
`serenata/normalise/privacy.py` joins it onto this model's columns.

**The refusals matter as much as the mappings.** `pro-acc` and `dir-awa-jus`
name the same element and are told apart only by an XPath predicate this
project's paths do not carry, so acting on either would mark a column
non-public on the strength of a guess. There are tests below for both
directions, because a mapping that silently over-reaches is worse than one that
covers less.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow.parquet as pq
import pytest

from serenata.normalise import Status, normalise_package, sdk_privacy
from serenata.normalise import privacy as privacy_module
from serenata.normalise.model import TABLES, Kind, table
from serenata.normalise.privacy import (
    BLOCK_TARGETS,
    RECORD_TARGETS,
    UNUSABLE,
    Target,
    _resolve,
    covers,
)
from serenata.normalise.sdk_privacy import PRIVACY_FIELDS, SDK_VERSIONS, PrivacyField

from .support import SYNTHETIC_NOTICE, make_notice_package
from .test_normalise import ORGANISATIONS, rows
from .test_personal_data import website_notice

#: A lot result whose statistics block withholds only the count, not the code
#: it counts. Real notices withhold both together — both blocks measured in
#: OJ S 157/2026 carry both codes — so this is the case that separates "the
#: SDK told us which column" from "something inside the block was withheld".
COUNT_ONLY = """
      <efac:NoticeResult>
        <efac:LotResult>
          <cbc:ID>RES-0001</cbc:ID>
          <efac:ReceivedSubmissionsStatistics>
            <efac:FieldsPrivacy>
              <efbc:FieldIdentifierCode>rec-sub-cou</efbc:FieldIdentifierCode>
              <cbc:ReasonCode>oth-int</cbc:ReasonCode>
            </efac:FieldsPrivacy>
            <efbc:StatisticsCode>tenders</efbc:StatisticsCode>
            <efbc:StatisticsNumeric>-1</efbc:StatisticsNumeric>
          </efac:ReceivedSubmissionsStatistics>
        </efac:LotResult>
      </efac:NoticeResult>"""

#: The same block, withheld with a code no version of the SDK defines.
UNKNOWN_CODE = COUNT_ONLY.replace("rec-sub-cou", "not-a-real-code")

#: A tender publishing `-1` with no privacy block at all: the placeholder alone
#: must never be read as a deferral.
SENTINEL_WITHOUT_PRIVACY = """
      <efac:NoticeResult>
        <efac:LotTender>
          <cbc:ID>TEN-0001</cbc:ID>
          <cac:LegalMonetaryTotal>
            <cbc:PayableAmount currencyID="SEK">-1</cbc:PayableAmount>
          </cac:LegalMonetaryTotal>
        </efac:LotTender>
      </efac:NoticeResult>"""

#: The same tender, with the block that says the amount was withheld.
SENTINEL_WITH_PRIVACY = SENTINEL_WITHOUT_PRIVACY.replace(
    "</efac:LotTender>",
    """  <efac:FieldsPrivacy>
            <efbc:FieldIdentifierCode>win-ten-val</efbc:FieldIdentifierCode>
            <cbc:ReasonCode>eo-int</cbc:ReasonCode>
          </efac:FieldsPrivacy>
        </efac:LotTender>""",
)

#: A privacy block carrying a reason but naming no field at all.
NO_CODE = """
      <efac:NoticeResult>
        <efac:LotTender>
          <cbc:ID>TEN-0001</cbc:ID>
          <cac:LegalMonetaryTotal>
            <cbc:PayableAmount currencyID="SEK">-1</cbc:PayableAmount>
          </cac:LegalMonetaryTotal>
          <efac:FieldsPrivacy>
            <cbc:ReasonCode>eo-int</cbc:ReasonCode>
          </efac:FieldsPrivacy>
        </efac:LotTender>
      </efac:NoticeResult>"""

#: A privacy block naming the payable amount, but sitting inside a subtree that
#: does not contain it. `covers` refuses it.
MISPLACED = """
      <efac:NoticeResult>
        <efac:LotTender>
          <cbc:ID>TEN-0001</cbc:ID>
          <cac:LegalMonetaryTotal>
            <cbc:PayableAmount currencyID="SEK">-1</cbc:PayableAmount>
          </cac:LegalMonetaryTotal>
          <efac:SubcontractingTerm>
            <efac:FieldsPrivacy>
              <efbc:FieldIdentifierCode>win-ten-val</efbc:FieldIdentifierCode>
            </efac:FieldsPrivacy>
          </efac:SubcontractingTerm>
        </efac:LotTender>
      </efac:NoticeResult>"""


def tender(extension: str) -> dict[str, Any]:
    found = rows("lot_tender", extension=ORGANISATIONS + extension)
    assert len(found) == 1
    return found[0]


def statistic(extension: str) -> dict[str, Any]:
    found = rows("lot_result_statistic", extension=ORGANISATIONS + extension)
    assert len(found) == 1
    return found[0]


class TestTheVendoredTable:
    """What the generator wrote, checked for the properties it promises."""

    def test_it_covers_the_versions_real_notices_declare(self) -> None:
        # Measured across OJ S 157/2026: 1,993 notices on 1.13, 906 on 1.14,
        # 291 on 1.12. A table generated from only the newest would be a claim
        # about a third of a publication day.
        assert {version.rsplit(".", 1)[0] for version in SDK_VERSIONS} >= {
            "1.12",
            "1.13",
            "1.14",
        }

    def test_it_carries_the_attribution_its_licence_requires(self) -> None:
        # The SDK is CC BY 4.0 and this file is a modified extract of it, so the
        # creator, the licence, a link to its terms and the fact of modification
        # all have to travel with it — and this file is what ships in the
        # distributed package. A regeneration that dropped them would be a
        # licence breach nobody would notice.
        source = Path(sdk_privacy.__file__).read_text(encoding="utf-8")
        for required in (
            "eForms SDK",
            "© European Union",
            "Publications Office",
            "https://github.com/OP-TED/eForms-SDK",
            "CC BY 4.0",
            "https://creativecommons.org/licenses/by/4.0/",
            "Modified",
        ):
            assert required in source, required

    def test_every_code_is_either_usable_or_refused_with_a_reason(self) -> None:
        placed = set(RECORD_TARGETS) | set(BLOCK_TARGETS)
        for field in PRIVACY_FIELDS:
            assert field.code in placed or field.code in UNUSABLE, field.code
        assert not placed & set(UNUSABLE), "a code cannot be both usable and not"

    def test_every_target_names_a_column_that_exists(self) -> None:
        # The join is computed against the model at import, so a renamed column
        # cannot leave a code pointing at nothing — but only if something looks.
        for targets in (*RECORD_TARGETS.values(), *BLOCK_TARGETS.values()):
            for target in targets:
                column = table(target.table).column(target.column)
                assert column.kind is not Kind.COMPUTED or target.path

    def test_a_record_target_belongs_to_a_record_built_table(self) -> None:
        for code, targets in RECORD_TARGETS.items():
            for target in targets:
                assert table(target.table).record, code
                assert table(target.table).column(target.column).path == target.path


class TestWhatItRefuses:
    """A mapping that over-reaches marks the wrong field non-public."""

    @pytest.mark.parametrize("code", ["pro-acc", "dir-awa-jus"])
    def test_a_predicate_that_mattered_is_refused(self, code: str) -> None:
        # Both are `cac:ProcessJustification/cbc:ProcessReasonCode`, told apart
        # only by `@listName`. This model's paths carry no predicates, so acting
        # on either would mark `procedure.process_reason_codes` on a coin toss.
        assert code not in RECORD_TARGETS
        assert code not in BLOCK_TARGETS
        assert "predicate" in UNUSABLE[code]

    @pytest.mark.parametrize("code", ["gro-max-val", "gro-ree-val", "cou-ori"])
    def test_a_code_naming_a_field_this_model_lacks_is_refused(self, code: str) -> None:
        # Fourteen codes still name a field with no column here — lots-group
        # framework values, country of origin. `field_privacy` records every
        # one of them regardless, so nothing is lost, only unacted on.
        assert code in UNUSABLE
        assert "no column" in UNUSABLE[code]

    @pytest.mark.parametrize(
        "code", ["not-val", "max-val", "ree-val", "not-max-val", "not-app-val"]
    )
    def test_the_amounts_the_model_gained_are_now_marked(self, code: str) -> None:
        # These five were refused for want of a column until the value columns
        # were added. They are 69 of the 215 privacy blocks in one publication
        # day, and every one of them is an amount a classifier would otherwise
        # read as a quantity.
        assert code in RECORD_TARGETS, UNUSABLE.get(code)
        assert code not in UNUSABLE

    def test_a_block_naming_no_field_marks_nothing(self) -> None:
        # A publisher may give a reason and no field identifier. There is no
        # target to derive, and guessing from the one column that happens to
        # hold `-1` would be exactly the inference this module refuses.
        row = tender(NO_CODE)
        assert row["payable_amount"] == "-1"
        assert row["payable_amount_status"] == Status.PRESENT

    def test_a_code_landing_in_both_a_record_and_a_block_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No SDK version does this, so the guard is only real if something
        # exercises it. `win-ten-val` names a column of `lot_tender`; give the
        # same code a second field naming a statistics block and neither may be
        # marked, because the row it belongs to is no longer determined.
        statistics = (
            "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent"
            "/efext:EformsExtension/efac:NoticeResult/efac:LotResult"
            "/efac:ReceivedSubmissionsStatistics/efbc:StatisticsNumeric"
        )
        monkeypatch.setattr(
            privacy_module,
            "PRIVACY_FIELDS",
            (
                *PRIVACY_FIELDS,
                PrivacyField("win-ten-val", "BT-INVENTED", statistics, ()),
            ),
        )
        records, blocks, unusable = _resolve()
        assert "win-ten-val" not in records
        assert "win-ten-val" not in blocks
        assert "both" in unusable["win-ten-val"]

    def test_the_refusals_are_the_larger_half(self) -> None:
        # Not a target to optimise: a reader deciding whether to trust a
        # `present` status needs to know most codes cannot be acted on yet.
        assert len(UNUSABLE) > len(RECORD_TARGETS) + len(BLOCK_TARGETS)

    def test_covers_refuses_a_block_that_sits_beside_its_target(self) -> None:
        target = Target("lot_tender", "payable_amount", "cac:LegalMonetaryTotal/x")
        assert covers("", target)
        assert covers("cac:LegalMonetaryTotal", target)
        assert not covers("efac:SubcontractingTerm", target)
        assert not covers("cac:LegalMonetaryTotalOther", target)


class TestAWithheldAmount:
    """The case open-work #13 was filed for."""

    def test_it_reads_withheld_and_keeps_the_published_value(self) -> None:
        row = tender(SENTINEL_WITH_PRIVACY)
        assert row["payable_amount"] == "-1"
        assert row["payable_amount_currency"] == "SEK"
        assert row["payable_amount_status"] == Status.WITHHELD

    def test_the_sentinel_alone_is_not_a_deferral(self) -> None:
        # The anti-vacuity check for the test above: without the privacy block
        # the same `-1` reads `present`, so the status comes from what the
        # publisher declared and not from the shape of the value.
        row = tender(SENTINEL_WITHOUT_PRIVACY)
        assert row["payable_amount"] == "-1"
        assert row["payable_amount_status"] == Status.PRESENT

    def test_a_block_that_does_not_contain_the_field_marks_nothing(self) -> None:
        row = tender(MISPLACED)
        assert row["payable_amount_status"] == Status.PRESENT

    def test_only_the_named_column_is_marked(self) -> None:
        row = tender(SENTINEL_WITH_PRIVACY)
        marked = [
            name
            for name in row
            if name.endswith("_status") and row[name] == Status.WITHHELD
        ]
        assert marked == ["payable_amount_status"]


class TestAWithheldStatistic:
    """The bid count: the input to the classifier this project will write first."""

    def test_a_block_naming_only_the_count_marks_only_the_count(self) -> None:
        row = statistic(COUNT_ONLY)
        assert row["statistic_value"] == "-1"
        assert row["statistic_value_status"] == Status.WITHHELD
        # The code was published — `tenders`, not the `unpublished` placeholder
        # — and `rec-sub-cou` does not name it.
        assert row["statistic_code"] == "tenders"
        assert row["statistic_code_status"] == Status.PRESENT

    def test_a_code_the_mapping_cannot_place_still_marks_the_block(self) -> None:
        # Containment alone proves something in this block was withheld, which
        # was the only signal available before the SDK mapping. Keeping it means
        # a code added to eForms tomorrow degrades to conservative rather than
        # to silence.
        row = statistic(UNKNOWN_CODE)
        assert row["statistic_value_status"] == Status.WITHHELD
        assert row["statistic_code_status"] == Status.WITHHELD

    def test_the_case_that_already_worked_has_not_regressed(self) -> None:
        # open-work #13 asked for this explicitly. The default fixture withholds
        # both the count and the code it counts, as every measured real block
        # does, and both must still read `withheld`.
        found = [
            r for r in rows("lot_result_statistic") if r["statistic_value"] == "-1"
        ]
        assert len(found) == 1
        assert found[0]["statistic_value_status"] == Status.WITHHELD
        assert found[0]["statistic_code_status"] == Status.WITHHELD

    def test_a_statistic_with_no_privacy_block_is_untouched(self) -> None:
        found = [
            r for r in rows("lot_result_statistic") if r["statistic_code"] == "tenders"
        ]
        assert len(found) == 1
        assert found[0]["statistic_value_status"] == Status.PRESENT
        assert found[0]["statistic_code_status"] == Status.PRESENT


class TestTheRestOfTheDatasetIsUnaffected:
    """A status column that is not named keeps saying what it said."""

    def test_no_other_table_gains_a_withheld_status(self) -> None:
        withheld = {
            name
            for candidate in TABLES
            for row in rows(candidate.name)
            for name in row
            if name.endswith("_status") and row[name] == Status.WITHHELD
        }
        # The fixture withholds a bid count, the code it counts, and — since the
        # value columns were added — the notice total its `not-val` block names.
        assert withheld == {
            "statistic_value_status",
            "statistic_code_status",
            "total_amount_status",
        }


@pytest.mark.parametrize(
    ("indicator", "suppressed"),
    [("true", True), ("1", True), ("false", False), ("0", False), (None, False)],
)
def test_natural_person_websites_do_not_reach_parquet(
    tmp_path: Path, indicator: str | None, suppressed: bool
) -> None:
    source = tmp_path / "synthetic-websites.tar.gz"
    source.write_bytes(
        make_notice_package({SYNTHETIC_NOTICE: website_notice(indicator)})
    )
    root = tmp_path / "dataset"
    result = normalise_package(source, root)
    assert result.notices == 1
    assert result.unparsed == result.unnormalised == ()
    assert result.rows["organisation"] == 2
    organisations = {
        row["org_local_id"]: row
        for row in pq.read_table(root / "organisation").to_pylist()
    }
    candidate = organisations["ORG-0001"]
    assert candidate["website"] == (
        None if suppressed else "https://synthetic-candidate.invalid/company"
    )
    assert candidate["website_status"] == (
        Status.ABSENT if suppressed else Status.PRESENT
    )
    assert candidate["is_natural_person"] == indicator
    assert candidate["is_natural_person_status"] == (
        Status.ABSENT if indicator is None else Status.PRESENT
    )
    control = organisations["ORG-0002"]
    assert control["website"] == "https://synthetic-control.invalid/company"
    assert control["website_status"] == Status.PRESENT
    if suppressed:
        # Decode every table: a compressed-byte search cannot prove value absence.
        for path in result.files:
            assert "synthetic-candidate.invalid" not in repr(
                pq.read_table(path).to_pylist()
            )
    before = {path: path.read_bytes() for path in result.files}
    normalise_package(source, root)
    assert {path: path.read_bytes() for path in result.files} == before
