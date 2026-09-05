# ADR-0013: Derive supersession from the archive, and refuse to guess

- Status: accepted — corrections and withdrawals; end-to-end validation needs a
  continuous archive
- Amendment: 2026-09-05, withdrawals designed once the change reason was measured
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

The change reason was then measured too, over the same notices, from the eForms
`change-corrig-justification` list: `update-add` 1,889, `cor-buy` 551,
`cor-pub` 186, `info-release` 54, `cancel-intent` 18, `cancel` 14,
`susp-review` 9, `cor-esen` 2. The last three separate a withdrawal from a
correction, which nothing in the model could do before. **117 links carry no
reason code**, so neither part implies the other.

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

**A notice announcing that its own procurement is not proceeding normally is
excluded with its lot results**: reason `cancel`, `cancel-intent` or
`susp-review`. Supersession already removes the notice such an announcement
corrects; this removes the announcement, whose own lot results describe an
outcome that may never have happened.

Treating the three alike is a judgement, not a reading of the code list.
`cancel` is terminal, `cancel-intent` announces an intention and `susp-review`
suspends pending a challenge — all three leave the outcome unsettled, and
silence is the honest output. The set is a named constant so it can be revisited
against a corpus where the distinction bites.

**The free-text reason description is not ingested.** It could carry a person's
own words (constraint 2) and no classifier may read it (constraint 5). The code
is a controlled vocabulary and carries the distinction on its own.

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

Implemented in `RULE_VERSION` 3 and 4. Supersession removes two lot outcomes
from the archive's population of 8,159; the withdrawal exclusion removes a
further 25, from 5 notices. **The 96 flags are unchanged through both** — none
of the excluded outcomes was flagged — and coverage moves from 4,299 to 4,283.
That the output did not move is a fact about this corpus, not evidence the
exclusions are inert.

Acceptance tests cover, on synthetic fixtures: a corrected notice leaving the
population while its corrector stays; a link naming another version; a link
naming the version held; two correctors excluding one target once; a chain; a
self-reference terminating; and, excluding nothing, a link out of the corpus, a
legacy link, an unrecognised shape and no link at all. The cutoff travels to
every outcome and every flag, reruns are byte-identical, and a correction
arriving changes the population rather than being asserted vacuously.

Withdrawal tests cover each cancel-like reason excluding its own notice, each
ordinary correction reason excluding nothing, both exclusions applying together,
a reason without a link, and a link without a reason.

## Revisit triggers

A continuous archive becoming available, which is what would let either
exclusion be validated end to end; a corpus where a cancel-like reason changes a
flag, which would make the three-code set worth revisiting one by one; the
legacy namespace becoming
resolvable, which is the 38.3% of links that entity resolution
in milestone 3 could resolve; observed chains deeper than one, or a target
corrected by notices in different packages; any published finding, after which
supersession stops being an internal question and
[corrections-policy.md](../corrections-policy.md) governs the retraction.
