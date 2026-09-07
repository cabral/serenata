# Counsel instruction — unknown natural-person status

**Status: UNRESOLVED. Drafted, not sent, not answered.** This is the question
put to counsel for [open-work #11](../open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status).
It is not legal advice and it authorizes nothing. Affected work stays on hold
until the decision record at the foot of this file is completed by counsel and
an authorized human.

## The one-paragraph version

TED notices carry a boolean, `efbc:NaturalPersonIndicator`, saying whether an
organisation is a natural person trading in their own name. Where it says so,
this project already suppresses that organisation's name, registration number
and addresses at parse. The problem is that the field is **absent from 96.6% of
the organisation records measured**, and this project's own semantics
([ADR-0006](../adr/0006-absence-is-recorded-not-collapsed.md)) hold that absent
means "not provided", never "false". So for almost every organisation the
project stores, whether the record describes an institution or a private
individual is unknown from the notice. Two questions follow, and the project
asks counsel to answer them **separately**, because only one of them is urgent.

## Two questions, deliberately split

The item has been tracked as a publication question. That is the less urgent
half, and putting them in one instruction has been obscuring the other one.

| | Question | Risk accrues | Otherwise blocked? |
|---|---|---|---|
| **Part A** | May the project hold and process records of unknown status at all, and on what basis? | Continuously, now | **No.** This is happening today. |
| **Part B** | May a flag be published pointing at such a record? | Only on publication | **Yes** — by four unrelated open gates |

Publication cannot happen for at least four reasons independent of this item:
retained-field personal data ([#14](../open-work.md#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields)),
unverified flags ([#17](../open-work.md#17-build-the-first-classifier)),
correction handling unexercised against real corrigenda
([#18](../open-work.md#18-validate-correction-handling-against-a-continuous-archive)),
and the unresolved lawful basis in
[ADR-0010](../adr/0010-raw-archive-retention.md). Answering Part B first
therefore buys the project nothing and leaves Part A running. **Counsel is asked
to answer Part A first, and may answer it without reaching Part B.**

## What the project holds and does

Facts, with their sources in this repository. All are counts; no field value
appears here or in the reports cited.

- **Corpus.** Five TED daily packages, 19,180 notices, normalised to twelve
  Parquet tables — [`docs/dataset-shape.md`](../dataset-shape.md). Local disk,
  gitignored, no third-party synchronisation. Raw XML retained as fetched.
- **The population in question.** 77,444 `organisation` rows. The indicator is
  **present on 3.4%** and **absent on 96.6%**.
- **What "present" says.** On the one publication day broken out in
  [`docs/personal-data.md`](../personal-data.md): **7 `true`, 365 `false`**.
  That is a statement about organisations that filled the field in. The project
  does **not** treat it as an estimate for the 96.6% that did not, and asks
  counsel not to either — the entities that omit an optional field are not a
  random sample of those that complete it.
- **What already happens on `true`.** Name, registration identifier, postal
  address fields and website are suppressed at parse
  ([`serenata/parse/notice.py`](../../serenata/parse/notice.py),
  [`serenata/parse/personal_data.py`](../../serenata/parse/personal_data.py)).
  Unreadable and empty present values suppress too. An opaque notice-scoped key
  is kept so the row still joins. **This is structural suppression, not
  anonymisation**: the source notice remains public and linkable.
- **Why the registration identifier matters most.** In Sweden a sole trader's
  `organisationsnummer` is the owner's `personnummer`. The maintainer operates
  under Swedish law. Whether other member states' sole-trader identifiers behave
  the same way has not been established, and the project would like to know
  whether the answer changes the rule.
- **What a flag actually contains.** One classifier exists and has produced
  **96 flags from 8,132 lot outcomes**, none published. The flag record
  ([`serenata/classify/records.py`](../../serenata/classify/records.py)) carries
  **no organisation reference of any kind** — no buyer, no supplier, no name, no
  identifier. It carries a bid count, a market baseline, and a URL to the
  notice's XML on TED. **Identification, if it occurs, is by that link**, not by
  a stored name. The project does not assume the distinction helps it and asks
  counsel to address it directly (question B4).
- **Which role is involved.** That classifier reads exactly one organisation
  field — the buyer's country — and reads no supplier at all. The buyer is read
  and never emitted; the supplier is never read.
- **Aggregates.** Published measurements are counts by country, CPV division and
  procedure type. The classifier will not compare a lot against a market of
  fewer than 50 comparable lot results (`SEGMENT_FLOOR`), which was chosen as a
  statistical floor and not as an identifiability control.

## Part A — processing (answer this first)

The project asks counsel to rule on **current holdings**, not a future launch.

- **A1. Lawful basis and necessity.** ADR-0010 proposes Article 6(1)(f) for
  reproducible procurement analysis and does not claim it is established. Does
  it hold for records whose natural-person status is unknown? What
  balancing-test documentation is required, and does the answer differ for the
  raw XML archive, the normalised tables and the flag files?
- **A2. A bounded measurement authorization.** The project is in a deadlock it
  cannot resolve alone: it cannot propose a corroboration threshold without
  knowing how the indicator is distributed by role and by member state, and
  gathering that is itself processing it has not been cleared to do. It
  therefore asks specifically for permission to run **counts-only** queries over
  the already-held corpus — the distribution of the indicator by organisation
  role and country, no field value in any output — on the same terms as the
  existing generated reports, which carry element paths and frequencies and are
  covered by a test asserting no value appears in them. Is that permissible, and
  under what conditions and expiry?
- **A3. Retention.** ADR-0010 set no period for today's unpublished holdings and
  explicitly does not treat its 2027-09-03 review date as permission to keep
  them until then. What period, review trigger and deletion criteria apply, and
  how are derived copies and backups treated?
- **A4. Article 14.** What information duty arises on indirect collection here,
  on what timing, and does any exception apply? If Article 14(5)(b) is relied
  on, what safeguards and public information are required?
- **A5. DPIA.** Is one required under Article 35? None is claimed completed.
- **A6. Security and access.** Local gitignored storage with no third-party sync
  is current policy, not an audited control. What is required?
- **A7. Rights and incidents.** How must a data-subject request be handled
  across raw archive, normalised tables, flags and backups, and how does the
  immutability of the raw archive yield to a valid erasure request?

## Part B — publication and corroboration

### B1. The baseline question

May a flag be published that points at a notice when the natural-person status
of the organisations in that notice is unknown? The project's default, absent an
answer, is no.

### B2. Corroborating a buyer from the legal definition, not from the data

The project puts a proposed position to counsel rather than asking an open
question, because it believes this one is answerable without new data.

**Proposed:** a buyer in a TED notice can be corroborated as a legal person from
the definition of the publishing role itself. [Directive 2014/24/EU,
Article 2(1)(1)](https://eur-lex.europa.eu/eli/dir/2014/24/oj) defines
contracting authorities as the State, regional or local authorities, bodies
governed by public law, or associations of these — a set that cannot include a
natural person. If that reading holds, the buyer side needs no register lookup
and no inference from a role code: the corroboration is definitional.

The project has identified three places where it may not hold, and asks counsel
to scope each rather than confirm the general claim:

- **Utilities.** [Directive 2014/25/EU](https://eur-lex.europa.eu/eli/dir/2014/25/oj)
  covers contracting entities including holders of special or exclusive rights.
  Can such a holder be a natural person?
- **Subsidised contracts.** [Directive 2014/24/EU, Article 13](https://eur-lex.europa.eu/eli/dir/2014/24/oj)
  applies to certain contracts awarded by bodies that are *not* contracting
  authorities. What is the natural-person exposure there?
- **Voluntary publication.** Notices published below threshold have no
  definitional floor on who may publish them. Is the argument lost entirely for
  these, or bounded?

The project stores `notice.regulatory_domain` and `notice_subtype_code` and can
gate on either, so a rule of the form "the argument holds except for these
notice classes" is directly implementable.

**A caution the project asks counsel to address explicitly.** Establishing that
a *buyer entity* is a legal person is not the same as establishing that the
*stored row* contains no personal data. Retained-field leakage is real and
measured — 427 address-shaped values across five days, 139 shaped like a
person's own address, mostly in free-text descriptions
([`docs/known-issues.md`](../known-issues.md)). The project's working assumption
is that B2 clears the entity question only and leaves gate #14 untouched. Please
confirm or correct that, since conflating the two would read as clearance the
project does not have.

### B3. The supplier side

The project proposes to **hold the supplier side unconditionally** until
cross-source entity resolution exists (milestone 3, not started). Sole traders
genuinely win public contracts, and no definitional argument is available. Is
there anything short of register corroboration that counsel would accept — an
explicit `false`, a jurisdiction-specific identifier format, a contract value
threshold — or is the hold correct? Note that a register lookup would itself be
a new data source, which this project treats as its own escalation.

### B4. Does linking differ from naming?

A published flag would carry a URL to an official EU publication that itself
names the buyer and carries the contact details this project drops at ingestion.
The project does not assume that linking is materially different from naming,
and asks counsel whether it is — under GDPR and under Swedish `förtal`
(Brottsbalken ch. 5) — and whether the answer changes if the flag carries no
entity field of its own, as it currently does not.

### B5. Aggregate identifiability

Published aggregates are counts by country and CPV division. A sufficiently
small cell identifies a notice by elimination even though no entity is named.
The classifier's existing floor of 50 comparable lot results was chosen for
statistical reasons; the project asks whether an identifiability floor is
required as well, at what size, and whether it must apply to hand-written
tables in case files as well as to generated reports.

### B6. Conflicting and unreadable indicators

Present-but-unreadable and empty values already suppress. Two contradictory
indicators on one organisation now suppress as well: any organisation carrying a
`true`-equivalent value anywhere is treated as a natural person regardless of
what else it carries. That was implemented ahead of this instruction because it
is strictly more protective than the behaviour it replaced and needed no real
data to change, and because the previous behaviour made suppression depend on
which element the publisher wrote first. The project asks counsel to confirm
that "err toward suppression" is the correct resolution rather than assuming it.

## What each answer changes in the code

So counsel can see that these are not abstract questions.

| Answer | Consequence |
|---|---|
| A1 negative, or A3 short | Existing raw and derived holdings are deleted or rebuilt to a narrower scope; the corpus behind every measurement in this repository shrinks or goes. |
| A2 granted | A counts-only survey by role and country runs, and B2/B3 become answerable on evidence rather than argument. |
| A2 refused | The corroboration threshold stays unquantified; the project records that and does not proceed on a guess. |
| B2 accepted | All 96 current flags become publishable **subject to every other gate**, because the current classifier is buyer-side only. Rule implemented as a notice-class gate with the carve-outs counsel scopes. |
| B2 refused | No per-notice flag is publishable at all; the project publishes aggregate data notes only, and says why. |
| B3 held | Costs nothing today — no supplier-side classifier exists — and constrains milestone 3 by design. |
| B5 answered | A minimum cell size enters the report generators and the pre-publication checklist. |
| B6 confirmed | A parse-stage fix and synthetic tests; no real-data processing involved. |

## Implementation and evidence required after any answer

Per the gate-3 row in [`docs/automation/handoffs.md`](../automation/handoffs.md):
a bounded processing and publication matrix covering every indicator status
(`true`, `false`, absent, unreadable, conflicting) crossed with subject role;
synthetic acceptance tests for each cell, including linkable keys and incidental
identifiers; and an assessment of existing raw and derived holdings under the
same decision. Absence, role codes and registration numbers are not treated as
proof of legal-person status. No attempt to reconstruct a dropped identity is
authorized by any answer to this instruction.

## Decision record

Copied from the template in [`docs/automation/handoffs.md`](../automation/handoffs.md).
Unfilled.

| Decision field | Status |
|---|---|
| Decision status and provenance | UNRESOLVED — [counsel, date, authenticated advice reference; authorized human decision separately] |
| Bounded scope | [UNRESOLVED: purpose, jurisdictions, sources, fields/statuses, subject roles, operations, recipients, corpus and code/policy revisions] |
| Permitted / prohibited actions | [UNRESOLVED: explicit per-operation limits, conditions and rationale; processing is separate from publication] |
| Expiry / reassessment | [UNRESOLVED: expiry date, review owner, triggers for source/field/code/purpose changes, new leakage or rights requests] |
| Implementation conditions | [UNRESOLVED: ADR and privacy-rule changes, synthetic acceptance tests, independent review and sandbox evidence] |
| Existing holdings | [UNRESOLVED: controlled inventory covering archives, normalised data, flags, replicas/backups; access limits; authorized rebuild/deletion/retention actions, deadlines and owner] |
| Completion evidence | [UNRESOLVED: screened validation/disposition attestations for old and new copies, residual risk, exceptions and next step] |
