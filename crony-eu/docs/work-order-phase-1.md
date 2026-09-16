# Work order: phase 1 (France, communes, one département)

Goal: one département processed end to end. At the end of phase 1 the maintainer runs a documented sequence of commands and gets staged sources, candidate matches, a review screen, F1 hits with their tags and overlaps, measured pair rates and precision, and case packets for the hits that qualify.

The maintainer picks the département before session 1. Its code is the only thing about the slice that goes into session notes.

Revised 2026-09-16. Two changes run through every session below, both from [ADR-0014](../../docs/adr/0014-replace-serenata-with-crony.md):

- **Officer role history is phase 1 work.** It was phase 2, while phase 1's only flag needed it. Session 3 is now a feasibility gate that can stop the phase.
- **Phase 1 measures descriptive pair rates**, not excess risk. See `crony-eu/docs/flags/F1-same-body.md`.

Session 0 is built. Everything below it is an order, not a description.

Three things reconnaissance settled before session 1, recorded here so they are not re-derived: the open company API carries officer birth dates as `YYYY-MM` (the precision ADR-0003 assumes) but **no role dates at all**, so phase 1 produces no packet-eligible hits until INPI; and that same API carries every SIRENE field session 2 wanted, so the SIRENE stock is not ingested and `fr_sirene.py` is not written.

## How to run a session

1. Read `crony-eu/CLAUDE.md`, this file, and the sections of `crony-eu/docs/sources/france.md` and `crony-eu/docs/flags/` that the session touches.
2. Propose a plan in plan mode and wait for approval.
3. Where behaviour is specified, write tests against generated fixtures first.
4. Never print personal values from real data (CLAUDE.md, constraint 13). Inspect real data through schemas, counts, null rates and pattern summaries.
5. Stop at every gate marked STOP and report.
6. Finish with the definition of done from CLAUDE.md, then tick the box below with one line on what changed.

Progress:

- [x] Session 0: bootstrap. Package, config, paths, http, parquet, `crony doctor`, both suites from one pytest, the data guard in CI. Two decisions it forced: ADR-0005 (one licence, AGPL-3.0-only) and ADR-0006 (standard library, no typer/rich/jinja2/vis-network).
- [ ] Session 1: élus
- [ ] Session 2: contracts, buyers, populations
- [ ] Session 3: supplier officers and role history (**feasibility gate**)
- [ ] Session 4: matching and review
- [ ] Session 5: F1 and pair rates
- [ ] Session 6: case packets and HTML

## Session 0: bootstrap

Deliver:

- the layout from CLAUDE.md, with empty modules for later sessions
- a `pyproject.toml` for this project: project `crony-eu`, package `crony_eu`, `requires-python = ">=3.12"`, script `crony = "crony_eu.cli:app"`. Runtime dependencies: duckdb, pyarrow, httpx, typer, rich, jinja2. Dev dependencies: pytest, hypothesis, ruff, mypy, pre-commit. Add them with `uv add` / `uv add --dev` so versions resolve and lock.
- ruff: rule sets E, F, I, B, UP, SIM, RUF. mypy: strict for `crony-eu/src/`.
- **Line length is 88, not the 100 the handover asked for**, for as long as this project lives inside a repository whose ruff configuration is already 88. `crony-eu/scripts/check_no_data.py` was rewrapped to 88 on 2026-09-16 for that reason. Two line lengths in one tree means one of them is not checked; pick 100 back up if and when this project gets a repository of its own.
- an SPDX header `# SPDX-License-Identifier: AGPL-3.0-or-later` at the top of every source file. **Settle the licence statement before writing the first one:** the repository's `LICENSE` is plain AGPL-3.0 and this project says "or later". One ADR, then the header.
- `crony-eu/.gitignore`, `crony-eu/.pre-commit-config.yaml` and `crony-eu/scripts/check_no_data.py` are already here; add `crony-eu/tests/test_check_no_data.py`
- CI: this project lives inside a repository that already has `.github/workflows/ci.yml`. Extend it rather than adding a second workflow that runs on the same push: uv setup, then ruff, mypy, pytest (without `live` tests) and `check_no_data.py --all`. Reconciling the two projects' checks while both exist is part of the session, not an afterthought.
- `config.py`: `CRONY_DATA_DIR` is required, absolute, creatable, and after resolving symlinks it must not be inside the repository root (`git rev-parse --show-toplevel`, falling back to the package location). Each violation raises an error that says which rule failed.
- `paths.py`: helpers for the `$CRONY_DATA_DIR` layout in CLAUDE.md
- `http.py`:
  - one httpx client per source, with a user agent naming the project and the repository URL
  - a token-bucket rate limiter per source (configurable, default 5 requests per second)
  - retries on 429, 5xx and network errors: exponential backoff with jitter, at most 5 attempts, honouring `Retry-After`
  - `download(url, dest)` streams to a temporary file, computes sha256, renames atomically, and appends an entry to `manifest.json`
