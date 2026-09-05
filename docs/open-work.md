# Open work

Known gaps and the work planned against them, in enough detail to be picked up
without a conversation first. The README's milestone table says where the
project is going; this says what is actually open right now and what each item
requires.

Every item states the constraints that bind it. That is not ceremony: the rules
in [`CLAUDE.md`](../CLAUDE.md) are strict enough that a well-meant change can
violate one without its author noticing — an incompatible dependency licence, a
field that quietly carries a person's name, a classifier without a measured
false-positive profile. Those are cheaper to prevent than to review.

[`tests/test_constraints.py`](../tests/test_constraints.py) checks specified
patterns and metadata for constraints 1, 3, 4, 5 and 6; it does not certify every
possible violation or the empirical validity of a classifier. **Constraint 2 —
no personal data — is not fully met.** The eForms structural drop list in
[personal-data.md](personal-data.md) is executable and tested, but retained-field
leakage is documented and source-linkable opaque keys do not establish anonymity.
The explicit-natural-person Company/TouchPoint `WebsiteURI` leak is fixed in
code; stored datasets have not been rebuilt. Legacy mapping is still absent.

**Release remains blocked.** Lawful basis, retention, transparency and DPIA
necessity require counsel review for current private holdings, not just future
publication ([ADR-0010](adr/0010-raw-archive-retention.md)). Under
[GDPR Articles 4, 5, 6 and 14 and Recital 26](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng),
collection and storage are processing and indirect identifiability matters.
Neither an unpublished dataset nor passing tests establishes compliance.

If you pick something up, say so on the tracker so two people don't start the
same thing. Questions are welcome before code, especially on the blocking items.

Finished items keep their number and a one-paragraph summary here; the full
record of how each was built and what it corrected is in the
[decision log](decision-log.md). This file is meant to stay short enough to read.

## Open right now

