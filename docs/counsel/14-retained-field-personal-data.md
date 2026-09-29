# Counsel instruction: personal data in retained fields

**Status: UNRESOLVED. Drafted, not sent, not answered.** This is the question
put to counsel for [open-work #14](../open-work.md#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields).
It is not legal advice and it authorizes nothing. Changing what "dropped at
ingestion" means is on the project's escalation list, so the affected work
stays on hold until the decision record at the foot of this file is completed
by counsel and an authorized human.

## The short version

The project drops contact blocks, beneficial owners and named evaluators by
element path, before a record exists. That rule cannot catch a publisher who
types a contact address into a field that is not a contact field, and
publishers do. Across five publication days, 427 values in seven retained
columns are shaped like an email address, and 139 of those are shaped like a
person's own address (`firstname.lastname@`). Most sit in two free-text
description columns that no classifier reads. The project holds them today, in
the raw archive and in the normalised tables.

It asks counsel what to do about them, and whether the answer for values it
already holds differs from the answer for values it collects from now on.

## What the project holds

Counts only, from [`docs/dataset-shape.md`](../dataset-shape.md). No value
appears here or in that report.

| Column | Address-shaped | Shaped like a person's |
|---|---:|---:|
| `lot.description` | 234 | 77 |
| `procedure.description` | 125 | 45 |
| `organisation.street` | 18 | 6 |
| `organisation.website` | 17 | 5 |
| `organisation.company_ids` | 16 | 4 |
| `organisation.name` | 11 | 1 |
| `organisation.city` | 6 | 1 |
| **Total** | **427** | **139** |

Limits of these numbers, which the project asks counsel to keep in view:

- They are a pattern match for email-shaped strings. They are not an inventory
  of personal data. Names, telephone numbers and other identifiers typed into
  free text are not counted, because no pattern for them has been written and
  the project has not run one over the corpus. The true amount is unknown and
  larger than 427.
- "Shaped like a person's" is a guess about a local part. A role mailbox can
  match it and a personal one can miss it. It is not a legal classification.
- Five days is a sample. The rate elsewhere may differ.
- The two description columns (359 of 427) are carried as provenance. Core
  classifiers read structured fields only (constraint 5), so no rule reads
  them. That limits use. It does not remove them from storage.

Related fix already made in code, not yet applied to stored data: the
`WebsiteURI` of an organisation explicitly marked as a natural person is now
suppressed. Stored datasets have not been rebuilt.

## Options

The first three are in open-work #14. The fourth is a proposal the project
believes fits its constraints best and wants tested.

1. **Reject the value.** When a retained column holds an address-shaped string,
   store a status saying the project suppressed it (kept distinct from
   publisher-withheld and from absent) and no value. Cost: a city name is lost
   when a publisher put an address in it.
2. **Redact the match.** Keep the surrounding text and remove the address.
   Cost: the dataset then holds partially rewritten source text, which the
   project has never done, and a pattern that misses a variant leaves it in.
3. **Flag for human review.** Hold the row until someone looks. Cost: 427 is a
   small share and a large queue, and it does not scale.
4. **Do not carry the description columns at all.** Drop `lot.description` and
   `procedure.description` at parse, by path, the same kind of rule as the
   existing ones. No pattern, no judgement about a value. This removes 359 of
   the 427 and every unpatterned name or number inside those two columns.
   Cost: the project loses free text it does not read. The five remaining
   columns (68 values) would still need option 1 or a decision to leave them.

A value-level rule of any kind is the first content-based rule in the
pipeline. The project does not think a regex over values conflicts with
constraint 5 (it is not a classifier and reads nothing for meaning) but wants
that argued, not assumed.

## Questions

### Part A: what is held now

- **A1.** Is the current holding of these values, in the raw archive and in the
  normalised tables, permissible pending a rule, and for how long? ADR-0010
  claims no lawful basis for it.
- **A2.** For values already held: delete, rebuild the derived tables under
  the chosen rule, or something else? Does the raw archive need the same
  treatment as the normalised tables? The archive is immutable by design
  ([ADR-0002](../adr/0002-fetch-daily-bulk-packages.md)), and the project asks
  how that yields to a valid obligation to remove.
- **A3.** Is a counts-only pattern scan permissible over the held corpus to
  find out how large the problem is? It would extend the existing email-shaped
  count to telephone-shaped strings and would output counts by column only. Any
  wider scan is itself processing the project has not been cleared to do.
- **A4.** Do Article 14 and Article 35 (DPIA) duties change because these
  values are incidental, typed by the publisher outside any contact field,
  rather than collected as contact data?

### Part B: the rule from now on

- **B1.** Which of options 1 to 4 does counsel consider adequate, and is a
  combination (for example 4 for the descriptions, 1 for the rest) better than
  any single one?
- **B2.** If option 1 or 2 is chosen, is an email-shaped pattern enough, or is
  a rule that misses telephone numbers and names inadequate on its face? If
  inadequate, the project would rather take option 4 than write a broader
  pattern and claim coverage it cannot demonstrate.
- **B3.** Does dropping a column change the source-linkability analysis? The
  source notice stays public and linkable either way, and the project does not
  claim that dropping a value anonymises the record.
- **B4.** Is suppressing a value that a public authority published on a
  public register a matter of law, or of the project's own preference? The
  project's constraint 2 says the law decides. It asks for the law.

## What each answer changes in the code

| Answer | Consequence |
|---|---|
| Option 4 accepted | Two paths added to `serenata/parse/personal_data.py` and `docs/personal-data.md` in one change, two model columns removed, dataset rebuilt, synthetic tests. No real-data processing needed to implement. |
| Option 1 accepted | A new suppression status, a value-level check beside `is_dropped()`, an ADR, a model change in `docs/data-model.md`, synthetic tests including near-miss values. |
| Option 2 accepted | As option 1, plus a specification of what redaction preserves and tests that it never leaves a match behind. |
| A2 requires rebuild or deletion | The corpus behind every measurement in this repository is rebuilt or shrinks, and each measurement is redone afterwards. |
| A3 refused | The size of the problem stays a lower bound and the project says so wherever it cites 427. |

## Evidence required after any answer

A processing matrix over the retained columns; synthetic acceptance tests for
each rule, including near-miss values that must survive and variants that must
not; an assessment of existing raw and derived holdings under the same
decision; and a regenerated `dataset-shape.md` showing the remaining
address-shaped count. A zero there is a pattern result and not a clearance.
Nothing here authorizes recovering or reconstructing any suppressed value.

## Decision record

Copied from the template in [`docs/automation/handoffs.md`](../automation/handoffs.md).
Unfilled.

| Decision field | Status |
|---|---|
| Decision status and provenance | UNRESOLVED: [counsel, date, authenticated advice reference; authorized human decision separately] |
| Bounded scope | UNRESOLVED: [columns, sources, jurisdictions, operations, corpus and code/policy revisions] |
| Permitted / prohibited actions | UNRESOLVED: [explicit per-operation limits and conditions; processing is separate from publication] |
| Expiry / reassessment | UNRESOLVED: [expiry date, review owner, triggers for new columns, new leakage or rights requests] |
| Implementation conditions | UNRESOLVED: [ADR and privacy-rule changes, synthetic acceptance tests, independent review] |
| Existing holdings | UNRESOLVED: [inventory of archives, normalised data, flags, replicas and backups; authorized rebuild, deletion or retention actions, deadlines and owner] |
| Completion evidence | UNRESOLVED: [validation and disposition attestations for old and new copies, residual risk, exceptions, next step] |
