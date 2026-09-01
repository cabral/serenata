# Serenata Europa

An open-source pipeline that reads the EU's public procurement notices and flags
statistical anomalies anyone can verify against the source.

The EU publishes around 700,000 procurement notices a year through
[TED](https://ted.europa.eu), since late 2024 in the machine-readable eForms
standard. Dashboards for analysts exist. A continuously running, open pipeline
that turns those notices into verifiable public flags does not. This project
builds one.

## Lineage

In 2016, three of us in Brazil built
[Operação Serenata de Amor](https://github.com/okfn-brasil/serenata-de-amor):
an open-source system, crowdfunded by 1,296 people, that read 3 million
parliamentary expense claims and flagged the ones that didn't add up. Volunteer
verification of its findings led to 629 formal complaints against sitting
congresspeople. The project is now stewarded by Open Knowledge Brasil.

Serenata Europa is a successor by one of its co-founders,
[Felipe Cabral](https://github.com/cabral), redesigned for EU data:
same method (a written, falsifiable hypothesis behind every classifier; human
verification before publication; everything traceable to the source record),
new territory.

## What a flag means

A flag is a statistical anomaly matched against a documented risk indicator,
nothing more. Most flags have innocent explanations. Every flag links to the
source notice so you can check it yourself, every classifier's hypothesis and
measured error rates are published in [`docs/hypotheses/`](docs/hypotheses/),
and flags concern institutions and companies, never private individuals.

## Status

**Milestone 1, fetch stage landed** (September 2026): `serenata fetch` archives
TED's daily notice packages, with provenance and checksums. Nothing parses or
classifies them yet — the archive is raw XML, and the normalised dataset does
not exist. The milestone plan:

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Ingestion and normalisation pipeline (TED/eForms to a documented open dataset) | in progress |
| 2 | Anomaly classifier suite, each a documented hypothesis with measured base rates | not started |
| 3 | Entity resolution against open national company registers | not started |
| 4 | Public API and versioned bulk data releases | not started |
| 5 | Verification interface (every flag, its hypothesis, its source notice) | not started |
| 6 | Documentation, packaging, contributor onboarding | not started |

## Layout

```
serenata/
  fetch/        # TED API + bulk download, raw XML archiving (the only networked stage)
    client.py   #   throttled, retrying HTTP access to TED's public endpoints
    ojs.py      #   calendar date -> Official Journal S issue
    archive.py  #   the raw archive and the manifests vouching for it
    packages.py #   fetch a date range into the archive
  parse/        # eForms and legacy-TED XML -> typed intermediate records
  normalise/    # intermediate records -> the documented model -> Parquet
  classify/     # hypothesis classifiers, one module each
  cli.py        # entry point: serenata fetch|normalise|classify
tests/
docs/
  adr/          # architecture decision records
  data-model.md
  hypotheses/   # one file per classifier: hypothesis, sources, base rates
data/           # gitignored workspace, except the committed sample/
```

## Fetching notices

TED publishes one package per publication day, addressed by its Official
Journal S issue number. `fetch` resolves the dates you ask for to those issues
and archives each package whole, with a manifest recording its source URL,
SHA-256 and size:

```
uv run serenata fetch --from 2026-08-17 --to 2026-08-21
uv run serenata fetch --from 2026-08-17 --dry-run   # resolve, download nothing
```

```
data/raw/ted/daily/2026/202600157.tar.gz
data/raw/ted/daily/2026/202600157.manifest.json
```

Days that published nothing — weekends, holidays — are reported as such rather
than guessed at from a calendar. Re-running is safe: a package already archived
and matching its checksum is skipped, and one whose bytes have changed stops
the run instead of being overwritten, because raw files are ground truth.

The stage requests one package per publication day rather than one file per
notice, spaces its requests, backs off when asked to, and identifies itself in
its User-Agent. [ADR-0002](docs/adr/0002-fetch-daily-bulk-packages.md) records
why, and the verified facts about TED's interfaces behind it.

## Running the tests

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/cabral/serenata
cd serenata
uv sync
uv run pytest
```

Tests run offline against fixtures in `tests/fixtures/`; nothing in the test
suite touches the network, and the suite refuses a socket if anything tries.

The constraints this project runs on are executable, not just documented.
[`tests/test_constraints.py`](tests/test_constraints.py) enforces them on every
run: fetch is the only stage that may import a network library, no stage
downstream of it may read a clock or an unseeded random source, no module may
import an NLP or LLM library, no user-facing string may call a flagged record
corrupt or fraudulent, every classifier must have a complete hypothesis file,
and every dependency's licence must be AGPL-3.0 compatible. Some of those gates
have nothing to check yet; they are written now so they bind the code that
arrives later rather than being argued about afterwards.

## Contributing

Early days. What is open, and what each piece requires, is in
[`docs/open-work.md`](docs/open-work.md) — a few items there are marked as good
places to start. The constraints that govern all code in this repository are in
[`CLAUDE.md`](CLAUDE.md) (they apply to humans too), and design decisions are
recorded in [`docs/adr/`](docs/adr/). Issues and questions welcome.

## Data source and attribution

© European Union, 1998–2026. Source: [TED](https://ted.europa.eu), the Supplement
to the Official Journal of the European Union. Notices published there may be
freely reused for commercial and non-commercial purposes, on condition that the
source is acknowledged, under Commission Decision
[2011/833/EU](https://eur-lex.europa.eu/eli/dec/2011/833/oj/eng).

[`docs/data-reuse.md`](docs/data-reuse.md) records the specific terms, what this
project does not do under them, and the still-open question of which licence
this project's own published datasets carry.

## License

[AGPL-3.0](LICENSE) for the code. The original Serenata used MIT; this project
uses AGPL so that hosted forks of the pipeline stay open, which matters for a
project whose entire value is that you can check its work. The licence for
published datasets is a separate decision and is not yet settled — see
[`docs/data-reuse.md`](docs/data-reuse.md).
