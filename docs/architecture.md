# Architecture

How the pipeline is put together, and — the part that matters more — **why the
boundaries are where they are.** Each limits a class of failures; none certifies
privacy or legal compliance. The reasoning is in the ADRs.

New to the project? Read this, then [`glossary.md`](glossary.md) for the
vocabulary, then [`data-model.md`](data-model.md) for what the dataset actually
contains.

## The shape

```
TED
 └─ fetch (networked) ──▶ raw archive (byte-preserved packages)
   └─ parse ──▶ typed records (structural suppression, not anonymisation)
     └─ normalise ──▶ Parquet (twelve-table model)
       └─ classify ──▶ flags (v2 built; measurement pending)
         └─ publish: NOT BUILT; release blocked
```

Five stages are planned. Four have runnable, separately tested modules;
publication is not built.

| Stage | Reads | Writes | Networked | Built |
|---|---|---|---|---|
| `fetch` | TED's API and daily packages | `data/raw/…tar.gz` + manifest | **yes, only here** | ✅ |
| `parse` | an archived package | typed records, in memory | no | ✅ eForms only |
| `normalise` | records | Parquet, partitioned by year | no | ✅ |
| `classify` | Parquet | flag rows, partitioned by year | no | ✅ one rule |
| `publish` | flags | API, verification interface | — | ❌ |

`survey` sits beside them rather than in the chain: it measures archived
packages and writes the generated reports under `docs/`. It is analysis, not a
stage, and nothing downstream depends on it.

## The four boundaries, and what each one guarantees

### 1. TED → the raw archive: *this is the only place the network exists*

Whole publication days are downloaded and stored **byte for byte, immutable,
addressed by checksum**. Nothing later re-fetches, and no derived record is ever
produced from anything but an archived file.

That is what makes a published flag checkable years later: the exact bytes it
came from are still on disk. It is also what lets every other stage be
deterministic, because a stage that cannot reach the network cannot vary with
what the network says today.

`tests/test_constraints.py` enforces it — no module outside `fetch` may import
an HTTP or socket library — and `tests/conftest.py` refuses a socket for the
whole suite. The one deliberate exception is `tests/test_ted_contract.py`, which
runs weekly against the live service to catch TED changing under us.

> [ADR-0002](adr/0002-fetch-daily-bulk-packages.md) — daily bulk packages ·
> [ADR-0010](adr/0010-raw-archive-retention.md) — proposed basis and retention;
> current private holdings still require counsel review

### 2. The archive → records: *this is where structural suppression runs*

Parse reads notices out of the tarball without extracting them, streaming
element by element, and **drops the documented paths before they reach a
record**. This limits what is retained; it does not establish that every
retained value is free of personal data.

Measured on one publication day: **32,135 leaf elements, 3.6% of every leaf**,
removed. [`dropped-fields.md`](dropped-fields.md) counts them and checks each
against the model's columns; none is one.

The five-day [dataset-shape report](dataset-shape.md) documents **427
email/address-shaped values in retained columns**, including **139
personal-address-shaped values** and **359 in descriptions**. These are pattern
counts, not a complete personal-data inventory. Explicit-natural-person
Company/TouchPoint `WebsiteURI` suppression is now implemented, but existing
datasets have not been rebuilt. Other leakage remains unresolved.

Opaque notice-scoped organisation keys still join to the source publication;
they do not make a person anonymous. Most notices omit the natural-person
indicator. Neither missing names nor a missing indicator proves anonymity
([GDPR Art. 4(1) and Recital 26](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng)).
Downstream review is required, and **dataset and flag publication remain
blocked**. Collection, storage and internal use are processing too, not an
exemption while the project is private. The current implementation does not
fully meet the no-personal-data constraint.

> [ADR-0003](adr/0003-xml-parsing-without-defusedxml.md) — streaming, no DTDs ·
> [`personal-data.md`](personal-data.md) — the list, executable as
> `serenata/parse/personal_data.py`

### 3. Records → the model: *this is where meaning is assigned*

Parse produces values keyed by their **element path** and nothing more. It does
not know what a lot is. Normalise maps path to column against
[`data-model.md`](data-model.md), which is executable as
`serenata/normalise/model.py` with a test that fails when the two disagree.

Three rules make this boundary trustworthy rather than convenient:

- **Absence is recorded, never collapsed.** Every value column carries a
  `<column>_status` — `present`, `empty`, `absent`, `withheld`,
  `not_applicable`. "Not provided" and "withheld by the publisher" are different
  facts, and a classifier that confuses them reads a lawful deferral as a low
  number.
