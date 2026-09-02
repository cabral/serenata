# Data model

The contract the normalise stage is written against: one relational model that
both eForms and legacy TED notices map into. Everything downstream of parse
depends on it, so it is a contract rather than a description — a change here is
a change to every classifier's inputs.

Storage is Parquet queried with DuckDB ([ADR-0001](adr/0001-parquet-duckdb-storage.md)).
Two decisions this document rests on have their own records:
[ADR-0005](adr/0005-element-paths-as-provenance.md) on how a field says where it
came from, and [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md) on how
it says it has no value.

## What this is written against

Every source path below was **observed** in the 3,190 notices of OJ S 157/2026,
and the presence figures are that package's, from
[`field-usage.md`](field-usage.md). Where a field the model needs is rare, the
figure says so rather than the model pretending otherwise. `tests/test_data_model.py`
fails if a path cited here is not one the survey actually measured.

The shorthand `<ext>` stands for
`notice/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension`,
and `<org>` for `<ext>/efac:Organizations/efac:Organization`.

One publication day is one day's mix of notice types and member states. Rerunning
the survey over more packages ([#2](open-work.md#2-survey-which-eforms-fields-notices-actually-populate))
may move the percentages; it should not move the structure, and if it does, this
document is what gets corrected.

## Identity: what is stable and what is not

This is the part most likely to be got wrong, so it comes first.

**eForms identifiers are scoped to their notice.** `ORG-0001` and `LOT-0001`
identify an organisation and a lot *within one notice*. The same buyer appears
as `ORG-0002` in the next day's notice. They are not global keys and the model
must not treat them as such.

So every table's primary key is a pair: the notice, plus the local identifier.

| Key | Source | Present | Note |
|---|---|---:|---|
| `source_notice_id` | `notice/cbc:ID` | 100.0% | the notice UUID; on every row in every table |
| `source_publication_id` | `<ext>/efac:Publication/efbc:NoticePublicationID` | 100.0% | the citable TED reference, e.g. `00566631-2026` |

`source_publication_id` is what a published flag links to, so a reader can open
the notice and check the claim. It is on every row for that reason, not for
joining.

**The one cross-notice key that exists** is `cbc:ContractFolderID` (98.3%): a
prior information notice, a contract notice and an award notice for the same
procurement share it. It is the spine that makes "this procedure took N days" a
question the data can answer. The missing 1.7% is a real gap, recorded per
[ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md) rather than filled in.

**Organisation identity across notices is not settled here.** `cbc:CompanyID`
(99.9%) is a national registration number and is the obvious candidate, but
national schemes differ, the same body appears under variant numbers, and
validating that is entity resolution — milestone 3. Until then the model carries
`company_id` as an attribute, **not** as a key, and joins across notices on it
are the classifier author's risk to argue, not the model's promise.

## What parse hands over

The normalise stage does not read XML; it reads the records
`serenata.parse` produces, and two properties of those records decide whether
the columns below can be filled at all.

**Repeats are preserved and paired.** A path may occur several times in one
record — 97% of lot records and 73% of lot results in OJ S 157/2026 do this —
so each field carries the sibling index of every element on its path.
Two fields belong to the same repeated block exactly when those indices agree
down to that block's depth. This is what makes
`submissions_statistic_code` and `submissions_statistic_value` a pair rather
than two unrelated lists, and a lot result may carry a dozen such blocks.

**Attributes are kept.** `currencyID` is what makes an amount a sum of money,
`listName` says which code list a coded value belongs to, and `languageID`
distinguishes a buyer's name in one language from the same buyer's name in
another. Six currencies appear on `PayableAmount` in a single publication day.

## Entities

Nine tables. Each row carries `source_notice_id` and `source_publication_id`;
they are not repeated in the field tables below.

```
                    procedure  (contract_folder_id)
                        |
        notice ---------+--------- lot
          |                         |
    organisation              lot_result --- settled_contract
          |                         |              |
    organisation_role          lot_tender ---------+
                                    |
                            tendering_party
```

### `notice`

One row per notice. The publication event itself.

| Column | Source path | Present |
|---|---|---:|
| `notice_id` | `notice/cbc:ID` | 100.0% |
| `publication_id` | `<ext>/efac:Publication/efbc:NoticePublicationID` | 100.0% |
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
| `contract_folder_id` | `notice/cbc:ContractFolderID` | 98.3% |
| `root_element` | the notice's root element | 100.0% |
| `changed_notice_id` | `<ext>/efac:Changes/efbc:ChangedNoticeIdentifier` | 14.8% |

`root_element` is not an element path — it is the document's root, which the
survey records separately because notice types differ there
(`ContractNotice` 1,608, `ContractAwardNotice` 1,522, `PriorInformationNotice`
58, `BusinessRegistrationInformationNotice` 2).

`changed_notice_id` is the corrigendum link. Handling corrections properly is
[#6](open-work.md#6-handle-corrected-and-withdrawn-notices) and needs its own
ADR; the column exists now so the fact is not lost at parse time.

### `procedure`

One row per `contract_folder_id` per notice. Procedure-level facts, which sit
outside the lot structure.

| Column | Source path | Present |
|---|---|---:|
| `contract_folder_id` | `notice/cbc:ContractFolderID` | 98.3% |
| `title` | `notice/cac:ProcurementProject/cbc:Name` | 99.9% |
| `description` | `notice/cac:ProcurementProject/cbc:Description` | 99.9% |
| `procurement_type_code` | `notice/cac:ProcurementProject/cbc:ProcurementTypeCode` | 99.7% |
| `cpv_code` | `notice/cac:ProcurementProject/cac:MainCommodityClassification/cbc:ItemClassificationCode` | 99.9% |
| `internal_id` | `notice/cac:ProcurementProject/cbc:ID` | 83.9% |
| `procedure_code` | `notice/cac:TenderingProcess/cbc:ProcedureCode` | 91.1% |
| `process_reason_code` | `notice/cac:TenderingProcess/cac:ProcessJustification/cbc:ProcessReasonCode` | 76.4% |
| `country_code` | `notice/cac:ProcurementProject/cac:RealizedLocation/cac:Address/cac:Country/cbc:IdentificationCode` | 91.7% |
| `nuts_code` | `notice/cac:ProcurementProject/cac:RealizedLocation/cac:Address/cbc:CountrySubentityCode` | 83.9% |

`title` and `description` are free text and are carried as **provenance only**.
Constraint 5 keeps classifiers to structured fields: no core classifier reads
either. They exist so a human verifying a flag can see what was bought.

`procedure_code` and `process_reason_code` are the fields a
direct-award hypothesis would rest on. Both are coded, both are below 100%, and
both therefore need [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md)'s
status column to be read honestly.

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
| `internal_id` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cbc:ID` | 90.0% |
| `country_code` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cac:RealizedLocation/cac:Address/cac:Country/cbc:IdentificationCode` | 94.1% |
| `nuts_code` | `notice/cac:ProcurementProjectLot/cac:ProcurementProject/cac:RealizedLocation/cac:Address/cbc:CountrySubentityCode` | 86.5% |
| `funding_programme_code` | `notice/cac:ProcurementProjectLot/cac:TenderingTerms/cbc:FundingProgramCode` | 94.1% |
| `contracting_system_code` | `notice/cac:ProcurementProjectLot/cac:TenderingProcess/cac:ContractingSystem/cbc:ContractingSystemTypeCode` | 93.9% |
| `gpa_covered` | `notice/cac:ProcurementProjectLot/cac:TenderingProcess/cbc:GovernmentAgreementConstraintIndicator` | 92.3% |
| `electronic_auction` | `notice/cac:ProcurementProjectLot/cac:TenderingProcess/cac:AuctionTerms/cbc:AuctionConstraintIndicator` | 89.7% |

### `organisation`

One row per `efac:Organization` per notice. **Read
[`personal-data.md`](personal-data.md) before adding a column here** — this is
the table where constraint 2 bites.

| Column | Source path | Present |
|---|---|---:|
| `org_local_id` | `<org>/efac:Company/cac:PartyIdentification/cbc:ID` | 99.9% |
| `name` | `<org>/efac:Company/cac:PartyName/cbc:Name` | 99.9% |
| `company_id` | `<org>/efac:Company/cac:PartyLegalEntity/cbc:CompanyID` | 99.9% |
| `country_code` | `<org>/efac:Company/cac:PostalAddress/cac:Country/cbc:IdentificationCode` | 99.9% |
| `city` | `<org>/efac:Company/cac:PostalAddress/cbc:CityName` | 99.9% |
| `postal_zone` | `<org>/efac:Company/cac:PostalAddress/cbc:PostalZone` | 99.9% |
| `nuts_code` | `<org>/efac:Company/cac:PostalAddress/cbc:CountrySubentityCode` | 99.9% |
| `street` | `<org>/efac:Company/cac:PostalAddress/cbc:StreetName` | 92.4% |
| `website` | `<org>/efac:Company/cbc:WebsiteURI` | 91.1% |
| `is_natural_person` | `<org>/efbc:NaturalPersonIndicator` | 9.5% |

**`is_natural_person` governs five of the columns above.** Where it is true, the
organisation is a sole trader and `name`, `company_id`, `city`, `postal_zone`,
`nuts_code` and `street` are a private individual's personal data — the
registration number most sharply, since in Sweden a sole trader's
`organisationsnummer` is the owner's `personnummer`. Parse suppresses them and
keeps `org_local_id`, so the row is anonymous but still joins.

Where the indicator is **absent** — about 90% of notices — its status column
reads `absent`, which is not `false`. Whether a flag may be published about such
an organisation is [#11](open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status).

There is no contact column, no beneficial owner table, and no committee member
anywhere in this model. That is [`personal-data.md`](personal-data.md) and it is
not negotiable.

### `organisation_role`

One row per (notice, organisation, role). An organisation is a buyer in one
notice and a supplier in another, so the role is an edge, not a column on
`organisation`.

| Role value | Source path for the reference | Present |
|---|---|---:|
| `buyer` | `notice/cac:ContractingParty/cac:Party/cac:PartyIdentification/cbc:ID` | 99.9% |
| `procurement_service_provider` | `notice/cac:ContractingParty/cac:Party/cac:ServiceProviderParty/cac:Party/cac:PartyIdentification/cbc:ID` | 67.4% |
| `appeal_receiver` | `notice/cac:ProcurementProjectLot/cac:TenderingTerms/cac:AppealTerms/cac:AppealReceiverParty/cac:PartyIdentification/cbc:ID` | 99.3% |
| `tenderer` | `<ext>/efac:NoticeResult/efac:TenderingParty/efac:Tenderer/cbc:ID` | 44.0% |
| `contract_signatory` | `<ext>/efac:NoticeResult/efac:SettledContract/cac:SignatoryParty/cac:PartyIdentification/cbc:ID` | 8.0% |

Each value is an `ORG-nnnn` reference resolved against `organisation` **within
the same notice**. `buyer_type_code`
(`notice/cac:ContractingParty/cac:ContractingPartyType/cbc:PartyTypeCode`, 88.4%)
and `buyer_activity_code`
(`notice/cac:ContractingParty/cac:ContractingActivity/cbc:ActivityTypeCode`,
91.9%) hang off the `buyer` row.

Despite its element name, `cac:SignatoryParty` references an organisation, not a
person who signed. It is kept for that reason and no other.

### `tendering_party`

One row per `efac:TenderingParty`. A bid can come from a consortium, so the
party that tendered is distinct from the organisations composing it.

| Column | Source path | Present |
|---|---|---:|
| `tendering_party_id` | `<ext>/efac:NoticeResult/efac:TenderingParty/cbc:ID` | 44.0% |
| `name` | `<ext>/efac:NoticeResult/efac:TenderingParty/cbc:Name` | 11.0% |

Members are `organisation_role` rows with role `tenderer`. The 44% presence is
not sparseness: award notices carry results and contract notices do not, and
those are roughly half the day each.

### `lot_tender`

One row per bid. **This is where most classifier inputs live.**

| Column | Source path | Present |
|---|---|---:|
| `tender_id` | `<ext>/efac:NoticeResult/efac:LotTender/cbc:ID` | 44.0% |
| `lot_ref` | `<ext>/efac:NoticeResult/efac:LotTender/efac:TenderLot/cbc:ID` | 44.0% |
| `tendering_party_ref` | `<ext>/efac:NoticeResult/efac:LotTender/efac:TenderingParty/cbc:ID` | 44.0% |
| `tender_reference` | `<ext>/efac:NoticeResult/efac:LotTender/efac:TenderReference/cbc:ID` | 44.0% |
| `payable_amount` | `<ext>/efac:NoticeResult/efac:LotTender/cac:LegalMonetaryTotal/cbc:PayableAmount` | 40.2% |
| `is_ranked` | `<ext>/efac:NoticeResult/efac:LotTender/efbc:TenderRankedIndicator` | 21.5% |
| `rank_code` | `<ext>/efac:NoticeResult/efac:LotTender/cbc:RankCode` | 14.5% |
| `is_variant` | `<ext>/efac:NoticeResult/efac:LotTender/efbc:TenderVariantIndicator` | 16.7% |
| `subcontracting_term_code` | `<ext>/efac:NoticeResult/efac:LotTender/efac:SubcontractingTerm/efbc:TermCode` | 41.0% |

`payable_amount` carries a currency attribute in the source, and so has a
`payable_amount_currency` companion — see [Amounts](#amounts) below. Currency
normalisation is a **normalise-stage** job, deterministic and documented, and it
is not done yet: the model stores amount and currency as published, and a
classifier comparing across currencies has to say how it converted.

### `lot_result`

One row per lot outcome. The bid-count statistics here are the single most
important input the model carries.

| Column | Source path | Present |
|---|---|---:|
| `lot_result_id` | `<ext>/efac:NoticeResult/efac:LotResult/cbc:ID` | 47.5% |
| `lot_ref` | `<ext>/efac:NoticeResult/efac:LotResult/efac:TenderLot/cbc:ID` | 47.5% |
| `result_code` | `<ext>/efac:NoticeResult/efac:LotResult/cbc:TenderResultCode` | 39.8% |
| `winning_tender_ref` | `<ext>/efac:NoticeResult/efac:LotResult/efac:LotTender/cbc:ID` | 43.8% |
| `contract_ref` | `<ext>/efac:NoticeResult/efac:LotResult/efac:SettledContract/cbc:ID` | 43.5% |
| `submissions_statistic_code` | `<ext>/efac:NoticeResult/efac:LotResult/efac:ReceivedSubmissionsStatistics/efbc:StatisticsCode` | 39.4% |
| `submissions_statistic_value` | `<ext>/efac:NoticeResult/efac:LotResult/efac:ReceivedSubmissionsStatistics/efbc:StatisticsNumeric` | 39.4% |
| `highest_tender_amount` | `<ext>/efac:NoticeResult/efac:LotResult/cbc:HigherTenderAmount` | 10.3% |
| `lowest_tender_amount` | `<ext>/efac:NoticeResult/efac:LotResult/cbc:LowerTenderAmount` | 10.3% |
| `decision_reason_code` | `<ext>/efac:NoticeResult/efac:LotResult/efac:DecisionReason/efbc:DecisionReasonCode` | 6.3% |
| `appeal_statistic_value` | `<ext>/efac:NoticeResult/efac:LotResult/efac:AppealRequestsStatistics/efbc:StatisticsNumeric` | 6.7% |

The submissions statistics are a code/value pair — the code says *which* count
(tenders received, SME tenders, tenders from other member states) and the value
is the number. A classifier reading the value without the code is reading an
unknown quantity.

**This pair is why [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md)
exists.** A single-bid classifier — the most cited red flag in the literature —
reads exactly this field. `efac:ReceivedSubmissionsStatistics` is one of the
fields publishers can withhold through `efac:FieldsPrivacy`, and it is observed
withheld in this package. If "withheld" collapsed into the same NULL as "not
provided" and a classifier read either as a low bid count, the project would
publish a flag against a buyer who did nothing but exercise a lawful deferral.
That is the failure this model is shaped to prevent.

### `settled_contract`

| Column | Source path | Present |
|---|---|---:|
| `contract_id` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:ID` | 43.8% |
| `contract_reference` | `<ext>/efac:NoticeResult/efac:SettledContract/efac:ContractReference/cbc:ID` | 43.6% |
| `tender_ref` | `<ext>/efac:NoticeResult/efac:SettledContract/efac:LotTender/cbc:ID` | 43.7% |
| `issue_date` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:IssueDate` | 42.6% |
| `award_date` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:AwardDate` | 20.4% |
| `title` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:Title` | 15.6% |
| `url` | `<ext>/efac:NoticeResult/efac:SettledContract/cbc:URI` | 5.6% |
| `is_framework` | `<ext>/efac:NoticeResult/efac:SettledContract/efbc:ContractFrameworkIndicator` | 5.6% |

`award_date` is present in 20.4% of notices against `issue_date`'s 42.6%. Any
hypothesis about the interval between publication and award has to survive that
gap, and the base rate must be measured over the population that actually
carries both — not over all award notices.

### `field_privacy`

One row per field a publisher marked as withheld or deferred. Small (1.6% of
notices) and load-bearing.

| Column | Source path | Present |
|---|---|---:|
| `field_identifier_code` | `<ext>/efac:NoticeResult/efac:FieldsPrivacy/efbc:FieldIdentifierCode` | 1.6% |
| `reason_code` | `<ext>/efac:NoticeResult/efac:FieldsPrivacy/cbc:ReasonCode` | 1.6% |
| `publication_date` | `<ext>/efac:NoticeResult/efac:FieldsPrivacy/efbc:PublicationDate` | 0.1% |

`efbc:ReasonDescription` is **not** a column: it is free prose and is dropped at
parse per [`personal-data.md`](personal-data.md). `efac:FieldsPrivacy` also
appears under `efac:LotResult`, `efac:LotTender` and elsewhere; each occurrence
produces a row scoped to the record it qualifies.

This table is what turns a withheld field into the status
`withheld` on the field it names, rather than into an unexplained NULL.

**How its rows are built.** `efac:FieldsPrivacy` is not a parse container, so
its values arrive as fields of whichever record encloses them, under a relative
path ending in `efac:FieldsPrivacy/…`. Normalise reads those, and their
`Field.occurrence` says which block each belongs to when a record carries
several. The enclosing record is what the row is scoped to.

## Absence

Full reasoning in [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md).
The contract:

**Every nullable column has a companion `<column>_status` column** taking one of
five values. Uniformly, without per-field judgement about which columns deserve
one.

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
shows it happening. `absent` is the complement. `withheld` comes from
`field_privacy`, and is observed. `not_applicable` is derived from the eForms notice-subtype
rules and is the only one requiring a lookup the parse stage does not yet have —
until it does, an inapplicable field is recorded `absent`, which is conservative
and honest rather than silently wrong.

A classifier that reads a value without reading its status is a bug, and one
that treats `withheld` as a low count is the specific bug this design exists to
prevent.

## Amounts

**Every amount column has a `<column>_currency` companion**, taking the
`currencyID` attribute of the element the amount came from. Six currencies
appear on `PayableAmount` in a single publication day — RON, EUR, PLN, CZK, HUF
and SEK — so an amount column on its own is a number, not a sum of money, and
two of them cannot be compared or summed.

The columns this applies to are `lot_tender.payable_amount`,
`lot_result.highest_tender_amount` and `lot_result.lowest_tender_amount`. Any
amount added later takes a companion in the same commit.

Currency is recorded, never converted. Conversion needs a rate and a date, both
of which are choices, and a classifier that compares across currencies has to
state which it made.

## Keys and ordinals

Records of the same kind are told apart by `ordinal`: **the container's
position among all containers of its kind in the notice, in document order**,
not its position among its immediate siblings. The distinction shows when a
notice carries more than one `ext:UBLExtension` — organisations in the second
continue the numbering rather than restarting.

`(source_notice_id, kind, ordinal)` is therefore a stable key, and it
deliberately says nothing about which parent a record hung from. The model does
not carry parentage either, so nothing downstream should infer it from the
ordinal.

## Repeated values

A path may occur several times in one record — 97% of lot records and 73% of
lot results do — so **asking a record for a single value at a repeated path is
an error, not a coin toss**: `Record.value()` raises rather than returning an
arbitrary one of several, and `Record.values()` returns them all in document
order.

Normalise fills a scalar column from a repeated path only where the model says
which one it means. Where the model carries the whole set, it says so. Pairing
across a repeated block — the statistic code with its number — is done on
`Field.occurrence`, described in [What parse hands over](#what-parse-hands-over).

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
  `<ext>/efac:Publication/efbc:PublicationDate` — not from the run clock.
- Rows sorted by their primary key before every write. Never rely on scan order.
- Writer options pinned — compression, row group size, writer version — because
  Parquet is only byte-stable if the writer is made so. That is the normalise
  stage's responsibility under ADR-0001, and
  [#9](open-work.md#9-add-the-rerun-identity-determinism-test) is the test that
  proves it.
- Status columns are low-cardinality strings; dictionary encoding makes the
  companion column nearly free, which is what allows the uniform rule above.

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
- **Legacy TED mappings**, above.
