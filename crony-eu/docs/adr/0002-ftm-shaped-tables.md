# ADR-0002: FtM-shaped tables, a two-table export, no FtM library in phase 1

Status: accepted, 2026-09-10

## Context

FollowTheMoney (FtM) is the data model behind OpenSanctions and OpenAleph. Using its vocabulary keeps two doors open: importing OpenSanctions' data on politically exposed persons when a second country joins (phase 3), and loading case data into OpenAleph if a shared server ever makes sense.

The `followthemoney` Python package depends on `pyicu`, which the package's own README describes as its trickiest dependency, and it brings a statement-based storage model that phase 1 does not need.

My Little Crony's output is two tables, one of nodes and one of connections, rendered into a standalone HTML file with visNetwork, an R wrapper around the vis-network JavaScript library. That format is simple enough for a journalist to open, and it maps directly onto a node table and an edge table in DuckDB.

## Decision

- Each stage writes typed Parquet tables and transforms them with DuckDB.
- Every node and edge carries an `ftm_schema` column holding the FtM schema name it corresponds to: Person, Company, PublicBody for nodes; Membership, Directorship, ContractAward, Ownership, UnknownLink for edges.
- No dependency on `followthemoney` until phase 3. At that point an import/export module is added and tested against these tables.
- The export is `nodes.csv` and `edges.csv` (contract in CLAUDE.md) plus one HTML file per case, rendered with vis-network directly.

## Consequences

- SQL stays simple and every stage can be inspected in DuckDB.
- A test pins the allowed `ftm_schema` values so they don't drift from FtM names.
- Property-level provenance lives in our own columns until the phase 3 module exists; that module needs mapping tests.
