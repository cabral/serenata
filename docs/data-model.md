# Data model

The contract the normalise stage is written against: one relational model that
both eForms and legacy TED notices map into. Everything downstream of parse
depends on it, so it is a contract rather than a description — a change here is
a change to every classifier's inputs.

Storage is Parquet queried with DuckDB ([ADR-0001](adr/0001-parquet-duckdb-storage.md)).
Three decisions this document rests on have their own records:
[ADR-0005](adr/0005-element-paths-as-provenance.md) on how a field says where it
came from, [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md) on how it
says it has no value, and
[ADR-0007](adr/0007-repeated-values-are-carried-not-resolved.md) on what happens
when a notice gives it several.

`serenata/normalise/model.py` is this document in executable form, the way
`serenata/parse/personal_data.py` is `personal-data.md`, and
`tests/test_normalise_model.py` fails if the two disagree — so a column here
without a builder, or a builder without a column here, does not merge.

## What this is written against

Every source path below was **observed** in **19,180 notices across five
publication days of 2026** — OJ S 52, 94, 113, 157 and 168 — and the presence
figures are those packages', from [`field-usage.md`](field-usage.md). Where a
field the model needs is rare, the figure says so rather than the model
pretending otherwise. `tests/test_data_model.py` fails if a path cited here is
not one the survey actually measured.

Presence is not the only thing measured, and it was not enough. This document
originally gave one column to each path, which is a claim that the path occurs
once per record — false for nine of them against the first day measured, and ten
once a second day was, and not visible in a presence figure. `field-usage.md`
now reports **how many times each path occurs inside a single record**, and
`tests/test_normalise_model.py` fails if a column that holds one value reads a
path measured occurring more than once. The claim is checked rather than
assumed — against the days that have been measured, which is why the count went
from nine to ten and may go to eleven.

The shorthand `<ext>` stands for
`notice/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension`,
and `<org>` for `<ext>/efac:Organizations/efac:Organization`.

**That prediction has now been tested, and it was half right.** This document
was written against one publication day, and said that rerunning the survey over
more packages might move the percentages but should not move the structure.
Five days moved 66 of the percentages, none of them by more than 3 points — and
moved the structure once: `procedure.process_reason_codes` is a set now,
because 5 notices state two legal grounds where the first day's 3,190 never
stated more than one. Four days of notices bought one structural correction,
which is the rate at which this kind of error surfaces. More days will surface
more, and this document is what gets corrected.

## Identity: what is stable and what is not

This is the part most likely to be got wrong, so it comes first.

**eForms identifiers are scoped to their notice.** `ORG-0001` and `LOT-0001`
identify an organisation and a lot *within one notice*. The same buyer appears
as `ORG-0002` in the next day's notice. They are not global keys and the model
must not treat them as such.

**And the notice's own UUID is not unique either.** `notice/cbc:ID` looks like
the obvious primary key and is not one: two UUIDs each appear **twice** in
OJ S 157/2026, published as two notices on the same day — different notice
numbers, same contract folder, same issue date, same subtype. Keying on the
UUID would have merged two publications into one row.

Across all five days measured, **six UUIDs appear twice**, and one of those six
spans **two different publication dates**. So the duplication is not a
same-day artefact that a date could disambiguate: the same UUID can come back
weeks later.

So every table is keyed on the **publication**, which is unique across all
19,180 notices measured, plus the local identifier of the record within it.

| Key | Source | Present | Note |
|---|---|---:|---|
| `source_publication_id` | `<ext>/efac:Publication/efbc:NoticePublicationID` | 100.0% | the citable TED reference, e.g. `00566631-2026`; the primary key, on every row in every table |
| `source_notice_id` | `notice/cbc:ID` | 100.0% | the notice UUID; on every row, and **not** unique |

`source_publication_id` is also what a published flag links to, so a reader can
open the notice and check the claim.

**The one cross-notice key that exists** is `cbc:ContractFolderID` (98.3%): a
prior information notice, a contract notice and an award notice for the same
procurement share it. It is the spine that makes "this procedure took N days" a
question the data can answer. The missing 1.7% is a real gap, recorded per
[ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md) rather than filled in.

**Organisation identity across notices is not settled here.** `cbc:CompanyID`
(99.9%) is a national registration number and is the obvious candidate, but
national schemes differ, the same body appears under variant numbers, and
validating that is entity resolution — milestone 3. Until then the model carries
`company_ids` as an attribute, **not** as a key, and joins across notices on it
are the classifier author's risk to argue, not the model's promise.

## What parse hands over

The normalise stage does not read XML; it reads the records
`serenata.parse` produces, and two properties of those records decide whether
the columns below can be filled at all.

**Repeats are preserved and paired.** A path may occur several times in one
record — 97% of lot records and 73% of lot results in OJ S 157/2026 do this —
so each field carries the sibling index of every element on its path.
Two fields belong to the same repeated block exactly when those indices agree
down to that block's depth. This is what makes a statistic's code and its number
one row of `lot_result_statistic` rather than two unrelated lists, and a lot
result may carry a dozen such blocks.

