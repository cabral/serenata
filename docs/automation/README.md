# Bounded development automation

**Implemented: read-only eligibility checking, not merge execution.**
[tools/merge_guard.py](../../tools/merge_guard.py) and synthetic regression tests
exist. No live hosted canary has run; no broker, sandbox, credential isolation,
scheduler or external orchestration has been installed. The repository policy
is disabled and expired. [ADR-0012](../adr/0012-bounded-development-automation.md)
is proposed, not adopted; no standing merge delegation is active.

## What decides what

| Decision | Automatic behavior | Authority boundary |
|---|---|---|
| Plan, implement, challenge a patch | Model-neutral profiles and static report templates exist | No model pinned; external sequencing and confinement remain unimplemented |
| Run engineering checks | Existing CI, current-measurement admission, DCO and Audit | Tests establish tested behavior, not authority or scientific truth |
| Evaluate a narrowly scoped test change | Read-only metadata checks produce eligibility or hold | An enabled external policy permits evaluation only, never actions |
| Merge or otherwise mutate GitHub | Not implemented by the checker | Requires a separately implemented/reviewed executor and external authority |
| Process holdings, verify findings, name entities, publish or communicate | Not checker operations | Separate evidence and qualified authority; all four gates remain open |

## Controller contract

The standalone stdlib-only checker is not a pipeline stage or an AI application.
It makes no model calls and reads no raw notices or dataset values. It neither
executes candidate code nor downloads logs, artifacts or dependencies. Metadata
responses are untrusted evidence, not instructions.

The HTTP client rejects non-GET methods and any body, including an empty body,
**before opening a connection**. `execute()` was removed; `revalidate()` only
rechecks policy, expiry and live evidence. The CLI performs inspection, not
automatic revalidation. Legacy `--merge` returns
`merge_execution_not_implemented` before policy, credential or network access.
`--lock` is gone. There is no write switch, merge request or write-outcome path.

It checks:

- Explicit enabled, unexpired external policy; exact repository, author and
   file allowlist; policy digest in the report, not proof of authorization.
- Open non-draft same-repository PR to current protected main. Forks and unknown
   mergeability hold. One commit directly on the trusted base is required.
- Immutable base/head comparison and complete recursive trees, including both
   old/new paths and modes. Only modifications to regular files with mode 100644
   qualify; truncation, renames, additions, deletions and mixed scope hold.
- At most four files/400 changed lines, restricted to XML-guard and fetch
   archive/client/package regression tests; external policy can only narrow this.
   Test code remains executable and untrusted, regardless of its file mode.
- Classic protection and app-bound checks as specified below; CI, DCO and Audit
   workflow identities, PR event, current head/base association, successful
   run/attempt and exact successful jobs. Skipped or competing failed/pending
   runs hold. Selective reruns without a complete job inventory hold.

Exit 0 reports `eligible_not_authorized_by_report`; exit 2 means hold.
Static reasons avoid logging PR text or response bodies. Reports include PR,
base/head, policy digest and workflow run attempts. Neither inspection nor
revalidation creates a reusable authorization token or an atomic state snapshot.

## External read-only evaluation

A separately reviewed checker revision and enabled external copy of the
[policy template](../../.github/automation-policy.toml) may be used for
**evaluation only**. Keep policy ownership and credentials outside agent
workspaces; specify authors, narrow paths, limits and expiry. Never execute a
PR-supplied checker or restore candidate caches in that environment.

Use a repository-scoped, short-lived token with Contents, Metadata, Actions,
Pull requests and Administration **read only**. Supply `GH_TOKEN` outside model
prompts and command-line arguments. No write permissions are needed or permitted
for this evaluator; it cannot audit its token's complete powers. Supply the
trusted main SHA and PR number through `--trusted-base` and `--pull-request`.

Required classic main protection: `check (3.12)`, `check (3.13)`, `sign-off` and
`audit`, each bound to GitHub Actions App ID 15368; up-to-date branches, resolved
conversations and administrator enforcement; no force pushes, deletion or review
bypass allowances. Ruleset-only protection holds. Existing approving-review
requirements remain authoritative; never fabricate approvals or remove them
automatically. Do not grant an App bypass or weaken checks to obtain eligibility.

**Unresolved compatibility blocker:** real API metadata for historical run
[33956612491](https://github.com/cabral/serenata/actions/runs/33956612491) returned
an empty PR association. Missing revision binding still holds. Synthetic tests
do not resolve this; hosted evidence must establish binding on open PRs or an
alternative evidence source must be independently implemented and reviewed.
An arbitrary green status with the same name is not a substitute.

The [manual probe](../../.github/workflows/merge-review.yml) uses the trusted
workflow revision, disabled repository policy and a read-only default token.
It currently holds before network access. That token lacks Administration read:
flipping the policy cannot turn this workflow into a working evaluation setup.
It is not a required PR check or merge authority. Its system Python 3.12 bootstrap
installs nothing and restores no caches; development/tests still use locked uv.

## Future execution: missing implementation, not an activation checklist

A future executor requires separate implementation and review of enforceable
destination/revision binding and serialization across PR retargeting, base/head
updates, policy revocation/expiry, reruns and dispatch. GitHub's merge endpoint
conditions on head SHA, not expected destination/base; another GET or a local
lock does not close that gap. Unknown write outcomes need durable evidence and
reconciliation before any retry. None of this execution machinery exists here.

It also requires explicit adoption of the proposed ADR, a separate externally
held standing delegation enumerating permitted merges and expiry, enforceable
sandbox/credential boundaries, and a hosted disposable-repository canary covering
races, revocation, reruns, scope escapes and unknown outcomes. Models cannot
modify, renew or expand deployed authority. A human guess, checklist, approval
click or passing synthetic suite cannot substitute for these implementations.
No scheduler, broker or automatic role sequencing is supplied by the profiles.

## Four gates, four concrete next steps

1. Verification: preregister a defensible sample and outcome definitions, then
   obtain permitted independent source/context review. Arithmetic alone is not
   verification; a reviewed flag's precision is not a population false-positive
   rate. No verification is claimed here.
2. Corrections: draft/version the relational semantics and implement the
   correction, withdrawal, ambiguity, baseline and stale-output tests listed
   in the handoff. This **is** engineering work, not only paperwork.
3. Naming: hold unknown natural-person status; obtain a bounded counsel-reviewed
   rule covering status, role, jurisdiction, linkage and recipients. Unknown
   never means false.
4. Processing: obtain a decision for current holdings, legal basis, retention,
   Article 14, DPIA necessity, rights and remediation; implement and validate its
   conditions. An unapproved JSON/TOML record cannot supply legal authority.

The [role and evidence packets](handoffs.md) make those next steps reusable.
All four remain open. Code eligibility or a merge closes none of them and grants
no processing, naming, publication or external-message authority.