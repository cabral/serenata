"""The relational model, in executable form.

`docs/data-model.md` is the contract; this module is that document as code, the
way `serenata.parse.personal_data` is `docs/personal-data.md` as code.
`tests/test_normalise_model.py` fails if the two disagree, so a column added
here without a documented source path — or documented without being built —
does not merge.

Three things a column has to say, and one it deliberately does not.

**Where it came from.** ``path`` is the source element path *relative to the
record's container*, which is the form `serenata.parse` hands over. The
document cites absolute paths; `container` plus `path` reconstructs one, and
the test does exactly that rather than trusting a second transcription.

**Whether it holds one value or a set.** A path that occurs more than once in a
record is ordinary — 53,192 of 58,248 lots carry two
``cbc:ContractingSystemTypeCode``, and a lot result was measured carrying 750
winning-tender references. `Record.value` raises on those rather than picking
one, and a column that picked one would be reporting an arbitrary member of a
set. Such a column is a `SET`: it carries the whole set, in document order, and
is named plurally (ADR-0007).

**Which language it is in**, for free text. A title repeats per language — 77
notices carry two, always in distinct languages — so a `TEXT` column takes the
occurrence in the notice's own ``cbc:NoticeLanguageCode`` and records which
language that was in a ``<column>_language`` companion (ADR-0007).

What a column does not say is its type. Every value is stored as published, as
a string. Casting is a decision with edge cases — a withheld amount is
published as ``-1``, which a numeric column would store as a negative sum of
money — so it belongs to whoever queries, explicitly, and not to a silent
conversion here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from serenata.parse.records import CONTAINERS as PARSE_CONTAINERS
from serenata.parse.records import EXTENSION, NOTICE

#: The eForms extension prefix, relative to a notice-level record.
EXT = EXTENSION.split("/", 1)[1]

#: Container path -> the parse record kind produced from it, and the reverse.
#: `serenata.parse` owns this mapping; the model reads it rather than restating
#: it, so a container renamed there cannot leave a table pointing at nothing.
CONTAINER_OF = {kind: path for path, kind in PARSE_CONTAINERS.items()}


class Kind(StrEnum):
    """How a column reads its source path."""

    #: One value. The path was measured occurring at most once per record;
    #: a record that repeats it anyway is a `RepeatedValue` failure, not a
    #: coin toss.
    SCALAR = "scalar"
    #: Every value at the path, in document order, as a list.
    SET = "set"
    #: Free text published once per language; the notice's language wins.
    TEXT = "text"
    #: Filled by the builder rather than read from a path.
    COMPUTED = "computed"


class Status(StrEnum):
    """Why a column has the value it has, per ADR-0006.

    ``not_applicable`` is declared and never produced: deriving it needs the
    eForms notice-subtype rules, which live in the SDK this pipeline does not
    carry. An inapplicable field records `ABSENT` until it does, which
    understates what is known rather than overstating it.
    """

    PRESENT = "present"
    EMPTY = "empty"
    ABSENT = "absent"
    WITHHELD = "withheld"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class Column:
    """One column, and the source element it is read from."""

    name: str
    #: Source path relative to the table's container, or ``""`` when computed.
    path: str = ""
    kind: Kind = Kind.SCALAR
    #: Whether an amount's ``currencyID`` is kept in a companion column. An
    #: amount without one is a number, not a sum of money: six currencies
    #: appear on ``PayableAmount`` in one publication day.
    currency: bool = False
    #: Structural columns — keys, ordinals, the partition — carry no status:
    #: they are how the row is addressed, not something a notice provided.
    structural: bool = False

    @property
    def companions(self) -> tuple[str, ...]:
        """The companion columns this one carries, in output order."""
        if self.structural:
            return ()
        extra = [f"{self.name}_status"]
        if self.currency:
            extra.append(f"{self.name}_currency")
        if self.kind is Kind.TEXT:
            extra.append(f"{self.name}_language")
        return tuple(extra)


@dataclass(frozen=True)
class Table:
    """One output table: where its rows come from and how they are keyed."""

    name: str
    #: The parse record kind one row is built from, or ``""`` for a table whose
    #: rows are built from several kinds (`organisation_role`, `field_privacy`).
    record: str
    columns: tuple[Column, ...]
    #: Sort key. Rows are sorted by it before every write, so the same input
    #: produces the same bytes whatever order the records arrived in
    #: (constraint 4, ADR-0001).
    key: tuple[str, ...]

    @property
    def container(self) -> str:
        """The absolute path of the element one row is built from."""
        return CONTAINER_OF.get(self.record, "notice")

    def column(self, name: str) -> Column:
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(name)

    def field_names(self) -> tuple[str, ...]:
        """Every column this table writes, values and companions, in order."""
        names: list[str] = []
        for column in self.columns:
            names.append(column.name)
            names.extend(column.companions)
        return tuple(names)


def _identity() -> tuple[Column, ...]:
    """The columns every row carries, whichever table it is in.

    ``source_publication_id`` is the citable TED reference a published flag
    links to, so a reader can open the notice and check the claim. It is on
    every row for that reason, not for joining. ``publication_year`` is the
    partition, taken from the notice's publication date and never from the run
    clock.
    """
    return (
        Column("source_notice_id", structural=True),
        Column("source_publication_id", structural=True),
        Column("publication_year", structural=True),
    )


def _record_key(*extra: str) -> tuple[str, ...]:
    """A table's sort key, led by the identifier that is actually unique.

    Not the notice UUID. ``notice/cbc:ID`` repeats: two UUIDs each appear twice
    in OJ S 157/2026, published under different notice numbers on the same day
    with the same contract folder and issue date — the same notice published
    twice. Keying on the UUID would merge two publications into one key, and
    ``source_publication_id`` is unique across all 3,190.
    """
    return ("source_publication_id", *extra)


#: ``(source_publication_id, kind, ordinal)`` is the stable key of a container
#: record: the container's position among all of its kind in the notice, in
#: document order. It says nothing about which parent the record hung from,
#: because the model does not carry parentage either.
ORDINAL = Column("ordinal", structural=True)


NOTICE_TABLE = Table(
    name="notice",
    record=NOTICE,
    key=_record_key(),
    columns=(
        *_identity(),
        # `notice_id` and `publication_id` in docs/data-model.md are these two
        # identity columns; a second copy of the same value under a second name
        # is not a column, it is a trap for whoever joins on the wrong one.
        Column("gazette_id", f"{EXT}/efac:Publication/efbc:GazetteID"),
        Column("publication_date", f"{EXT}/efac:Publication/efbc:PublicationDate"),
        Column("issue_date", "cbc:IssueDate"),
        Column("issue_time", "cbc:IssueTime"),
        Column("notice_type_code", "cbc:NoticeTypeCode"),
        Column("notice_subtype_code", f"{EXT}/efac:NoticeSubType/cbc:SubTypeCode"),
        Column("version_id", "cbc:VersionID"),
        Column("regulatory_domain", "cbc:RegulatoryDomain"),
        Column("customization_id", "cbc:CustomizationID"),
        Column("language_code", "cbc:NoticeLanguageCode"),
        Column("contract_folder_id", "cbc:ContractFolderID"),
        # Not an element path: the document's own root, which is how notice
        # types differ before any field is read.
        Column("root_element", kind=Kind.COMPUTED),
        Column("changed_notice_id", f"{EXT}/efac:Changes/efbc:ChangedNoticeIdentifier"),
        # The link parsed into its parts (ADR-0013). Two identifier namespaces
        # share the column, so which one a link used is recorded rather than
        # assumed, and an unrecognised shape is `unknown` rather than dropped.
        Column("changed_notice_namespace", kind=Kind.COMPUTED),
        Column("changed_notice_target", kind=Kind.COMPUTED),
        Column("changed_notice_version", kind=Kind.COMPUTED),
    ),
)


PROCEDURE_TABLE = Table(
    name="procedure",
    record=NOTICE,
    key=_record_key(),
    columns=(
        *_identity(),
        Column("contract_folder_id", "cbc:ContractFolderID"),
        Column("title", "cac:ProcurementProject/cbc:Name", Kind.TEXT),
        Column("description", "cac:ProcurementProject/cbc:Description", Kind.TEXT),
        Column(
            "procurement_type_code",
            "cac:ProcurementProject/cbc:ProcurementTypeCode",
        ),
        Column(
            "cpv_code",
            "cac:ProcurementProject/cac:MainCommodityClassification"
            "/cbc:ItemClassificationCode",
        ),
        Column("internal_id", "cac:ProcurementProject/cbc:ID"),
        Column("procedure_code", "cac:TenderingProcess/cbc:ProcedureCode"),
        # A procedure can rest on more than one legal ground, and 5 notices in
        # 19,180 state two. It was a scalar column while one publication day
        # was the whole evidence base, and every one of those five failed to
        # normalise rather than storing an arbitrary ground (ADR-0007).
        Column(
            "process_reason_codes",
            "cac:TenderingProcess/cac:ProcessJustification/cbc:ProcessReasonCode",
            Kind.SET,
        ),
        # What the buyer expected to spend, against what the notice records
        # being awarded. The gap between the two is one of the indicators the
        # published literature is built on, and neither was carried before.
        Column(
            "estimated_amount",
            "cac:ProcurementProject/cac:RequestedTenderTotal"
            "/cbc:EstimatedOverallContractAmount",
            currency=True,
        ),
        Column(
            "total_amount",
            f"{EXT}/efac:NoticeResult/cbc:TotalAmount",
            currency=True,
        ),
        # A framework's ceiling for the whole notice. `max` is the binding one;
        # `approximate` is the buyer's estimate of what will be called off, and
        # eForms carries both because they answer different questions.
        Column(
            "framework_overall_max_amount",
            f"{EXT}/efac:NoticeResult/efbc:OverallMaximumFrameworkContractsAmount",
            currency=True,
        ),
        Column(
            "framework_overall_approximate_amount",
            f"{EXT}/efac:NoticeResult/efbc:OverallApproximateFrameworkContractsAmount",
            currency=True,
        ),
    ),
)


LOT_TABLE = Table(
    name="lot",
    record="lot",
    key=_record_key("ordinal"),
    columns=(
        *_identity(),
        ORDINAL,
        Column("lot_id", "cbc:ID"),
        Column("title", "cac:ProcurementProject/cbc:Name", Kind.TEXT),
        Column("description", "cac:ProcurementProject/cbc:Description", Kind.TEXT),
        Column(
            "procurement_type_code",
            "cac:ProcurementProject/cbc:ProcurementTypeCode",
        ),
        Column(
            "cpv_code",
            "cac:ProcurementProject/cac:MainCommodityClassification"
            "/cbc:ItemClassificationCode",
        ),
        Column("internal_id", "cac:ProcurementProject/cbc:ID"),
        Column("funding_programme_code", "cac:TenderingTerms/cbc:FundingProgramCode"),
        Column(
            "estimated_amount",
            "cac:ProcurementProject/cac:RequestedTenderTotal"
            "/cbc:EstimatedOverallContractAmount",
            currency=True,
        ),
        # The deadline for receiving tenders, as two columns because eForms
        # publishes two elements and both carry their own UTC offset. How long
        # bidders were given is the difference between this and the publication
        # date, and a length computed from the date alone is wrong by up to a
        # day — so the pair is stored as published and the arithmetic belongs to
        # whoever asks, explicitly (ADR-0006 on storing values as published).
        Column(
            "submission_deadline_date",
            "cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndDate",
        ),
        Column(
            "submission_deadline_time",
            "cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndTime",
        ),
        # Repeated in 53,192 of 58,248 lots: eForms emits one code per
        # contracting system the lot uses, so the set is the value.
        Column(
            "contracting_system_codes",
            "cac:TenderingProcess/cac:ContractingSystem/cbc:ContractingSystemTypeCode",
            Kind.SET,
        ),
        Column(
            "gpa_covered",
            "cac:TenderingProcess/cbc:GovernmentAgreementConstraintIndicator",
        ),
        Column(
            "electronic_auction",
            "cac:TenderingProcess/cac:AuctionTerms/cbc:AuctionConstraintIndicator",
        ),
    ),
)


ORGANISATION_TABLE = Table(
    name="organisation",
    record="organisation",
    key=_record_key("ordinal"),
    columns=(
        *_identity(),
        ORDINAL,
        Column("org_local_id", "efac:Company/cac:PartyIdentification/cbc:ID"),
        Column("name", "efac:Company/cac:PartyName/cbc:Name", Kind.TEXT),
        # 2,570 organisations carry more than one registration number —
        # several `cac:PartyLegalEntity` blocks, up to five. Picking one would
        # be picking which national register to believe.
        Column(
            "company_ids",
            "efac:Company/cac:PartyLegalEntity/cbc:CompanyID",
            Kind.SET,
        ),
        Column(
            "country_code",
            "efac:Company/cac:PostalAddress/cac:Country/cbc:IdentificationCode",
        ),
        Column("city", "efac:Company/cac:PostalAddress/cbc:CityName"),
        Column("postal_zone", "efac:Company/cac:PostalAddress/cbc:PostalZone"),
        Column("nuts_code", "efac:Company/cac:PostalAddress/cbc:CountrySubentityCode"),
        Column("street", "efac:Company/cac:PostalAddress/cbc:StreetName"),
        Column("website", "efac:Company/cbc:WebsiteURI"),
        # Absent from about 90% of notices, and absent is "not provided", never
        # "false". Where it is true, parse has already suppressed the columns
        # above it governs, so the row is anonymous and still joins.
        Column("is_natural_person", "efbc:NaturalPersonIndicator"),
    ),
)


#: Role -> (parse record kind, source path relative to that record) for the
#: organisation reference. An organisation is a buyer in one notice and a
#: supplier in another, so the role is an edge rather than a column.
ROLE_SOURCES: dict[str, tuple[str, str]] = {
    "buyer": (NOTICE, "cac:ContractingParty/cac:Party/cac:PartyIdentification/cbc:ID"),
    "procurement_service_provider": (
        NOTICE,
        "cac:ContractingParty/cac:Party/cac:ServiceProviderParty/cac:Party"
        "/cac:PartyIdentification/cbc:ID",
    ),
    "appeal_receiver": (
        "lot",
        "cac:TenderingTerms/cac:AppealTerms/cac:AppealReceiverParty"
        "/cac:PartyIdentification/cbc:ID",
    ),
    "tenderer": ("tendering_party", "efac:Tenderer/cbc:ID"),
    # Despite its element name, `cac:SignatoryParty` references an organisation
    # rather than a person who signed. It is kept for that reason and no other.
    "contract_signatory": (
        "settled_contract",
        "cac:SignatoryParty/cac:PartyIdentification/cbc:ID",
    ),
}

#: Columns that qualify one role's edge, keyed by the role they belong to, as
#: ``(column name, path relative to the role's record)``. Each is paired to its
#: reference on `Field.occurrence`, so a notice with 163 buyers — the largest
#: measured — keeps each buyer's type with that buyer.
ROLE_QUALIFIERS: dict[str, tuple[tuple[str, str], ...]] = {
    "buyer": (
        (
            "buyer_type_code",
            "cac:ContractingParty/cac:ContractingPartyType/cbc:PartyTypeCode",
        ),
        (
            "buyer_activity_code",
            "cac:ContractingParty/cac:ContractingActivity/cbc:ActivityTypeCode",
        ),
    ),
    "tenderer": (("is_group_lead", "efac:Tenderer/efbc:GroupLeadIndicator"),),
}


ORGANISATION_ROLE_TABLE = Table(
    name="organisation_role",
    record="",
    key=_record_key("role", "scope_table", "scope_ordinal", "block_ordinal"),
    columns=(
        *_identity(),
        Column("role", structural=True),
        # The record the reference was read from, so a role that is scoped to a
        # lot or a settled contract still says which one.
        Column("scope_table", structural=True),
        Column("scope_ordinal", structural=True),
        # The reference's position among that role's references in the record.
        # It is what keeps the key unique where a notice names one organisation
        # twice in the same role — six rows of 18,659 in OJ S 157/2026, each a
        # buyer described under two contracting-party blocks.
        Column("block_ordinal", structural=True),
        Column("org_ref", kind=Kind.COMPUTED),
        Column("buyer_type_code", kind=Kind.COMPUTED),
        Column("buyer_activity_code", kind=Kind.COMPUTED),
        Column("is_group_lead", kind=Kind.COMPUTED),
    ),
)


TENDERING_PARTY_TABLE = Table(
    name="tendering_party",
    record="tendering_party",
    key=_record_key("ordinal"),
    columns=(
        *_identity(),
        ORDINAL,
        Column("tendering_party_id", "cbc:ID"),
        Column("name", "cbc:Name", Kind.TEXT),
    ),
)


LOT_TENDER_TABLE = Table(
    name="lot_tender",
    record="lot_tender",
    key=_record_key("ordinal"),
    columns=(
        *_identity(),
        ORDINAL,
        Column("tender_id", "cbc:ID"),
        Column("lot_ref", "efac:TenderLot/cbc:ID"),
        Column("tendering_party_ref", "efac:TenderingParty/cbc:ID"),
        Column("tender_reference", "efac:TenderReference/cbc:ID"),
        Column(
            "payable_amount",
            "cac:LegalMonetaryTotal/cbc:PayableAmount",
            currency=True,
        ),
        Column("is_ranked", "efbc:TenderRankedIndicator"),
        Column("rank_code", "cbc:RankCode"),
        Column("is_variant", "efbc:TenderVariantIndicator"),
        Column("subcontracting_term_code", "efac:SubcontractingTerm/efbc:TermCode"),
    ),
)


LOT_RESULT_TABLE = Table(
    name="lot_result",
    record="lot_result",
    key=_record_key("ordinal"),
    columns=(
        *_identity(),
        ORDINAL,
        Column("lot_result_id", "cbc:ID"),
        Column("lot_ref", "efac:TenderLot/cbc:ID"),
        Column("result_code", "cbc:TenderResultCode"),
        # One lot result was measured naming 750 winning tenders and 747
        # contracts: a framework awarded to many suppliers is one result.
        Column("winning_tender_refs", "efac:LotTender/cbc:ID", Kind.SET),
        Column("contract_refs", "efac:SettledContract/cbc:ID", Kind.SET),
        Column("highest_tender_amount", "cbc:HigherTenderAmount", currency=True),
        Column("lowest_tender_amount", "cbc:LowerTenderAmount", currency=True),
        # This result's own framework ceiling, and the buyer's revised estimate
        # of it. Both are withheld often enough to matter: `max-val` and
        # `ree-val` are 17 of the privacy blocks in one publication day, and
        # until these columns existed there was nothing for those codes to mark
        # (ADR-0008).
        Column(
            "framework_max_amount",
            "efac:FrameworkAgreementValues/cbc:MaximumValueAmount",
            currency=True,
        ),
        Column(
            "framework_reestimated_amount",
            "efac:FrameworkAgreementValues/efbc:ReestimatedValueAmount",
            currency=True,
        ),
        Column(
            "decision_reason_code",
            "efac:DecisionReason/efbc:DecisionReasonCode",
        ),
    ),
)


#: Statistic block -> the kind recorded in `lot_result_statistic.statistic_kind`.
#: Both are code/value pairs that repeat within one lot result — twelve blocks
#: in the largest measured — so they are rows of their own rather than a pair of
#: columns that could only hold one block each.
STATISTIC_BLOCKS = {
    "efac:ReceivedSubmissionsStatistics": "received_submissions",
    "efac:AppealRequestsStatistics": "appeal_requests",
}

LOT_RESULT_STATISTIC_TABLE = Table(
    name="lot_result_statistic",
    record="lot_result",
    key=_record_key("lot_result_ordinal", "statistic_kind", "block_ordinal"),
    columns=(
        *_identity(),
        Column("lot_result_ordinal", structural=True),
        Column("statistic_kind", structural=True),
        Column("block_ordinal", structural=True),
        # The code says *which* count — tenders received, SME tenders, tenders
        # from other member states. A classifier reading the value without the
        # code is reading an unknown quantity.
        Column("statistic_code", kind=Kind.COMPUTED),
        Column("statistic_value", kind=Kind.COMPUTED),
    ),
)

#: Column -> its source element *inside* a statistics block. The columns above
#: are `COMPUTED` because a block is a row rather than a record, so they carry
#: no path of their own; this is where that path is stated, once. `rows.py`
#: reads the block with it and `privacy.py` joins the eForms SDK's withheld
#: fields onto it, so the two cannot drift into disagreeing about which element
#: a column holds.
STATISTIC_COLUMNS: tuple[tuple[str, str], ...] = (
    ("statistic_code", "efbc:StatisticsCode"),
    ("statistic_value", "efbc:StatisticsNumeric"),
)


SETTLED_CONTRACT_TABLE = Table(
    name="settled_contract",
    record="settled_contract",
    key=_record_key("ordinal"),
    columns=(
        *_identity(),
        ORDINAL,
        Column("contract_id", "cbc:ID"),
        Column("contract_reference", "efac:ContractReference/cbc:ID"),
        Column("tender_refs", "efac:LotTender/cbc:ID", Kind.SET),
        Column("issue_date", "cbc:IssueDate"),
        Column("award_date", "cbc:AwardDate"),
        Column("title", "cbc:Title", Kind.TEXT),
        Column("url", "cbc:URI"),
        Column("is_framework", "efbc:ContractFrameworkIndicator"),
    ),
)


#: Where a place of performance sits, per table it qualifies: the path prefix of
#: the repeatable `cac:RealizedLocation` block, relative to that record.
LOCATION_BLOCK = "cac:ProcurementProject/cac:RealizedLocation"

REALIZED_LOCATION_TABLE = Table(
    name="realized_location",
    record="",
    key=_record_key("scope_table", "scope_ordinal", "block_ordinal"),
    columns=(
        *_identity(),
        Column("scope_table", structural=True),
        Column("scope_ordinal", structural=True),
        Column("block_ordinal", structural=True),
        Column("country_code", kind=Kind.COMPUTED),
        Column("nuts_code", kind=Kind.COMPUTED),
    ),
)

#: Column -> its source element inside a `cac:RealizedLocation` block, stated
#: once here for the same reason as `STATISTIC_COLUMNS`: `rows.py` reads the
#: block with it, and anything auditing which source elements this model covers
#: needs them too. A block column is `COMPUTED` and carries no path of its own,
#: so without this the paths would exist only inside a function.
LOCATION_COLUMNS: tuple[tuple[str, str], ...] = (
    ("country_code", "cac:Address/cac:Country/cbc:IdentificationCode"),
    ("nuts_code", "cac:Address/cbc:CountrySubentityCode"),
)


#: The block a publisher marks a field non-public with, and its three coded
#: children. The free-text `efbc:ReasonDescription` is not among them: it is
#: dropped at parse per docs/personal-data.md.
PRIVACY_BLOCK = "efac:FieldsPrivacy"

FIELD_PRIVACY_TABLE = Table(
    name="field_privacy",
    record="",
    key=_record_key("scope_table", "scope_ordinal", "scope_path", "block_ordinal"),
    columns=(
        *_identity(),
        Column("scope_table", structural=True),
        Column("scope_ordinal", structural=True),
        # The element the block sits inside, relative to its record — empty
        # when it qualifies the record itself. Measured inside
        # `efac:ReceivedSubmissionsStatistics`, `efac:FrameworkAgreementValues`
        # and `efac:NoticeResult` among others, so the record alone does not
        # say what was withheld.
        Column("scope_path", structural=True),
        Column("block_ordinal", structural=True),
        Column("field_identifier_code", kind=Kind.COMPUTED),
        Column("reason_code", kind=Kind.COMPUTED),
        Column("publication_date", kind=Kind.COMPUTED),
    ),
)

#: Column -> its source element inside an `efac:FieldsPrivacy` block. The block's
#: fourth child, `efbc:ReasonDescription`, is deliberately absent: it is free
#: text that docs/personal-data.md drops at parse.
PRIVACY_COLUMNS: tuple[tuple[str, str], ...] = (
    ("field_identifier_code", "efbc:FieldIdentifierCode"),
    ("reason_code", "cbc:ReasonCode"),
    ("publication_date", "efbc:PublicationDate"),
)


#: Every table, in the order they are written. Keyed lookups go through
#: `table`, so nothing downstream hardcodes an index into this tuple.
TABLES: tuple[Table, ...] = (
    NOTICE_TABLE,
    PROCEDURE_TABLE,
    LOT_TABLE,
    ORGANISATION_TABLE,
    ORGANISATION_ROLE_TABLE,
    TENDERING_PARTY_TABLE,
    LOT_TENDER_TABLE,
    LOT_RESULT_TABLE,
    LOT_RESULT_STATISTIC_TABLE,
    SETTLED_CONTRACT_TABLE,
    REALIZED_LOCATION_TABLE,
    FIELD_PRIVACY_TABLE,
)


def table(name: str) -> Table:
    """The table called ``name``."""
    for candidate in TABLES:
        if candidate.name == name:
            return candidate
    raise KeyError(name)
