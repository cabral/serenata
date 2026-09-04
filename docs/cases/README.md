# Cases

One file per detection idea, `NNN-slug.md`, with a status line: idea, scoped,
measured, building, live, or rejected.

| # | Case | Status |
|---|---|---|
| [001](001-single-bid.md) | Single bid on a competitive procedure | **rejected** at the base-rate gate — it fires on 36.8% of the population |
| [002](002-single-bid-against-its-segment.md) | A single bid where single bids are rare | **measured** — passes four gates, 2.23% of the population it covers |

A case file is where an idea is argued **before** it becomes code. The four
intake gates it has to pass — the signal exists as a structured field, the legal
question is answered, the base rate is measured, and "this flag is wrong if…"
can be completed — are in
[`.claude/skills/case-research/SKILL.md`](../../.claude/skills/case-research/SKILL.md).
A case that passes all four graduates to a hypothesis file in
[`../hypotheses/`](../hypotheses/) and enters the classifier workflow.

**Rejected cases keep their file and the reason.** Half the value of this
directory is the record of what was considered and did not fly: a reader
deciding whether to trust the output can see what was ruled out and why, which
is not visible anywhere else. A project that only publishes its successes is
asking to be taken on faith.
