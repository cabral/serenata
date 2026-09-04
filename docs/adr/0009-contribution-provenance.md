# ADR-0009: Keep the DCO, enforce it, and say what it means when an assistant wrote the patch

- Status: accepted
- Date: 2026-09-03
- Enforced by: `.github/workflows/dco.yml`

## Context

[`CONTRIBUTING.md`](../../CONTRIBUTING.md) has asked for a
[Developer Certificate of Origin](https://developercertificate.org/) sign-off on
every commit since it was written. **One commit out of 66 carries the trailer —
the commit that added the rule.** Nobody has followed it since, including its
author.

That is not a small inconsistency in this repository. There are tests that fail
when a document describes code that does not exist, and a section in
`known-issues.md` for figures that were measured once and might have rotted. A
CONTRIBUTING that states a requirement the maintainer has never met is the same
defect, sitting in the first place a new contributor looks.

The question that forced the decision is sharper than housekeeping: **most of
this codebase is written with an AI assistant.** Forty-four of the 66 commits
carry a `Co-Authored-By` trailer naming one. If a model wrote the patch, what is
a human certifying by signing it?

## Decision

**Keep the DCO. Make it automatic, check it in CI, and write down what it means
for a patch written with an assistant.**

The DCO is not a statement about who typed the code. Its three clauses are about
**the right to submit**: that the contribution is the submitter's to offer under
this project's licence, or is derived from work that permits it. An assistant is
not a party to it and cannot sign it. The human whose identity is on the commit
certifies they have the right to submit the work — and that is a true, meaningful
statement about an AI-assisted patch.

Heavy assistant use makes that certification **more** valuable, not less. The
realistic provenance risk here is not authorship, it is a model reproducing a
memorised fragment of code carrying an incompatible licence. DCO clause (a) — "I
have the right to submit it under the open source license indicated in the file"
— is exactly where that risk lands, and it puts a human name against it.

Three mechanisms, because the rule failed for three years' worth of commits on
discipline alone:

- [`.githooks/prepare-commit-msg`](../../.githooks/prepare-commit-msg) appends
  the trailer, installed once per clone with
  `git config core.hooksPath .githooks`. A rule that depends on remembering a
  flag is a rule that will be missed.
- [`.github/workflows/dco.yml`](../../.github/workflows/dco.yml) fails a pull
  request whose commits lack it, and says how to fix it.
- CONTRIBUTING states plainly what signing means when a tool helped, so nobody
  has to guess.

**Scoped to commits a pull request adds, never to history.** The 65 unsigned
commits stay unsigned. Rewriting published history to satisfy a policy adopted
afterwards would change every hash for no gain; the rule starts here and applies
forward.

**Merge commits are exempt.** They carry no content of their own to certify, and
GitHub creates them server-side where no hook runs.

## Consequences

- **The honest part, stated rather than glossed.** Commits on this project are
  often made by an assistant running under the maintainer's git identity, and
  the hook applies the trailer automatically. So the trailer is not evidence
  that a human read that diff at the moment it was written. What makes it true
  is the review before merge, which is a human act on a human's account. Anyone
  auditing this should read a sign-off here as *"the maintainer takes
  responsibility for this contribution"*, which is what the DCO asks, and not as
  *"a human typed this"*, which it never asked.
- **`Co-Authored-By` is the disclosure, and it is separate.** The two trailers
  answer different questions — who is responsible for submitting, and what wrote
  it. Neither substitutes for the other, and both stay.
- **A wrinkle worth knowing and not acting on.** Output generated entirely by a
  model probably attracts no copyright in either the US or the EU, both of which
  require a human author. That does not weaken AGPL-3.0 over this project: the
  work as a whole is a human-selected, human-reviewed compilation, and the
  human-authored parts are protected normally. It does mean enforcement against
  a copier would be weaker for any purely machine-authored fragment. This is
  unlitigated, it is the same for every project using these tools, and no
  practical step follows from it today beyond keeping the human attestation
  visible.
- A contributor rebasing a branch that predates this gets a failing check.
  `git rebase --signoff origin/main` fixes it, and the workflow says so.
- This adds a required check to pull requests. It is ten lines of shell and no
  third-party action, so it costs nothing to keep and nothing to audit.

## What would change this

- **A funder or institution requiring a CLA** instead. That is a different
  instrument with different consequences for contributors, and it would replace
  this rather than sit beside it — an escalation, not a patch.
- **External contributions at volume**, where a hosted DCO bot with its own
  remediation flow may beat ten lines of shell. Swap the mechanism, keep the
  policy.
- **Case law or legislation on AI authorship** that makes the copyright wrinkle
  above operative rather than theoretical. Then this ADR gets a successor, and
  the answer may be to record machine-authored spans explicitly rather than to
  argue about the whole.
