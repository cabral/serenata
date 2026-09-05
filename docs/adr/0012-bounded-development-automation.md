# ADR-0012: Automate bounded decisions, not authority

- Status: proposed — read-only checker implemented; executor and delegation absent
- Date: 2026-09-05
- Enforced by: `tests/test_merge_guard.py::TestMergeGuard` checks eligibility and read-only revalidation; synthetic tests do not prove hosted enforcement, isolation or authority

## Context

Synthetic engineering checks must remain separate from empirical verification,
corrections, naming and processing decisions. Neither a model's confidence nor
a human checklist can supply missing evidence, authority or enforcement.

## Decision

Separate proposal, checking, authority and execution. The implemented checker
reads GitHub metadata and reports eligibility only. HTTP rejects non-GET/body
requests before connection; `revalidate()` replaces execution. `--merge` holds
with `merge_execution_not_implemented` before access; `--lock` is removed. There
is no write switch. An enabled external policy permits evaluation, not actions,
using only repository-scoped Contents/Metadata/Actions/Pull requests/Administration
read permissions. The repository template remains disabled and expired.

Evaluation has a four-regression-test-file ceiling, exact paths/authors, one
commit on the trusted base, bounded diff, classic app-bound branch protection
and current CI/DCO/Audit evidence. Production code, evidence, public docs,
dependencies, policies and the checker itself are outside that ceiling.
Model-neutral profiles pin no model; orchestration and sandboxing are not
implemented. See the [operating procedure](../automation/README.md).

A future, separately adopted external standing delegation could authorize
enumerated merges without per-merge clicks, only after separate executor review
and deployment. This proposed ADR adopts none. All four scientific/correction/
legal gates remain open with [specific handoffs](../automation/handoffs.md);
code eligibility grants no processing, naming, publication or messaging authority.

## Consequences

The synthetic regression tests are not a hosted canary. Historical real API run
33956612491 returned an empty PR association; revision binding remains a
compatibility blocker, not solved by synthetic evidence. The manual probe's
disabled policy and token lacking Administration read prevent working evaluation
by merely flipping the policy.

A future executor needs enforceable destination/revision binding and serialization
covering PR retargeting, base updates, policy revocation, reruns and dispatch,
plus unknown-write reconciliation. Head-SHA checking or another GET is not
atomic destination/base binding. No broker or scheduler exists here. Separate
sandbox/credential boundaries and a hosted canary must be implemented and verified;
human approval cannot replace them. Models cannot renew or expand authority.
Reports, policy hashes and ADR-0009 DCO trailers are not approval signatures.

## Revisit triggers

Broader source changes, new models/tools with capabilities beyond the isolated
workspace, forks, merge queues, multiple writers, unavailable workflow binding,
new legal decisions or an escaped/bypassed gate require review. Stop first;
never silently widen scope or weaken checks to obtain a green run.