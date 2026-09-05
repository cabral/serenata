# ADR-0013: Derive supersession from the archive, and refuse to guess

- Status: accepted — corrections only; withdrawals undesignable until the change
  reason is measured
- Date: 2026-09-05
- Enforced by: `tests/test_normalise_corrections.py::TestTheColumnsTheModelBuilds`
  for the link parts and `tests/test_classify_corrections.py` for supersession.
  Withdrawals are not implemented and no test claims they are;
  [`docs/correction-links.sql`](../correction-links.sql) reproduces the measurement

## Context

[ADR-0002](0002-fetch-daily-bulk-packages.md) archives whole publication days as
immutable snapshots, and named corrections as the main limitation of that
choice: a snapshot keeps saying what was published that day. A flag on a notice
TED later corrected or withdrew is a flag on something that no longer stands,
which is the one failure the project's promise cannot absorb.

The normalised model already records `changed_notice_id` from
`efac:Changes/efbc:ChangedNoticeIdentifier` and acts on nothing.
[Open work #6](../open-work.md#6-handle-corrected-and-withdrawn-notices) requires
the structure to be measured before a mapping is designed.
[`correction-links.md`](../correction-links.md) is that measurement, over 19,180
notices. Four findings constrain any design:

- **14.8%** of notices carry a correction link; **118** of them are award
  notices, which is what the single-bid rule reads.
- The column is **polymorphic**: 61.7% hold an eForms notice UUID with a
  two-digit version suffix, 38.3% hold a legacy TED publication number and
  year — the numbering that preceded eForms, which no notice in an eForms
  dataset carries.
- Raw links resolve **0 of 2,840** times; **45** resolve after the version
  suffix is removed. The low rate measures the sampled archive, not the mapping.
- **7** targets are corrected by more than one notice. The data alone does not
  order them.

Nothing measured distinguishes a correction from a withdrawal.

## Decision

**Supersession is derived from archived inputs and carried as a structured
field.** No stage performs a live lookup, and no transform or classifier reads a
wall clock (constraint 4). The archive as fetched is the cutoff, and a flag
records the cutoff it was computed against, the way
[ADR-0011](0011-flags-carry-their-own-baseline.md) makes it carry its baseline.

**A link is parsed into its parts, and the namespace is recorded.** The notice
model gains the target identifier, the target version and which namespace the
link used. A link in the unresolvable namespace is recorded as such, never
dropped and never silently treated as absent: 38.3% is a fact about the data,
not noise. [ADR-0006](0006-absence-is-recorded-not-collapsed.md) already
requires "not provided" and "not applicable" to stay distinct; "present but not
resolvable here" is a third state and gets its own value.

**A notice is superseded when another notice in the same corpus targets its
identifier.** Not its identifier *and* version, which is what this decision
first said: 28 of the archive's 46 resolvable links name a version other than
the one held, and a link naming version 02 is evidence that a version 02 exists,
which the copy held at version 01 is already behind. Matching exactly on version
would keep those 28 notices in the population while knowing they are stale. The
version each link names is still recorded, so the two cases stay distinguishable.

The notice identifier is not unique — the model already documents the same
notice published twice under different numbers — so one corrector can exclude
both copies. That is the intent: both are that notice.

**Where the data does not decide, the pipeline refuses rather than picks.** Two
notices correcting one target make that target `ambiguous`. A link that resolves
to nothing in the corpus makes the target `unresolved`. Neither is reported as
"not corrected", and neither is repaired by choosing a winner, which is the same
stance the classifier's integrity gate already takes toward duplicate keys.

**Superseded and ambiguous notices leave the classifier population.** That
changes denominators and therefore segment baselines, so it is a logic change:
`RULE_VERSION` bumps and the current-version measurement gate must be satisfied
again. Old measurements are not relabelled.

**Contract modifications are not corrections.**
`efac:ContractModification/efbc:ChangedNoticeIdentifier` is a different relation
on 6.0% of notices, repeating up to 46 times in one notice. It stays out of this
mapping.

**Withdrawals are not implemented, because nothing measured detects one.**
Distinguishing them needs the change reason, which the model does not carry and
the path survey records only as presence. Until that is measured, this ADR
covers corrections only, and the gap is stated rather than filled by assumption.

## Consequences

Correction handling **cannot be demonstrated end to end on the current
archive**. At 1.6% resolution over five sampled days, a passing test suite would
be exercising synthetic fixtures, not the behaviour. A continuous archive
spanning the corrected notices' publication dates is a prerequisite for the
demonstration, and fetching one is subject to the unresolved processing review
in [ADR-0010](0010-raw-archive-retention.md). This ADR does not resolve that
review by inference, and adopting it does not authorize the fetch.

Because none of the 96 current flags sits on a notice corrected within the
corpus, adopting this changes no flag today. That is the absence of evidence of
staleness, not evidence of currency, and it is why this is a release blocker
rather than a completed item.

Implemented in `RULE_VERSION` 3, which removes two lot outcomes from the
archive's population of 8,159 — both in segments below the size floor, so
coverage, the segment rates and the 96 flags are unchanged.

Acceptance tests cover, on synthetic fixtures: a corrected notice leaving the
population while its corrector stays; a link naming another version; a link
naming the version held; two correctors excluding one target once; a chain; a
self-reference terminating; and, excluding nothing, a link out of the corpus, a
legacy link, an unrecognised shape and no link at all. The cutoff travels to
every outcome and every flag, reruns are byte-identical, and a correction
arriving changes the population rather than being asserted vacuously.

Withdrawals have **no** test, because they have no behaviour: a test here would
be inventing the feature it checks.

## Revisit triggers

A continuous archive becoming available; the change reason being measured, which
is what would let withdrawals be designed; the legacy namespace becoming
resolvable, which is the 38.3% of links that entity resolution
in milestone 3 could resolve; observed chains deeper than one, or a target
corrected by notices in different packages; any published finding, after which
supersession stops being an internal question and
[corrections-policy.md](../corrections-policy.md) governs the retraction.