**Attributes are kept.** `currencyID` is what makes an amount a sum of money,
`listName` says which code list a coded value belongs to, and `languageID`
distinguishes a buyer's name in one language from the same buyer's name in
another. Six currencies appear on `PayableAmount` in a single publication day.

## Entities

Twelve tables. Each row carries `source_publication_id`, `source_notice_id` and
`publication_year`; they are not repeated in the field tables below.

Nine hold the entities. Three exist because a repeatable block cannot be a
column — `lot_result_statistic`, `realized_location` and `field_privacy` — and
`organisation_role` was already an edge table for the same reason. See
[Repeated values](#repeated-values) and
[ADR-0007](adr/0007-repeated-values-are-carried-not-resolved.md).

```
                    procedure  (contract_folder_id)
                        |
        notice ---------+--------- lot
          |             |           |
    organisation  realized_location |
          |                         |
    organisation_role          lot_result --- settled_contract
                                    |              |
                            lot_result_statistic   |
                                    |              |
                             lot_tender -----------+
                                    |
                            tendering_party

     field_privacy — scoped to whichever record above it qualifies
```

### `notice`

One row per notice. The publication event itself. Its identity columns are the
`source_publication_id` and `source_notice_id` every row carries; a second copy
of the same value under a second name would only be a trap for whoever joined on
the wrong one.

| Column | Source path | Present |
|---|---|---:|
| `gazette_id` | `<ext>/efac:Publication/efbc:GazetteID` | 100.0% |
| `publication_date` | `<ext>/efac:Publication/efbc:PublicationDate` | 100.0% |
| `issue_date` | `notice/cbc:IssueDate` | 100.0% |
| `issue_time` | `notice/cbc:IssueTime` | 100.0% |
| `notice_type_code` | `notice/cbc:NoticeTypeCode` | 100.0% |
| `notice_subtype_code` | `<ext>/efac:NoticeSubType/cbc:SubTypeCode` | 100.0% |
| `version_id` | `notice/cbc:VersionID` | 100.0% |
| `regulatory_domain` | `notice/cbc:RegulatoryDomain` | 100.0% |
| `customization_id` | `notice/cbc:CustomizationID` | 100.0% |
| `language_code` | `notice/cbc:NoticeLanguageCode` | 100.0% |
| `contract_folder_id` | `notice/cbc:ContractFolderID` | 97.7% |
| `root_element` | the notice's root element | 100.0% |
| `changed_notice_id` | `<ext>/efac:Changes/efbc:ChangedNoticeIdentifier` | 14.8% |
| `changed_notice_namespace` | the link's identifier namespace | 14.8% |
| `changed_notice_target` | the link without its version suffix | 14.8% |
| `changed_notice_version` | the version the link names | 9.1% |

`root_element` is not an element path — it is the document's root, which the
survey records separately because notice types differ there
(`ContractNotice` 1,608, `ContractAwardNotice` 1,522, `PriorInformationNotice`
58, `BusinessRegistrationInformationNotice` 2).

`changed_notice_id` is the corrigendum link, as TED published it.
`changed_notice_namespace`, `changed_notice_target` and
`changed_notice_version` are that value split into its parts by
`serenata.normalise.corrections`, which is [ADR-0013](adr/0013-correction-and-withdrawal-semantics.md)
as code. They are not element paths.

Two unrelated identifier namespaces share the published column, measured in
[correction-links.md](correction-links.md): `eforms`, an eForms notice
identifier with a two-digit version suffix (1,752 of 2,840 links), and
`ted_legacy`, a legacy TED publication number and year (1,088). `unknown` is
declared for a shape neither pattern matches and is not produced by the
measured corpus. Only `eforms` targets can join `source_notice_id`, and only
after the suffix is removed — with it attached, a link resolves against
nothing.

A `ted_legacy` link carries no version, so `changed_notice_version` records
`absent` there rather than `not_applicable`: inapplicability is derivable from
the namespace, but that status is reserved for the notice-subtype rules this
pipeline does not carry (see [Absence](#absence)). The parts mirror the link's
own status otherwise — a withheld link has withheld parts.

Whether a target is *in* the dataset is not asked here. Supersession is a
question about the whole corpus, and one notice's rows cannot answer it;
the classify stage derives it. Handling corrections end to end remains
[#6](open-work.md#6-handle-corrected-and-withdrawn-notices), and withdrawals
are not detectable from anything measured yet.

### `procedure`

One row per notice: the procedure-level facts that sit outside the lot
structure.

| Column | Source path | Present |
|---|---|---:|
| `contract_folder_id` | `notice/cbc:ContractFolderID` | 97.7% |
| `title` | `notice/cac:ProcurementProject/cbc:Name` | 100.0% |
| `description` | `notice/cac:ProcurementProject/cbc:Description` | 100.0% |
| `procurement_type_code` | `notice/cac:ProcurementProject/cbc:ProcurementTypeCode` | 99.7% |
| `cpv_code` | `notice/cac:ProcurementProject/cac:MainCommodityClassification/cbc:ItemClassificationCode` | 100.0% |
| `internal_id` | `notice/cac:ProcurementProject/cbc:ID` | 81.7% |
| `procedure_code` | `notice/cac:TenderingProcess/cbc:ProcedureCode` | 91.5% |
| `process_reason_codes` | `notice/cac:TenderingProcess/cac:ProcessJustification/cbc:ProcessReasonCode` | 76.7% |
| `estimated_amount` | `notice/cac:ProcurementProject/cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount` | 41.5% |
| `total_amount` | `<ext>/efac:NoticeResult/cbc:TotalAmount` | 33.9% |
| `framework_overall_max_amount` | `<ext>/efac:NoticeResult/efbc:OverallMaximumFrameworkContractsAmount` | 6.3% |
| `framework_overall_approximate_amount` | `<ext>/efac:NoticeResult/efbc:OverallApproximateFrameworkContractsAmount` | 3.9% |

`title` and `description` are free text and are carried as **provenance only**.
Constraint 5 keeps classifiers to structured fields: no core classifier reads
either. They exist so a human verifying a flag can see what was bought. Both are
published once per language and are stored in the notice's own language, with a
`_language` companion saying which — see [Repeated values](#repeated-values).

`procedure_code` and `process_reason_codes` are the fields a
direct-award hypothesis would rest on. Both are coded, both are below 100%, and
both therefore need [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md)'s
status column to be read honestly.

`process_reason_codes` is a set because **a procedure can rest on more than one
legal ground**, and 5 notices of 19,180 state two. It was a scalar column while
one publication day was the whole evidence base, where the path never repeats;
widening the base to five days found the case. Those five notices did not
quietly store one of the two grounds — `Record.value` refused them, so they
failed to normalise until the column carried the set (ADR-0007). A
direct-award hypothesis reads the whole set: "the buyer cited this ground" is a
different question from "this was the only ground cited".

The place of performance is not here: `cac:RealizedLocation` repeats — one
procedure record was measured carrying 148 of them — so it is
[`realized_location`](#realized_location) rows.

### `lot`

One row per `cac:ProcurementProjectLot`. Most notices carry exactly one; the lot
is where the procurement's substance actually lives.

| Column | Source path | Present |
|---|---|---:|
| `lot_id` | `notice/cac:ProcurementProjectLot/cbc:ID` | 99.8% |
| `title` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cbc:Name` | 99.7% |
| `description` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cbc:Description` | 99.8% |
| `procurement_type_code` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cbc:ProcurementTypeCode` | 99.5% |
| `cpv_code` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cac:MainCommodityClassification/cbc:ItemClassificationCode` | 99.5% |
| `internal_id` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cbc:ID` | 87.8% |
| `funding_programme_code` | `notice/cac:ProcurementProjectLot/cac:TenderingTerms/cbc:FundingProgramCode` | 94.1% |
| `estimated_amount` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cac:RequestedTenderTotal/cbc:EstimatedOverallContractAmount` | 37.3% |
| `submission_deadline_date` | `notice/cac:ProcurementProjectLot/cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndDate` | 47.3% |
| `submission_deadline_time` | `notice/cac:ProcurementProjectLot/cac:TenderingProcess/cac:TenderSubmissionDeadlinePeriod/cbc:EndTime` | 47.3% |
| `contracting_system_codes` | `notice/cac:ProcurementProjectLot/cac:TenderingProcess/cac:ContractingSystem/cbc:ContractingSystemTypeCode` | 93.9% |
| `gpa_covered` | `notice/cac:ProcurementProjectLot/cac:TenderingProcess/cbc:GovernmentAgreementConstraintIndicator` | 92.0% |
| `electronic_auction` | `notice/cac:ProcurementProjectLot/cac:TenderingProcess/cac:AuctionTerms/cbc:AuctionConstraintIndicator` | 90.1% |

`contracting_system_codes` is a set: 53,192 of 58,248 lots carry exactly two
codes, one per contracting system the lot uses. `title` and `description` follow
the same language rule as `procedure`'s, and the lot's places of performance are
[`realized_location`](#realized_location) rows.

### `organisation`

One row per `efac:Organization` per notice. **Read
[`personal-data.md`](personal-data.md) before adding a column here** — this is
the table where constraint 2 bites.

| Column | Source path | Present |
|---|---|---:|
| `org_local_id` | `<org>/efac:Company/cac:PartyIdentification/cbc:ID` | 100.0% |
| `name` | `<org>/efac:Company/cac:PartyName/cbc:Name` | 100.0% |
| `company_ids` | `<org>/efac:Company/cac:PartyLegalEntity/cbc:CompanyID` | 100.0% |
| `country_code` | `<org>/efac:Company/cac:PostalAddress/cac:Country/cbc:IdentificationCode` | 100.0% |
| `city` | `<org>/efac:Company/cac:PostalAddress/cbc:CityName` | 100.0% |
| `postal_zone` | `<org>/efac:Company/cac:PostalAddress/cbc:PostalZone` | 100.0% |
| `nuts_code` | `<org>/efac:Company/cac:PostalAddress/cbc:CountrySubentityCode` | 100.0% |
| `street` | `<org>/efac:Company/cac:PostalAddress/cbc:StreetName` | 90.3% |
| `website` | `<org>/efac:Company/cbc:WebsiteURI` | 90.2% |
| `is_natural_person` | `<org>/efbc:NaturalPersonIndicator` | 11.1% |

`company_ids` is a set: 2,570 organisations carry more than one registration
number, up to five, and picking one would be picking which national register to
believe.

**`is_natural_person` governs five of the columns above.** Where it is true, the
organisation is a sole trader and `name`, `company_ids`, `city`, `postal_zone`,
`nuts_code` and `street` are a private individual's personal data — the
registration number most sharply, since in Sweden a sole trader's
`organisationsnummer` is the owner's `personnummer`. Parse suppresses them and
keeps `org_local_id`, so the row is anonymous but still joins. In the normalised
package this is visible: the 7 organisations flagged true have
`name_status = absent` and an `org_local_id` that is present.

Where the indicator is **absent** — about 90% of notices — its status column
reads `absent`, which is not `false`. Whether a flag may be published about such
an organisation is [#11](open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status).

There is no contact column, no beneficial owner table, and no committee member
anywhere in this model. That is [`personal-data.md`](personal-data.md) and it is
not negotiable. What the drop list cannot catch is a publisher typing a contact
address into a field that is not a contact field, which happens: see
[`known-issues.md`](known-issues.md).

### `organisation_role`

One row per organisation reference: which organisation played which role, and
where in the notice the reference was made. An organisation is a buyer in one
notice and a supplier in another, so the role is an edge, not a column on
`organisation`.

| Role value | Source path for the reference | Present |
|---|---|---:|
| `buyer` | `notice/cac:ContractingParty/cac:Party/cac:PartyIdentification/cbc:ID` | 100.0% |
| `procurement_service_provider` | `notice/cac:ContractingParty/cac:Party/cac:ServiceProviderParty/cac:Party/cac:PartyIdentification/cbc:ID` | 65.4% |
| `appeal_receiver` | `notice/cac:ProcurementProjectLot/cac:TenderingTerms/cac:AppealTerms/cac:AppealReceiverParty/cac:PartyIdentification/cbc:ID` | 99.3% |
| `tenderer` | `<ext>/efac:NoticeResult/efac:TenderingParty/efac:Tenderer/cbc:ID` | 41.1% |
| `contract_signatory` | `<ext>/efac:NoticeResult/efac:SettledContract/cac:SignatoryParty/cac:PartyIdentification/cbc:ID` | 7.2% |

Each value is an `ORG-nnnn` reference in `org_ref`, resolved against
`organisation` **within the same notice**. `scope_table` and `scope_ordinal` say
which record the reference was read from — the notice, a lot, a tendering party
or a settled contract — and `block_ordinal` its position among that role's
references there.

A row per *reference*, not per distinct organisation: five notices name the same
organisation as buyer in two contracting-party blocks carrying different type
codes, and collapsing them would have to choose one of the two descriptions.

Two columns qualify a role rather than being roles themselves. `buyer_type_code`
(`notice/cac:ContractingParty/cac:ContractingPartyType/cbc:PartyTypeCode`, 88.4%)
and `buyer_activity_code`
(`notice/cac:ContractingParty/cac:ContractingActivity/cbc:ActivityTypeCode`,
91.9%) hang off the `buyer` row, and `is_group_lead`
(`<ext>/efac:NoticeResult/efac:TenderingParty/efac:Tenderer/efbc:GroupLeadIndicator`)
off the `tenderer` row. Each is paired to its reference on the block they share,
so a notice with 163 buyers — the largest measured — keeps each buyer's type
with that buyer. On a role a qualifier does not apply to, its status is `absent`
(see [Absence](#absence): `not_applicable` is not derivable yet).

Despite its element name, `cac:SignatoryParty` references an organisation, not a
person who signed. It is kept for that reason and no other.

### `tendering_party`

One row per `efac:TenderingParty`. A bid can come from a consortium, so the
party that tendered is distinct from the organisations composing it.

| Column | Source path | Present |
|---|---|---:|
| `tendering_party_id` | `<ext>/efac:NoticeResult/efac:TenderingParty/cbc:ID` | 41.1% |
| `name` | `<ext>/efac:NoticeResult/efac:TenderingParty/cbc:Name` | 12.3% |

Members are `organisation_role` rows with role `tenderer`. The 44% presence is
not sparseness: award notices carry results and contract notices do not, and
those are roughly half the day each.

### `lot_tender`

One row per bid. **This is where most classifier inputs live.**

| Column | Source path | Present |
|---|---|---:|
| `tender_id` | `<ext>/efac:NoticeResult/efac:LotTender/cbc:ID` | 41.1% |
| `lot_ref` | `<ext>/efac:NoticeResult/efac:LotTender/efac:TenderLot/cbc:ID` | 41.1% |
| `tendering_party_ref` | `<ext>/efac:NoticeResult/efac:LotTender/efac:TenderingParty/cbc:ID` | 41.1% |
| `tender_reference` | `<ext>/efac:NoticeResult/efac:LotTender/efac:TenderReference/cbc:ID` | 41.1% |
| `payable_amount` | `<ext>/efac:NoticeResult/efac:LotTender/cac:LegalMonetaryTotal/cbc:PayableAmount` | 38.2% |
| `is_ranked` | `<ext>/efac:NoticeResult/efac:LotTender/efbc:TenderRankedIndicator` | 21.2% |
| `rank_code` | `<ext>/efac:NoticeResult/efac:LotTender/cbc:RankCode` | 15.4% |
| `is_variant` | `<ext>/efac:NoticeResult/efac:LotTender/efbc:TenderVariantIndicator` | 15.4% |
| `subcontracting_term_code` | `<ext>/efac:NoticeResult/efac:LotTender/efac:SubcontractingTerm/efbc:TermCode` | 38.9% |

`payable_amount` carries a currency attribute in the source, and so has a
`payable_amount_currency` companion — see [Amounts](#amounts) below. Currency
normalisation is a **normalise-stage** job, deterministic and documented, and it
is not done yet: the model stores amount and currency as published, and a
classifier comparing across currencies has to say how it converted.

### `lot_result`

One row per lot outcome.

| Column | Source path | Present |
|---|---|---:|
| `lot_result_id` | `<ext>/efac:NoticeResult/efac:LotResult/cbc:ID` | 44.7% |
| `lot_ref` | `<ext>/efac:NoticeResult/efac:LotResult/efac:TenderLot/cbc:ID` | 44.7% |
| `result_code` | `<ext>/efac:NoticeResult/efac:LotResult/cbc:TenderResultCode` | 38.0% |
| `winning_tender_refs` | `<ext>/efac:NoticeResult/efac:LotResult/efac:LotTender/cbc:ID` | 40.9% |
| `contract_refs` | `<ext>/efac:NoticeResult/efac:LotResult/efac:SettledContract/cbc:ID` | 40.8% |
| `highest_tender_amount` | `<ext>/efac:NoticeResult/efac:LotResult/cbc:HigherTenderAmount` | 9.8% |
| `lowest_tender_amount` | `<ext>/efac:NoticeResult/efac:LotResult/cbc:LowerTenderAmount` | 9.8% |
| `framework_max_amount` | `<ext>/efac:NoticeResult/efac:LotResult/efac:FrameworkAgreementValues/cbc:MaximumValueAmount` | 6.3% |
| `framework_reestimated_amount` | `<ext>/efac:NoticeResult/efac:LotResult/efac:FrameworkAgreementValues/efbc:ReestimatedValueAmount` | 3.9% |
| `decision_reason_code` | `<ext>/efac:NoticeResult/efac:LotResult/efac:DecisionReason/efbc:DecisionReasonCode` | 6.3% |

`winning_tender_refs` and `contract_refs` are sets: one lot result was measured
naming 750 winning tenders and 747 contracts, which is what a framework awarded
to many suppliers looks like.

The submissions and appeal statistics are **not** columns here. Each is a
repeatable code/value block — up to seventeen in one lot result — so they are
[`lot_result_statistic`](#lot_result_statistic) rows, which is also where the
single most important input this model carries lives.

### `lot_result_statistic`

One row per statistics block of a lot result. **The single most important input
this model carries**, and the reason
[ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md) exists.

| Column | Source path | Present |
|---|---|---:|
| `statistic_code` | `<ext>/efac:NoticeResult/efac:LotResult/efac:ReceivedSubmissionsStatistics/efbc:StatisticsCode` | 37.6% |
| `statistic_value` | `<ext>/efac:NoticeResult/efac:LotResult/efac:ReceivedSubmissionsStatistics/efbc:StatisticsNumeric` | 37.6% |

`statistic_kind` says which block the row came from: `received_submissions`, or
`appeal_requests` from
`<ext>/efac:NoticeResult/efac:LotResult/efac:AppealRequestsStatistics/efbc:StatisticsNumeric`
(6.7%) and its `efbc:StatisticsCode` sibling. `lot_result_ordinal` and
`block_ordinal` place the row.

The code says *which* count — `tenders` (3,282 rows), `t-esubm`, `t-sme`,
`t-oth-eea` — and the value is the number. **A classifier reading the value
without the code is reading an unknown quantity**, which is why the pair is a
row rather than two columns that could each hold one of twelve blocks.

**A withheld count is published, not omitted.** Two blocks in this package carry
the code `unpublished` and the number `-1`, with `efac:FieldsPrivacy` blocks
inside them naming `rec-sub-cou` (the number) and `rec-sub-typ` (the code it
counts). Both columns read `withheld`. A classifier reading the number without
the status would read a lawful deferral as a negative bid count.

Scope here is by containment as well as by code: a privacy block *inside* a
statistics block is about that block, which is what keeps one withheld count
from marking the other eleven a lot result can carry. Where the code is missing
or unresolvable both columns are marked, which is the conservative direction and
was the only behaviour available before the SDK mapping existed.

### `settled_contract`

| Column | Source path | Present |
|---|---|---:|
| `contract_id` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:ID` | 40.9% |
| `contract_reference` | `<ext>/efac:NoticeResult/efac:SettledContract/efac:ContractReference/cbc:ID` | 40.7% |
| `tender_refs` | `<ext>/efac:NoticeResult/efac:SettledContract/efac:LotTender/cbc:ID` | 40.8% |
| `issue_date` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:IssueDate` | 39.5% |
| `award_date` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:AwardDate` | 19.4% |
| `title` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:Title` | 15.2% |
| `url` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:URI` | 5.3% |
| `is_framework` | `<ext>/efac:NoticeResult/efac:SettledContract/efbc:ContractFrameworkIndicator` | 4.6% |

`tender_refs` is a set: 756 settled contracts name more than one tender, up to
35.

`award_date` is present in 20.4% of notices against `issue_date`'s 42.6%. Any
hypothesis about the interval between publication and award has to survive that
gap, and the base rate must be measured over the population that actually
carries both — not over all award notices.

### `realized_location`

One row per place of performance, for a procedure or a lot.
`cac:RealizedLocation` repeats — 3,185 records carry more than one, and one
carries 148 — so a location is a row rather than a pair of columns that could
hold one.

| Column | Source path | Present |
|---|---|---:|
| `country_code` | `notice/cac:ProcurementProject/cac:RealizedLocation/cac:Address/cac:Country/cbc:IdentificationCode` | 90.3% |
| `nuts_code` | `notice/cac:ProcurementProject/cac:RealizedLocation/cac:Address/cbc:CountrySubentityCode` | 83.0% |

For a lot the same fields are read from
`notice/cac:ProcurementProjectLot/cac:ProcurementProject/cac:RealizedLocation/cac:Address/cac:Country/cbc:IdentificationCode`
(94.1%) and
`notice/cac:ProcurementProjectLot/cac:ProcurementProject/cac:RealizedLocation/cac:Address/cbc:CountrySubentityCode`
(86.5%). `scope_table` is `procedure` or `lot`, `scope_ordinal` the record, and
`block_ordinal` the location's position in it.

The block also carries a city, postal zone, street and free-text description.
None of them is a column: a place of performance is not a party's address, the
model has no use for them yet, and a field with no use is a field not worth the
argument about what it might contain.

### `field_privacy`

One row per field a publisher marked as withheld or deferred. Small — 215 rows
across the package — and load-bearing.

| Column | Source path | Present |
|---|---|---:|
| `field_identifier_code` | `<ext>/efac:NoticeResult/efac:FieldsPrivacy/efbc:FieldIdentifierCode` | 1.5% |
| `reason_code` | `<ext>/efac:NoticeResult/efac:FieldsPrivacy/cbc:ReasonCode` | 1.5% |
| `publication_date` | `<ext>/efac:NoticeResult/efac:FieldsPrivacy/efbc:PublicationDate` | 0.1% |

`efbc:ReasonDescription` is **not** a column: it is free prose and is dropped at
parse per [`personal-data.md`](personal-data.md).

**The block is scoped to the element it sits inside**, which is finer than the
record. `efac:FieldsPrivacy` was measured inside `efac:NoticeResult` (52),
`efac:LotTender` (116), `efac:LotResult` (22), `efac:FrameworkAgreementValues`
(17), `efac:ReceivedSubmissionsStatistics` (4) and an awarding criterion (1). A
row therefore carries `scope_table` and `scope_ordinal` for the record, plus
`scope_path` for the element within it and `block_ordinal` for which block.

This table is what turns a withheld field into the status `withheld` on the
field it names, for the codes the eForms SDK can place — 143 of these 215 rows.
Every row is kept either way, including the 72 whose code this model cannot act
on; see [Absence](#absence).

## Absence

Full reasoning in [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md).
The contract:

**Every column that is not structural has a companion `<column>_status`
column** taking one of five values. Uniformly, without per-field judgement about
which columns deserve one. Structural columns — the keys, the ordinals, the
partition — have none: they are how a row is addressed, not something a notice
provided.

| Status | Meaning |
|---|---|
| `present` | the element carried a value |
| `empty` | the element was present and carried no value |
| `absent` | the element was not in the notice — "not provided" |
| `withheld` | the publisher marked it non-public via `efac:FieldsPrivacy` |
| `not_applicable` | the notice subtype makes the field inapplicable |

`present` and `empty` are directly observable. `empty` is also, measurably,
rare: a pass over OJ S 157/2026 finds **zero** blank leaf elements among all
897,471 — dropped paths included, since that count applies no filter — so
the 296 paths `field-usage.md` reports as "containers or blank elements" are all
containers. The status is kept because conflating a blank element with an absent
one would be silently wrong and costs nothing to avoid, not because this package
shows it happening. `absent` is the complement.

**`withheld` is derived from the code the publisher published**, because a
withheld value is published rather than omitted. An amount marked non-public
arrives as `-1`, and a bid count as the code `unpublished` with the number `-1`.
A classifier reading those as quantities reads a lawful deferral as a negative
price, which is the failure this status exists to prevent.

An `efac:FieldsPrivacy` block names its target with an eForms field identifier —
`win-ten-val`, `ten-val-low`, `rec-sub-cou` — and the eForms SDK is what says
which element each code means. That table is generated into
`serenata/normalise/sdk_privacy.py` and joined onto these columns at import;
[ADR-0008](adr/0008-eforms-sdk-privacy-mapping.md) records the decision, the
licence and the checks. **212 of the 215 privacy blocks in this package mark a
column**:

| Column | Blocks | Code |
|---|---:|---|
| `lot_tender.payable_amount` | 74 | `win-ten-val` |
| `procedure.total_amount` | 44 | `not-val` |
| `lot_tender.is_variant` | 42 | `win-ten-var` |
| `lot_result.highest_tender_amount` | 11 | `ten-val-hig` |
| `lot_result.lowest_tender_amount` | 11 | `ten-val-low` |
| `lot_result.framework_max_amount` | 11 | `max-val` |
| `procedure.framework_overall_max_amount` | 6 | `not-max-val` |
| `lot_result.framework_reestimated_amount` | 6 | `ree-val` |
| `procedure.framework_overall_approximate_amount` | 2 | `not-app-val` |
| `lot_result_statistic.statistic_value` | 2 | `rec-sub-cou` |
| `lot_result_statistic.statistic_code` | 2 | `rec-sub-typ` |
| `lot_result.decision_reason_code` | 1 | `no-awa-rea` |

**The remaining 3 are refused rather than approximated**, and each is still a
`field_privacy` row. All three are told apart from another field only by an
XPath predicate, which these paths do not carry (ADR-0005) — so acting on them
would mark the wrong column. Sixteen of the SDK's 47 codes resolve here; the
rest name fields this model has no column for, and `privacy.UNUSABLE` names
every gap with its reason.

Five of those sixteen were unresolvable until the value columns above existed:
`not-val`, `max-val`, `ree-val`, `not-max-val` and `not-app-val` are 69 blocks
between them, and the code was recorded with nothing to mark. Adding the columns
the indicator literature needed closed the privacy gap as a side effect, which
is why coverage moved from 143 to 212.

**The value is never rewritten.** A withheld amount still reads `-1`, exactly as
the notice published it; only the status carries the interpretation. That
matters because the two do not always agree: in this package, two payable
amounts declared non-public carry a value other than `-1`, one lot result
carries `1` for both its declared-non-public highest and lowest tender amount,
and two settled contracts carry a contract reference of `-1` that no block
declares. [`dataset-shape.md`](dataset-shape.md) counts `-1` by column
independently of any declaration, so neither signal hides the other.

`not_applicable` is derived from the eForms notice-subtype rules and needs the
same SDK. Until then an inapplicable field is recorded `absent`, which is
conservative and honest rather than silently wrong — and nothing downstream may
read `absent` as proof a field was applicable.

A classifier that reads a value without reading its status is a bug, and one
that treats `withheld` as a low count is the specific bug this design exists to
prevent.

## Amounts

**Every amount column has a `<column>_currency` companion**, taking the
`currencyID` attribute of the element the amount came from. Nine currencies
appear on `PayableAmount` in a single publication day — RON, EUR, PLN, CZK, HUF,
SEK, CHF, DKK and NOK — so an amount column on its own is a number, not a sum of
money, and two of them cannot be compared or summed.

The columns this applies to are `lot_tender.payable_amount`,
`lot_result.highest_tender_amount` and `lot_result.lowest_tender_amount`. Any
amount added later takes a companion in the same commit.

Currency is recorded, never converted. Conversion needs a rate and a date, both
of which are choices, and a classifier that compares across currencies has to
state which it made.

**An amount of `-1` is not a price.** It is how a withheld value is published;
see [Absence](#absence). Amounts are stored as the strings the notice carried,
so nothing here silently turns that sentinel into a number.

## Keys and ordinals

Every table is keyed on `source_publication_id` — the notice UUID is not unique,
as [Identity](#identity-what-is-stable-and-what-is-not) says — plus what
identifies the row within that publication.

Records of the same kind are told apart by `ordinal`: **the container's
position among all containers of its kind in the notice, in document order**,
not its position among its immediate siblings. The distinction shows when a
notice carries more than one `ext:UBLExtension` — organisations in the second
continue the numbering rather than restarting.

`(source_publication_id, ordinal)` is therefore a stable key, and it
deliberately says nothing about which parent a record hung from. The model does
not carry parentage either, so nothing downstream should infer it from the
ordinal.

Rows built from a repeatable block inside a record — statistics, locations,
privacy entries, role references — add the record they sit in and a
`block_ordinal`, the block's position in document order within that record.
Every key is unique across the 98,629 rows the package produces, and a test
asserts it.

## Repeated values

A path may occur several times in one record — 97% of lot records and 73% of lot
results do — so **asking a record for a single value at a repeated path is an
error, not a coin toss**: `Record.value()` raises rather than returning an
arbitrary one of several.

[ADR-0007](adr/0007-repeated-values-are-carried-not-resolved.md) settles what
this model does with them. Three shapes, three answers:

- **A bare repeated value is a set column**, a `list<string>` in document order,
  named plurally: `contracting_system_codes`, `company_ids`,
  `winning_tender_refs`, `contract_refs`, `tender_refs`.
- **A repeated block with structure inside it is its own table**, one row per
  block: `lot_result_statistic`, `realized_location`, `field_privacy`,
  `organisation_role`. The pairing a block gives — a statistic's code with its
  own number — survives as a row and cannot come apart.
- **Free text published once per language is stored in the notice's own
  language**, with a `<column>_language` companion saying which. In all 37,498
  title, description and organisation-name fields measured, the notice's
  language is among those offered; where it would not be, the first in document
  order wins. The other languages stay in the archived source, which is the
  ground truth.

A column declared to hold one value **raises** when it meets several: the notice
is reported as unnormalised and named, and the run continues. That is model
drift being reported rather than an arbitrary value being stored, and it is not
hypothetical: it happened to 5 notices the first time this model met a
publication day it had not been written against. Each was named, the other
19,175 normalised, and the fix was to make `process_reason_codes` carry the set.
A model that had picked a value instead would have produced 19,180 rows and no
sign that five of them were arbitrary.

## Excluded by design

Fields that could name a natural person get **no column here**, not a nullable
one. The list, its reasoning and its measured frequencies are
[`personal-data.md`](personal-data.md); the short form is that any path through
`cac:Contact`, `efac:UltimateBeneficialOwner` or `cac:TechnicalCommitteePerson`,
plus the free-text `efac:FieldsPrivacy/efbc:ReasonDescription`, is dropped at
parse and never reaches this model.

Adding a column that maps to one of those paths is a constraint 2 violation
whether or not anyone notices, which is why the drop is enforced in code and
tested rather than left to this document.

**What a path-based drop list cannot catch** is a publisher typing a contact
address into a field that is not a contact field. Scanning the normalised
package finds 46 email-shaped values in columns that should hold a city, a
registration number, a street or a description — 13 of them shaped like a
person's own address. The drop list is structural and correct; this is a
different problem and is recorded in [`known-issues.md`](known-issues.md) rather
than quietly tolerated.

## Legacy TED: mapped later, not guessed now

The model is **one model** — buyers, procedures, lots, bids and awards exist in
both formats, and that structural claim is not in doubt. What does not exist yet
is the per-field mapping from legacy TED elements into these columns.

The reason is the same as in [`personal-data.md`](personal-data.md): OJ S
157/2026 contains **zero** legacy-schema notices, so there is nothing to measure,
and this project does not publish spec-read mappings as though they were
measured. Every table above would gain a "legacy TED source" column; all of them
are currently empty.

Until a pre-2024 package is fetched and surveyed, parse refuses legacy notices.
Nothing is blocked by this today: no archived package contains one.

## Storage

Parquet, queried with DuckDB ([ADR-0001](adr/0001-parquet-duckdb-storage.md)).

- One dataset per table, partitioned by `publication_year` from
  `<ext>/efac:Publication/efbc:PublicationDate` — not from the run clock. A
  notice whose date is missing or unreadable lands in `publication_year=unknown`
  rather than being dropped.
- Hive-style layout: `<root>/<table>/publication_year=<year>/<package id>.parquet`.
  The file is named after the source package, so rerunning a package rewrites
  its own file and two packages in the same year sit side by side without a
  generated name.
- **Values are stored as published, as strings.** Casting is a decision with
  edge cases — the `-1` sentinel above is the worked example — and belongs to
  whoever queries, explicitly. The exception is the ordinals, which are this
  project's own numbering and are stored as integers.
- Rows sorted by their primary key before every write. Never rely on scan order.
- Writer options pinned — zstd at level 3, format version 2.6, v2 data pages,
  dictionary encoding, 20,000-row row groups — because Parquet is only
  byte-stable if the writer is made so. `serenata.normalise.dataset.WRITER` is
  where they live and `uv.lock` pins the writer itself.
- A table with no rows is still written, with its schema, so a query against an
  empty table returns nothing rather than failing to find a file.
- Status columns are low-cardinality strings; dictionary encoding makes the
  companion column nearly free, which is what allows the uniform rule above.

One daily package of 3,190 notices produces 98,629 rows across the twelve
tables, 4.2 MB on disk, in about 12 seconds and 339 MB of peak resident memory
(see [`known-issues.md`](known-issues.md) for how the stages were measured). The
five days this model is measured against are 632,068 rows.
Rerunning it writes byte-identical files, which
[#9](open-work.md#9-add-the-rerun-identity-determinism-test) asserts in CI.

The row counts, and how populated each column of this model actually is, are in
[`dataset-shape.md`](dataset-shape.md) — generated from the archive rather than
written here, so a model that stops matching its own output says so.

## What this does not settle

- **Cross-notice organisation identity.** Milestone 3. `company_id` is an
  attribute here, not a key.
- **Currency normalisation.** Amounts are stored as published, with their
  currency. A cross-currency comparison is the classifier's argument to make.
- **Corrections and withdrawals.** `changed_notice_id` is captured;
  [#6](open-work.md#6-handle-corrected-and-withdrawn-notices) decides what to do
  with it.
- **`not_applicable` derivation.** Needs the notice-subtype rules from the
  eForms SDK, which the offline pipeline does not carry today.
- **The 72 privacy blocks whose code cannot be placed**, above. Sixty-nine name
  a field with no column here — the notice's total amount most often — and three
  are distinguished from another field only by an XPath predicate these paths do
  not carry. Adding the columns makes most of them resolve with no other change
  (ADR-0008).
- **Personal data a publisher put in the wrong field**, above. The model has no
  mechanism for it, and inventing one is a decision rather than a patch.
- **Legacy TED mappings**, above.
