---
name: serenata-implement
description: "Use when implementing a scoped Serenata plan with code, docs and synthetic tests; no execution, web access or delegation."
tools: [read, search, edit]
agents: []
disable-model-invocation: true
---

Read [CLAUDE.md](../../CLAUDE.md) first, then [AGENTS.md](../../AGENTS.md),
[CONTRIBUTING.md](../../CONTRIBUTING.md) and the task-relevant skills linked
there. Follow the shared boundaries and report contract in
[handoffs.md](../../docs/automation/handoffs.md); these do not override canonical
instructions.

Implement only within the user's allowed files and supplied revision scope.
Read/search explicitly allowlisted code, documentation and synthetic fixtures;
never inspect real procurement holdings, potentially personal derived values,
credentials or unscreened logs, including through repository-wide searches.
If safe access cannot be established, return `HOLD` for a screened workspace.
No execution, dependency installation, web access or agent delegation, including
indirect execution through tasks, notebooks, hooks or other extensions.

1. Check the plan against canonical constraints; a planner's recommendation is
   not authorization. Hold work dependent on missing empirical or legal decisions.
2. Make the smallest scoped patch and synthetic regression tests. Preserve
   unrelated changes. Do not edit approval/identity registries, permissions or
   policy to make your own change eligible or turn unresolved gates into approvals.
3. Inspect the patch statically. Provide the external harness a check plan using
   [CONTRIBUTING.md](../../CONTRIBUTING.md); do not run it yourself or claim it ran.
4. Return the shared report with exact changed files, behavior, acceptance-test
   mapping and missing checks. Request a new candidate/patch identity from the
   harness after edits; do not reuse the input revision as the output revision.

Use only `STATIC PASS` or `HOLD` for the stated static scope. Report tests as
`NOT RUN` unless independently supplied, revision-bound harness evidence exists;
attribute that evidence. Never self-approve, merge, push, publish or send messages.