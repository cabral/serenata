# ADR-0001: Parquet + DuckDB for the normalised dataset

- Status: accepted
- Date: 2026-06-12

## Context

Milestone 1 produces one artefact: a normalised relational dataset built
from TED notices (~700k/year, so single-digit millions of rows over the
period we care about — large for a spreadsheet, small for a database). The
workload is batch: the pipeline rebuilds or appends to the dataset, then
classifiers run read-only analytical queries over it. There is no public
API yet, no concurrent writers, and no requirement to serve queries to
anyone but the pipeline and an analyst's laptop.

Two project constraints shape the choice. Determinism: same input data and
classifier version must yield byte-identical outputs, which favours storage
that is itself a plain, inspectable artefact. And AGPL-3.0 compatibility for
every dependency.

## Decision

Store the normalised dataset as Parquet files and query them with DuckDB.
No database server in milestone 1.

- Parquet makes the dataset an artefact: columnar files that can be
  checksummed, versioned, published as bulk downloads, and read from any
  language without us operating anything. That matches the project's core
  promise — anyone can check our work — better than state inside a server.
- DuckDB is an in-process SQL engine that queries Parquet directly. The
  classifiers get full SQL with zero infrastructure, and an analyst gets the
  same with `pip install duckdb`.
- Licences are compatible with AGPL-3.0: DuckDB is MIT, Apache Arrow/pyarrow
  is Apache-2.0.

Determinism note: Parquet output is only byte-stable if the writer makes it
so. The normalise stage owns this — fixed row ordering, fixed schema and
writer settings, pinned writer version — and a test must verify it.

## Consequences

- Nothing to deploy or operate; the full pipeline runs on one machine.
- The dataset can be shipped as-is (object storage, torrents, Zenodo)
  without an export step.
- No concurrent or transactional writes; the pipeline is the only writer,
  by design.
- Memory and one-machine limits apply to query size. Fine at TED scale;
  worth rechecking if scope grows beyond TED.

## What would trigger Postgres

Postgres enters with the public API milestone, when the dataset must be
served to many users with authentication, quotas, and uptime. It would come
earlier only if we acquire a genuinely transactional workload first — for
example, human curation of entity-resolution matches with audit history.
Even then, Parquet stays as the publication format for bulk data releases;
Postgres would serve, not replace, the artefact.
