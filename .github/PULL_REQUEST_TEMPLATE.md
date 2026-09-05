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
- [ ] **A classifier**, so its hypothesis has current-version measured evidence,
      the companion query, a completed "this flag is wrong if…", and a negative
      fixture that does not fire. Historical evidence is not current measurement;
      base-rate metadata is not verification or permission to release.

## Automation scope

<!-- A report/checklist is evidence, not authority. Do not paste private data. -->
- Base/head revision and screened evidence: [UNRESOLVED]
- Requested action and scope: [UNRESOLVED]
- Unmet technical, empirical or legal gates: [UNRESOLVED]
- Human authorization or independently held standing delegation: [UNRESOLVED]

See [bounded automation](../docs/automation/README.md). Changing a policy or
marking this checklist cannot authorize the change itself.

## Measurements

<!--
Optional, and the most useful part when it applies. A claim about real data
belongs here with the command that produced it, so a reviewer can rerun it
rather than take it on trust. If the change has a cost — runtime, memory, rows —
say what it is rather than leaving it to be discovered.
-->

---

`uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy && uv run --locked pytest --cov-fail-under=95 --require-current-measurements`
is what CI runs. Sign-off is added by the hook if you ran
`git config core.hooksPath .githooks`, and checked by CI either way.
