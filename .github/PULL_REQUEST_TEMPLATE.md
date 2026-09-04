## What this changes, and why

<!--
Why, not what — the diff already says what. If a number decided something, put
the number in.
-->

## Before merging

Delete anything that does not apply. What is left should be true.

- [ ] **The schema changed**, so `docs/personal-data.md` and
      `serenata/parse/personal_data.py` were reviewed together in this PR. A
      field inside `cac:Contact`, `efac:UltimateBeneficialOwner` or
      `cac:TechnicalCommitteePerson` is already dropped by path and needs
      nothing; a field somewhere new is a personal-data decision.
- [ ] **A document that describes this code changed with it.** `docs/data-model.md`
      and `docs/personal-data.md` have drift tests; the rest do not.
- [ ] **A generated report was regenerated** — `docs/field-usage.md`,
      `docs/dataset-shape.md`, `docs/dropped-fields.md`. They are produced from archived
      packages, not edited.
- [ ] **This decision constrains future work**, so there is an ADR.
- [ ] **A classifier**, so there is a hypothesis file with status `measured` or
      later, a base rate with the query that produced it, a completed "this flag
      is wrong if…", and a negative fixture that does not fire.

## Measurements

<!--
Optional, and the most useful part when it applies. A claim about real data
belongs here with the command that produced it, so a reviewer can rerun it
rather than take it on trust. If the change has a cost — runtime, memory, rows —
say what it is rather than leaving it to be discovered.
-->

---

`uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest`
is what CI runs. Sign-off is added by the hook if you ran
`git config core.hooksPath .githooks`, and checked by CI either way.
