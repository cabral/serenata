# ADR-0006: The standard library, not typer, rich, jinja2 or vis-network

Status: accepted, 2026-09-16. Amends ADR-0002 on how a case network is rendered.

## Context

`crony-eu/CLAUDE.md` named a stack before any of it was written: typer for the
CLI, rich for the review screen, jinja2 for the HTML template, and the
vis-network JavaScript library vendored as a standalone UMD build with its
licence and a pinned sha256. [ADR-0002](0002-ftm-shaped-tables.md) chose the
two-table export and said it would be rendered "with vis-network directly",
following My Little Crony, which used visNetwork through R.

The repository this project now lives in already has duckdb, httpx and pyarrow,
each of them licence-checked on every test run. The four named above would be
new, and one of them is a 600KB minified JavaScript file committed to a
repository whose first rule is about what may be committed to it.

Phase 1 asks very little of any of them. The CLI is eight subcommands with flags.
The review screen is a record, a prompt and a keypress. The HTML template is one
file with values substituted into it. The network is somewhere between ten and
thirty nodes, which is the size My Little Crony topped out at after a year and
the size a person can hold in their head.

## Decision

**No new dependencies in phase 1.** The three already present cover the data
work; the standard library covers the rest.

- **`argparse` instead of typer.** Subcommands, flags, help text. It is
  wordier at the definition site and identical at the call site.
- **`print` and `input` instead of rich.** The review screen shows one candidate
  and reads one key. If it turns out that colour is what makes a reviewer
  reliable rather than merely comfortable, that is a finding worth a dependency
  and worth measuring first.
- **`string.Template` instead of jinja2.** One template, no loops that a
  generated fragment cannot express, and no autoescaping to configure wrongly.
  Escaping is explicit at every substitution instead, which for a file that will
  carry a person's name is where it should be visible.
- **A server-rendered inline `<svg>` instead of vis-network.** The layout is
  computed in Python, deterministically, and written into the file as static
  markup.

## Consequences

**The export gets stricter, not looser.** With no library there is no script at
all, so the Content-Security-Policy meta tag drops `script-src` entirely:

```
default-src 'none'; style-src 'unsafe-inline'; img-src data:
```

CLAUDE.md's rule that the HTML loads nothing from the network was always
satisfiable with vis-network inlined. This satisfies it by having nothing to
inline. It also removes the vendored asset, its `VERSION` file, its hash check
in `crony doctor`, and the licence file beside it.

**Determinism gets easier.** A fixed `layout.randomSeed` makes vis-network's
physics reproducible in principle and depends on the library's implementation
not changing between versions. A layout computed in our own code and written as
coordinates is reproducible because the coordinates are in the file.

**The network loses interaction.** No dragging, no zoom, no hover physics. A
static picture with a legend and a sources panel, plus the edge list as CSV
beside it, is what a reader gets. For thirty nodes that is likely enough, and
"likely" is doing real work in that sentence: nobody has looked at one yet.

**Revisit when there is something to look at.** The honest test is a real packet
in front of a journalist. If the static picture is the thing that makes it
unusable, vis-network comes back with a measurement behind it, this record gets
an amendment, and the CSP goes back to allowing inline script. That is a
reversible decision and it is cheaper to reverse than to undo.

## What this does not change

The export contract, the two tables, the `ftm_schema` column and the decision to
keep `followthemoney` out of phase 1 are all ADR-0002 and all unchanged. Only the
renderer changed.