| # | Item | What it needs |
|---|------|---------------|
| [3](#3-document-and-drop-the-fields-that-can-name-a-natural-person) | Legacy TED person-carrying fields | a pre-2024 package to measure |
| [4](#4-build-the-parse-stage) | Legacy TED parsing | blocked on 3 |
| [6](#6-handle-corrected-and-withdrawn-notices) | Corrected and withdrawn notices | design, deterministic code and tests |
| [11](#11-decide-the-publication-rule-for-unknown-natural-person-status) | Unknown natural-person status | counsel review of current processing and a publication rule |
| [14](#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields) | Personal data in retained fields and private holdings | counsel, remediation, rebuild and validation |
| [15](#15-decide-whether-beneficial-ownership-can-be-analysed-at-all) | Whether beneficial ownership can be analysed | counsel |
| [17](#17-build-the-first-classifier) | Verification of individual flags | blocked release; also needs 6, 11 and 14 |

The eForms prototype and first classifier are built. Remaining work includes
engineering, empirical measurement and legal decisions; it is not just paperwork
before publication.

## Everything, in order

| # | Item | Status | Issue |
|---|------|--------|-------|
| 1 | [Write the data model contract](#1-write-the-data-model-contract) | **done** | — |
| 2 | [Survey which eForms fields notices actually populate](#2-survey-which-eforms-fields-notices-actually-populate) | **done** | — |
| 3 | [Document and drop the fields that can name a natural person](#3-document-and-drop-the-fields-that-can-name-a-natural-person) | eForms structural drops built; privacy gaps and legacy open | [#13](https://github.com/cabral/serenata/issues/13) |
| 4 | [Build the parse stage](#4-build-the-parse-stage) | **eForms done**, legacy refused | — |
| 5 | [Add an opt-in test for TED's live contract](#5-add-an-opt-in-test-for-teds-live-contract) | **done** | [#17](https://github.com/cabral/serenata/issues/17) |
| 6 | [Handle corrected and withdrawn notices](#6-handle-corrected-and-withdrawn-notices) | corrections implemented (ADR-0013); withdrawals blocked on measuring the change reason; release blocker | [#15](https://github.com/cabral/serenata/issues/15) |
| 7 | [Commit a small sample package for end-to-end tests](#7-commit-a-small-sample-package-for-end-to-end-tests) | **done** | [#16](https://github.com/cabral/serenata/issues/16) |
| 8 | [Write CONTRIBUTING.md](#8-write-contributingmd) | **done** | — |
| 9 | [Add the rerun-identity determinism test](#9-add-the-rerun-identity-determinism-test) | **done** | [#12](https://github.com/cabral/serenata/issues/12) |
| 10 | [Settle the licence for published datasets](#10-settle-the-licence-for-published-datasets) | **done** | — |
| 11 | [Decide the publication rule for unknown natural-person status](#11-decide-the-publication-rule-for-unknown-natural-person-status) | current processing and publication unresolved | [#14](https://github.com/cabral/serenata/issues/14) |
| 12 | [Build the normalise stage](#12-build-the-normalise-stage) | **done** | [#11](https://github.com/cabral/serenata/issues/11) |
| 13 | [Derive the withheld status from the eForms field identifiers](#13-derive-the-withheld-status-from-the-eforms-field-identifiers) | **done** | [#21](https://github.com/cabral/serenata/issues/21) |
| 14 | [Decide what to do about personal data in fields that are not contact fields](#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields) | needs counsel | [#22](https://github.com/cabral/serenata/issues/22) |
| 15 | [Decide whether beneficial ownership can be analysed at all](#15-decide-whether-beneficial-ownership-can-be-analysed-at-all) | needs counsel | [#25](https://github.com/cabral/serenata/issues/25) |
| 16 | [Add the value and timing columns the red-flag literature needs](#16-add-the-value-and-timing-columns-the-red-flag-literature-needs) | **done** | [#27](https://github.com/cabral/serenata/issues/27) |
| 17 | [Build the first classifier](#17-build-the-first-classifier) | **v2 built and measured**; verification and release blocked | [#33](https://github.com/cabral/serenata/issues/33) |

**Order matters.** The field survey fed the model, then parsing, normalisation,
privacy-status mapping and determinism tests made the eForms prototype usable
for development. These do not close the remaining privacy or correction gaps.

**Milestone 1 is not complete.** An eForms ingestion/normalisation prototype is
built; legacy TED, privacy remediation and correction/withdrawal handling remain
open. Milestone 2 has a written hypothesis and an implemented, measured
version-2 rule. Empirical false-positive assessment and full verification are
pending. No flag has completed the verification protocol.

Every open item below has a GitHub issue mirroring it. Say there that you are
taking something, so two people do not start the same thing.

---


## 1. Write the data model contract

**Done.** [`data-model.md`](data-model.md) is the contract: twelve tables with a
measured source path and presence figure for every column, executable as
`serenata/normalise/model.py` with a test that fails when the two disagree.
Building [#12](#12-build-the-normalise-stage) against real records corrected it
three times.

[Full record](decision-log.md#1-write-the-data-model-contract).

---

## 2. Survey which eForms fields notices actually populate

**Done.** [`field-usage.md`](field-usage.md) reports 19,180 notices from five
publication days of 2026: 497 element paths carry a value, 323 are containers
or blank. It also
reports how often a path repeats inside one record, which is what stopped a
scalar column being given to a path that repeats.

[Full record](decision-log.md#2-survey-which-eforms-fields-notices-actually-populate).

---

## 3. Document and drop the fields that can name a natural person

**eForms structural drops built; privacy gaps and the legacy TED half are open.**
[`personal-data.md`](personal-data.md) is the list, measured against 3,190 real
notices rather than read off the specification, and executable as
`serenata/parse/personal_data.py` with a test that fails if the two disagree.
This tests the documented paths, not the absence of all personal data. Retained
fields, unknown natural-person status and source-linkable keys remain the work
of #11 and #14; the `WebsiteURI` fix still needs a dataset rebuild and validation.

**What is still open.** The five 2026 packages now measured — spanning March to
September — contain **zero legacy-schema notices between them**, so there is no
measured basis for that half, and this project does not publish spec-read lists
as though they were measured. Until it exists, parse refuses a legacy notice
rather than guessing which of its fields can name a person. Five days spread
across six months finding none is also evidence about how the blocker lifts: it
will not lift by fetching more recent days.

Fetching a pre-2024 package is one command against an already-built stage —
though whether TED still serves daily packages that far back is unverified, and
checking that is the first step rather than an assumption.

Full record of the eForms half:
[decision log](decision-log.md#3-document-and-drop-the-fields-that-can-name-a-natural-person).

---

## 4. Build the parse stage

**eForms done; legacy notices are refused rather than guessed at.**
`serenata/parse/` reads archived notices into typed intermediate records,
applying documented structural drops as it reads. In the recorded run, all
19,180 notices of five publication days parse with no failures; the first of
them produced 46,223 records.

**What is still open** is the same blocker as
[#3](#3-document-and-drop-the-fields-that-can-name-a-natural-person): a legacy
notice raises with a message naming the docs, because parsing one would be a
guess about which fields carry personal data. A package of them fails loudly
rather than yielding nothing, which would look exactly like an empty package.

Full record of the eForms half:
[decision log](decision-log.md#4-build-the-parse-stage).

---

## 5. Add an opt-in test for TED's live contract

**Done.** `tests/test_ted_contract.py` asserts seven assumptions against the
live service; `.github/workflows/contract.yml` runs it weekly. Reaching the
network takes two deliberate steps, so the suite's offline promise still holds.

[Full record](decision-log.md#5-add-an-opt-in-test-for-teds-live-contract).

---

## 6. Handle corrected and withdrawn notices

The fetch stage archives whole publication days as immutable snapshots. TED
notices can later be corrected or withdrawn, and a snapshot cannot represent
that: the archive keeps saying what was published that day, which is correct as
history but not as current state.

This matters more than it sounds. A flag raised against a notice that was later
corrected or withdrawn is a flag against something that no longer stands, and
the project's whole promise is that a reader can check a flag against its
source. ADR-0002 flagged it as the main limitation of whole-day snapshots.

**What to decide and implement** — record the design in an ADR, then code it:

- How a correction is detected. TED publishes corrigenda as notices in their own
  right; the relation to the original has to be read from the data.
- Whether corrections are folded into the normalised model, tracked as a version
  chain, or both.
- What a flag on a superseded notice should do — suppressed, marked, or
  withdrawn — and how a published finding is retracted.

**Constraints.** Raw archives stay immutable: handling corrections means new
records, never rewriting an archived package. Constraint 4 still binds — the
same archive and code produce the same flags, so "current state" must be derived
from archived inputs, not from a live lookup at classify time.

**Measured, then designed; not implemented.**
[`correction-links.md`](correction-links.md) measures the structure over 19,180
notices, and [ADR-0013](adr/0013-correction-and-withdrawal-semantics.md) proposes
the mapping from it. What the measurement changed about the design:

- The link column is **polymorphic** — 61.7% an eForms notice UUID with a
  version suffix, 38.3% a second namespace matching no identifier the model
  carries. The namespace has to be recorded, not assumed.
- Links resolve **45 of 2,840** times, and only after the version suffix is
  removed. That measures five sampled days, not the mapping: correction
  handling cannot be demonstrated end to end without a continuous archive,
  which the [ADR-0010](adr/0010-raw-archive-retention.md) review gates.
- **7** targets are corrected by more than one notice, so ambiguity is real at
  this sample size and the pipeline must refuse rather than pick.
- **Withdrawals remain undesignable**: nothing measured distinguishes one from a
  correction. The change reason is not in the model and the path survey records
  presence, not values.

**Corrections are implemented; withdrawals are not.** `RULE_VERSION` 3 excludes
notices another notice in the corpus corrects, every flag carries the
`correction_cutoff` its check saw, and the rule is remeasured at version 3:
8,157 lot outcomes, the same 96 flags. Two outcomes leave, both below the
segment floor.

**Done when** withdrawals are handled too, which needs the change reason
measured first — it is not in the model, and the path survey records presence
rather than values. Until then a withdrawn notice is treated as a live one.

**Release blocker.** Adopting ADR-0013 changes no flag today — none of the 96
sits on a notice corrected within the corpus — which is the absence of evidence
of staleness, not evidence of currency.


---

## 7. Commit a small sample package for end-to-end tests

**Done.** [`data/sample/`](../data/sample/) holds six synthetic notices in the
layout TED delivers, and `tests/test_sample_package.py` runs the whole pipeline
over them. Synthetic rather than real, because a contact address appears in
99.9% of real notices.

[Full record](decision-log.md#7-commit-a-small-sample-package-for-end-to-end-tests).

---

## 8. Write CONTRIBUTING.md

**Done.** [`CONTRIBUTING.md`](../CONTRIBUTING.md) takes someone from clone to a
pull request that passes CI without reading `CLAUDE.md` first.

[Full record](decision-log.md#8-write-contributingmd).

---

## 9. Add the rerun-identity determinism test

**Done.** The pipeline runs twice in CI and every written file's SHA-256 is
compared. Three cases, including two different packages that must produce
*different* bytes — the guard against a test that passes by comparing nothing.

[Full record](decision-log.md#9-add-the-rerun-identity-determinism-test).

---

## 10. Settle the licence for published datasets

**Done.** Published datasets and findings are **CC BY 4.0**
([ADR-0004](adr/0004-dataset-licence.md)), generated into every report rather
than pasted, with a test asserting it.

[Full record](decision-log.md#10-settle-the-licence-for-published-datasets).

---

## 11. Decide the publication rule for unknown natural-person status

`efbc:NaturalPersonIndicator` can explicitly mark a natural person, and
[#3](#3-document-and-drop-the-fields-that-can-name-a-natural-person) suppresses
specified identifying values when it is true. The problem is what the
indicator does *not* say: it is **absent from about 90% of notices**, and under
this project's own absence semantics absent is "not provided", never "false".

For an organisation without the indicator, whether it describes a legal person
or an individual trading under their own name is unresolved by that field.
Notice-level absence counts are not an organisation-level prevalence estimate.
An official procurement notice does not make an entity institutional by default.

**This is an ingestion and storage question as well as a publication question.**
Source-linked opaque keys can remain indirectly identifying even when specified
names and identifiers are suppressed. Counsel must assess current holdings and
the permitted processing, not just the wording of future flags. No attempt to
reconstruct a dropped identity is authorised.

**What to decide.**

- Whether a flag may be published about an entity whose natural-person status is
  unknown, or only about one positively corroborated as an organisation.
- What corroboration counts. `cac:PartyLegalEntity/cbc:CompanyID` is present in
  99.9% of notices, but a registration number does not by itself prove the
  registrant is not a natural person — in Sweden a sole trader's is their
  personnummer. Milestone 3's entity resolution against national company
  registers is the obvious source of a better answer, and is a long way off.
- Whether the answer differs for a buyer and for a supplier, without treating
  a role code as proof that a record cannot identify a natural person.

**Constraints.** The legal guardrails route anything identifying a natural
person away from project channels entirely. Corroborating legal-person status
does not itself clear incidental personal data; aggregate outputs also need an
identifiability review. Constraint 3 binds whatever is published: an anomaly,
never an accusation.

**Done when** counsel-reviewed processing and publication rules are recorded,
implemented and tested, and verification can justify the identity and data
included in any proposed flag. Current holdings must be assessed under those
rules. This remains a privacy and release gate, not a publication-only concern.


---

## 12. Build the normalise stage

**Done.** `serenata/normalise/` writes the model as Parquet. All 3,190 notices
of one publication day become **98,629 rows across twelve tables**, byte-identical
on rerun; five days are 632,068 rows. Building it corrected the data model three
times, and widening the evidence to five days corrected it a fourth.

[Full record](decision-log.md#12-build-the-normalise-stage).

---

## 13. Derive the withheld status from the eForms field identifiers

**Done.** The eForms SDK's privacy table is generated into
`serenata/normalise/sdk_privacy.py` and joined onto the model's columns
([ADR-0008](adr/0008-eforms-sdk-privacy-mapping.md)). A withheld amount reads
`withheld` rather than `present`.

[Full record](decision-log.md#13-derive-the-withheld-status-from-the-eforms-field-identifiers).

---

## 14. Decide what to do about personal data in fields that are not contact fields

Constraint 2's drop list is structural: it rejects any path through
`cac:Contact`, `efac:UltimateBeneficialOwner` or `cac:TechnicalCommitteePerson`.
It cannot catch a publisher who types
a contact address into a field that is not a contact field.

They do. Scanning five normalised packages finds **427 email-shaped values in 7
columns** — city, registration number, street, website, name, description — and
**139 of them are shaped like a person's own address** (`firstname.lastname@`).
These are pattern counts, not a complete personal-data inventory or legal
classification. They demonstrate the limits of the structural rule, not that
everything outside its paths is safe.

**359 of the 427 are in the two description columns.** Most observed matches
are in free text that no classifier reads and the current private dataset still
carries. Remediation must also cover the other retained fields; this count does
not limit the problem to descriptions.

The explicit-natural-person Company/TouchPoint `WebsiteURI` omission is a
separate structural leak, now fixed in code. Existing datasets have not been
rebuilt; those stored outputs must not be described as remediated.

**What to decide.** A value-level rule is a different kind of rule from a
path-level one, and the options lose different things:

- **Reject the value**, recording project suppression distinctly from publisher
  withholding or source absence. Loses a city name when a publisher put an
  address in it; the status semantics need design too.
- **Redact the match**, keeping the rest of the value. Keeps more, and means the
  dataset contains partially rewritten source values, which the project has so
  far never done.
- **Flag the row for review** and publish nothing until a human looks. Does not
  scale — 427 values in 632,068 rows is small as a share and not small as a
  queue.

Whichever is chosen, [`personal-data.md`](personal-data.md) gains a section, the
rule becomes executable beside `is_dropped()`, and the decision needs an ADR
because it changes what "dropped at ingestion" means.

**Constraints.** Constraint 2 is legal, not stylistic, and the guardrails say to
err toward dropping. Constraint 5 bears on the mechanism: a regex over values is
not NLP and not a classifier reading free text, but it is the first content-based
rule in the pipeline and should be argued rather than slipped in. Nonpublication
does not remove processing obligations. Review the lawful basis for current raw
and derived holdings, their retention, Article 14 transparency and DPIA necessity
with counsel now, not at launch. ADR-0010 does not certify them.

**This one needs counsel before it is acted on.** Whichever option is chosen
changes what "dropped at ingestion" means, and a change to the drop-at-ingestion
rule is on the project's escalation list rather than being a judgement call to
make in a pull request. Writing the options down is in scope; deciding between
them is not.

**Done when** counsel-reviewed rules cover existing holdings as well as future
outputs, are recorded in an ADR, and are executable and tested against the
measured cases. Rebuild affected datasets under the agreed rules, validate
remaining leakage and source linkability, and document disposition of old copies.
[personal-data.md](personal-data.md) must describe the scope and limits. A regex
or successful rebuild alone cannot certify anonymity or authorise release.


---

## 15. Decide whether beneficial ownership can be analysed at all

The drop list rejects `efac:UltimateBeneficialOwner` outright, and that is
**1,486 of the 32,135 leaf elements** removed from one publication day —
identifiers, family and first names, nationality and residence addresses.
[`dropped-fields.md`](dropped-fields.md) counts them.

The current classifier uses neither contact details nor beneficial ownership.
The drop-path/model comparison documents exclusions, not the value or legality
of every possible future analysis. Ownership relationships could support other
hypotheses, such as a common owner behind competing bidders, but that would need
separate evidence and legal review. This item records the capability trade; it
does not authorise recovering the data.

**What makes it hard.** A beneficial owner is a natural person by definition.
This is not personal data that leaked into a business field; it is person-level
data by design, and the legal guardrails route a classifier needing person-level
data to escalation rather than to a design session. Nothing about it can be
decided in a pull request.

**What to decide.**

- Whether any analysis of this subtree is available at all, or whether the
  answer is simply no.
- If some is: whether a relation intended not to identify an individual — "this
  supplier and that one declare an owner in common", as a boolean, without
  storing who — is a different question legally than storing the owner. A boolean
  relation can still identify people by linkage; the source-linkable opaque-key
  treatment of sole traders is not an anonymity precedent.
- Whether any of it may be *published*, which is a separate question again, and
  where the answer is most likely no under the defamation guardrail.
- Whether `efac:Nationality` raises additional risks in context. Nationality is
  not automatically an Article 9 special category; person-level use remains an
  escalation and the field stays dropped.

**Constraints.** Constraint 2 is legal, not stylistic. Whatever is decided,
[ADR-0010](adr/0010-raw-archive-retention.md) records unresolved retention and
lawful-basis questions, not an approval, and
[`personal-data.md`](personal-data.md) is where the rule becomes executable. A
change to the drop-at-ingestion rule is on the escalation list.

**Done when** an ADR records the answer, including "no" if that is the answer,
so the capability is a recorded trade rather than an absence nobody documented.

**Not blocking anything.** Filed so the trade is visible.


---

## 16. Add the value and timing columns the red-flag literature needs

**Done.** Nine columns across `procedure`, `lot` and `lot_result` — estimated
and awarded amounts, framework values, the submission deadline. The model held
three amount columns before and holds nine now. It closed the privacy-marking
gap from 143 of 215 blocks to 212 as a side effect.

[Full record](decision-log.md#16-add-the-value-and-timing-columns-the-red-flag-literature-needs).

---

---

## 17. Build the first classifier

**Version 2 built and measured.** `serenata classify` runs
[`single_bid_in_segment`](hypotheses/single_bid_in_segment.md) over the
normalised dataset and writes flags as Parquet. The measured run over five
publication days produces **96 flags from 8,157 lot outcomes**, byte-identical
on rerun, each carrying the baseline it was measured against
([ADR-0011](adr/0011-flags-carry-their-own-baseline.md)). Eligible segments
cover 4,299 outcomes (52.7%), excluding 3,858 (47.3%) below the size floor.
These are coverage and base-rate figures, not empirical error rates.

Version 2 rejects duplicate structural/join keys, ambiguous and fractional
tender counts, requires a present statistic code and resolves every buyer
reference to a present, agreed country. Output is staged before replacement and
stale rule files are removed on success; a multi-year replacement is not
transactional. Version 3 adds the ADR-0013 supersession exclusion, which
removes two lot outcomes here, both below the segment floor; that is a fact
about this corpus and not a general one. CI's `--require-current-measurements` gate
passes, which is metadata sanity rather than proof of the measurement, and
default local tests do not clear it. Any further real-data measurement depends
on the unresolved processing review below.

**Release is blocked**, including on deterministic correction handling and tests
in [#6](#6-handle-corrected-and-withdrawn-notices), identity rules in
[#11](#11-decide-the-publication-rule-for-unknown-natural-person-status) and
privacy remediation and current-holdings review in
[#14](#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields).
There is **no empirical false-positive rate**. One historical v1 flag's
arithmetic has been re-derived; **none has completed the verification protocol**.

The record of how it was argued follows.

The two case files in
[`cases/`](cases/) are constraint 6's first half done: the indicator argued
before any code exists.

[Case 001](cases/001-single-bid.md) took the most established red flag in the
literature — a single bid on a competitive procedure — through the four intake
gates and **rejected it at the base rate**. It fires on **36.8%** of competitive
lot results with a published bid count, and 42.1% once framework agreements are
excluded the way the Commission's own indicator excludes them. A flag on two in
five contract awards is a description of the market, not an anomaly in it. The
comparator scan says the same thing from the other side: opentender, DIGIWHIST
and the Single Market Scoreboard already publish this number, so there is no
delta either.

[Case 002](cases/002-single-bid-against-its-segment.md) is the form that
survives. Compare a lot against its own market — the buyer's country and the CPV
division — rather than against a European average. Single-bid rates across the
26 measured segments large enough to have a baseline run from 6.5% to 78.2%,
motivating segment-specific comparison; the rule fires on **2.23%** of the
population it covers. The intake case
supported building the rule, not release approval or a measured error rate.

**What it needed**, and what each answer was:

- **A hypothesis file**, which is where the four open design questions got
  settled. The baseline is computed from the corpus rather than frozen, and
  every flag carries it, so the corpus dependence is visible in the row instead
  of argued away. The grouping is country and CPV division, with the
  falsification test written down. The provisional threshold is 15% in a market
  of at least 50, retained from the v1 sweep — including its inability to
  distinguish 15% from 20%. Version-2 sensitivity remains unmeasured. The unit
  is the lot result.
- **A flag record**, which the data model did not have.
  [ADR-0011](adr/0011-flags-carry-their-own-baseline.md).
- **The classifier**, `serenata/classify/single_bid_in_segment.py`: a pure
  function over rows, no clock, no network, no free text.
- **Tests.** The rule over rows built by hand, including every way it declines
  to fire; the reader against a dataset whose four excluded cases are there to
  be excluded; the rerun-identity check on the flag files; and the published
  query run against the code's own so the two definitions cannot drift.

**Constraints.** Constraint 6 requires a version-matching measurement; constraint
4 binds baseline computation and correction handling. Synthetic-fixture work
can continue without claiming that processing real holdings is legally cleared.

**Next steps:** close the engineering and privacy gates, extend the measurement
to an approved wider corpus, then verify flags under the full protocol. Record innocent
explanations and empirical errors rather than treating arithmetic agreement as
verification.
