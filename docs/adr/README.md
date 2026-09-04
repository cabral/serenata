# Architecture decision records

One file per decision, named `NNNN-short-title.md`, numbered in the order
taken. Each records the context, the decision, its consequences, and what
would make us revisit it. Design decisions not already covered by
[`CLAUDE.md`](../../CLAUDE.md) are proposed here before they ship in code.

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
