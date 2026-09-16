# Transition ledger

What exists in this repository on 2026-09-16, and what happens to each piece
now that [ADR-0014](adr/0014-replace-serenata-with-crony.md) has made Crony the
repository's purpose and put Serenata Europa's TED pipeline on a path to
retirement.

This file is an inventory, not a plan. It says where every piece stands and who
decides its fate. The work order for what replaces it is
[`crony-eu/docs/work-order-phase-1.md`](../crony-eu/docs/work-order-phase-1.md).

## The recoverable checkpoint

The annotated tag `serenata-europa-pre-transition` points at `4d2cba6`, the last
commit of the TED/eForms project as a maintained whole. Everything retired
during the transition is recoverable from there, and every branch listed below
exists on `origin` as well as locally.

**The tag is local until someone pushes it.** `git push origin
serenata-europa-pre-transition` is a deliberate act and has not been performed
by the session that created it.

Nothing in this ledger deletes code. The only file removed in the reconciliation
commit is `crony-eu-handover.zip`, and only because it was verified byte-for-byte
identical to the `crony-eu/` tree committed alongside it.

## Three words, and what each one means

| word | meaning |
|---|---|
| **keep** | it belongs to Crony, or to the repository regardless of which project occupies it |
| **finish** | it is unfinished, and finishing it is worth doing even though Serenata is retiring |
| **retire** | it goes when the replacement check for it exists, and not before |

A fourth answer appears where it is honest: **maintainer decides**. Those rows
are not deadlocks to be resolved by an agent guessing.

## Uncommitted work at the start of the transition

The working tree held three untracked items and no staged, unstaged or stashed
changes.

| path | disposition | why |
|---|---|---|
| `crony-eu/` | **keep** | the handover tree; committed in the reconciliation commit, with the corrections in ADR-0014 applied |
| `scope.md` | **keep** | promoted to the canonical scope of this repository |
| `crony-eu-handover.zip` | **retire** | verified identical to `crony-eu/`; a transport artifact, not a source |

## Branches with commits not on `main`

All three are pushed to `origin` and none is lost by anything here.

| branch | commits | disposition | why |
|---|---|---|---|
| `counsel-blocker-visible` | 1 | **finish** | it makes `docs/counsel/`, `docs/known-issues.md` and `docs/open-work.md` say that no counsel is engaged. That is true before and after the transition, and [ADR-0010](adr/0010-raw-archive-retention.md)'s unresolved review does not retire with the pipeline |
| `conflicting-natural-person-indicator` | 1 | **maintainer decides** | it suppresses a sole trader whose eForms indicators contradict each other — a privacy correction to a parse stage that is retiring. It changes nothing unless the archive is reprocessed, and reprocessing is itself blocked by ADR-0010. Worth merging if the archive is ever rebuilt; not worth finishing as a feature |
| `legacy-package-availability` | 2 | **retire** | legacy pre-2024 TED parsing is the clearest case of an obsolete feature. its `legacy-availability.md` measurement is evidence of what TED actually serves rather than a feature, and is worth keeping; the branch preserves it |

Nine further branches are merged into `main` and carry nothing unique.

## Runtime and tests

| path | disposition | why |
|---|---|---|
| `serenata/fetch/` | **retire** | TED's API and daily packages; Crony fetches French open data instead |
| `serenata/parse/` | **retire** | eForms XML. `serenata/parse/personal_data.py` is retired with it, and its constraint is not: Crony's equivalent is the `crony-eu/docs/sources/` allowlist and `crony-eu/scripts/check_no_data.py` |
| `serenata/normalise/` | **retire** | the twelve-table eForms model |
| `serenata/classify/` | **retire** | `single_bid_in_segment` at `RULE_VERSION` 4. Its shape — a rule that carries the baseline it was measured against — is what Crony's F1 is being rewritten to match |
| `serenata/survey/` | **retire** | measures eForms field usage |
| `serenata/cli.py`, `serenata/eforms.py`, `serenata/packages.py` | **retire** | the TED entry point and its shared readers |
| `tests/test_fetch_*`, `test_parse.py`, `test_normalise*`, `test_classify_*`, `test_survey.py`, `test_shape.py`, `test_dropped.py`, `test_eforms_xml_guard.py`, `test_package.py`, `test_sample_package.py`, `test_ted_contract.py`, `test_cli.py` | **retire** | they test the modules above and go in the same group as what they test |
| `tests/test_constraints.py` | **keep, then rewrite** | the licence, determinism, no-NLP and no-accusation gates apply to Crony unchanged. The eForms-specific import lists inside them do not |
| `tests/test_docs.py`, `tests/test_adr.py` | **keep** | they check documentation and decision records, and this transition is exactly the moment those checks earn their keep. `test_docs.py` is extended to cover `crony-eu/` in the reconciliation commit |
| `tests/test_automation.py`, `tests/test_merge_guard.py`, `tests/test_workflows.py` | **keep** | repository governance, not TED |
| `tests/test_hypothesis_admission.py` | **keep, then rewrite** | the rule that a classifier cannot merge without measured evidence survives; the metadata format it reads is Serenata's |
| `tools/generate_sdk_privacy.py` | **retire** | eForms SDK |
| `tools/merge_guard.py` | **keep** | ADR-0012, disabled and unchanged |

