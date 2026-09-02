# Open work

Known gaps and the work planned against them, in enough detail to be picked up
without a conversation first. The README's milestone table says where the
project is going; this says what is actually open right now and what each item
requires.

Every item states the constraints that bind it. That is not ceremony: the rules
in [`CLAUDE.md`](../CLAUDE.md) are strict enough that a well-meant change can
violate one without its author noticing — an incompatible dependency licence, a
field that quietly carries a person's name, a classifier without a measured
false-positive profile. Those are cheaper to prevent than to review.

Most of them no longer depend on you noticing.
[`tests/test_constraints.py`](../tests/test_constraints.py) enforces constraints
1, 3, 4, 5 and 6 in CI, so a change that violates one fails with a message
naming it. **Constraint 2 — no personal data — is the one with legal weight.**
It is now mechanized for eForms: [`personal-data.md`](personal-data.md) is the
field list, `serenata/parse/personal_data.py` is that document in executable
form, and a test fails if the two disagree. The legacy TED half of the list does
not exist yet, which is why item 3 stays open.

If you pick something up, say so on the tracker so two people don't start the
same thing. Questions are welcome before code, especially on the blocking items.

| # | Item | Status |
|---|------|--------|
| 1 | [Write the data model contract](#1-write-the-data-model-contract) | **done** |
| 2 | [Survey which eForms fields notices actually populate](#2-survey-which-eforms-fields-notices-actually-populate) | **done** |
| 3 | [Document and drop the fields that can name a natural person](#3-document-and-drop-the-fields-that-can-name-a-natural-person) | **eForms done**, legacy open |
| 4 | [Build the parse stage](#4-build-the-parse-stage) | **eForms done**, legacy refused |
| 5 | [Add an opt-in test for TED's live contract](#5-add-an-opt-in-test-for-teds-live-contract) | open |
| 6 | [Handle corrected and withdrawn notices](#6-handle-corrected-and-withdrawn-notices) | needs an ADR, later |
| 7 | [Commit a small sample package for end-to-end tests](#7-commit-a-small-sample-package-for-end-to-end-tests) | start here |
| 8 | [Write CONTRIBUTING.md](#8-write-contributingmd) | start here |
| 9 | [Add the rerun-identity determinism test](#9-add-the-rerun-identity-determinism-test) | blocked on normalise |
| 10 | [Settle the licence for published datasets](#10-settle-the-licence-for-published-datasets) | **done** |
| 11 | [Decide the publication rule for unknown natural-person status](#11-decide-the-publication-rule-for-unknown-natural-person-status) | needs a decision, before findings |

**Order matters.** 2 fed 1; 1, 3 and 4 are all done for eForms, so the stage
boundary has moved to normalise. 6 is filed so it is not discovered late, not
because it should be done now. 9 cannot start until there is pipeline output to
compare — which is now one stage away rather than two.

---

## 1. Write the data model contract

**Done.** [`docs/data-model.md`](data-model.md) is the contract: nine tables —
`notice`, `procedure`, `lot`, `organisation`, `organisation_role`,
`tendering_party`, `lot_tender`, `lot_result`, `settled_contract`,
`field_privacy` — with a measured source path and presence figure for every
column. `tests/test_data_model.py` checks all 85 cited paths against the 751 the
survey measured, and separately that no column maps to a path
`personal_data.is_dropped()` rejects.

Two decisions it rests on got their own records:

- [ADR-0005](adr/0005-element-paths-as-provenance.md) — provenance is the
  **element path**, not the eForms BT code, which answers the question #2 left
  open. BT codes need the eForms SDK, and the mapping is an annotation that can
  be added later without touching a column, a key or a classifier.
- [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md) — every nullable
  column carries a `<column>_status` of `present`, `empty`, `absent`,
  `withheld` or `not_applicable`.

The second is the one with teeth. `efac:ReceivedSubmissionsStatistics` — the bid
count, and the input to the single-bid classifier this project will almost
certainly write first — is a field publishers can withhold through
`efac:FieldsPrivacy`, and it is observed withheld in this package. Collapsing
"withheld" into the same NULL as "not provided" would let a classifier read a
lawful deferral as a low bid count and flag a buyer for the project's own data
handling.

Two things it deliberately does not settle: cross-notice organisation identity
(`company_id` is an attribute, not a key — that is milestone 3), and the legacy
TED mappings, for the same reason as [#3](#3-document-and-drop-the-fields-that-can-name-a-natural-person)
— no legacy notice has been measured, and spec-read mappings are not published
as though they were.

The original statement of the problem follows.

`docs/data-model.md` was a table of contents, not a model. It is the
contract the normalise stage is written against, so nothing downstream of parse
can start until it exists. This is the gate for the rest of milestone 1.

**What to write.** One relational model spanning eForms and legacy TED notices:

- **Entities and relations** — contracting authorities, companies,
  procedures/notices, lots, awards.
- **Per-field provenance** — which source field (eForms BT code or legacy TED
  element) each value came from, and from which notice.
- **Absence semantics** — "not provided" and "not applicable" are different
  facts and are recorded as such. They must not collapse into one NULL.
- **Excluded by design** — fields dropped because they could carry a natural
  person's name. These get no column, and the document says which and why.
- **Keys** — how every derived record traces back to its source notice ID.

**Constraints.** Constraint 2 (no personal data) decides what may appear here at
all: a field that could name a natural person gets no column, not even a
nullable one. Constraint 5: the model serves structured-field classifiers, not
free text. [ADR-0001](adr/0001-parquet-duckdb-storage.md) fixes storage as
Parquet queried with DuckDB.

**Start from the measurements.** [`docs/field-usage.md`](field-usage.md) already
answers which paths carry data and which never do, across 3,190 real notices, so
the model can be argued from evidence rather than from the specification's
optionality. Note what it does not answer: it reports element paths rather than
eForms BT codes, and the model needs to decide which of the two it is written
against.

**Done when** the document describes every entity, its fields, their source
mappings for both eForms and legacy TED, and the absence encoding; and a reader
can tell for any field which source element produced it.

---

## 2. Survey which eForms fields notices actually populate

**Done.** [`docs/field-usage.md`](field-usage.md) reports 3,190 eForms notices
from OJ S 157/2026: **456 element paths carry a value, 296 appear only as
containers or blank elements.** `serenata/survey/` produces it, and rerunning it
against the same archive reproduces the file byte for byte.

One finding shapes [#1](#1-write-the-data-model-contract): the report gives
element paths, not eForms BT codes. Mapping a path to its BT code needs the
eForms SDK, which the offline survey does not carry, so the data model has to
either carry that mapping itself or be written against paths and say so.

Surveying more days is worthwhile before the model is finalised — one publication
day is one day's mix of notice types and member states. Rerun with more packages:

```
python -m serenata.survey data/raw/ted/daily/2026/*.tar.gz -o docs/field-usage.md
```

The original statement of the problem follows.

eForms permits far more fields than any notice uses, and usage varies by member
state — optional fields are often empty. Designing the model from the spec would
produce columns that are empty in practice and miss the ones that matter.
Measure it, then write [#1](#1-write-the-data-model-contract) against the
measurements.

**What to do.** Take one or more archived daily packages (`serenata fetch`
produces them; one day is ~3,190 notices) and report, per eForms field: how
often it is present and non-empty, broken down by publishing member state and
notice subtype, with the count of notices surveyed and the period covered.
Output a document under `docs/` that #1 can cite. A throwaway script is fine,
but say where it lives and how to re-run it.

**Constraints.** Constraint 4 (determinism): the survey reads archived packages
from disk, does not fetch, and gives the same numbers on the same archive.
Constraint 2: it counts field *presence* — it does not reproduce values from
person-carrying fields, not even as examples. Structured fields only.

**Done when** the report covers a stated, reproducible set of notices,
distinguishes "field absent" from "field present but empty", and is enough for
someone writing #1 to decide which fields are worth modelling.

**Good entry point:** needs no pipeline code, only the archive and the eForms
field list. Start from one package rather than a year.

---

## 3. Document and drop the fields that can name a natural person

**Done for eForms; the legacy TED half is still open.**
[`docs/personal-data.md`](personal-data.md) is the list, measured against the
same 3,190 notices `field-usage.md` reports on rather than read off the
specification. `serenata/parse/personal_data.py` is that document in executable
form and `tests/test_personal_data.py` fails if the two disagree.

What it settles: four subtrees are dropped outright wherever they appear
(`cac:Contact`, `efac:UltimateBeneficialOwner`, `cac:TechnicalCommitteePerson`,
and the free-text `efac:FieldsPrivacy/efbc:ReasonDescription`), matched on path
segments so a field TED adds inside one of them is dropped on arrival. And the
sole-trader case is handled: where `efbc:NaturalPersonIndicator` is true the
organisation's identifying values are suppressed — including its registration
identifier, which in Sweden is the owner's personnummer — while its opaque
intra-notice key is kept, so the record is anonymised rather than deleted.

Three findings from the measurement are worth carrying forward:

- A contact e-mail and telephone number are present in **99.9%** of notices.
  This was never a rare edge case to handle later.
- A beneficial owner's identifier appears in **8.1%** of notices while their
  surname appears in 0.8%, so a list built by looking for name-shaped elements
  would have missed most of that subtree.
- `efbc:NaturalPersonIndicator` is **absent from about 90% of notices**, and
  absent is "not provided", not "false". What to do about that gap is
  [#11](#11-decide-the-publication-rule-for-unknown-natural-person-status).

**Still open: legacy TED.** OJ S 157/2026 contains zero legacy-schema notices,
so there is no measured basis for that half and this project does not publish
spec-read lists as though they were measured. Until it exists, parse must refuse
a legacy notice rather than guess. Fetching a pre-2024 package is one command
against an already-built stage; `personal-data.md` says which.

The original statement of the problem follows.

Constraint 2 says person-carrying fields are dropped **at ingestion**, not
stored and filtered later. The parse stage is where that happens, so it needs a
written list of which fields those are before it is built — otherwise the rule
is enforced by whoever happens to be reading the XML that day.

This is a legal constraint (GDPR, Swedish defamation law), not a style
preference. [ADR-0002](adr/0002-fetch-daily-bulk-packages.md) states the
boundary the project works to: raw archives are a local cache of already-public
official documents, and nothing derived from them carries a person's name.

**What to do.** Produce a documented list, for both eForms and legacy TED, of
every source field that can contain a natural person's name or personal contact
details — contact points, sole traders, signatories, anything else the schemas
allow. For each: the field identifier, why it is person-carrying, and whether it
is dropped outright or has a non-personal part worth keeping (an organisation
name sharing an element with a contact name, say).

**Constraints.** The list is the authority the parse stage implements against;
if a field is not on it, that was a decision, so the document says why. Err
toward dropping — a dropped field that turns out to be safe costs a later
change, a retained one that carries a name is a legal problem. Fields on this
list get no column in #1.

**Done when** the list exists under `docs/` covering both formats, every entry
says what it is and why it is excluded, and #1 and #4 can both be written
against it without further judgement calls about individual fields.

---

## 4. Build the parse stage

**Done for eForms; legacy notices are refused rather than guessed at.**
`serenata/parse/` reads archived notices into typed intermediate records:
`notice.py` streams one notice, `packages.py` walks a package, `records.py`
defines the records, and `personal_data.py` is the drop list from
[#3](#3-document-and-drop-the-fields-that-can-name-a-natural-person).

Run against the real OJ S 157/2026 archive, all **3,190 notices parse** into
46,223 records and 865,288 fields, with no failures and 82 MB peak memory.

Three things that measurement settled:

- **Constraint 2 holds on real data.** 32,135 leaf elements — **3.6% of every
  leaf in the package** — are dropped before they reach a record, and a check
  over all 46,223 records finds no field whose path the drop list rejects. The
  7 organisations flagged as natural persons lose 48 identifying values between
  them and keep their opaque keys, so those records are anonymised, not deleted.
- **`empty` is real but not observed.** There are **zero** blank leaf elements
  among all 897,471 — counted without the drop filter, so the dropped 32,135 are
  in that denominator — and the 295 paths `field-usage.md` reports as
  "containers or blank elements" are all containers. [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md)
  was corrected: the status is kept because conflating blank with absent would
  be silently wrong, not because this package shows it happening.
- **Format dispatch is on the root element, not the filename.** A name is a
  claim; the root namespace is the document saying what it is.

A review then found three ways the records lost information, all fixed and all
measured on the same package:

- **Repetition is ordinary, not exotic.** 97.3% of lot records and 73.3% of lot
  results repeat at least one path. Returning the first of several would have
  handed a classifier one arbitrary value: 2,866 lot results carry repeated
  `efac:ReceivedSubmissionsStatistics` code/value pairs, which is the single-bid
  classifier's own input. Fields now carry the sibling index of every element on
  their path, so blocks pair; `value()` raises rather than guessing, and
  `values()` returns them all. Every one of the package's statistics blocks
  pairs, with none left over.
- **Attributes were discarded**, so `currencyID` went with them — six currencies
  appear on `PayableAmount` in one publication day, and `data-model.md` promises
  amounts "as published, with their currency". Kept now, and reviewed against
  constraint 2: the seven attribute names form closed vocabularies (`listName`
  is the widest at 114 distinct values across 285,176 occurrences, all eForms
  code-list identifiers), and none carries anything email- or phone-shaped.
- **An element with both text and children lost its text.** Zero occurrences in
  the package, but a silent loss is the wrong failure. Recorded now, with the
  one exception documented: an element that becomes a record has no field of its
  own to hold stray text.

Parse peaks at **89 MB** against the survey's 4.3 MB on the same package, because
it keeps every value it extracts while the survey keeps counts. ADR-0003's memory
consequence was clarified to say the bound it promises is on the XML tree, which
is what that decision governs, not on what a stage chooses to keep.

The last three findings closed the package layer:

- **Raising from inside a generator ended the run.** `parse_package` promised
  callers they could catch a bad notice and continue, which a generator cannot
  do — it closes, and every notice after the first failure was lost while
  iteration appeared to end normally. It now yields `ParsedNotice | Unparsed`,
  so a caller cannot mistake a truncated run for a complete one.
- **The tarball walk was duplicated** and had already drifted on which members
  count as notices. `serenata/packages.py` owns it now.
- **The streaming walk was duplicated.** `serenata.eforms.stream_elements` owns
  the parser, the prolog guard, the element release and the no-root check;
  each reader keeps only what it accumulates. Measured cost: the survey +2% and
  unchanged memory, parse +12% (48.6s to 54.4s per package). Recorded because it
  is a real trade — about forty lines of duplication, including the release
  pattern and the DTD refusal's plumbing, against 12% on the only stage that
  touches every byte. If that ratio ever stops being worth it, the measurement
  is here to argue from.

Still open from the same review: `child_counts` allocates a dict per element,
about 1.7 million per package, which is the likeliest remaining win if parse's
runtime ever matters.

The eForms vocabulary moved to `serenata/eforms.py`, shared with the survey. Not
tidying: `personal_data.py`'s drop list is written in those prefixes, and a
second copy that drifted would silently stop rejecting the paths it exists to
reject. The survey's report regenerates byte-identically after the move.

**Legacy notices raise** with a message naming the docs and open-work #3. A
package of them fails loudly rather than yielding nothing, because a stage that
quietly produced zero notices would look exactly like an empty package.

Still open: wiring `serenata parse` into the CLI, which is its own commit as
`fetch` was.

The original statement of the problem follows.

`serenata/parse/` was a docstring. It turns archived notices into typed
intermediate records, running offline against the packages `fetch` produces.
**Both of its blockers are now cleared for eForms.** The drop list it must
implement is written and executable —
[`personal-data.md`](personal-data.md) and `serenata/parse/personal_data.py` —
and [`data-model.md`](data-model.md) is the shape it produces records in, with a
measured source path for every column. Legacy notices are still blocked on
[#3](#3-document-and-drop-the-fields-that-can-name-a-natural-person) and must be
refused rather than parsed. **This is the next piece of work.**

**What to do.**

- Read notices out of the archived `.tar.gz` packages without extracting them to
  disk first, where practical.
- Dispatch on notice format. Packages mix both: eForms filenames carry eight
  digits and the year (`00566631_2026.xml`), legacy TED six. Confirm against the
  XML root element rather than trusting the filename alone.
- Drop person-carrying fields here by calling
  `personal_data.is_dropped()` **before** a value is read — they must not reach
  an intermediate record, not even to be filtered out downstream. Apply
  `suppressed_for_natural_person()` to an organisation flagged with
  `efbc:NaturalPersonIndicator`. Note that this one needs an `efac:Organization`
  subtree buffered before it can be decided, since the indicator can be read
  after the name it governs; `personal-data.md` explains why that does not
  conflict with ADR-0003's streaming requirement.
- Carry the source notice ID on every record.

**XML handling is decided — follow it.**
[ADR-0003](adr/0003-xml-parsing-without-defusedxml.md) settles the question that
was open here: parse with the standard library, refuse any notice carrying a
document type declaration, and stream rather than build a whole tree. No
`defusedxml`. `serenata/survey/paths.py` already implements exactly this and is
the reference to copy, not a thing to improve on.

Two measurements from that work bind the parse design:

- **One real notice is 40 MB**, 1,569 times the 25 KB median and a fifth of its
  whole day's uncompressed volume. A whole-tree parse cost 161 MB for that one
  file; streaming costs 0.5 MB, and a full 3,190-notice package surveys in
  4.4 MB peak. Parse handles far more data than the survey does, so
  `fromstring(handle.read())` is not an option — it will meet this notice.
- **No real notice uses a DTD**: zero `<!DOCTYPE` and zero `<!ENTITY` across all
  3,190 notices in OJ S 157/2026. Refusing them costs nothing and closes entity
  amplification, the one attack the standard library's parser is open to.

**Constraints.** Constraint 4: parse is offline and deterministic — no network,
no wall-clock in outputs, no unseeded randomness. Constraint 5: structured
fields only, no NLP or LLM calls. The raw package is read-only input; parse
never writes back into the archive.

**Done when** both eForms and legacy TED notices from a real archived package
parse into typed records; tests run offline against `tests/fixtures/` per that
directory's rules; and a malformed notice fails loudly with its notice ID rather
than being silently skipped.

---

## 5. Add an opt-in test for TED's live contract

The fetch tests run against a stand-in TED whose responses were shaped from
observed behaviour. They catch regressions in our logic but not a change on
TED's side: if `ojs-number` were renamed, or the `limit` cap dropped below 250,
the suite would stay green and a backfill would fail. We want a tripwire, kept
out of the default suite so the offline promise holds.

**What the current code assumes**, verified against the live service on
2026-09-01 and recorded in [ADR-0002](adr/0002-fetch-daily-bulk-packages.md):

- `POST https://api.ted.europa.eu/v3/notices/search`, no authentication.
- `fields` must be non-empty — an empty list is rejected with HTTP 400.
- `limit` is capped at 250; above that returns `SEARCH_EXCEEDS_MAX_LIMIT`.
- A notice carries `ojs-number` in the form `"157/2026"`.
- `GET https://ted.europa.eu/packages/daily/{yyyynnnnn}` returns a gzipped tar
  whose members sit under one `YYYYMMDD_NNN` directory.

**What to do.** Assert each of those against the real service, marked so they
are excluded by default (a pytest marker, run explicitly or on a schedule). They
must not run in the normal `pytest` invocation — `tests/conftest.py` refuses
sockets precisely so the default suite cannot reach the network. Keep them cheap
and polite: a handful of `limit: 1` requests, not a crawl.

**Done when** `uv run pytest` still runs fully offline with the socket guard
intact; the contract tests can be run on demand and fail loudly naming which
assumption broke; and if they run in CI, they run on a schedule rather than on
every push.

---

## 6. Handle corrected and withdrawn notices

The fetch stage archives whole publication days as immutable snapshots. TED
notices can later be corrected or withdrawn, and a snapshot cannot represent
that: the archive keeps saying what was published that day, which is correct as
history but not as current state.

This matters more than it sounds. A flag raised against a notice that was later
corrected or withdrawn is a flag against something that no longer stands, and
the project's whole promise is that a reader can check a flag against its
source. ADR-0002 flagged it as the main limitation of whole-day snapshots.

**What to decide** — a design decision, so an ADR rather than a patch:

- How a correction is detected. TED publishes corrigenda as notices in their own
  right; the relation to the original has to be read from the data.
- Whether corrections are folded into the normalised model, tracked as a version
  chain, or both.
- What a flag on a superseded notice should do — suppressed, marked, or
  withdrawn — and how a published finding is retracted.

**Constraints.** Raw archives stay immutable: handling corrections means new
records, never rewriting an archived package. Constraint 4 still binds — the
same archive and code produce the same flags, so "current state" must be derived
from archived inputs, not from a live lookup at classify time.

**Done when** an ADR records the decision and its consequences, and the data
model (#1) can represent whichever answer it reaches.

**Do not start here.** It depends on the normalised model existing, and the
answer partly depends on what corrections look like once notices are parsed.
Filed now so it is not discovered late.

---

## 7. Commit a small sample package for end-to-end tests

`data/sample/` is empty and says so: "Empty until the pipeline can read it." Now
that `fetch` produces packages, it can. A committed sample lets tests exercise a
real archive end to end without fetching. A full daily package is ~20 MB
compressed and 3,190 notices — far too large to commit, so the sample is a
handful of notices in the same shape.

**What to do.** Build a small `.tar.gz` in the layout a real package uses:
notices under one `YYYYMMDD_NNN` directory, eForms filenames with eight digits
and the year. Include both an eForms and a legacy TED notice so #4 can be tested
against both. Commit it under `data/sample/` and document what it contains and
where it came from.

**Constraints.** `data/sample/README.md` and `tests/fixtures/README.md` set the
rules and they are not negotiable: obviously synthetic notices (impossible IDs,
names like "EXAMPLE BODY"), or real public notices reproduced accurately and
named after their notice ID. Never plausible-looking fabrications — nothing that
could be mistaken for a real finding. Never anything containing a natural
person's name; if reproducing a real notice, check it against #3 first.

**Done when** the sample is committed and small enough to live in git
comfortably, its README says what each notice is and which case it covers, and a
test reads it through the archive layer without special-casing.

---

## 8. Write CONTRIBUTING.md

The README points contributors at `CLAUDE.md` for the constraints and
`docs/adr/` for decisions, which is accurate but assumes a reader knows to look
and knows what an ADR is for. There is no single page telling someone how to
land a change here.

**What to write.**

- How to get set up and run what CI runs: `uv sync`, `uv run pytest`,
  `uv run ruff check .`, `uv run ruff format --check .`.
- The hard constraints restated plainly, with the reasoning: AGPL-compatible
  dependencies only, no personal data, flags are anomalies and never
  accusations, determinism, structured fields only, and no classifier without a
  documented hypothesis and measured base rates.
- When to open an ADR rather than putting a decision in code.
- Commit and PR expectations: small, one concern each, imperative messages.
- What tests are expected to look like, including that the suite runs offline
  and `tests/conftest.py` enforces it.

**Constraints.** `CLAUDE.md` is the source of truth. CONTRIBUTING.md restates it
for a newcomer and links to it; where the two disagree, `CLAUDE.md` wins and
CONTRIBUTING.md is what needs fixing.

**Done when** someone who has never seen the project can go from clone to a PR
that passes CI and does not violate a constraint, without reading `CLAUDE.md`
first.

---

## 9. Add the rerun-identity determinism test

Constraint 4 says the same input data and the same code produce the same bytes.
`tests/test_constraints.py` enforces the static half of that — no clock, no
unseeded randomness in the stages downstream of fetch — but a static check
cannot prove the output is actually stable. Only running the pipeline twice can.

The `coding` skill already describes this test as though it exists: *"The test
for this is not a code review, it's a rerun: execute the pipeline twice on the
same fixtures and compare output checksums. That test lives in CI and must pass
on every classifier PR."* It does not exist, because nothing downstream of fetch
produces output yet.

**What to do.** Once `normalise` writes Parquet, run the pipeline twice over the
same fixture archive into two directories and assert the outputs are
byte-identical, comparing checksums rather than parsed contents. Parquet is only
byte-stable if the writer makes it so — [ADR-0001](adr/0001-parquet-duckdb-storage.md)
puts that responsibility on the normalise stage: fixed row ordering, fixed
schema and writer settings, pinned writer version.

**Constraints.** The test runs offline against committed fixtures
([#7](#7-commit-a-small-sample-package-for-end-to-end-tests) provides them). It
must not depend on a clock, so nothing in the compared output may carry a
timestamp that is not itself derived from the source data — the fetch manifest's
`fetched_at` is provenance and is not pipeline output.

**Done when** the pipeline runs twice in CI on every push and the outputs match
byte for byte, and the claim in the `coding` skill is true rather than aspirational.

**Blocked** until [#4](#4-build-the-parse-stage) and the normalise stage exist.

---

## 10. Settle the licence for published datasets

**Done.** Published datasets and findings are **CC BY 4.0**, decided in
[ADR-0004](adr/0004-dataset-licence.md) and stated in
[`data-reuse.md`](data-reuse.md). `serenata.survey` generates the grant into
every report beside the TED attribution line, and `tests/test_survey.py` asserts
it, so a regenerated dataset cannot lose the terms it is published under.

Version 4.0 specifically, because it licenses the EU sui generis database right
alongside copyright — that right, not authorship, is what attaches to a table of
measurements — and because it is the licence TED applies to its own editorial
content. The code stays [AGPL-3.0](../LICENSE); neither grant implies the other.

The original statement of the problem follows.

`docs/field-usage.md` is the first dataset this project has published, and it
carries no licence of its own. The code is [AGPL-3.0](../LICENSE); a data licence
is a separate decision and is not implied by it.

The intended default is **CC BY 4.0** — free reuse including commercially,
provided credit is given, the licence is linked, and changes are indicated.
Version 4.0 also covers the EU's sui generis database rights, which is the right
that actually attaches to a table of measurements. It is the same licence TED
applies to its own editorial content, so a derived dataset's terms sit legibly
next to its source.

**What to do.** Confirm the choice once, then record it in an ADR so it stops
being an open question, and state it in [`data-reuse.md`](data-reuse.md) and on
each published dataset. This is a decision to take deliberately rather than to
infer: it governs everything the project publishes afterwards, and changing a
data licence after third parties have relied on it is far more awkward than
choosing it now.

**Done when** an ADR records the licence and its reasoning, `data-reuse.md`
states it rather than marking it open, and published datasets carry it.

**Not blocking the pipeline**, but it does gate the first public data release.

---

## 11. Decide the publication rule for unknown natural-person status

`efbc:NaturalPersonIndicator` tells us an organisation is a sole trader, and
[#3](#3-document-and-drop-the-fields-that-can-name-a-natural-person) suppresses
that organisation's identifying values when it is true. The problem is what the
indicator does *not* say: it is **absent from about 90% of notices**, and under
this project's own absence semantics absent is "not provided", never "false".

So for most organisations in the dataset, whether the record describes a company
or a private individual trading under their own name is unknown, and no amount
of reading the XML resolves it. Parse handles what it can; this is what is left.

**Why it is not an ingestion question.** Dropping every organisation name would
end the project — naming buyers and suppliers is the dataset. The names are kept
because an organisation in an official procurement notice is institutional by
default. The residual risk is not in storing them, it is in *publishing a flag*
about one that turns out to be a person.

**What to decide.**

- Whether a flag may be published about an entity whose natural-person status is
  unknown, or only about one positively corroborated as an organisation.
- What corroboration counts. `cac:PartyLegalEntity/cbc:CompanyID` is present in
  99.9% of notices, but a registration number does not by itself prove the
  registrant is not a natural person — in Sweden a sole trader's is their
  personnummer. Milestone 3's entity resolution against national company
  registers is the obvious source of a better answer, and is a long way off.
- Whether the answer differs for a buyer and for a supplier. Contracting
  authorities are institutions by definition; suppliers are where sole traders
  actually appear.

**Constraints.** The legal guardrails route anything identifying a natural
person away from project channels entirely, so the conservative answer is
available and cheap: publish only where the entity is corroborated, and count
the rest without naming them. Constraint 3 also binds — whatever is published is
an anomaly, never an accusation.

**Done when** an ADR records the rule and the verification interface can state,
for any published flag, why the entity it names is an organisation.

**Before the first finding, not before parse.** Nothing is published yet, so
this blocks milestone 2, not milestone 1.
