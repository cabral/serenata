# ADR-0011: A flag is a row that carries its own baseline

- Status: accepted
- Date: 2026-09-04
- Enforced by: `tests/test_classify_flags.py::TestAFlagCarriesItsEvidence` and
  `tests/test_classify_flags.py::TestRerunsAreIdentical`

## Context

The first classifier
([`single_bid_in_segment`](../hypotheses/single_bid_in_segment.md)) needs
somewhere to put its output, and the data model has no notion of a flag. Two
questions have to be answered before any classifier writes anything, because
both constrain every classifier after it.

**What a flag record contains.** The project's promise is that a reader can
check a flag against its source. A row saying "publication 00566631-2026, lot
result 3, single bid" satisfies nobody: to check it, a reader has to rebuild
the comparison that made one bid interesting, which means rerunning the
pipeline. That is not verification, it is repetition.

**What the baseline is measured against.** This classifier compares a lot
outcome to its market — the buyer's country and the CPV division — and that
baseline has to come from somewhere. Two options, and they differ in what they
break:

- **Computed from the dataset being classified.** Deterministic in the sense
  constraint 4 requires: same input, same output. But the corpus is now an
  input, so a lot flagged in a September run may not be flagged in an October
  run that has more notices in its segment — without either the notice or the
  code having changed.
- **Frozen to a stated reference period**, shipped as a table. Stable across
  runs, and it ages: a reference table built from 2026 says nothing honest
  about 2028, and reproducing it requires the archive it was built from, which
  is the same problem moved somewhere less visible.

## Decision

**A flag is a row in a `flag` table, written as Parquet beside the normalised
dataset, and it carries the evidence for its own claim** — the values the rule
read, and the baseline it compared them against.

Every flag row carries, at minimum:

- `source_publication_id` and `source_notice_id`, the identity every row in this
  project carries, and `source_url`, the notice's XML on TED. The XML rather
  than the human-readable page because it is the document the pipeline actually
  read; TED serves the same notice at `/en/notice/{publication id}/xml`.
- `rule` and `rule_version`. The version is the classifier's own integer,
  bumped whenever its logic changes, so two runs that disagree can be told
  apart from two rules that disagree.
- What was flagged: the lot result's ordinal and its lot reference.
- **The evidence**: the field values the rule evaluated, and the baseline —
  for this classifier, the bid count, the segment, the segment's size and its
  single-bid rate.

**The baseline is computed from the dataset being classified.** Determinism
holds in the form constraint 4 states it, and the corpus dependence is made
visible rather than argued away: the segment's size and rate are *in the row*,
so a reader can see exactly what the comparison was, and two runs over different
corpora produce visibly different flags rather than a silent change of mind.

Flags are written with the same pinned Parquet settings and the same
sort-before-write discipline as the normalised dataset, partitioned by
publication year, under `data/flags/`.

## Consequences

- **A flag is checkable without rerunning anything.** The row says one bid, in
  a market of 308 comparable lot results where 20 drew a single bid, and links
  the notice. Everything a verifier needs to disagree is in front of them.
- **The corpus is part of a flag's meaning, and says so.** "This lot was
  unusual for its market *as this dataset measured that market*" is a weaker
  claim than "this lot was unusual", and it is the true one. A published finding
  states the dataset it came from, which the archive checksums already pin.
- **Flag counts are not comparable across runs** unless the datasets are. This
  is a real cost. It is paid in exchange for a baseline nobody has to trust,
  and it is why the rule version is a column rather than a release note.
- **Rows carry evidence columns specific to their rule.** The `flag` table is
  therefore a wide table with a rule-specific evidence payload rather than a
  narrow one. Kept as typed columns, not free-form text, so a query can filter
  on them; a second classifier adds its own columns rather than reusing these.
- **A flag is not a finding.** Nothing here decides that anything may be
  published. Constraint 3 governs the words, open-work #11 governs whether the
  entity may be named at all, and open-work #6 governs what happens to a flag
  on a notice that was later corrected.

## Revisit triggers

- **The archive spans more than a year.** A rolling reference period — classify
  a day against the twelve months before it — becomes both meaningful and
  cheap, and it would make flags comparable across runs. Today's five days
  cannot support it.
- **A second classifier needs a baseline of a different shape**, or the evidence
  columns stop being a natural fit for a shared table. That is the signal to
  split `flag` into a narrow core and per-rule evidence tables.
- **A published finding has to be reproduced by a third party** and the corpus
  dependence makes it harder than rerunning the pipeline. That would mean this
  decision optimised for the wrong reader.
- **Postgres arrives** (ADR-0001's own triggers). Flags are the rows an API
  serves, so the storage question reopens with it.
