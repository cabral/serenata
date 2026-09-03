---
name: coding
description: Use for any code change in the Serenata Europa repo. That means new classifiers, pipeline stages, schema changes, tests, dependency changes, refactors, and ADRs. Also use it when reviewing a diff or deciding whether something is ready to merge. If a session touches a .py file, a pyproject.toml, or anything under docs/adr or docs/hypotheses, this skill applies. It carries the classifier development workflow (hypothesis file first, base rate before thresholds, determinism proofs), the merge checklist, and the stack conventions (Python 3.12+, uv, Parquet, DuckDB, Postgres deferred).
---

# Coding

CLAUDE.md at the repo root is the source of truth for the hard constraints. This skill is the how. If the two ever disagree, CLAUDE.md wins and the disagreement gets fixed in the same session.

The six constraints, restated so they're in front of you, numbered as CLAUDE.md numbers them:

1. AGPL-3.0. Everything that runs in production is published.
2. No personal data at ingestion. Fields that can contain names, emails, or phone numbers of natural persons are dropped before storage.
3. Flags are statistical anomalies, not accusations. No user-facing string, doc, or example output calls a flagged record `corrupt`, `fraudulent`, or `guilty`.
4. Deterministic outputs. Same input produces byte-identical output.
5. Core classifiers read structured fields only. No free text, no NLP, no LLM calls, no fuzzy logic inside a classifier.
6. No classifier merges without a written falsifiable hypothesis and a measured base rate.

Constraints 1, 3, 4, 5 and 6 are mechanically enforced by `tests/test_constraints.py`, which runs in CI, along with the rule that fetch is the only networked stage. Constraint 2 is now mechanized too, for eForms: `docs/personal-data.md` is the field list, `serenata/parse/personal_data.py` is that document in executable form, and `tests/test_personal_data.py` derives its assertions from the document so the two cannot drift. The legacy TED half of the list does not exist yet — there are no legacy notices in any archived package to measure — so a legacy notice must be refused rather than parsed on a guess. If you change a constraint here, change it there too.

The reason these are hard: every flag this project publishes must be reproducible by a stranger from public data. A journalist, an NLnet reviewer, or a lawyer for a flagged buyer should be able to rerun the code and get the same rows. Nondeterminism, hidden data, or judgment calls buried in text parsing break that, and with it the entire credibility posture.

## Building a classifier

Do these steps in order. The order is the point.

### 1. Write the hypothesis file

Create `docs/hypotheses/<module>.md` before writing any detection code, named after the classifier module it governs — a classifier at `serenata/classify/<module>.py` has `docs/hypotheses/<module>.md`. That coupling is what `tests/test_constraints.py` checks, and it is why the name is the module rather than a number. (Case files under `docs/cases/` keep the `NNN-slug` numbering; hypotheses are addressed by the code they bind.) Template:

```markdown
# <name>

Status: scoped | measured | building | live | rejected

## Claim
One falsifiable sentence. "Contracts awarded fewer than N days after
publication are anomalous relative to their CPV category" is falsifiable.
"Some awards look rushed" is not.

## This flag is wrong if...
Complete the sentence. If you can't, stop here.

## Fields used
Exact eForms BT codes / TED fields. If a needed signal only exists in
free text, the classifier fails constraint 4. Go back to case-research.

## Population and denominator
What set of notices does this apply to? What gets excluded and why?

## Base rate
Filled in step 2. The query that produced it lives next to this file.

## Comparators
Does opentender.eu, DIGIWHIST, ARACHNE, or Kingfisher already flag this?
What is our delta?

## Legal check
Personal data needed? Naming risk? See the legal skill. Record the answer.
```

### 2. Measure the base rate

Run the denominator query against real data before choosing any threshold. Store the query as a `.sql` file next to the hypothesis doc and paste the number and run date into it. A threshold picked before seeing the base rate is a guess wearing a lab coat. A flag that fires on 40% of notices describes the market, not an anomaly.

### 3. Implement

A classifier is a pure function over normalized structured rows. It takes rows in, returns flag rows out. It does not touch the network, the clock, the filesystem (beyond its input), or an LLM.

Normalization, deduplication, and enrichment live in pipeline stages upstream of classifiers. Those stages may do more work (currency conversion, buyer-name normalization) but must be equally deterministic and documented in the schema docs. The boundary matters: if someone asks "why did this row get flagged," the answer must be a rule over named fields, not "the matcher decided they were similar."

Every flag row carries: notice id, source URL, the field values the rule evaluated, the rule name and version. A flag that can't point at its evidence doesn't ship.

### 4. Prove determinism

Rules that keep reruns byte-identical:

- Sort explicitly before every write. Never rely on scan order.
- Timestamps in outputs come from the data, never from the runtime clock. UTC everywhere.
- No randomness. If sampling is ever unavoidable, fix the seed and document why.
- Write Parquet with pinned options (compression, row group size) so the same rows produce the same bytes.
- Pin dependency versions via the committed uv lockfile.

The test for this is not a code review, it's a rerun: execute the pipeline twice on the same fixtures and compare output checksums. That test lives in CI and must pass on every classifier PR.

### 5. Tests

- Fixtures are small, sanitized notices under `tests/fixtures/`. Never commit real personal data, even accidentally present in a source notice. Sanitize on the way in.
- Golden-file tests: fixture in, expected flag rows out, compared exactly.
- The rerun-identity test from step 4.
- One negative fixture per classifier: a notice that looks close to the flag condition but shouldn't fire. This is where the false-positive taxonomy from case-research pays off.

## Merge checklist

Run this before approving any classifier or pipeline PR. Reject with the specific item, not a vibe.

- Hypothesis file exists, status is "measured" or later, base rate number is present with its query.
- The "wrong if" sentence is filled in and actually falsifiable.
- Rerun-identity test passes.
- No new ingested field can contain natural-person data. If the schema changed, `docs/personal-data.md` and `serenata/parse/personal_data.py` changed with it, in the same PR. Note the drop rules match on *path segments*, not on an enumerated list of leaves: a new field inside `cac:Contact`, `efac:UltimateBeneficialOwner` or `cac:TechnicalCommitteePerson` is already dropped and needs no change. It needs one only if it sits somewhere new.
- Classifier logic reads structured fields only.
- New dependencies are AGPL-compatible and source-available. Check the license before `uv add`, not after.
- An ADR exists if the change constrains future work or reverses a prior ADR.
- Docs updated. Honest and short beats impressive. If a sentence in the docs would survive with its adjective deleted, delete the adjective.

## Stack conventions

- Python 3.12+, managed by uv exclusively. `uv add`, `uv run`, lockfile committed. No pip installs, no poetry, no conda.
- Storage is Parquet, partitioned by year (add country if query patterns justify it). Query with DuckDB SQL. Dataframes only at the edges, for output shaping.
- Postgres stays out until the ADR-0001 triggers fire (concurrent users or a live API, milestone 4/5 territory). If a problem seems to need Postgres before then, the problem is probably the query. Fix the query.
- ruff for lint and format, pytest for tests, type hints on public functions.
- The data directory is gitignored. Only fixtures small enough to read in a review get committed.
- Full TED history is millions of rows. That fits DuckDB on a laptop. If a job doesn't fit, profile before reaching for infrastructure.

## ADRs

Write one when a decision constrains future work, picks between real alternatives, or reverses an earlier ADR. Numbered files at `docs/adr/NNNN-slug.md` with four sections: Context, Decision, Consequences, and Revisit triggers. The revisit triggers are what make ADRs useful two years later; ADR-0001's Postgres triggers are the model. Keep each ADR under a page. If it needs more, the decision probably isn't crisp yet.