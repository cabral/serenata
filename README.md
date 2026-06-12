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

**Week 1 — scaffolding** (June 2026): package skeleton, tests, CI, and design
records exist; the pipeline does not fetch, parse, or classify anything yet.
The milestone plan:

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
serenata_europa/
  fetch/        # TED API + bulk download, raw XML archiving (the only networked stage)
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

## Running the tests

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/cabral/serenata
cd serenata
uv sync
uv run pytest
```

Tests run offline against fixtures in `tests/fixtures/`; nothing in the test
suite touches the network.

## Contributing

Early days. The constraints that govern all code in this repository are in
[`CLAUDE.md`](CLAUDE.md) (they apply to humans too), and design decisions are
recorded in [`docs/adr/`](docs/adr/). Issues and questions welcome.

## License

[AGPL-3.0](LICENSE). The original Serenata used MIT; this project uses AGPL so
that hosted forks of the pipeline stay open, which matters for a project whose
entire value is that you can check its work.
