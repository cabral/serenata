# Serenata Europa

**This repository is being handed over to a different project.**
[ADR-0014](docs/adr/0014-replace-serenata-with-crony.md) makes Crony what it is
for; [`scope.md`](scope.md) is the canonical scope and
[`docs/transition-ledger.md`](docs/transition-ledger.md) says what happens to
every piece of what it replaces. Serenata Europa's TED pipeline is retiring, in
groups, as the replacement check for each group exists.

**Which file governs your task.**

| you are working on | read |
|---|---|
| anything under `crony-eu/` | [`crony-eu/CLAUDE.md`](crony-eu/CLAUDE.md), then this file for the repository-wide rules |
| the retiring TED pipeline (`serenata/`, its tests, its docs) | this file |
| the repository itself: CI, licence, DCO, automation, documentation gates | this file |

The two constraint lists are both real and they do not say the same thing,
because the two projects do not do the same thing. Where they meet:

- **Constraint 2 below is about this repository's derived model and about the
  repository tree.** Serenata's model holds no natural person. Crony's model
  holds elected officials and company officers by design, and keeps every one of
  them outside the repository, under `$CRONY_DATA_DIR` on an encrypted volume.
  Neither project puts a real person's record into git. A session that reads
  "no personal data, ever" as forbidding Crony's data model has read the wrong
  file for its task; a session that reads Crony's rules as permission to commit
  a name has misread both.
- **Constraints 1, 3 and 4 are the same rule in both projects**: a compatible
  licence, a flag that is a question rather than an accusation, and byte-identical
  reruns.
- **Constraint 6 is the same rule under another name.** Crony's version is that
  a flag without a measured base rate is `uncalibrated` and cannot reach a case
  packet.

Open-source anomaly detection pipeline for EU public procurement data (TED/eForms).
Successor to Operação Serenata de Amor (okfn-brasil/serenata-de-amor), rebuilt for
EU data by co-founder Felipe Cabral. This is a public repository, read by people
deciding whether the output can be trusted. Code quality, documentation honesty,
and the constraints below are not optional. That last sentence survives the
handover unchanged; it was never about TED.

## Hard constraints — never violate, never "temporarily" work around

1. License is AGPL-3.0. Every dependency must be compatible. Check before adding.
2. No personal data, ever. The data model ingests contracting authorities,
   companies, and contracts. If a source field could contain a natural person's
   name (contact persons, sole traders), it is dropped at ingestion, not stored
   and filtered later. This is a legal constraint (GDPR, Swedish defamation law),
   not a style preference. The field list is docs/personal-data.md, executable as
   serenata/parse/personal_data.py; extend both in the same PR as any schema
   change.
3. Flags are statistical anomalies, not accusations. Any user-facing string, doc,
   or example output describes flags as anomalies with possible innocent
   explanations, linked to the source notice. Never the words "corrupt",
   "fraud", or "guilty" applied to a flagged record.
4. Determinism. Same input data + same classifier version = same flags, byte for
   byte. No wall-clock dependence in outputs, no unseeded randomness, no network
   calls inside transform/classify steps. Fetching is the only networked stage.
5. Structured fields first. Core classifiers use eForms/TED structured fields
   only. No NLP, no LLM calls, no free-text analysis in the core pipeline. (A
   clearly separated experimental area may exist later; it is out of scope now.)
6. Every classifier is a documented hypothesis. A classifier may not be merged
   without: a written hypothesis citing its risk-indicator source (ECA, OCP
   red-flags, DIGIWHIST literature), tests, and measured base rates on real
   historical data. A flag whose false-positive profile is unknown is not
   shippable.

## Stack decisions (made; don't relitigate without Felipe's sign-off)

These describe the TED pipeline. Crony's own stack is in
[`crony-eu/CLAUDE.md`](crony-eu/CLAUDE.md) and agrees with the ones that are
about engineering (Python 3.12+, uv, Parquet, DuckDB, pytest, ruff, no other
formatter) rather than about TED. The Postgres-with-the-public-API line retires
with the milestone plan it belonged to: Crony ships no API and publishes
nothing.

- Python 3.12+, `pyproject.toml`, `uv` for dependency management.
- Storage for the normalised dataset: Parquet files + DuckDB. No database server
  in M1. Postgres enters later, with the public API milestone.
- Data flow: fetch (networked, raw XML archived as-is) -> parse -> normalise
  (one documented relational model spanning eForms and legacy TED) -> classify
  -> publish. Each stage is a separate module, runnable and testable alone.
- Raw source files are immutable once fetched and are the ground truth; every
  derived record keeps a reference back to its source notice ID.
- Code, comments, identifiers, docs: English. Findings published later may be
  multilingual; not a code concern now.
- Tests: pytest. CI: GitHub Actions, runs lint (ruff) + tests on every push.
- Formatting: ruff format. No other formatters.

## Data source facts (TED; verify against current docs before coding against them)

Crony's sources are French and listed in
[`crony-eu/docs/sources/france.md`](crony-eu/docs/sources/france.md), under the
same rule: a source nobody has written a section for is a source nobody may
fetch.

- TED publishes ~700k notices/year. Access: the TED Search API and daily bulk
  packages (XML). Notices from late 2024 onward use eForms (UBL-based XML);
  earlier notices use legacy TED XML schemas.
- eForms field usage varies by member state; optional fields are often empty.
  The normalisation layer must record field provenance and absence explicitly —
  "not provided" and "not applicable" are different facts.
- Do not scrape the TED website. Use the documented API/bulk channels only, with
  polite rate limits and a descriptive User-Agent identifying the project.

## Working style

- Small PRs/commits, imperative messages, one concern each. Every commit carries
  a `Signed-off-by` trailer (DCO) and, where a tool helped write it, a
  `Co-Authored-By` one. CI enforces the first; ADR-0009 says what each means.
- When a design decision isn't covered here, propose it in a short ADR
  (docs/adr/NNNN-title.md) instead of burying it in code.
- The README is part of the product: funders, journalists and contributors read
  it. Keep the project plan, milestone status, and honest limitations current.
- Never fabricate sample data that looks like real findings. Examples in docs use
  obviously synthetic notice IDs or real public notices reproduced accurately.