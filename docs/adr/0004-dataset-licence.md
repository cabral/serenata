# ADR-0004: Published datasets are CC BY 4.0

- Status: accepted
- Date: 2026-09-02

## Context

[`docs/field-usage.md`](../field-usage.md) is the first dataset this project has
published, and until now it carried no licence of its own. The repository is
public, so it was already being read under terms nobody had stated.

The code is [AGPL-3.0](../../LICENSE). That grant covers the code and says
nothing about the data: a licence for one is not a licence for the other, and
leaving the second unstated does not make it permissive — it makes it unclear.
A reader who wants to build on the measurements has no basis to know whether
they may.

The right that actually attaches here is worth naming precisely. A table of
measurements is largely facts, and facts are not copyrightable. What EU law does
grant over a systematically arranged collection is the **sui generis database
right** (Directive 96/9/EC), which arises from the investment in obtaining and
verifying the contents rather than from any creative authorship. Any licence this
project picks has to speak to that right, or it licenses almost nothing.

This is also the point at which the decision is cheapest. Changing a data licence
after third parties have relied on it is far more awkward than choosing it before
the first release anyone builds on.

## Decision

Published datasets and findings are licensed **[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)**.

Version 4.0 specifically, for two reasons that decided it over the alternatives:

- **It covers sui generis database rights explicitly.** Version 3.0 did not;
  4.0 licenses them alongside copyright. Since the database right is the main
  right in play, an earlier version would leave the substance unlicensed.
- **It is the licence TED applies to its own editorial content.** A derived
  dataset whose terms match its source is legible to a reuser in one step,
  rather than requiring them to reason about how two regimes compose.

Attribution is a condition this project can meet and wants to impose: the value
of the work is that a reader can trace a number back to the notice it came from,
and a credit requirement keeps that chain intact downstream.

The code licence remains AGPL-3.0-only and is a separate grant. Neither implies
the other, and both are stated wherever they apply.

## Consequences

- Every published dataset carries the CC BY 4.0 grant, and
  [`docs/data-reuse.md`](../data-reuse.md) states it rather than marking it open.
- The grant is **generated** into `docs/field-usage.md` by
  `serenata.survey`, beside the TED attribution line, and a test asserts it. A
  regenerated report cannot quietly lose its licence any more than it can lose
  its attribution.
- Commercial reuse is permitted. That is intended: the project's purpose is that
  the measurements get used, and a non-commercial clause would bar exactly the
  newsrooms most likely to act on them.
- This grant covers what this project produces. It does not and cannot relicense
  TED's underlying material, which stays under Commission Decision 2011/833/EU
  with its own acknowledgement condition. Both notices travel together.
- Nothing here changes what may be published in the first place. Constraint 2
  governs that: a licence describes the terms of a dataset, not its contents,
  and no licence makes personal data publishable.

## What would change this

- **Counsel or a funder requiring different terms.** The choice was taken
  deliberately rather than under advice; advice would supersede it.
- **A published dataset that is not a derived measurement.** Findings that
  reproduce notice content sit closer to TED's own material, and the interaction
  between the two grants would need stating rather than assuming.
- **A reuser needing the attribution condition dropped**, if the credit
  requirement ever turned out to be the thing blocking the work from being used.
  CC0 is the fallback, and it would be a deliberate change recorded here.