- **A repeated value is never resolved by picking one.** It becomes a set
  column, a table of its own, or the notice's own language with a companion
  saying which. A scalar column that meets several values raises rather than
  choosing.
- **Values are stored as published, as strings.** A withheld amount is `-1` in
  the source and `-1` in the dataset; the status carries the interpretation.
  Casting is the query's decision, taken explicitly.

> [ADR-0005](adr/0005-element-paths-as-provenance.md) · [ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md) · [ADR-0007](adr/0007-repeated-values-are-carried-not-resolved.md) · [ADR-0008](adr/0008-eforms-sdk-privacy-mapping.md)

### 4. The model → Parquet: *this is where determinism is made real*

Byte-stability is not a property Parquet has; it is one this stage produces.
Rows are sorted by their table's key before every write, the schema comes from
the model rather than from the values present, writer options are pinned in one
constant, and the partition is the notice's **own publication year** — never the
run clock.

The proof is a rerun, not a review: the pipeline runs twice over the same
package in CI and the checksums are compared.

> [ADR-0001](adr/0001-parquet-duckdb-storage.md) — Parquet + DuckDB, and why no
> database server yet

## The classifier and the release boundary

The [single-bid classifier](hypotheses/single_bid_in_segment.md) is implemented
at **version 2**. It rejects duplicate structural/join keys and ambiguous tender
counts, checks statistic-code presence, and requires every buyer reference to
resolve to a present, agreed country. The writer stages output before replacing
files and removes stale files for that rule on success; replacement across years
is not transactional.

Version 4 also excludes notices another notice in the corpus corrects and
notices announcing their own cancellation (ADR-0013), and a flag carries the
`correction_cutoff` that check saw. Measured at version 4: **96 flags from
8,132 lot outcomes**. No empirical false-positive
rate is known, and no flag has completed verification.

The eForms ingestion/normalisation prototype is built, not milestone 1 complete.
Legacy parsing, privacy remediation, and deterministic correction/withdrawal
handling with tests remain open. An ADR alone cannot close correction handling.
Publication additionally needs verification and legal review, including current
private holdings; [open work](open-work.md) records these gates.

## What holds it together

**Six hard constraints** in [`CLAUDE.md`](../CLAUDE.md): AGPL-compatible dependencies only,
no personal data, flags are anomalies and never accusations, determinism,
structured fields only, and no classifier without a measured hypothesis.
Automated checks cover specified patterns, fixtures and metadata, not every
possible violation. Passing tests is not a privacy, legal or empirical-validity
certification; the current rule's measurement remains pending.

**Document/code consistency checks.** Tests compare the documented path rules
and model columns with their implementations. They do not validate every prose
claim or detect every possible privacy leak:

| Document | Code | Guarded by |
|---|---|---|
| [`personal-data.md`](personal-data.md) | `serenata/parse/personal_data.py` | `tests/test_personal_data.py` |
| [`data-model.md`](data-model.md) | `serenata/normalise/model.py` | `tests/test_normalise_model.py` |

**Claims that regenerate.** [`field-usage.md`](field-usage.md),
[`dataset-shape.md`](dataset-shape.md) and [`dropped-fields.md`](dropped-fields.md)
are produced from checksummed archives and reproduce byte for byte. A number in
those files is a measurement anyone can rerun, not a sentence someone wrote once.

**Decisions with expiry conditions.** Every ADR ends with what would make us
revisit it — the section that is useful two years later — and begins with an
`Enforced by:` line naming a check or stating that nothing mechanical enforces
the policy. `tests/test_adr.py` checks that references resolve; it does not
validate the legal conclusions or implementation claims in an ADR.

## What is deliberately not here

- **No database server.** Parquet on disk, queried with DuckDB. Postgres waits
  for the triggers in ADR-0001, which are concurrent users or a live API.
- **No free-text analysis anywhere in the pipeline.** Constraint 5. Titles and
  descriptions are carried for readers, never read by a classifier.
- **No cross-notice entity identity.** `company_ids` is an attribute, not a key.
  Resolving one organisation across notices is milestone 3 and needs national
  registers, so today every row is scoped to the publication it came from.
- **No legacy TED.** Pre-2024 notices are refused rather than guessed at,
  because the mapping for them has never been measured.

[`known-issues.md`](known-issues.md) is the full and honest list.