**Do not finish a retiring feature to preserve it.** Retirement happens in
coherent groups as the Crony check that replaces each group becomes available,
not in one deletion commit, and not before.

## Documentation

| path | disposition | why |
|---|---|---|
| `docs/adr/0001`–`0013` | **keep, with a disposition line** | historical numbering is preserved and no record is deleted. Each now carries a `- Transition:` line saying whether it is carried, retired or a continuing obligation |
| `docs/architecture.md`, `data-model.md`, `glossary.md`, `field-usage.md`, `dataset-shape.md`, `dropped-fields.md`, `personal-data.md`, `correction-links.md`, `correction-links.sql` | **keep as a record** | they describe a pipeline that is retiring, and they are the measured evidence behind it. They are marked as describing the retiring pipeline rather than edited into fiction |
| `docs/hypotheses/`, `docs/cases/` | **keep as a record** | what the project declined to publish is part of its method, and a rejected case keeps its file. That was true before the transition |
| `docs/corrections-policy.md`, `docs/corrections/` | **keep** | a policy for correcting a published finding, written before the first finding. Crony publishes nothing, so the policy is dormant, not void |
| `docs/data-reuse.md` | **keep** | TED's reuse terms bind the archive already fetched |
| `docs/counsel/` | **keep** | the unresolved instruction and the fact that no counsel is engaged |
| `docs/open-work.md`, `docs/known-issues.md`, `docs/decision-log.md` | **keep** | the open items outlive the pipeline; the two legal ones are the reason this ledger has a separate section for data |
| `docs/automation/` | **keep** | ADR-0012, disabled and unchanged |
| `.claude/skills/` | **keep, reconciled** | the working rules. `coding` and `case-research` describe a TED pipeline and are marked as such pending rewrite; `legal`, `communication` and `patreon` bind either project |
| `.github/agents/`, `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md` | **keep, reconciled** | reconciled in wording, not activated. No automation changes state in this transition |

## Data, backups and legal records

**These are not cleanup targets and their disposition is not decided here.**

`data/raw/ted/daily/2026/` holds five archived TED publication days. Those bytes
are personal data under [ADR-0010](adr/0010-raw-archive-retention.md), whose
lawful basis, retention period and DPIA question are unresolved and awaiting
counsel who is not engaged. `data/normalised/` and `data/flags/` are derived from
them and inherit the question.

Retiring the code that reads an archive does not dispose of the archive, does not
answer the lawful-basis question, and does not start or stop any retention clock.
Deleting it is also not automatically the safe answer: deletion is itself a
processing decision, and the instruction in
[`docs/counsel/`](counsel/README.md) is the route, not a judgement call made
while tidying a repository.

`data/sample/` is six synthetic notices used by the end-to-end test. It carries
no personal data and retires with that test.

## What this ledger does not cover

- The Serenata Europa name, the NLnet application, the Patreon campaign and any
  public commitment made under them. Those are commitments to people, and
  [ADR-0014](adr/0014-replace-serenata-with-crony.md) records that they need an
  answer before the retirement is announced rather than after.
- The GitHub repository name, its issues and its pull requests.
- Whether Crony eventually moves to the repository root or to a repository of
  its own.
