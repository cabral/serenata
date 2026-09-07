# Fields that can name a natural person

The list the parse stage implements. Constraint 2 says fields that could carry a
natural person's name are dropped **at ingestion** — not stored and filtered
later — so this document has to exist before parse is written, or the rule ends
up enforced by whoever happens to be reading the XML that day.

This is a legal constraint (GDPR, and the defamation exposure that follows from
naming people), not a style preference. Where a judgement was made, it is
recorded here with its reasoning, so [#1](open-work.md#1-write-the-data-model-contract)
and [#4](open-work.md#4-build-the-parse-stage) can be written against it without
re-deciding anything field by field.

`serenata/parse/personal_data.py` is this document in executable form, and
`tests/test_personal_data.py` fails if the two disagree.

## How this list was produced

The original eForms list is **measured**, not read off the specification: its
paths were observed in the 3,190 notices of OJ S 157/2026, the same package
[`field-usage.md`](field-usage.md) reports on, and the percentages are that
package's. The website suppression entries added below are verified by
synthetic regression tests, not a new data survey; their frequencies are not
measured here. Paths the schema permits but no notice used are noted as such
rather than silently omitted.

The legacy TED half is **not yet measured** — see [below](#legacy-ted-notices-not-yet-measured).

Two shorthands, so the tables stay readable. Both expand to the literal element
path; the code carries the full form.

- `<ext>` = `notice/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/efext:EformsExtension`
- `<orgs>` = `<ext>/efac:Organizations`
- `<org>` = `<orgs>/efac:Organization`

## The rule

1. **Four subtrees are dropped outright**, wherever they appear, by structural
   match rather than by an enumerated path list. A field TED adds inside one of
   them tomorrow is dropped without anyone noticing it arrived.
2. **One case is conditional**: where an organisation is flagged as a natural
  person, the identifying values listed below are suppressed too.
3. Other fields are kept by these rules. Retention is not proof that a value
  is institutional or free of personal data; see the limits below.

Err toward dropping. A dropped field that turns out to be safe costs a later
change; a retained one that carries a name is a legal problem.

## Dropped outright

### 1. Contact blocks — any path through `cac:Contact`

A contact block exists to name a human being to telephone. It is the single
largest source of personal data in eForms, and it is nearly universal.

| Path | Present | Why |
|---|---:|---|
| `<org>/efac:Company/cac:Contact/cbc:Name` | 66.3% | a contact person's name |
| `<org>/efac:Company/cac:Contact/cbc:ElectronicMail` | 99.9% | personal or role mailbox |
| `<org>/efac:Company/cac:Contact/cbc:Telephone` | 99.9% | direct line |
| `<org>/efac:Company/cac:Contact/cbc:Telefax` | 42.1% | as above |
| `<org>/efac:Company/cac:Contact/cbc:JobTitle` | 2.8% | identifies a post, and with it its holder |
| `<org>/efac:Company/cac:Contact/cbc:Department` | 0.1% | as above |
| `<org>/efac:TouchPoint/cac:Contact/cbc:ElectronicMail` | 3.7% | second contact block, same content |
| `<org>/efac:TouchPoint/cac:Contact/cbc:Telephone` | 2.6% | " |
| `<org>/efac:TouchPoint/cac:Contact/cbc:Telefax` | 1.0% | " |
| `<org>/efac:TouchPoint/cac:Contact/cbc:Name` | 0.5% | " |
| `<org>/efac:TouchPoint/cac:Contact/cbc:ID` | <0.1% | " |
| `<orgs>/efac:UltimateBeneficialOwner/cac:Contact/cbc:ElectronicMail` | 0.5% | contact details of a natural person |
| `<orgs>/efac:UltimateBeneficialOwner/cac:Contact/cbc:Telephone` | 0.4% | " |
| `<orgs>/efac:UltimateBeneficialOwner/cac:Contact/cbc:Telefax` | 0.2% | " |
| `notice/cac:SenderParty/cac:Contact/cbc:ElectronicMail` | 0.1% | whoever filed the notice |

**Nothing downstream wants these.** The classifiers are statistical tests over
structured fields; no hypothesis in this project takes a phone number as input.
Dropping the whole block costs the pipeline nothing and removes its largest
personal-data surface.

Note the two frequencies at 99.9%: an email address and a telephone number are
present in almost every notice published in the EU. This is not a rare edge
case to be handled later.

### 2. Ultimate beneficial owners — any path through `efac:UltimateBeneficialOwner`

A UBO **is** a natural person by definition; the element exists to name one.
This is the most sensitive data in the schema and the whole subtree goes.

| Path | Present | Why |
|---|---:|---|
| `<orgs>/efac:UltimateBeneficialOwner/cbc:ID` | 8.1% | identifier for that person |
| `<orgs>/efac:UltimateBeneficialOwner/efac:Nationality/cbc:NationalityID` | 6.5% | a person's nationality |
| `<orgs>/efac:UltimateBeneficialOwner/cbc:FamilyName` | 0.8% | a person's surname |
| `<orgs>/efac:UltimateBeneficialOwner/cbc:FirstName` | 0.1% | a person's given name |
| `<orgs>/efac:UltimateBeneficialOwner/cac:ResidenceAddress/cac:Country/cbc:IdentificationCode` | 0.7% | **a home address** |
| `<orgs>/efac:UltimateBeneficialOwner/cac:ResidenceAddress/cbc:CountrySubentityCode` | 0.7% | " |
| `<orgs>/efac:UltimateBeneficialOwner/cac:ResidenceAddress/cbc:CityName` | 0.6% | " |
| `<orgs>/efac:UltimateBeneficialOwner/cac:ResidenceAddress/cbc:PostalZone` | 0.6% | " |
| `<orgs>/efac:UltimateBeneficialOwner/cac:ResidenceAddress/cbc:StreetName` | 0.5% | " |
| `<org>/efac:UltimateBeneficialOwner/cbc:ID` | 8.1% | the organisation→owner cross-reference |

**The identifier is ten times commoner than the name.** A UBO's `cbc:ID` and
nationality appear in 8.1% and 6.5% of notices while `cbc:FamilyName` appears in
0.8% — so a list built by looking for name-shaped elements would have missed
most of this subtree. An identifier for a natural person is personal data
whether or not the name sits beside it, which is why the rule matches the
subtree rather than the leaves.

The cross-reference on the last row is dropped for the same reason as the
record: keeping the link lets the association be rebuilt from a later source
even after the owner's own fields are gone. Dropping one end is not enough.

`cac:ResidenceAddress` is a private individual's home address, published because
a beneficial-ownership regime requires disclosure to a register. That
disclosure obligation is not a licence for this project to re-publish it.

### 3. Named evaluators — any path through `cac:TechnicalCommitteePerson`

| Path | Present | Why |
|---|---:|---|
| `notice/cac:ProcurementProjectLot/cac:TenderingTerms/cac:AwardingTerms/cac:TechnicalCommitteePerson/cbc:FamilyName` | <0.1% (2 notices) | names a person who sat on an evaluation committee |

Rare — two notices in a publication day — and the most dangerous field in the
schema for this project specifically. A named individual attached to an award
decision is exactly the material the [legal guardrails](../CLAUDE.md) route away
from project channels. It gets no column.

### 4. Withheld-field explanations — `efac:FieldsPrivacy/efbc:ReasonDescription`

| Path | Present | Why |
|---|---:|---|
| `<ext>/efac:NoticeResult/efac:FieldsPrivacy/efbc:ReasonDescription` | 0.3% | free text written by the publisher |
| `<ext>/efac:NoticeResult/efac:LotTender/efac:FieldsPrivacy/efbc:ReasonDescription` | 0.3% | " |
| `<ext>/efac:NoticeResult/efac:LotResult/efac:DecisionReason/efac:FieldsPrivacy/efbc:ReasonDescription` | <0.1% | " |

Free prose explaining why a field was withheld from publication. Free text can
embed a name, and constraint 5 keeps the pipeline to structured fields anyway,
so it has no use here to trade against the risk.

The rest of the `efac:FieldsPrivacy` block — `efbc:FieldIdentifierCode`,
`cbc:ReasonCode`, `efbc:PublicationDate` — is **kept**. It is coded, carries no
prose, and records that the publisher deliberately withheld a field. The project
honours that: a field marked withheld is never reconstructed or inferred from
another notice.

## The sole-trader case: conditional suppression

`efbc:NaturalPersonIndicator` is present in **9.5%** of notices across 27
countries. Across the whole publication day it is `true` **7 times** and `false`
365 times.

When it is true, the "organisation" is a natural person trading in their own
name — and then the fields that would otherwise be plain company data are
personal data:

| Path | Present | What it becomes |
|---|---:|---|
| `<org>/efac:Company/cac:PartyName/cbc:Name` | 99.9% | the person's own name |
| `<org>/efac:Company/cac:PartyLegalEntity/cbc:CompanyID` | 99.9% | **a national identity number** |
| `<org>/efac:Company/cac:PostalAddress/**` | 92.4–99.9% | usually a home address |
| `<org>/efac:Company/cbc:WebsiteURI` | not measured here | a website that can identify the person |
| `<org>/efac:TouchPoint/cac:PartyName/cbc:Name` | 6.8% | the person's own name |
| `<org>/efac:TouchPoint/cac:PostalAddress/**` | up to 6.5% | a possible home address |
| `<org>/efac:TouchPoint/cbc:WebsiteURI` | not measured here | another website that can identify the person |

The registration identifier deserves the emphasis. In Sweden a sole trader's
`organisationsnummer` **is** the owner's `personnummer` — the national identity
number of a private individual, in a field that for every other organisation is
an innocuous company registration number. Felipe operates under Swedish law, so
this is the concrete case; whether other member states' sole-trader identifiers
behave the same way has not been checked, and the rule below does not depend on
the answer.

**The rule:** where an `efac:Organization` carries `efbc:NaturalPersonIndicator`
= true, the identifying values in that organisation's record are suppressed at
parse — name, registration identifier, postal addresses and Company/TouchPoint
websites. The existing indicator policy also suppresses for `1` and unreadable
present values (including empty ones); explicit `false` or `0` does not suppress.
Whitespace and case are normalised when interpreting the indicator. An absent
indicator still does not trigger suppression. **Every** indicator on the
organisation is read rather than the first: where two contradict each other, the
one claiming personhood decides, so the outcome does not depend on which the
publisher wrote first. Suppression is the parse stage's decision alone — the
contradictory values themselves are carried into the record, because resolving a
repeated path by picking one is what [ADR-0007](adr/0007-repeated-values-are-carried-not-resolved.md)
forbids.

The website fix is verified with an obviously synthetic notice using `.invalid`
URLs, an explicit-natural-person organisation and an explicit-false control.
Both Company and repeated TouchPoint websites are absent from the suppressed
parsed record, even when the indicator follows them. `organisation.website`
is null with status `absent` in newly generated Parquet; control websites remain
parsed and the control's Company website remains in Parquet. TouchPoint websites
have no column in the current model, so their parse-boundary test is essential.
No real notices were inspected for this regression and no frequency is inferred
from it. Existing derived files are not repaired by changing the parser: affected
outputs need rebuilding before reuse or publication.

**What is kept is the opaque key.** `<org>/efac:Company/cac:PartyIdentification/cbc:ID`
is a notice-scoped token (`ORG-0001`) that links the organisation to its roles
in that notice. Keeping it means the *structure* survives — a lot can still be
counted and joined. Suppressing these fields does not establish anonymity:
source references remain, and identifiers or personal data elsewhere in a notice
are not covered by this organisation-local rule.

### What is unresolved, and stated rather than hidden

The indicator is **absent from about 90% of notices**. Under this project's own
absence semantics, absent is "not provided" — it is **not** "false". So for most
organisations, whether the record describes a company or a private individual
trading in their own name is genuinely unknown from the notice.

This list does not resolve that, and no reading of the XML can. What it does:

- records absence explicitly, as [#1](open-work.md#1-write-the-data-model-contract)
  requires, so nothing downstream can mistake unknown for "is a company";
- keeps `efbc:NaturalPersonIndicator` itself as a first-class field, because it
  is the only in-band signal that exists and dropping it would remove the
  project's ability to comply at all.

Unknown natural-person status affects ingestion, storage and analysis as well
as publication. [#11](open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status)
tracks the naming decision; [ADR-0010](adr/0010-raw-archive-retention.md) records
the unresolved processing review. This field guide does not authorize further
real-data processing while that review remains open. Synthetic tests can
continue without treating unknown status as a company classification.

## Kept, and why

Stated so the exclusions above are not read as covering them too.

| Path | Present | Why it stays |
|---|---:|---|
| `<org>/efac:Company/cac:PartyName/cbc:Name` | 99.9% | buyer/supplier name; retained unless suppression applies, but may identify a person |
| `<org>/efac:Company/cac:PartyLegalEntity/cbc:CompanyID` | 99.9% | national registration number; the key entity resolution (milestone 3) needs |
| `<org>/efac:Company/cac:PartyIdentification/cbc:ID` | 99.9% | opaque intra-notice reference; source linkage may still identify a person |
| `<org>/efbc:NaturalPersonIndicator` | 9.5% | a boolean, and the signal the rule above depends on |
| `<ext>/efac:NoticeResult/efac:TenderingParty/cbc:Name` | 11.0% | tendering-party name; retention does not establish institutional status |
| `<ext>/efac:NoticeResult/efac:SettledContract/cac:SignatoryParty/cac:PartyIdentification/cbc:ID` | 8.0% | despite the element name, an organisation reference, not a signatory's name |
| `notice/cac:ProcurementProjectLot/cac:TenderingTerms/cac:EconomicOperatorShortList/cac:PreSelectedParty/cac:PartyName/cbc:Name` | <0.1% | an economic operator's name, same treatment as any other |

Postal addresses and websites of organisations are kept unless the conditional
rule applies. They can describe a contracting authority or supplier, but the
indicator does not establish that every retained value is non-personal.

## Legacy TED notices: not yet measured

**This half of the list does not exist yet, and the parse stage must not
process legacy notices until it does.**

OJ S 157/2026 contains **zero** legacy-schema notices — all 3,190 are eForms.
That is expected for a 2026 package, since eForms became mandatory during 2024,
but it means the evidence base behind everything above says nothing about the
legacy schemas, and this project does not write lists from spec-reading and
present them as measured.

What is known: legacy TED XML (`TED_EXPORT`) carries contact information in its
own structures — `CONTACT_DATA` blocks with elements for an attention-of person,
e-mail and telephone, attached to `CONTRACTING_BODY` and to award records.
Those are the obvious analogues of §1 above, and the same reasoning applies.

**Before parse handles a legacy notice**, resolve the processing review above,
then obtain a pre-2024 package and survey it under the approved handling rules.
Extend §§1–4 with measured paths the same way. The fetch interface is one
command against an already-implemented stage:

```
uv run serenata fetch --from 2023-06-01 --to 2023-06-02
```

Until then, a legacy notice must be **refused with a message naming this
document**, not parsed on a best guess. Refusing costs nothing today: no
archived package contains one.

## Implementation notes for the parse stage

**The conditional rule needs a buffered subtree.** ADR-0003 requires streaming,
and a pure path-by-path filter cannot apply the sole-trader rule, because
`efbc:NaturalPersonIndicator` may be read *after* the name it governs. Parse
must therefore accumulate one `efac:Organization` element, decide, and only then
emit — not buffer the document. Organisations are small; the 40 MB notice that
shaped ADR-0003 is large because of attachments and lot descriptions, not
because of its organisation list.

**Match structurally, not by enumerated path.** The four outright drops are
containment tests on a path's segments, so a leaf TED adds inside `cac:Contact`
next year is dropped on arrival rather than on discovery. That is the point of
expressing them this way.

**Outright dropping means never constructing.** `personal_data.is_dropped()`
is consulted before a value is read, not after. Conditional suppression differs:
organisation fields are buffered so the indicator can be read regardless of
element order, then identifying fields are removed before the final parsed
record is returned. They do not reach normalisation or newly written Parquet;
this does not mean their XML text was never materialised in memory.

## Re-verifying this list

The measurements come from a single publication day. When the survey is rerun
over more packages — which [#2](open-work.md#2-survey-which-eforms-fields-notices-actually-populate)
recommends before the data model is finalised — check the new report for paths
matching `cac:Contact`, `efac:UltimateBeneficialOwner`, `Person`, `FamilyName`,
`FirstName` or `Contact` that do not appear above. A new one is not
automatically a gap in the rule: the structural matches in §§1–3 already cover
anything inside those subtrees. It is a gap only if it sits somewhere new.

## What this list costs

[`dropped-fields.md`](dropped-fields.md) measures it, generated from archived
packages rather than asserted here: **32,135 leaf elements, 3.6% of every leaf**
in one publication day. It checks every dropped path against the columns of
[`data-model.md`](data-model.md) and finds no overlap — every removal is a
contact block, a beneficial owner, a named committee member or a free-text
privacy reason, and never an amount, a date, a code, a bid count or a company
identifier.

That measurement is what answers "why not mirror TED in full and filter at
publication": a pipeline keeping this data would compute the same flags from it,
because core classifiers read structured fields only. [ADR-0010](adr/0010-raw-archive-retention.md)
records the rest of that reasoning and the basis on which the archive is held.

The one exception is `efac:UltimateBeneficialOwner`, 1,486 removals, which is a
real analytic loss and is filed as [open-work #15](open-work.md#15-decide-whether-beneficial-ownership-can-be-analysed-at-all)
rather than left as a silent absence.

## What this list cannot catch

Every rule above is **structural**: it matches a path, and it drops everything
inside a subtree whether or not anyone has read the leaf. That is the right
shape for the rule, and it has a limit worth stating plainly, because a reader
who assumes the list is exhaustive would be wrong about a legal constraint.

A publisher can type a contact address into a field that is not a contact field.
Scanning the normalised OJ S 157/2026 dataset finds **46 email-shaped values in
7 columns** — a city, a registration number, a street, a website, a title, a
description — and **13 of them are shaped like a person's own address**
(`firstname.lastname@`). These are historical measurements, not re-run for the
website fix. Those paths are not dropped outright: some are suppressed only
within an organisation meeting the natural-person rule. Personal data misplaced
in retained fields remains outside the structural rule.

Fixing this needs a value-level rule, which is a different kind of rule from
everything above, and the options — reject the value, redact the match, flag the
row — lose different things. That decision is
[open-work #14](open-work.md#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields)
and it gates the first published dataset. Until it is taken, **this list is the
rule and the gap is known**, which is the honest position rather than a quiet
regex.
