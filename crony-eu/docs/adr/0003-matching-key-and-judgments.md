# ADR-0003: Deterministic matching key, human-confirmed judgments

Status: accepted, 2026-09-10

## Context

A wrong match between an elected official and a company officer is a false accusation waiting to happen. France offers a birth date on both sides: the Répertoire national des élus carries full birth dates, and company officer data is expected to carry year and month (session 3 checks this before any matching code is written). Names vary between sources: accents, hyphens, particles, compound given names, and birth name versus usage name.

## Decision

- Candidate rule `FR-NAME-BIRTHYM-v1`: normalised surname variant, first given name and birth year-month must all match exactly. The normalisation is specified in CLAUDE.md.
- Candidates go to an append-only judgments table with status `pending`. Possible statuses: pending, confirmed, rejected, ambiguous. The latest row per `judgment_id` wins; nothing is overwritten.
- Only `confirmed` judgments, set by a person in `crony review`, create person-to-company edges in exports.
- Precision is measured, not assumed. A seeded random sample of candidates (100 by default) is reviewed and the result goes into the flag spec.
- Probabilistic matching (Splink) waits until a country without birth data on both sides joins the project.

## Consequences

- High precision. Recall drops when a name changes (marriage, typos, transliteration), and the size of that drop stays unknown until someone measures it on a hand-built sample.
- Review work grows with scope, which is one reason phase 1 runs one département at a time.
- A rule change gets a new rule id. Old judgments keep the rule id they were made under.

## Amendment, 2026-09-16: a confirmed identity is not a dated link

This record made a judgment the gate for a person-to-company edge, and that was only half the gate.

A `confirmed` judgment says two records describe the same person. It says nothing about when that person held the office. F1 asks whether a councillor held a company office *at the time* their commune paid that company, and a confirmed identity with an undated role cannot answer it. The first bundle put officer role dates in phase 2 while phase 1's only flag needed them.

So:

- officer role start and end are phase 1 data, fetched in session 3 from INPI's register, with the date's meaning recorded beside it. A filing date is not a role start date.
- `role_overlap = unknown` is a permitted and expected value. It blocks a case packet and does not block counting, reporting or review.
- a judgment row records the `rule_id` it was decided under, and the log stays append-only so that a packet built on a judgment that later becomes `rejected` can be found and withdrawn. The append-only property was already here for correctness; it is now load-bearing for withdrawal too.

Consequence: precision as this record defines it, the share of sampled candidates a person confirms, measures identity matching alone. It is not the share of F1 hits that survive scrutiny, and the flag spec reports the two separately so neither is read as the other.
