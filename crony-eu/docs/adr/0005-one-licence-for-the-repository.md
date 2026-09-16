# ADR-0005: One licence for the repository, AGPL-3.0-only

Status: accepted, 2026-09-16

## Context

The handover said this project is AGPL-3.0-**or-later** and put an SPDX header
saying so on every source file. The repository it arrived in is AGPL-3.0, its
`LICENSE` is the plain AGPL-3.0 text, and its `pyproject.toml` declares
`AGPL-3.0-only`.

[ADR-0014 in the other series](../../../docs/adr/0014-replace-serenata-with-crony.md)
left the two statements alone on purpose and said the reconciliation needed its
own record. This is that record, and it is needed now because session 0 writes
the first source file and the first SPDX header goes on it.

"Or later" is not a small difference. It delegates the licensing terms to
whatever the Free Software Foundation publishes next, on behalf of every person
who has contributed under it. Adding it to an existing AGPL-3.0 codebase is a
relicensing, and a relicensing needs the agreement of everyone whose
contributions it covers, not a decision by whoever is typing.

## Decision

**The whole repository is AGPL-3.0-only, this project included.**

- SPDX headers read `# SPDX-License-Identifier: AGPL-3.0-only`.
- `crony-eu/pyproject.toml` declares `AGPL-3.0-only`, matching the root.
- There is one `LICENSE` file, at the repository root, and this project does not
  add a second copy.

The handover's preference for "or later" is recorded here rather than acted on.
Adopting it later is possible and is a deliberate relicensing: it needs a new
record, and the agreement of every contributor whose commits it would cover.

## Consequences

One licence in one repository, which is what a reader and a packager both
expect. A fork that wants AGPL-4.0 terms, if such a thing ever exists, has to
ask rather than inherit.

Nothing about the existing code changes, and no existing sign-off is
reinterpreted. That is the point: a `Signed-off-by` certifies the right to
contribute under the licence in force when it was given, and leaving that
licence alone means none of them has to be revisited.

When this project moves to a repository of its own, the question reopens, and at
that point it can be answered for a codebase whose contributors are known and
few.
