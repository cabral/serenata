"""Which eForms privacy code withholds which field. Generated — do not edit.

Regenerate with `uv run python tools/generate_sdk_privacy.py`, which is where
the reasoning and the checks live. This file is data: the pipeline reads it
offline, and nothing here reaches the network (constraint 4).

A publisher marks a field non-public by writing its code into
`efac:FieldsPrivacy/efbc:FieldIdentifierCode` and publishing a placeholder — an
amount as `-1` — in the field itself. This table says which field each code
names, so `serenata.normalise.privacy` can mark that column `withheld` instead
of letting a classifier read the placeholder as a quantity (ADR-0006, ADR-0008).

## Attribution

Source: the **eForms SDK** (`fields/fields.json`), © European Union, published
by the Publications Office of the European Union at
https://github.com/OP-TED/eForms-SDK and licensed **CC BY 4.0**
(https://creativecommons.org/licenses/by/4.0/).

**Modified.** This is not the SDK. It is one relation extracted from it — the
privacy code against the field it withholds — reshaped into the table below and
carrying none of the SDK's other content. Generated from the versions in
`SDK_VERSIONS`, whose privacy mappings are identical across all of them.

See docs/adr/0008-eforms-sdk-privacy-mapping.md for why this is vendored, and
docs/data-reuse.md for the project's attribution terms.
"""

from __future__ import annotations

from typing import NamedTuple

#: The SDK versions this table was generated from and verified identical across.
SDK_VERSIONS: tuple[str, ...] = ("1.12.0", "1.13.3", "1.14.2", "1.15.1")


class PrivacyField(NamedTuple):
    """One field a privacy code withholds, as the SDK defines it."""

    #: The value published in `efbc:FieldIdentifierCode`.
    code: str
    #: The SDK's own identifier for the withheld field, e.g. `BT-720-Tender`.
    field_id: str
    #: The field's absolute XPath, verbatim, predicates included.
    xpath: str
    #: Other SDK fields whose XPath is identical once predicates are stripped.
    #: Non-empty means this code cannot be resolved to a column in a model that
    #: does not carry predicates, because two different fields share the path.
    shares_path_with: tuple[str, ...]


