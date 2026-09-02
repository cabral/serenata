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
congresspeople. Those figures are the original project's own, from the years its
founders ran it; it is now stewarded by Open Knowledge Brasil.

Serenata Europa is a successor by one of its co-founders,
[Felipe Cabral](https://github.com/cabral), redesigned for EU data:
same method (a written, falsifiable hypothesis behind every classifier; human
verification before publication; everything traceable to the source record),
new territory.

**This is an independent project.** It is not affiliated with, endorsed by, or
run by Open Knowledge Brasil, and OKBr carries no responsibility for anything
published here. The lineage above is shared history, not a partnership.

## What a flag means

A flag is a statistical anomaly matched against a documented risk indicator,
nothing more. Most flags have innocent explanations. Every flag links to the
source notice so you can check it yourself, every classifier's hypothesis and
measured error rates are published in [`docs/hypotheses/`](docs/hypotheses/),
and flags concern institutions and companies, never private individuals.

## Status

**Milestone 1, the pipeline reaches a dataset** (September 2026). `serenata fetch`
archives TED's daily notice packages with provenance and checksums.
[`serenata.survey`](serenata/survey/) measured which eForms fields notices
actually populate, so the data model could be designed against evidence rather
than against the specification — the result is
[`docs/field-usage.md`](docs/field-usage.md), and the model it produced is
[`docs/data-model.md`](docs/data-model.md).
[`serenata.parse`](serenata/parse/) reads archived notices into typed records,
dropping the fields that can name a person as it reads, and
[`serenata.normalise`](serenata/normalise/) writes those records as the
documented model in Parquet.

Against a real publication day, all 3,190 notices parse and become **98,629
rows across twelve tables** — 4.2 MB, twelve seconds, and byte-identical when
the run is repeated, which is the determinism the project's whole credibility
rests on and is now a test rather than an intention. 3.6% of every leaf element
in the package — the contact details, beneficial owners and named evaluators
listed in [`docs/personal-data.md`](docs/personal-data.md) — is dropped before
it reaches a record.

Building the stage against real notices corrected the data model three times,
which is the point of measuring rather than reading a specification: the notice
UUID turned out not to be unique, most columns turned out to repeat, and a
withheld value turned out to be published as `-1` rather than omitted. Each
correction is in [`docs/data-model.md`](docs/data-model.md) with the
measurement behind it.

**There is still no classifier and no flag.** Legacy pre-2024 TED notices are
refused rather than parsed, because the mapping for them has never been
measured. [`docs/known-issues.md`](docs/known-issues.md) is the full list of
what the pipeline does not do, or does incompletely. The milestone plan:

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
  eforms.py     # the eForms vocabulary and safe reading, shared by parse+survey
  packages.py   # streaming notices out of an archived package, shared likewise
  parse/        # archived notices -> typed intermediate records (eForms only)
    notice.py   #   read one notice, dropping personal data as it reads
    packages.py #   an outcome per notice: records, or why there are none
    records.py  #   the intermediate records, keyed by element path
    personal_data.py # the fields dropped at ingestion, executable
  normalise/    # intermediate records -> the documented model -> Parquet
    model.py    #   the twelve tables and their sources, executable
    rows.py     #   one notice's records -> the model's rows
    dataset.py  #   sorted, pinned, partitioned Parquet writing
  classify/     # hypothesis classifiers, one module each
  survey/       # measures which eForms fields notices populate (analysis, not a stage)
  cli.py        # entry point: serenata fetch|normalise|classify
tests/
  test_constraints.py  # the hard constraints, executable
docs/
  adr/          # architecture decision records
  open-work.md  # what is open, what each item needs, where to start
  field-usage.md # measured eForms field usage, generated by serenata.survey
  personal-data.md # fields that can name a person, and why each is dropped
  known-issues.md # what the pipeline does not do, or does incompletely
  data-model.md # the relational contract: entities, provenance, absence
  data-reuse.md # TED's reuse terms and this project's attribution
  hypotheses/   # one file per classifier: hypothesis, sources, base rates
data/           # gitignored workspace, except the committed sample/
.claude/skills/ # the working rules this project is built to, in long form
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

## Parsing notices

`parse` turns an archived package into typed records, offline. Values are keyed
by the element path they came from, so every one of them says where it came
from, and the containers the data model names — organisations, lots, tenders,
results, contracts — become records of their own.

```python
from pathlib import Path
from serenata.parse import Unparsed, parse_package

for outcome in parse_package(Path("data/raw/ted/daily/2026/202600157.tar.gz")):
    if isinstance(outcome, Unparsed):
        print("could not read", outcome.member, outcome.reason)
        continue
    for organisation in outcome.of_kind("organisation"):
        names = organisation.values("efac:Company/cac:PartyName/cbc:Name")
        print(outcome.notice_id, names)
```

`values` rather than `value` because a buyer may publish its name in several
languages, and a field carries the attributes that tell them apart. Asking for
one value where the notice holds several raises rather than returning an
arbitrary one — 97% of lot records repeat at least one path, so this is the
normal case, not an edge.

Fields that can name a natural person are never read into a record — not
recorded and filtered later, which is [a legal constraint](CLAUDE.md) rather
than a preference. Where a notice flags an organisation as a sole trader, the
values identifying it are suppressed and its notice-scoped key is kept, so the
record is anonymous but still joins. The list, with the measured frequency of
every field on it, is [`docs/personal-data.md`](docs/personal-data.md).

A notice that cannot be parsed is handed back as an `Unparsed`, naming itself
and why. Nothing is skipped quietly: a stage that dropped what it could not read
would leave gaps nobody could see, and one that raised would end the run at the
first bad notice — losing the rest just as silently.

## Normalising notices

`normalise` reads archived packages and writes the model in
[`docs/data-model.md`](docs/data-model.md) as Parquet, partitioned by the
notice's publication year:

```
uv run serenata normalise                        # every package in the archive
uv run serenata normalise data/raw/ted/daily/2026/202600157.tar.gz --out data/normalised
```

```
data/normalised/notice/publication_year=2026/202600157.parquet
data/normalised/lot_result_statistic/publication_year=2026/202600157.parquet
...
```

Then query it with DuckDB, which reads the files directly:

```sql
SELECT statistic_code, count(*)
FROM read_parquet('data/normalised/lot_result_statistic/**/*.parquet',
                  hive_partitioning = true)
WHERE statistic_kind = 'received_submissions'
  AND statistic_value_status = 'present'
GROUP BY 1 ORDER BY 2 DESC;
```

Two habits that query shows. Every value column has a `_status` beside it, and
reading the value without the status is a bug: a withheld bid count is
published as the code `unpublished` and the number `-1`, and a classifier that
missed that would flag a buyer for exercising a lawful deferral. And amounts
carry a `_currency` companion, because nine currencies appear on tender amounts
in a single publication day.

Rerunning a package rewrites its own files, byte for byte identically. A notice
that cannot be read, or that the model cannot map, is reported and counted
rather than dropped, and the command exits non-zero when a run loses one.

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

Early days. [`CONTRIBUTING.md`](CONTRIBUTING.md) is the page to read: setup,
the constraints and why they exist, when a decision needs an ADR, and how a
change is expected to arrive.

What is open, and what each piece requires, is in
[`docs/open-work.md`](docs/open-work.md) — a few items there are marked as good
places to start, and each open one has an issue mirroring it. The constraints
themselves live in [`CLAUDE.md`](CLAUDE.md) (they apply to humans too), design
decisions in [`docs/adr/`](docs/adr/), and the limits of what exists in
[`docs/known-issues.md`](docs/known-issues.md). Issues and questions welcome.

## Data source and attribution

© European Union, 1998–2026. Source: [TED](https://ted.europa.eu), the Supplement
to the Official Journal of the European Union. Notices published there may be
freely reused for commercial and non-commercial purposes, on condition that the
source is acknowledged, under Commission Decision
[2011/833/EU](https://eur-lex.europa.eu/eli/dec/2011/833/oj/eng).

[`docs/data-reuse.md`](docs/data-reuse.md) records the specific terms, what this
project does not do under them, and the licence this project's own published
datasets carry.

## License

[AGPL-3.0](LICENSE) for the code. The original Serenata used MIT; this project
uses AGPL so that hosted forks of the pipeline stay open, which matters for a
project whose entire value is that you can check its work.

Published datasets and findings are
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/): reuse them, including
commercially, with credit. That is a separate grant from the code licence and
neither implies the other — the reasoning is in
[ADR-0004](docs/adr/0004-dataset-licence.md), the terms in
[`docs/data-reuse.md`](docs/data-reuse.md).
