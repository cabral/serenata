# ADR-0013: Derive supersession from the archive, and refuse to guess

- Status: proposed — measurement done, design unimplemented, withdrawals unresolved
- Date: 2026-09-05
- Enforced by: nothing yet. [`docs/correction-links.sql`](../correction-links.sql)
  reproduces the measurement below; the acceptance tests named here are not written

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
  two-digit version suffix, 38.3% hold a second namespace matching no
  identifier the model carries.
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
identifier and version.** Precedence follows a total order derived from the
data — publication date, then package, then notice identifier — never arrival
order and never the clock.

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

Acceptance tests, all on synthetic fixtures, before any claim that this is
implemented: original → correction → later correction; withdrawal once
detectable; superseded notices; duplicate, missing, ambiguous and cyclic links;
out-of-order arrivals; stable precedence and cutoff semantics with no double
counting; explicit hold where current state cannot be resolved; changed
eligibility and segment membership with recomputed baselines, including notices
that gain or lose a flag without themselves changing; rule-version and evidence
mismatch rejection; replacement of stale output including empty results and
cross-year partitions; byte-identical reruns and input-order invariance, with
materially changed inputs changing expected outputs.

## Revisit triggers

A continuous archive becoming available; the change reason being measured, which
is what would let withdrawals be designed; the second identifier namespace being
resolvable, or being identified as a legacy TED numbering that entity resolution
in milestone 3 must handle; observed chains deeper than one, or a target
corrected by notices in different packages; any published finding, after which
supersession stops being an internal question and
[corrections-policy.md](../corrections-policy.md) governs the retraction.