- `crony doctor` with the checks listed in CLAUDE.md
- `crony-eu/README.md` is already here; update its status section once there is something to run

Tests:

- config refuses a relative path, a path inside the repository, and a symlink pointing into the repository
- the rate limiter, with an injected clock
- retries, with `httpx.MockTransport`: a 429 carrying `Retry-After`; two 503 responses followed by a 200
- manifest: atomic write, hash recorded, a second download of the same URL appends a new entry
- data guard: blocked suffixes, the size limit, forbidden top-level directories, the allowlists, and a throwaway git repository where committing a `.parquet` file fails through pre-commit

Accept when: `uv run crony doctor` passes with a temporary data directory, and CI is green on a pushed branch with both projects' checks running.

## Session 1: fr-rne-elus

Deliver:

- `crony-eu/src/crony_eu/sources/fr_rne_elus.py`: `fetch()` for the current dataset and the pre-election extract, resolving resource URLs through the data.gouv.fr API
- `stage()` writing `elus.parquet` with: elu_row_id, source_file (current or pre_election), mandate_type, departement_code, commune_code, commune_label, surname_raw, given_raw, sex, birth_date, csp_code, mandate_start, function_label, function_start, retrieved_at
- `elu_row_id` = sha256 of (source_file, mandate_type, surname_raw, given_raw, birth_date, commune_code, mandate_start, function_label), stable across runs
- a person-level table `elu_person` that groups the function rows of one person within one commune and mandate, with `elu_person_id` built the same way minus the function fields
- a date parser that accepts ISO 8601 and DD/MM/YYYY. Anything else fails the stage, reporting the file and row number, never the row content.

STOP: after the first real fetch, record the observed column names, types and null rates in `crony-eu/docs/sources/france.md`, and report them.

Tests: a fixture builder that generates élu rows with invented names; stage round-trip; id stability across runs; grouping into `elu_person`; both date formats; a malformed date produces an error message without row values.

Accept when: staging runs on the real files for the chosen département, row counts per file appear in the manifest, and `elu_row_id` is unique.

## Session 2: fr-decp, fr-sirene, fr-insee-pop

Deliver:

- DECP: fetch the consolidated Parquet; stage `contracts.parquet` (latest version of each contract) and `contract_versions.parquet` (every version)
- identifiers: SIRET as 14 digits and SIREN as 9, both checked with the Luhn algorithm. La Poste establishments are a known exception to the SIRET checksum; find INSEE's documented rule and test it.
- amounts as DECIMAL(18,2) in EUR, notification dates as DATE. Contracts whose titulaire has no SIRET or SIREN stay in the table with `supplier_has_siren = false`.
- SIRENE: stage `units.parquet` with siren, legal_category, admin_status, creation_date, headcount_band, diffusion_status, head_office_commune_code (from head-office establishment rows). Read only the needed columns.
- `commune_buyers.parquet`: siren -> commune_code, for units whose legal category is commune
- the F1 exclusion list (SEM, SPL, public bodies and similar): INSEE codes and labels written into `crony-eu/docs/flags/F1-same-body.md`
- INSEE population by commune code, latest vintage
- a data-quality report in `$CRONY_DATA_DIR/staged/_reports/` with aggregates only: DECP rows in scope, share of buyers mapped to a commune, share of suppliers with a SIREN, share of suppliers found in SIRENE, and amount outliers (top 0.1% by amount, listed by contract id)
- **the pair count**: distinct (commune, supplier) pairs with at least one contract in scope, by population band. This is F1's denominator and it is worth knowing before session 5 that it exists in usable numbers.

STOP: report the aggregate numbers, the pair counts and the current DECP publication threshold from the arrêtés, and record the threshold in `crony-eu/docs/sources/france.md`. The maintainer decides whether the slice is usable.

Tests: identifier normalisation (property tests: a SIRET starts with its SIREN; invalid checksums are flagged; the La Poste rule), latest-version selection on generated version chains, commune mapping, exclusion categories, pair counting on generated contracts that share a supplier.

## Session 3: supplier officers and role history (feasibility gate)

**This session can stop phase 1.** F1 cannot build a case packet without a dated officer role, and no French source is known to provide one. Everything downstream of here assumes an answer this session has to go and get.

STOP, before any code: read the OpenAPI specification of the open API, and INPI's RNE documentation, and record in `crony-eu/docs/sources/france.md`:

