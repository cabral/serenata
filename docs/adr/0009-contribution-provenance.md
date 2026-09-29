# ADR-0009: Keep the DCO, enforce it, and say what it means when an assistant wrote the patch

- Status: amended — the DCO decision stands; the operating model and sign-off practice below were added
- Date: 2026-09-03
- Amendment: 2026-09-29
- Enforced by: `.github/workflows/dco.yml` checks that a sign-off is present. The
  operating rules in the amendment are policy; nothing mechanical holds them.

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

## Amendment (2026-09-29): how assistants work, and who decides

The maintainer set the operating model. The project runs like a small
engineering shop that mostly runs itself: assistants design, write, test and
commit on their own, and check each change against the law and the project's
rules while they work. Those checks are part of the job. What they check against
is `CLAUDE.md`, the skills, the ADRs and the escalation list in the legal skill.

The decision rule is short. If those sources answer the question, the assistant
acts on the answer and keeps going. If they don't, or the question is on the
escalation list, the assistant stops that item, asks the maintainer, and carries
on with other work in the meantime. An open question is not a reason to go idle.

**Law decides, not policy.** What the project may store or process is a legal
question (lawful basis, minimisation, retention). A preference written into this
repository does not answer it in either direction. Open data the project has the
right to keep should be kept, and being published by an authority does not by
itself create that right. Whether it exists for personal data in notices is the
open question in ADR-0010. It needs counsel, so until counsel answers, the
drop-at-ingestion rule stays and ADR-0010 stays the record of what is unresolved.

**What changes.** Commits and pushes to a working branch need no approval per
step. `AGENTS.md`, `CONTRIBUTING.md` and the skills said otherwise and were
edited in the same change.

**What does not change.** These stay with the maintainer:

- merging, publishing, and any external message;
- anything that names or identifies a person or an entity;
- the licence, and the drop-at-ingestion rule;
- the CI checks, the merge guard and ADR-0012's delegation lane. An assistant
  does not edit the checks that apply to its own work to get a change through.

**Sign-off.** An assistant does not sign under its own name, and a trailer is not
added under a name its owner has not configured. A sign-off still reads as "the
maintainer takes responsibility for this contribution". Under this model that
rests on three things: the checks the assistant ran while working, CI, and the
maintainer's decision to merge. A session that runs under the assistant's own
git identity leaves `Co-Authored-By` only, and the maintainer's sign-off is added
before a pull request with `git rebase --signoff origin/main`, as the DCO
workflow already says.

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
