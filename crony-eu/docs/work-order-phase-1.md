# Work order: phase 1 (France, communes, one département)

Goal: one département processed end to end. At the end of phase 1 the maintainer runs a documented sequence of commands and gets staged sources, candidate matches, a review screen, F1 hits with their tags and overlaps, measured pair rates and precision, and case packets for the hits that qualify.

The maintainer picks the département before session 1. Its code is the only thing about the slice that goes into session notes.

**The slice is `dep:74`, chosen 2026-09-21.** A bounded pilot choice, and not a
claim that the survey established it as optimal: `crony survey departements`
measured what each département would give, the maintainer read it, and one had to
be picked for a pilot. All in-scope historical contracts are retained. There is
no notification-date cutoff, and none is to be introduced.

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
- [x] Session 1: élus. Four files fetched and staged: 1,066,291 rows, 994,761 people, birth key present on 100%. Found and fixed a silent date bug (the pre-election extracts publish a two-digit year, which `%d/%m/%Y` accepts), and added a plausibility gate that tells a misread file from a register typo. Observed schema in `crony-eu/docs/sources/france.md`.
- [x] Session 2: contracts, buyers, populations. DECP (3,281,288 versions -> 2,188,458 latest, 12,833 commune-buyer mappings) and the INSEE populations de référence 2023 staged; SIREN/SIRET checks with the La Poste rule; `crony survey departements` added so the slice is picked from counts. Three findings changed the plan: `donneesActuelles` is absent on 70,277 contract groups so the latest version is taken from `modification_id`; `titulaire_categorie` is the size band, not the catégorie juridique, so **F1's exclusion list moves to session 3**; and Paris, Lyon and Marseille buy under arrondissement codes, which the survey now reports rather than showing as zero. SIRENE is not ingested. **The département is not picked yet**: that is this session's STOP.
- [ ] Session 3: supplier officers and role history (**feasibility gate**)
- [ ] Session 4: matching and review. **Matching is built, review is not.** Keys, candidates and an append-only judgments log exist and run: `dep:74` gives 107 candidates from 10,002 élus and 5,022 keyed officers, 9 on a colliding key. The officer surname turned out to pack birth and usage names as `BIRTH (USAGE)`, and 51 of the 107 candidates depend on splitting it. `crony review` is built for both logs and tested on scripted keypresses. **Open: only the acceptance, which is a human action.** The maintainer runs `crony review --scope dep:74 --sample 5 --seed 1` end to end, and `crony review buyers --scope dep:74` over the 310 buyer assertions. An agent session does not run either on real data, because both show real records.
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

## Session 2: fr-decp, fr-insee-pop (and not fr-sirene)

Deliver:

- DECP: fetch the consolidated Parquet; stage `contracts.parquet` (latest version of each contract) and `contract_versions.parquet` (every version)
- identifiers: SIRET as 14 digits and SIREN as 9, both checked with the Luhn algorithm. La Poste establishments are a known exception to the SIRET checksum; find INSEE's documented rule and test it.
- amounts as DECIMAL(18,2) in EUR, notification dates as DATE. Contracts whose titulaire has no SIRET or SIREN stay in the table with `supplier_has_siren = false`.
- ~~SIRENE: stage `units.parquet`~~ **Not done, and not to be done.** The consolidated DECP already carries `acheteur_commune_code` on 100% of commune-buyer rows, so the national stock is not fetched to recompute it. See `crony-eu/docs/sources/france.md`.
- `commune_buyers.parquet`: siren -> commune_code, from DECP's `acheteur_categorie = 'Commune'` rather than from a SIRENE legal category, since DECP publishes no legal category at all. One row per (SIREN, commune): four SIRENs carry more than one commune code and one carries sixteen.
- ~~the F1 exclusion list (SEM, SPL, public bodies and similar)~~ **Moved to session 3.** DECP's only supplier category is the INSEE size band (PME, ETI, GE). The catégorie juridique the exclusion list needs comes from the open company API, which session 3 queries per supplier SIREN anyway. Until it is pinned, F1 cannot run as specified: a SEM whose seats are held by councillors on the commune's behalf is the flag's most confident wrong hit.
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
- `judgments.py`: append-only `$CRONY_DATA_DIR/matched/judgments.parquet` with judgment_id = sha256(rule_id, elu_person_id, officer_row_id), revision, rule_id, elu_person_id, officer_row_id, siren, status, decided_by, note, run_id; plus a `judgments_latest` view

  **No `decided_at`, changed 2026-09-22.** This list originally carried a
  wall-clock `decided_at`, and constraint 4 says the only timestamps inside data
  are `retrieved_at` values recorded at fetch time. The ADR-0007 handoff resolved
  the same conflict for the buyer log with a `revision` counter per id, and both
  logs now order themselves that way: the latest revision wins, history is read
  in revision order, and two runs over the same decisions write the same bytes.
  ADR-0003 never specified the timestamp, so no decision record changes; the
  work order yields to a hard constraint.
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

### ADR-0007 execution handoff