- the officer fields and their formats
- whether a role start date exists, whether a role end date exists, and what each date means. A filing date is not a role start date
- what INPI access requires, and whether the account exists

Then measure, before building anything on top:

- officer birth date precision. If year only, stop: ADR-0003 assumes month precision and the matching rule needs a new record
- role date coverage over the slice's supplier SIRENs: the share with a start date, the share with an end date, the share with both, as aggregates only

STOP: report those three coverage numbers and what the dates mean. **The maintainer decides whether phase 1 continues, and in which of three shapes:**

- role dates available at usable coverage: phase 1 as specified, case packets included
- role dates available but sparse: phase 1 continues, most hits stay `role_overlap = unknown`, and the expected packet count is reported now rather than discovered in session 6
- no role dates: phase 1 produces counts and no packets. That is a result, and it goes back to the trunk decision in `scope.md` rather than being worked around

Deliver, once the gate is passed:

- `crony-eu/src/crony_eu/sources/fr_entreprises_api.py`: `fetch(scope)`, one call per distinct supplier SIREN in the slice (from session 2), at 5 requests per second or fewer. Raw JSON per SIREN under `$CRONY_DATA_DIR/raw/fr-entreprises-api/<date>/<siren>.json`, recorded in the manifest.
- `crony-eu/src/crony_eu/sources/fr_inpi_rne.py`: the same narrow scope, per supplier SIREN, for role history. Authentication token from the environment, never from a file in the repository.
- `stage()`: `officers.parquet` with officer_row_id, siren, officer_type (natural or legal), surname_birth_raw, surname_usage_raw, given_names_raw, birth_ym, role_label, role_start, role_end, role_date_source, role_date_semantics, retrieved_at, source_url. Legal-person officers go to `officer_companies.parquet` for phase 2.
- `role_date_semantics` records what the date is (role start, filing date, unknown) as a value, not a footnote. A pipeline that cannot say what its dates mean cannot claim an overlap.
- SIRENs a source doesn't return (non-diffusible or not found) go to `officers_missing.parquet` with a reason code and the source that refused. They are not retried in a loop.
- resumable runs: SIRENs already in the manifest for the snapshot are skipped

Tests: `httpx.MockTransport` responses built by fixture code, for both sources; rate limit respected (injected clock); resume after an interruption; an officer with a start and no end; an officer with neither; the coverage report computed from generated officers.

Accept when: the coverage report (share of supplier SIRENs with at least one natural-person officer, and the three role-date shares) is in the data directory, and its aggregate numbers are in the session note.

## Session 4: matching and review

Deliver:

- `normalize.py`: `norm_name`, `given_key`, `birth_ym`, as specified in CLAUDE.md
- `keys.py`: key variants per élu and per officer, rule id `FR-NAME-BIRTHYM-v1`
- `candidates.py`: exact join on key variants within scope; `key_collision` flags; output `candidates.parquet`
- `judgments.py`: append-only `$CRONY_DATA_DIR/matched/judgments.parquet` with judgment_id = sha256(rule_id, elu_person_id, officer_row_id), rule_id, elu_person_id, officer_row_id, siren, status, decided_by, decided_at, note, run_id; plus a `judgments_latest` view
- new candidates enter as `pending`; an existing judgment is never overwritten, only superseded by a newer row. The full history is the point: a packet built on a judgment that later becomes `rejected` has to be findable, and only an append-only log can answer that.
- `judgments_history(judgment_id)`: every row for one judgment, oldest first, so the question "what did we believe when that packet was built, and what do we believe now" has an answer that is a query rather than a memory
- `review.py` (`crony review`): a rich screen with the élu's fields next to the officer's fields, the company name and SIREN, the commune, the role dates and what they mean, the territory hint (same département or not), and links to the company's annuaire-entreprises page and its DECP contracts. Keys: c confirm, r reject, a ambiguous, s skip, n note, q quit. `--flag F1` limits the queue to candidates behind F1 hits. `--sample N --seed S` draws a reproducible random sample for the precision estimate.
- a decision is written with the rule id it was made under. Changing the matching rule does not revalue old decisions, and a later reader can tell which rule a judgment belongs to.
- birth name versus usage name: compute candidate counts per surname variant, split by sex, and record the aggregate answer in `crony-eu/docs/sources/france.md`

Tests: normalisation properties (idempotent; accents, apostrophes, hyphens and double spaces; JEAN-PIERRE and JEAN PIERRE handled as specified); key collision detection; append-only semantics and latest-wins; history returned in order; a confirm followed by a reject leaving both rows readable; the review loop driven by scripted keypresses.

Accept when: candidates exist for the slice, and the maintainer runs `crony review --sample 5 --seed 1` end to end.

## Session 5: F1 and pair rates

Deliver:

