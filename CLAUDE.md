# Serenata Europa

Open-source anomaly detection pipeline for EU public procurement data (TED/eForms).
Successor to Operação Serenata de Amor (okfn-brasil/serenata-de-amor), rebuilt for
EU data by co-founder Felipe Cabral. An NLnet NGI Zero Commons Fund application is
pending (deadline 1 Aug 2026); this repository is referenced in that application
and will be read by NLnet reviewers. Code quality, documentation honesty, and the
constraints below are not optional.

## Hard constraints — never violate, never "temporarily" work around

1. License is AGPL-3.0. Every dependency must be compatible. Check before adding.
2. No personal data, ever. The data model ingests contracting authorities,
   companies, and contracts. If a source field could contain a natural person's
   name (contact persons, sole traders), it is dropped at ingestion, not stored
   and filtered later. This is a legal constraint (GDPR, Swedish defamation law),
   not a style preference.
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

## Data source facts (verify against current docs before coding against them)

- TED publishes ~700k notices/year. Access: the TED Search API and daily bulk
  packages (XML). Notices from late 2024 onward use eForms (UBL-based XML);
  earlier notices use legacy TED XML schemas.
- eForms field usage varies by member state; optional fields are often empty.
  The normalisation layer must record field provenance and absence explicitly —
  "not provided" and "not applicable" are different facts.
- Do not scrape the TED website. Use the documented API/bulk channels only, with
  polite rate limits and a descriptive User-Agent identifying the project.

## Working style

- Small PRs/commits, imperative messages, one concern each.
- When a design decision isn't covered here, propose it in a short ADR
  (docs/adr/NNNN-title.md) instead of burying it in code.
- The README is part of the product: NLnet reviewers and journalists read it.
  Keep the project plan, milestone status, and honest limitations current.
- Never fabricate sample data that looks like real findings. Examples in docs use
  obviously synthetic notice IDs or real public notices reproduced accurately.