[ADR-0007](adr/0007-consolidator-derived-attributes.md) is accepted by the
maintainer; its runtime enforcement is not built. Claude Code should implement
the following within the relevant sessions, after their existing STOP gates and
approval of an implementation plan. This handoff does not authorize a fetch,
merge, push or disclosure, or bypass the role-history feasibility gate.

**Resolve before implementation.** Identify an approved official source and
documented access method that can archive evidence for the exact buyer SIRET,
its identity as a commune and the claimed commune code. Verify field semantics
and temporal limitations, not just field presence. The existing supplier-SIREN
request is not evidence of buyer-SIRET coverage. If the listed sources cannot
supply that evidence, stop for source approval; do not scrape the annuaire or
revive SIRENE stock. Missing historical support remains unknown, not agreement.

**Resolved 2026-09-21, partly. The source is `fr-entreprises-api`**, already
approved, queried by putting the bare 14-digit SIRET in `q`. It returns that
exact establishment with its INSEE commune code, the legal-unit
`nature_juridique` (a commune is `7210`), `etat_administratif`, the
`[date_creation, date_fermeture]` window and
`statut_diffusion_etablissement`. A SIREN query returns no establishment at all,
so the ADR's refusal of head-office-only evidence is enforced by the source
rather than only by the rule. Verified fields, semantics and measured exposure
are in
[`crony-eu/docs/sources/france.md`](sources/france.md#verified-for-adr-0007-2026-09-21-buyer-siret-evidence).

**The temporal half was decided on 2026-09-21**, in
[ADR-0007 Amendment 1](adr/0007-consolidator-derived-attributes.md#amendment-1-2026-09-21-snapshot-corroboration-with-its-limits-named).
The source has no as-of parameter and no address history, and its publisher
describes it as a way to search for a company rather than to retrieve complete
SIRENE records, so a check establishes the mapping as of the snapshot. The
standard is now **snapshot corroboration**: identity corroborated against the
archived snapshot and historical geography recorded separately as `established`,
`contradicted` or `not_established`. Absence of address history alone stops
blocking; missing exact-identifier evidence, conflicting identity, ambiguous
succession or merger, and unresolved contradictions still block. Establishment
dates are consistency checks whose semantics must be read from documentation
before any boundary is enforced from them.

Two things this does **not** license. It does not relax officer-role or
mandate-overlap requirements, which are unchanged under constraint 9. And the
five successful probes behind it establish feasibility, not accuracy: the 26
buyer commune codes absent from the population vintage bound nothing about
mapping errors among the 12,772 that are present.

**Scoped implementation plan, 2026-09-21.** Engineering readiness and real-data
feasibility are separated, because they are blocked on different things and
conflating them is how synthetic completion gets reported as a result. Three
tiers. Nothing in tier A touches the network or needs an account; nothing in any
tier is a session 3 pass; nothing in any tier permits a real packet.

**Tier A, buildable now against generated fixtures.** Needs an approved plan and
nothing else.

| # | work | session | acceptance |
|---|---|---|---|
| A1 | attribute-level lineage in staging: declared against derived, bound to the manifest row, source field, URL and fetch-time `retrieved_at`. `decp_row_id` omits enrichment, so the binding carries the asserted values too | 2 | a derived attribute and a declared one carry distinct provenance; changing enrichment while keeping `decp_row_id` changes the binding |
| A2 | `fr_entreprises_api.py` adapter shape, driven by `httpx.MockTransport`: exact-SIRET resolution, and refusal on zero, several, or no exact match | 3 | one refusal test per failure mode; no best-match path exists to test |
| A3 | append-only `buyer_verification`, with a stable revision reference and deterministic ordering, no wall-clock field | 4 | append-only and latest-wins; history readable in order; a later adverse review is findable |
| A4 | `crony review` buyer action over archived evidence, recording the two fields apart | 4 | scripted keypresses; `not_established` reachable and never coerced to `true` |
| A4b | session 4's own matching core: `keys.py`, `candidates.py`, `judgments.py` and the person-company half of `crony review`. Not named in the first version of this plan, and A5 cannot be built without it. Not blocked by INPI | 4 | `FR-NAME-BIRTHYM-v1` key variants; exact join within scope; `key_collision`; append-only judgments with latest-wins |
| A5 | F1 eligibility and per-gate loss counting, over generated officers | 5 | candidate, confirmed and packet-eligible counted separately; one loss line per gate; eligible count agrees with export eligibility |
| A6 | export provenance, the verbatim sentence, refusal paths, evidence minimisation with decoys, byte-identical and input-order-independent rebuilds | 6 | one test per condition in constraint 11 plus the ADR-0007 conditions, each naming what failed |

**Tier B, needs real data from an open source. No account, no INPI.** These are
the numbers the flag spec still has blank, and they are reachable today for
`dep:74`.

| # | work | blocked on |
|---|---|---|
| B1 | **done 2026-09-22.** SEM (5415, 5515, 5615) and the public-law families 4xxx and 7xxx are pinned in the flag spec. SPL has no INSEE code and cannot be excluded by category, which is recorded as a limit rather than worked around | |
| B2 | **done 2026-09-22.** `date_de_naissance` is `YYYY-MM` on 97.31% of 5,164 officers, and no role date exists under any name | |
| B3 | buyer corroboration evidence for the slice's buyer SIRETs, archived under `$CRONY_DATA_DIR` | **fetched**; the review that reads it is A3 and A4 |
| B4 | **done 2026-09-22.** SIRENE overwrites the commune code forward for all establishments including closed ones, so no as-of code exists at any access level; `dateCreationEtablissement` is declaratory with a `1900-01-01` sentinel, so no window is enforced | |

**Tier C, needs a human or an account.** No code unblocks these.

| # | work | who |
|---|---|---|
| C1 | INPI account and credentials, kept outside chat and git and read from the environment | the maintainer |
| C2 | role-date coverage and semantics over the slice, the session 3 feasibility gate | after C1 |
| C3 | the buyer-mapping confirmations themselves | the maintainer, in `crony review` |
| C4 | counsel, and explicit disclosure approval before any packet leaves the machine | the maintainer |

**Retained evidence, not disclosed data.** Permitted in-scope records are kept
internally with an explicit exclusion reason per record rather than dropped, so
that a count can say which gate removed what. Non-diffusion, evidence
minimisation, counsel and disclosure approval are unchanged by any of this.

**Implementation order.**

1. In the source work, preserve attribute-level lineage for declared fields and
   enrichment. Bind evidence to the immutable manifest and source row, including
   source field, URL and fetch-time retrieval timestamp. DECP row identity omits
   enrichment, so `decp_row_id` alone cannot bind a buyer check to its inputs.
2. In matching and review, add a separate, append-only buyer-verification record
   and a maintainer review action over archived official evidence. Retain the
   exact buyer SIRET, asserted category and commune, input snapshot/hash, evidence
   references and result. Give each review revision a stable reference and
   deterministic ordering without adding wall-clock timestamps. A confirmation
   of the person-company match does not confirm the buyer mapping.

   The result is **two fields, not one**: `buyer_identity_corroborated`
   (`true`/`false`/`unknown`) and `historical_geography`
   (`established`/`contradicted`/`not_established`). Nothing in the pipeline may
   rewrite `not_established` as `true`, and no default may produce `true`.

   Resolution against the source must match **exactly**: a query returning zero
   results, more than one result, or no result carrying the exact SIRET is a
   refusal. Do not take a best match, and do not assume a search returns one
   usable result.
3. In F1, use this check for packet eligibility and the packet-eligible pair
   counts. Keep descriptive candidate and confirmed-match counts distinct; do
   not silently remove unverified buyers from their denominator.
4. In export, refuse before writing a packet if required provenance or a valid
   buyer verification is absent. Every qualifying packet carries, verbatim and
   with the retrieval date filled in, in the status block and in machine-readable
   provenance: "Buyer identity was corroborated against a registry snapshot
   retrieved on [date]. Historical commune-code continuity was not independently
   established." It is an evidentiary standard and not a disclaimer, so it never
   accompanies contradictory evidence; that case is refused. Cite declared and derived attributes distinctly
   in the CSV attributes, sources list and HTML panel; include the separate
   verification evidence and review reference. Copy only cited records, including
   the buyer evidence cited by the contract edge, never a whole API response
   containing unrelated records. Make `crony case check` report dependent packets
   invalid when a later buyer review rejects or makes the mapping ambiguous.

**Acceptance tests, generated fixtures only.**

- A derived commune attribute cites the consolidator, while the declaration and
  official verification retain their own source references. All three preserve
  fetch-time timestamps; no upstream retrieval time is invented.
- `historical_geography = not_established` does **not** refuse the build, appears
  in the status block and in provenance as itself, and no code path turns it into
  `true`. `contradicted` refuses.
- A search returning zero results, two results, or one result whose
  `matching_etablissements` lacks the exact SIRET is a refusal in every case.
- The required sentence appears verbatim in a qualifying packet, with the
  evidence retrieval date, and is absent from a refused one.
- Missing provenance, missing or adverse review, conflicting commune/category,
  a head-office-only match, or unresolved historical identity refuses the build
  without creating a packet. Person-match confirmation cannot bypass this gate.
- Changing enrichment while retaining `decp_row_id`, or changing the evidence
  snapshot, cannot reuse an old verification. A later adverse review invalidates
  dependent packets; unrelated packets remain valid.
- F1's packet-eligible counts agree with export eligibility. Byte-identical
  reruns, input-order independence, offline execution and decoy-record exclusion
  cover the added provenance and review evidence as well as the existing data.

Run focused tests first, then the required checks in `CONTRIBUTING.md` and
`crony-eu/CLAUDE.md`. Report implemented gates, passing tests and unresolved
source/temporal limitations separately; passing tests is not disclosure approval.
The older renderer bullet below is superseded by
[ADR-0006](adr/0006-standard-library-only.md): standard-library HTML and inline
SVG, no jinja2, vis-network or JavaScript.

### Deliverables

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