- `crony-eu/src/crony_eu/flags/f1_same_body.py` and its SQL, implementing `crony-eu/docs/flags/F1-same-body.md` exactly: scope, the six conditions, exclusions, tags, both overlaps, output columns
- `crony-eu/src/crony_eu/flags/base_rates.py` and `crony-eu/src/crony_eu/flags/sql/f1_base_rate.sql`, following the method in the flag spec, with Wilson intervals
- every rate over the same unit, distinct (commune, supplier) pairs, in all three cuts the spec names: candidate, confirmed, packet-eligible. No expected-rate comparison in phase 1; that needs officer data for companies that won nothing, which is phase 2.
- role-date coverage per band, reported beside the rates rather than in a separate file, because a rate whose overlap is mostly `unknown` is a different number from one whose overlap is mostly `true`
- `crony flag F1 --scope dep:<code>` and `crony base-rate F1 --scope dep:<code>`

STOP: show the maintainer the aggregate table, the coverage numbers and the precision estimate before writing them into the flag spec. After approval, fill the tables and change the spec's status line to the measurement date.

Tests: generated scenarios for every branch: an élu found only in the pre-election extract; a mandate starting after the notification date; a role starting after the notification date; a role ended before it; a role with no dates at all; an excluded legal category; the 432-12 tag set and not set; a consortium supplier; a contract with several versions; a key collision; a supplier with forty contracts to one commune counting once in the pair denominator.

## Session 6: case packets and HTML

Deliver:

- `crony-eu/src/crony_eu/export/model.py`: node and edge records matching the export contract in CLAUDE.md, with a test that pins the columns and the allowed `ftm_schema` values
- `crony-eu/src/crony_eu/export/case.py`: `crony case build <case_id>`. It **refuses** unless every condition in CLAUDE.md constraint 11 holds, and the refusal names which one failed:
  - the supplier may be redistributed
  - every person-to-company edge carries a `confirmed` judgment
  - `mandate_overlap` and `role_overlap` are both `true`
  - the flag is calibrated
  - It writes `nodes.csv`, `edges.csv`, `sources.md` (every source record with URL, retrieval date and licence), the evidence directory and `network.html`.
- evidence minimisation: the packet's `$CRONY_DATA_DIR/cases/<case_id>/evidence/` directory holds the raw records the packet's own edges cite and nothing else. Not the slice, not the neighbouring rows, not the officer list the match came from. A test builds a case from a generated slice with decoy records and asserts none of them is copied.
- the status block at the top of the packet: flag id, calibration date, rule id, run id, judgment ids, every overlap and its value, and the verification checklist copied from the flag spec
- `crony case check`: for every packet in `$CRONY_DATA_DIR/cases/`, compare the judgments it names against `judgments_latest`, and list the packets whose judgments have since become `rejected` or `ambiguous`. Those packets are invalid and the maintainer withdraws them from whoever has a copy. This is the whole reason the packet records judgment ids.
- `crony-eu/src/crony_eu/export/html.py` and `templates/network.html.j2`: the vis-network standalone UMD build (from the `vis-network` npm package; confirm the file's path inside the package) inlined, its version and sha256 recorded in `assets/VERSION`; the CSP meta tag; a fixed layout seed; node styles by kind; edge colour by kind and width from log10 of the amount; dashed `reported` edges; tooltips built as DOM nodes; a legend; a sources panel
- case ids: sha256 of (flag id, commune code, supplier SIREN, elu_person_id), shortened to 12 hex characters

Tests:

- building the same generated case twice gives byte-identical files
- building it from a different working directory, and with the rows in a different order in the input, gives the same bytes again. Sorting before writing is the claim; a test that only reruns the same process does not check it
- a golden-file test on a generated case
- the refusal path: one test per condition in constraint 11, each asserting the build fails and names the condition
- evidence minimisation, with decoy records
- `crony case check` finds a packet whose judgment was later rejected, and is silent about one whose judgment still stands
- the rendered HTML has no `src` or `href` pointing to http(s) inside script, link or style tags; source links appear only as anchors
- the CSP meta tag is present
- a fixture name containing `<script>` renders as text

Accept when: the maintainer opens a real packet offline in Firefox and in a Chromium browser with no console errors, the links in the sources panel work, and `crony case check` reports cleanly on a packet whose judgment has been flipped by hand.

## After phase 1

Phase 2 starts from the measured pair rates and precision, and from whatever session 3 found out about role dates. It gets its own work order: INPI at national scale, EPCI and département buyers, co-officers and their other companies (one to two hops), HATVP declarations, hand-entered `reported` edges, a TED cross-check reading TED directly, and the excess-risk comparison that phase 1 deliberately does not attempt.