PRIVACY_FIELDS: tuple[PrivacyField, ...] = (
    PrivacyField(
        "awa-cri-com",
        "BT-543-Lot",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cbc:CalculationExpression",
        ("BT-543-LotsGroup",),
    ),
    PrivacyField(
        "awa-cri-com",
        "BT-543-LotsGroup",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cbc:CalculationExpression",
        ("BT-543-Lot",),
    ),
    PrivacyField(
        "awa-cri-des",
        "BT-540-Lot",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/cbc:Description",
        ("BT-540-LotsGroup",),
    ),
    PrivacyField(
        "awa-cri-des",
        "BT-540-LotsGroup",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/cbc:Description",
        ("BT-540-Lot",),
    ),
    PrivacyField(
        "awa-cri-fix",
        "BT-5422-Lot",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-fixed']/efbc:ParameterCode",
        (
            "BT-5421-Lot",
            "BT-5421-LotsGroup",
            "BT-5422-LotsGroup",
            "BT-5423-Lot",
            "BT-5423-LotsGroup",
        ),
    ),
    PrivacyField(
        "awa-cri-fix",
        "BT-5422-LotsGroup",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-fixed']/efbc:ParameterCode",
        (
            "BT-5421-Lot",
            "BT-5421-LotsGroup",
            "BT-5422-Lot",
            "BT-5423-Lot",
            "BT-5423-LotsGroup",
        ),
    ),
    PrivacyField(
        "awa-cri-nam",
        "BT-734-Lot",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/cbc:Name",
        ("BT-734-LotsGroup",),
    ),
    PrivacyField(
        "awa-cri-nam",
        "BT-734-LotsGroup",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/cbc:Name",
        ("BT-734-Lot",),
    ),
    PrivacyField(
        "awa-cri-num",
        "BT-541-Lot-FixedNumber",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-fixed']/efbc:ParameterNumeric",
        (
            "BT-541-Lot-ThresholdNumber",
            "BT-541-Lot-WeightNumber",
            "BT-541-LotsGroup-FixedNumber",
            "BT-541-LotsGroup-ThresholdNumber",
            "BT-541-LotsGroup-WeightNumber",
        ),
    ),
    PrivacyField(
        "awa-cri-num",
        "BT-541-Lot-ThresholdNumber",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-threshold']/efbc:ParameterNumeric",
        (
            "BT-541-Lot-FixedNumber",
            "BT-541-Lot-WeightNumber",
            "BT-541-LotsGroup-FixedNumber",
            "BT-541-LotsGroup-ThresholdNumber",
            "BT-541-LotsGroup-WeightNumber",
        ),
    ),
    PrivacyField(
        "awa-cri-num",
        "BT-541-Lot-WeightNumber",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-weight']/efbc:ParameterNumeric",
        (
            "BT-541-Lot-FixedNumber",
            "BT-541-Lot-ThresholdNumber",
            "BT-541-LotsGroup-FixedNumber",
            "BT-541-LotsGroup-ThresholdNumber",
            "BT-541-LotsGroup-WeightNumber",
        ),
    ),
    PrivacyField(
        "awa-cri-num",
        "BT-541-LotsGroup-FixedNumber",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-fixed']/efbc:ParameterNumeric",
        (
            "BT-541-Lot-FixedNumber",
            "BT-541-Lot-ThresholdNumber",
            "BT-541-Lot-WeightNumber",
            "BT-541-LotsGroup-ThresholdNumber",
            "BT-541-LotsGroup-WeightNumber",
        ),
    ),
    PrivacyField(
        "awa-cri-num",
        "BT-541-LotsGroup-ThresholdNumber",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-threshold']/efbc:ParameterNumeric",
        (
            "BT-541-Lot-FixedNumber",
            "BT-541-Lot-ThresholdNumber",
            "BT-541-Lot-WeightNumber",
            "BT-541-LotsGroup-FixedNumber",
            "BT-541-LotsGroup-WeightNumber",
        ),
    ),
    PrivacyField(
        "awa-cri-num",
        "BT-541-LotsGroup-WeightNumber",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-weight']/efbc:ParameterNumeric",
        (
            "BT-541-Lot-FixedNumber",
            "BT-541-Lot-ThresholdNumber",
            "BT-541-Lot-WeightNumber",
            "BT-541-LotsGroup-FixedNumber",
            "BT-541-LotsGroup-ThresholdNumber",
        ),
    ),
    PrivacyField(
        "awa-cri-ord",
        "BT-733-Lot",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cbc:Description",
        ("BT-733-LotsGroup",),
    ),
    PrivacyField(
        "awa-cri-ord",
        "BT-733-LotsGroup",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cbc:Description",
        ("BT-733-Lot",),
    ),
    PrivacyField(
        "awa-cri-thr",
        "BT-5423-Lot",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-threshold']/efbc:ParameterCode",
        (
            "BT-5421-Lot",
            "BT-5421-LotsGroup",
            "BT-5422-Lot",
            "BT-5422-LotsGroup",
            "BT-5423-LotsGroup",
        ),
    ),
    PrivacyField(
        "awa-cri-thr",
        "BT-5423-LotsGroup",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-threshold']/efbc:ParameterCode",
        (
            "BT-5421-Lot",
            "BT-5421-LotsGroup",
            "BT-5422-Lot",
            "BT-5422-LotsGroup",
            "BT-5423-Lot",
        ),
    ),
    PrivacyField(
        "awa-cri-typ",
        "BT-539-Lot",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/cbc:AwardingCriterionTypeCode[@listName='award-criterion-type']",
        ("BT-539-LotsGroup",),
    ),
    PrivacyField(
        "awa-cri-typ",
        "BT-539-LotsGroup",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/cbc:AwardingCriterionTypeCode[@listName='award-criterion-type']",
        ("BT-539-Lot",),
    ),
    PrivacyField(
        "awa-cri-wei",
        "BT-5421-Lot",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='Lot']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-weight']/efbc:ParameterCode",
        (
            "BT-5421-LotsGroup",
            "BT-5422-Lot",
            "BT-5422-LotsGroup",
            "BT-5423-Lot",
            "BT-5423-LotsGroup",
        ),
    ),
    PrivacyField(
        "awa-cri-wei",
        "BT-5421-LotsGroup",
        "/*/cac:ProcurementProjectLot[cbc:ID/@schemeName='LotsGroup']/cac:TenderingTerms/cac:AwardingTerms/cac:AwardingCriterion/cac:SubordinateAwardingCriterion/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:AwardCriterionParameter[efbc:ParameterCode/@listName='number-weight']/efbc:ParameterCode",
        (
            "BT-5421-Lot",
            "BT-5422-Lot",
            "BT-5422-LotsGroup",
            "BT-5423-Lot",
            "BT-5423-LotsGroup",
        ),
    ),
    PrivacyField(
        "buy-rev-cou",
        "BT-635-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:AppealRequestsStatistics[efbc:StatisticsCode/@listName='irregularity-type']/efbc:StatisticsNumeric",
        ("BT-712(b)-LotResult",),
    ),
    PrivacyField(
        "buy-rev-typ",
        "BT-636-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:AppealRequestsStatistics[efbc:StatisticsCode/@listName='irregularity-type']/efbc:StatisticsCode",
        ("BT-712(a)-LotResult",),
    ),
    PrivacyField(
        "con-rev-buy",
        "BT-160-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:ConcessionRevenue/efbc:RevenueBuyerAmount",
        (),
    ),
    PrivacyField(
        "con-rev-use",
        "BT-162-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:ConcessionRevenue/efbc:RevenueUserAmount",
        (),
    ),
    PrivacyField(
        "cou-ori",
        "BT-191-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:Origin/efbc:AreaCode",
        (),
    ),
    PrivacyField(
        "cro-bor-law",
        "BT-09(b)-Procedure",
        "/*/cac:TenderingTerms/cac:ProcurementLegislationDocumentReference[cbc:ID/text()='CrossBorderLaw']/cbc:DocumentDescription",
        ("BT-01(d)-Procedure", "BT-01(f)-Procedure"),
    ),
    PrivacyField(
        "dir-awa-jus",
        "BT-136-Procedure",
        "/*/cac:TenderingProcess/cac:ProcessJustification[cbc:ProcessReasonCode/@listName='direct-award-justification']/cbc:ProcessReasonCode",
        ("BT-106-Procedure",),
    ),
    PrivacyField(
        "dir-awa-pre",
        "BT-1252-Procedure",
        "/*/cac:TenderingProcess/cac:ProcessJustification[cbc:ProcessReasonCode/@listName='direct-award-justification']/cbc:Description",
        (),
    ),
    PrivacyField(
        "dir-awa-tex",
        "BT-135-Procedure",
        "/*/cac:TenderingProcess/cac:ProcessJustification[cbc:ProcessReasonCode/@listName='direct-award-justification']/cbc:ProcessReason",
        ("BT-1351-Procedure",),
    ),
    PrivacyField(
        "gro-max-ide",
        "BT-556-NoticeResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:GroupFramework/efac:TenderLot/cbc:ID",
        (),
    ),
    PrivacyField(
        "gro-max-val",
        "BT-156-NoticeResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:GroupFramework/efbc:GroupFrameworkMaximumValueAmount",
        (),
    ),
    PrivacyField(
        "gro-ree-val",
        "BT-1561-NoticeResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:GroupFramework/efbc:GroupFrameworkReestimatedValueAmount",
        (),
    ),
    PrivacyField(
        "max-val",
        "BT-709-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:FrameworkAgreementValues/cbc:MaximumValueAmount",
        (),
    ),
    PrivacyField(
        "no-awa-rea",
        "BT-144-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:DecisionReason/efbc:DecisionReasonCode",
        (),
    ),
    PrivacyField(
        "not-app-val",
        "BT-1118-NoticeResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efbc:OverallApproximateFrameworkContractsAmount",
        (),
    ),
    PrivacyField(
        "not-max-val",
        "BT-118-NoticeResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efbc:OverallMaximumFrameworkContractsAmount",
        (),
    ),
    PrivacyField(
        "not-val",
        "BT-161-NoticeResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/cbc:TotalAmount",
        (),
    ),
    PrivacyField(
        "pro-acc",
        "BT-106-Procedure",
        "/*/cac:TenderingProcess/cac:ProcessJustification[cbc:ProcessReasonCode/@listName='accelerated-procedure']/cbc:ProcessReasonCode",
        ("BT-136-Procedure",),
    ),
    PrivacyField(
        "pro-acc-jus",
        "BT-1351-Procedure",
        "/*/cac:TenderingProcess/cac:ProcessJustification[cbc:ProcessReasonCode/@listName='accelerated-procedure']/cbc:ProcessReason",
        ("BT-135-Procedure",),
    ),
    PrivacyField(
        "pro-fea",
        "BT-88-Procedure",
        "/*/cac:TenderingProcess/cbc:Description",
        (),
    ),
    PrivacyField(
        "pro-typ",
        "BT-105-Procedure",
        "/*/cac:TenderingProcess/cbc:ProcedureCode",
        (),
    ),
    PrivacyField(
        "rec-sub-cou",
        "BT-759-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:ReceivedSubmissionsStatistics/efbc:StatisticsNumeric",
        (),
    ),
    PrivacyField(
        "rec-sub-typ",
        "BT-760-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:ReceivedSubmissionsStatistics/efbc:StatisticsCode",
        (),
    ),
    PrivacyField(
        "ree-val",
        "BT-660-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:FrameworkAgreementValues/efbc:ReestimatedValueAmount",
        (),
    ),
    PrivacyField(
        "rev-req",
        "BT-712(a)-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:AppealRequestsStatistics[efbc:StatisticsCode/@listName='review-type']/efbc:StatisticsCode",
        ("BT-636-LotResult",),
    ),
    PrivacyField(
        "rev-req",
        "BT-712(b)-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/efac:AppealRequestsStatistics[efbc:StatisticsCode/@listName='review-type']/efbc:StatisticsNumeric",
        ("BT-635-LotResult",),
    ),
    PrivacyField(
        "sub-con",
        "BT-773-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:SubcontractingTerm[efbc:TermCode/@listName='applicability']/efbc:TermCode",
        (),
    ),
    PrivacyField(
        "sub-des",
        "BT-554-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:SubcontractingTerm[efbc:TermCode/@listName='applicability']/efbc:TermDescription",
        (),
    ),
    PrivacyField(
        "sub-per",
        "BT-555-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:SubcontractingTerm[efbc:TermCode/@listName='applicability']/efbc:TermPercent",
        (),
    ),
    PrivacyField(
        "sub-per-kno",
        "BT-731-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:SubcontractingTerm[efbc:TermCode/@listName='applicability']/efbc:PercentageKnownIndicator",
        (),
    ),
    PrivacyField(
        "sub-val",
        "BT-553-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:SubcontractingTerm[efbc:TermCode/@listName='applicability']/efbc:TermAmount",
        (),
    ),
    PrivacyField(
        "sub-val-kno",
        "BT-730-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:SubcontractingTerm[efbc:TermCode/@listName='applicability']/efbc:ValueKnownIndicator",
        (),
    ),
    PrivacyField(
        "ten-ran",
        "BT-171-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/cbc:RankCode",
        (),
    ),
    PrivacyField(
        "ten-val-hig",
        "BT-711-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/cbc:HigherTenderAmount",
        (),
    ),
    PrivacyField(
        "ten-val-low",
        "BT-710-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/cbc:LowerTenderAmount",
        (),
    ),
    PrivacyField(
        "val-con-des",
        "BT-163-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efac:ConcessionRevenue/efbc:ValueDescription",
        (),
    ),
    PrivacyField(
        "win-cho",
        "BT-142-LotResult",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotResult/cbc:TenderResultCode",
        (),
    ),
    PrivacyField(
        "win-ten-val",
        "BT-720-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/cac:LegalMonetaryTotal/cbc:PayableAmount",
        (),
    ),
    PrivacyField(
        "win-ten-var",
        "BT-193-Tender",
        "/*/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension/efac:NoticeResult/efac:LotTender/efbc:TenderVariantIndicator",
        (),
    ),
)
