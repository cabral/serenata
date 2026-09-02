# Contributing

Thanks for looking. This page is what you need to land a change here without
reading the whole repository first.

[`CLAUDE.md`](CLAUDE.md) is the source of truth for the constraints below. It
applies to humans too, despite the name. Where this page and that one disagree,
that one wins and this page is what needs fixing.

## Getting set up

Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```
git clone https://github.com/cabral/serenata
cd serenata
uv sync
```

Run what CI runs, in the order it runs it:

```
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

All four must pass on 3.12 and 3.13. `pytest` enforces a 95% coverage floor —
a rot detector, not a ratchet; the suite sits at 99%.

The test suite runs **fully offline** and `tests/conftest.py` refuses a socket
if anything tries to open one. That is not a convenience: fetching is the only
networked stage, and a test that reached the network would quietly make the rest
of the pipeline non-reproducible.

## The constraints

Six rules bind every change. Five are enforced by
[`tests/test_constraints.py`](tests/test_constraints.py) and
[`tests/test_personal_data.py`](tests/test_personal_data.py), so you will find
out from a failing build rather than from a reviewer. They exist because this
project's only asset is that a stranger can rerun it and get the same rows.

**1. AGPL-3.0, and every dependency compatible.** Check a licence before
`uv add`, not after. A gate reads installed metadata on every run.

**2. No personal data, ever.** Fields that can name a natural person are dropped
*at ingestion* — never stored and filtered later. The list is
[`docs/personal-data.md`](docs/personal-data.md), executable as
`serenata/parse/personal_data.py`; a test derives its assertions from the
document so the two cannot drift. If you change what is ingested, change both in
the same pull request. This is a legal constraint (GDPR, Swedish defamation
law), not a style preference, and it is the one place to err on the side of
dropping too much.

**3. Flags are anomalies, never accusations.** No user-facing string, document
or example calls a flagged record corrupt, fraudulent or guilty. Most flags have
innocent explanations, and the project publishes about institutions whose
lawyers can read.

**4. Determinism.** The same input and the same code produce the same bytes. No
wall-clock in outputs, no unseeded randomness, no network below fetch. Sort
before every write; never rely on scan order.

**5. Structured fields only.** Core classifiers read named eForms/TED fields. No
NLP, no LLM calls, no fuzzy matching. If someone asks why a row was flagged, the
answer has to be a rule over named fields.

**6. No classifier without a documented hypothesis.** A written, falsifiable
claim, the fields it uses, its population, and a base rate measured on real data
— before the detection code, not after. A flag whose false-positive profile is
unknown is not shippable. See [`docs/hypotheses/`](docs/hypotheses/).

## Where decisions go

If a change settles a question that constrains later work, write a short ADR in
[`docs/adr/`](docs/adr/) — context, decision, consequences, and what would make
us revisit it — rather than burying the reasoning in code. The existing ones are
the model for length and tone. If it needs more than a page, the decision
probably is not crisp yet.

An ADR that turns out to be wrong gets an amendment with a date, not a quiet
edit. [ADR-0003](docs/adr/0003-xml-parsing-without-defusedxml.md) is the worked
example.

## The working rules in `.claude/skills/`

This project is largely built with an AI coding assistant, and the rules it
works to are in [`.claude/skills/`](.claude/skills/) — the classifier workflow
and merge checklist (`coding`), the intake gates a detection idea has to pass
(`case-research`), the defamation and GDPR guardrails (`legal`), and how the
project writes for people outside it (`communication`, `patreon`).

They are in the repository rather than on one laptop for two reasons. A rule
nobody can read is a rule nobody can follow, disagree with, or improve. And the
standards an assistant is held to should be the standards a human contributor is
held to; if they differ, one of them is wrong.

**They are ordinary files: improve them with a pull request like anything else.**
Where a skill and `CLAUDE.md` disagree, `CLAUDE.md` wins and the skill is what
needs fixing. Where a skill claims something about this repository that is not
true — that a test exists, that a document says something — that is a bug worth
a PR on its own, because a rule that misdescribes the code teaches the next
reader something false.

## Commits and pull requests

- Small, one concern each. Imperative subject: "Build the parse stage", not
  "parse stage" or "Built the parse stage".
- Say **why** in the body, not what the diff already shows. If a number decided
  something, put the number in.
- Update the docs in the same commit as the behaviour. A document that describes
  code that no longer exists is worse than no document.
- Every commit needs a `Signed-off-by` line — see below.

## Sign your work

Contributions come in under the [Developer Certificate of
Origin](https://developercertificate.org/) rather than a copyright assignment or
a CLA. It keeps the barrier low and the provenance clean: you are certifying you
wrote the patch or otherwise have the right to submit it under AGPL-3.0.

Add the line with `git commit -s`:

```
Signed-off-by: Your Name <your.email@example.com>
```

Use your real name and an address that reaches you. This is not yet checked
mechanically; a missing sign-off will be asked for in review.

## Tests

- Fixtures are **obviously synthetic** — impossible notice ids, names like
  `EXAMPLE BODY` — or real public notices reproduced accurately and named after
  their notice id. Never plausible-looking fabrications: nothing that could be
  mistaken for a real finding. Never anything containing a natural person's
  name. The rules are in [`tests/fixtures/README.md`](tests/fixtures/README.md)
  and they are not negotiable.
- Test the behaviour and say why it matters. A test whose name and comment
  explain what would break in the real world is worth three that assert
  mechanics.
- A test that can only pass vacuously should assert it is not passing vacuously.
  Several here do.
- For anything with a measured claim behind it, prefer a check against the real
  archive over an assertion about what you expect it to contain.

## Picking something up

[`docs/open-work.md`](docs/open-work.md) says what is open, what each item
needs, and where to start; a few are marked as good entry points. Issues mirror
it. Say on the issue that you are taking something, so two people do not start
the same thing.

[`docs/known-issues.md`](docs/known-issues.md) is the other half of the picture:
what the pipeline does not do, or does incompletely.

Questions before code are welcome, especially on anything touching constraint 2
or a classifier's hypothesis. Those are the two places where being wrong is
expensive.
