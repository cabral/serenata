# Architecture decision records

One file per decision, named `NNNN-short-title.md`, numbered in the order
taken. Each records the context, the decision, its consequences, and what
would make us revisit it. Design decisions not already covered by
[`CLAUDE.md`](../../CLAUDE.md) are proposed here before they ship in code.

## Two series, and which one you are reading

This directory holds decisions about this repository and about Serenata Europa's
TED pipeline. Crony's decisions are in
[`crony-eu/docs/adr/`](../../crony-eu/docs/adr/), also numbered from 0001.
Neither series was renumbered when the projects met, because renumbering would
break every citation in both, so a record citing the other says which it means.
[ADR-0014](0014-replace-serenata-with-crony.md) is where that arrangement comes
from.

## Every record taken before ADR-0014 says what became of it

The header of each earlier record carries a `- Transition:` line with one of
three answers:

- **carried** — the decision governs Crony too
- **retired** — it governed the TED pipeline and goes with it
- **continuing obligation** — it binds the maintainer whichever project occupies
  the repository, and retiring code does not discharge it

`tests/test_transition.py` checks that every earlier record answers, and answers
with one of those three. The third is the one to read carefully. ADR-0010's
archive is still on disk and its lawful basis is still unresolved; deleting the
code that reads it would change neither fact.

## Every record says what holds it true

The header carries an `Enforced by:` line naming the test class that keeps the
decision honest:

```
- Status: accepted
- Date: 2026-09-02
- Enforced by: `tests/test_normalise.py::TestAbsenceIsRecorded`
```

`tests/test_adr.py` checks that those names resolve, because a record pointing
at a class that was renamed is worse than one pointing at nothing — it claims a
guarantee that has quietly stopped existing. It also checks the reverse: a test
named here mentions the record back, so a reader arriving from the code finds
the reasoning rather than just the rule.

Where nothing mechanical can hold a decision true, the line **says so** rather
than naming the nearest test. ADR-0009 is enforced by a CI workflow rather than
by pytest; ADR-0010 is a policy about lawful basis and retention, and no test
can hold that true. Both say which, and the gate accepts the honest answer.
