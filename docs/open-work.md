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

Most of them no longer depend on you noticing.
[`tests/test_constraints.py`](../tests/test_constraints.py) enforces constraints
1, 3, 4, 5 and 6 in CI, so a change that violates one fails with a message
naming it. **Constraint 2 — no personal data — is the one with legal weight.**
It is now mechanized for eForms: [`personal-data.md`](personal-data.md) is the
field list, `serenata/parse/personal_data.py` is that document in executable
form, and a test fails if the two disagree. The legacy TED half of the list does
not exist yet, which is why item 3 stays open.

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
| [6](#6-handle-corrected-and-withdrawn-notices) | Corrected and withdrawn notices | an ADR |
| [11](#11-decide-the-publication-rule-for-unknown-natural-person-status) | Publication rule for unknown natural-person status | a decision, before the first finding |
| [14](#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields) | Personal data in non-contact fields | counsel |
| [15](#15-decide-whether-beneficial-ownership-can-be-analysed-at-all) | Whether beneficial ownership can be analysed | counsel |
| [17](#17-build-the-first-classifier) | Publishing what the first classifier finds | blocked on 6 and 11 |

Two of those seven are engineering behind the same blocker, four are decisions —
three of them not this project's to take alone — and one, 17, is the next thing
to build.

## Everything, in order

| # | Item | Status | Issue |
|---|------|--------|-------|
| 1 | [Write the data model contract](#1-write-the-data-model-contract) | **done** | — |
| 2 | [Survey which eForms fields notices actually populate](#2-survey-which-eforms-fields-notices-actually-populate) | **done** | — |
| 3 | [Document and drop the fields that can name a natural person](#3-document-and-drop-the-fields-that-can-name-a-natural-person) | **eForms done**, legacy open | [#13](https://github.com/cabral/serenata/issues/13) |
| 4 | [Build the parse stage](#4-build-the-parse-stage) | **eForms done**, legacy refused | — |
| 5 | [Add an opt-in test for TED's live contract](#5-add-an-opt-in-test-for-teds-live-contract) | **done** | [#17](https://github.com/cabral/serenata/issues/17) |
| 6 | [Handle corrected and withdrawn notices](#6-handle-corrected-and-withdrawn-notices) | needs an ADR, later | [#15](https://github.com/cabral/serenata/issues/15) |
| 7 | [Commit a small sample package for end-to-end tests](#7-commit-a-small-sample-package-for-end-to-end-tests) | **done** | [#16](https://github.com/cabral/serenata/issues/16) |
| 8 | [Write CONTRIBUTING.md](#8-write-contributingmd) | **done** | — |
| 9 | [Add the rerun-identity determinism test](#9-add-the-rerun-identity-determinism-test) | **done** | [#12](https://github.com/cabral/serenata/issues/12) |
| 10 | [Settle the licence for published datasets](#10-settle-the-licence-for-published-datasets) | **done** | — |
| 11 | [Decide the publication rule for unknown natural-person status](#11-decide-the-publication-rule-for-unknown-natural-person-status) | needs a decision, before findings | [#14](https://github.com/cabral/serenata/issues/14) |
| 12 | [Build the normalise stage](#12-build-the-normalise-stage) | **done** | [#11](https://github.com/cabral/serenata/issues/11) |
| 13 | [Derive the withheld status from the eForms field identifiers](#13-derive-the-withheld-status-from-the-eforms-field-identifiers) | **done** | [#21](https://github.com/cabral/serenata/issues/21) |
| 14 | [Decide what to do about personal data in fields that are not contact fields](#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields) | needs counsel | [#22](https://github.com/cabral/serenata/issues/22) |
| 15 | [Decide whether beneficial ownership can be analysed at all](#15-decide-whether-beneficial-ownership-can-be-analysed-at-all) | needs counsel | [#25](https://github.com/cabral/serenata/issues/25) |
| 16 | [Add the value and timing columns the red-flag literature needs](#16-add-the-value-and-timing-columns-the-red-flag-literature-needs) | **done** | [#27](https://github.com/cabral/serenata/issues/27) |
| 17 | [Build the first classifier](#17-build-the-first-classifier) | **built**; publishing is blocked | [#33](https://github.com/cabral/serenata/issues/33) |

**Order matters.** 2 fed 1; 1, 3, 4, 5, 7, 12, 13 and 16 are all done for
eForms, and 12 turned records into a dataset, which closed 9 with it. 13 then
made a withheld amount read `withheld` rather than `present`, and 16 gave the
model the amounts and the deadline the indicator literature needs — between
them, the last things standing between the dataset and a classifier that can
trust what it reads.

**Milestone 1 is complete for eForms.** What is open is either a decision rather
than a task (11, 14), a format this project has not measured (3, and the legacy
half of 4), or filed so it is not discovered late (6). The next code is the
first classifier — item 17 — which milestone 2 owns and which constraint 6
governs: a written hypothesis citing its risk-indicator source, tests, and
measured base rates on real historical data, before it merges. The base rates
are now measured; the hypothesis is not written.

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

**eForms done; the legacy TED half is open.**
[`personal-data.md`](personal-data.md) is the list, measured against 3,190 real
notices rather than read off the specification, and executable as
`serenata/parse/personal_data.py` with a test that fails if the two disagree.

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
dropping person-carrying fields as it reads. All 19,180 notices of five
publication days parse with no failures; the first of them produced 46,223
records.

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

**What to decide** — a design decision, so an ADR rather than a patch:

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

**Done when** an ADR records the decision and its consequences, and the data
model (#1) can represent whichever answer it reaches.

**Do not start here.** It depends on the normalised model existing, and the
answer partly depends on what corrections look like once notices are parsed.
Filed now so it is not discovered late.


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

`efbc:NaturalPersonIndicator` tells us an organisation is a sole trader, and
[#3](#3-document-and-drop-the-fields-that-can-name-a-natural-person) suppresses
that organisation's identifying values when it is true. The problem is what the
indicator does *not* say: it is **absent from about 90% of notices**, and under
this project's own absence semantics absent is "not provided", never "false".

So for most organisations in the dataset, whether the record describes a company
or a private individual trading under their own name is unknown, and no amount
of reading the XML resolves it. Parse handles what it can; this is what is left.

**Why it is not an ingestion question.** Dropping every organisation name would
end the project — naming buyers and suppliers is the dataset. The names are kept
because an organisation in an official procurement notice is institutional by
default. The residual risk is not in storing them, it is in *publishing a flag*
about one that turns out to be a person.

**What to decide.**

- Whether a flag may be published about an entity whose natural-person status is
  unknown, or only about one positively corroborated as an organisation.
- What corroboration counts. `cac:PartyLegalEntity/cbc:CompanyID` is present in
  99.9% of notices, but a registration number does not by itself prove the
  registrant is not a natural person — in Sweden a sole trader's is their
  personnummer. Milestone 3's entity resolution against national company
  registers is the obvious source of a better answer, and is a long way off.
- Whether the answer differs for a buyer and for a supplier. Contracting
  authorities are institutions by definition; suppliers are where sole traders
  actually appear.

**Constraints.** The legal guardrails route anything identifying a natural
person away from project channels entirely, so the conservative answer is
available and cheap: publish only where the entity is corroborated, and count
the rest without naming them. Constraint 3 also binds — whatever is published is
an anomaly, never an accusation.

**Done when** an ADR records the rule and the verification interface can state,
for any published flag, why the entity it names is an organisation.

**Before the first finding, not before parse.** Nothing is published yet, so
this blocks milestone 2, not milestone 1.


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
That is the right shape for the rule, and it cannot catch a publisher who types
a contact address into a field that is not a contact field.

They do. Scanning five normalised packages finds **427 email-shaped values in 7
columns** — city, registration number, street, website, name, description — and
**139 of them are shaped like a person's own address** (`firstname.lastname@`).
The drop list is not wrong; the data arrived in a field it has no reason to
reject.

**359 of the 427 are in the two description columns.** One publication day
suggested the problem was scattered across identity fields; five days say it is
overwhelmingly free text, which narrows the decision below to fields no
classifier reads and a published dataset would still carry.

**What to decide.** A value-level rule is a different kind of rule from a
path-level one, and the options lose different things:

- **Reject the value**, recording the field as withheld or absent. Loses a city
  name when a publisher put an address in it, which is the honest trade.
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
rule in the pipeline and should be argued rather than slipped in. Nothing is
published yet, so this blocks the first dataset release rather than the
pipeline.

**This one needs counsel before it is acted on.** Whichever option is chosen
changes what "dropped at ingestion" means, and a change to the drop-at-ingestion
rule is on the project's escalation list rather than being a judgement call to
make in a pull request. Writing the options down is in scope; deciding between
them is not.

**Done when** the rule is decided in an ADR, executable, tested against the
measured cases, and `personal-data.md` says which fields it applies to and why a
path-based list could not have caught them.


---

## 15. Decide whether beneficial ownership can be analysed at all

The drop list rejects `efac:UltimateBeneficialOwner` outright, and that is
**1,486 of the 32,135 leaf elements** removed from one publication day —
identifiers, family and first names, nationality and residence addresses.
[`dropped-fields.md`](dropped-fields.md) counts them.

Everything else the drop removes costs the analysis nothing: no other dropped
path is a column of the normalised model, and core classifiers read structured
fields only, so a pipeline that kept the rest would compute the same flags. This
subtree is the exception. **Beneficial ownership is one of the most analysable
signals in procurement integrity** — shell structures, a supplier owned by
someone connected to the buyer, the same owner behind nominally competing
bidders. Losing it is a real capability trade, and it is currently silent: the
data simply is not there and nothing says why.

**What makes it hard.** A beneficial owner is a natural person by definition.
This is not personal data that leaked into a business field; it is person-level
data by design, and the legal guardrails route a classifier needing person-level
data to escalation rather than to a design session. Nothing about it can be
decided in a pull request.

**What to decide.**

- Whether any analysis of this subtree is available at all, or whether the
  answer is simply no.
- If some is: whether an aggregate that never identifies an individual — "this
  supplier and that one declare an owner in common", as a boolean, without
  storing who — is a different question legally than storing the owner. The
  opaque-key treatment already used for sole traders is the precedent to argue
  from.
- Whether any of it may be *published*, which is a separate question again, and
  where the answer is most likely no under the defamation guardrail.
- Whether the answer differs for `efac:Nationality`, which is arguably special
  category data and should probably stay dropped regardless.

**Constraints.** Constraint 2 is legal, not stylistic. Whatever is decided,
[ADR-0010](adr/0010-raw-archive-retention.md) governs what may be retained and
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

**Built.** `serenata classify` runs
[`single_bid_in_segment`](hypotheses/single_bid_in_segment.md) over the
normalised dataset and writes flags as Parquet. Over five publication days it
produces **96 flags from 8,159 lot outcomes**, byte-identical on rerun, each
carrying the baseline it was measured against
([ADR-0011](adr/0011-flags-carry-their-own-baseline.md)). The implementation
and the hypothesis's published query agree on real data, and a test runs both
over one dataset so they cannot drift.

**What is still open is publishing any of it**, and neither blocker is code:
[#6](#6-handle-corrected-and-withdrawn-notices) — a flag on a corrected notice
— and [#11](#11-decide-the-publication-rule-for-unknown-natural-person-status)
— whether the entity may be named. The false-positive profile is also predicted
rather than observed: one flag of the 96 has been re-derived from its raw
archived notice, which is a start and not a verification pass.

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
26 segments large enough to have a baseline run from 6.5% to 78.2%, so no flat
threshold can be right in both tails; a rule keyed to the segment fires on
**2.23%** of the population it covers, which is small enough to verify by hand.
It passes all four gates.

**What it needed**, and what each answer was:

- **A hypothesis file**, which is where the four open design questions got
  settled. The baseline is computed from the corpus rather than frozen, and
  every flag carries it, so the corpus dependence is visible in the row instead
  of argued away. The grouping is country and CPV division, with the
  falsification test written down. The threshold is 15% in a market of at least
  50, chosen after a sweep the file records — including that the sample cannot
  tell 15% from 20%. The unit is the lot result.
- **A flag record**, which the data model did not have.
  [ADR-0011](adr/0011-flags-carry-their-own-baseline.md).
- **The classifier**, `serenata/classify/single_bid_in_segment.py`: a pure
  function over rows, no clock, no network, no free text.
- **Tests.** The rule over rows built by hand, including every way it declines
  to fire; the reader against a dataset whose four excluded cases are there to
  be excluded; the rerun-identity check on the flag files; and the published
  query run against the code's own so the two definitions cannot drift.

**Constraints.** Constraint 6 governs all of it. Constraint 4 binds the baseline
question specifically. Nothing here is publishable until
[#6](#6-handle-corrected-and-withdrawn-notices) settles what a flag on a
superseded notice does and
[#11](#11-decide-the-publication-rule-for-unknown-natural-person-status) settles
who may be named — but the classifier can be built and measured before either.

**Good entry point now:** verifying flags. The profile in the hypothesis is
what the design predicts; walking real flags through the verification protocol
is what would replace prediction with evidence, and it needs no code at all.
