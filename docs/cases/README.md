# Cases

One file per detection idea, `NNN-slug.md`, with a status line: idea, scoped,
measured, building, live, or rejected. There are no cases yet; the first
classifier has not been scoped.

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
