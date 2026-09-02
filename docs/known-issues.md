# Known issues and limitations

What the pipeline does not do, does incompletely, or does in a way that can
surprise. Each entry says whether it is planned work, a deliberate limit, or an
open question, and links to where it is tracked.

This is the list a reader should check before trusting an output or building on
the code. [`open-work.md`](open-work.md) is the companion — what is being built
and what each piece needs — and every open item there has an issue mirroring it.
[`CONTRIBUTING.md`](../CONTRIBUTING.md) is how to work on any of it.

## The pipeline stops after parse

There is **no normalised dataset, no classifier and no flag**. `fetch` archives
packages, `parse` turns them into typed records, and nothing yet writes Parquet
or evaluates anything. Statements in this repository about what the data shows
are measurements of the archive, not findings.

Tracked as milestone 1 in the [README](../README.md) and issue [#11](https://github.com/cabral/serenata/issues/11);
normalise is the next stage.

## Legacy TED notices are refused, not parsed

Notices published before eForms became mandatory during 2024 use the legacy TED
schemas, and `parse` **raises rather than reading them**. The mapping from legacy
elements into the data model has never been measured, because no archived
package contains a legacy notice, and guessing which of those fields can carry a
person's name is the guess constraint 2 exists to forbid.

Nothing is blocked by this today. It bounds the pipeline to notices from roughly
late 2024 onward, which is most of what matters for current procurement and none
of the historical record.

Tracked as [open-work #3](open-work.md#3-document-and-drop-the-fields-that-can-name-a-natural-person)
and issue [#13](https://github.com/cabral/serenata/issues/13).

## The survey and the parse stage disagree on what a notice is

`serenata.survey` decides a member is eForms from its **filename** — eight
digits and a year — while `serenata.parse` decides from the **root element's
namespace**. An eForms document delivered under a legacy-style filename is
counted by the survey as a skipped legacy notice and parsed by parse.

In the surveyed package this changes nothing: it contains 3,190 eForms notices
and zero legacy ones, and every filename matches its content. But
[`field-usage.md`](field-usage.md)'s counts rest on the filename heuristic, so
the figure to quote is "eForms-named notices", not "eForms notices". Parse's
test is the better one and the survey should adopt it — issue [#18](https://github.com/cabral/serenata/issues/18).

## `not_applicable` is never derived

[ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md) defines five absence
states. Four are produced. `not_applicable` — a field the notice subtype makes
meaningless — needs the eForms notice-subtype rules, which live in the SDK the
offline pipeline does not carry.

Until it does, an inapplicable field records `absent`. That understates what is
known rather than overstating it, and **nothing downstream may read `absent` as
proof a field was applicable**.

## `empty` is supported but never observed

The same ADR's `empty` status — an element present and blank — is produced by
the parser and appears in **no notice measured**: zero blank leaves among all
897,471 in OJ S 157/2026. The status is kept because conflating a blank element
with an absent one would be silently wrong and costs nothing to avoid, not
because this package shows it happening.

Related: [`field-usage.md`](field-usage.md) reports 296 paths appearing "only as
containers or blank elements". The survey cannot tell those apart; parse can,
and all of them are containers. The report's wording is hedged rather than
wrong, and its numbers are unaffected.

## Text on a container element is not represented

An element that becomes a record has no field of its own to hold stray text, so
text directly on one of the six container paths is dropped. The case is
enumerable, structurally meaningless in eForms, and was measured at **zero
occurrences**. Text on any other element with children is recorded.

## Organisations are not resolved across notices

`ORG-0001` identifies an organisation **within one notice**. The same buyer is a
different local id in the next day's notice, and this project does not yet join
them. `company_id` — the national registration number, present in 99.9% of
notices — is the obvious candidate and is carried as an attribute, **not as a
key**: national schemes differ and the same body appears under variant numbers.

Any count of "contracts awarded to X across notices" is therefore an argument
the caller has to make, not something the model provides. Entity resolution is
milestone 3.

## Corrections and withdrawals are captured but not applied

A notice can be corrected or withdrawn after publication. `notice.changed_notice_id`
records the corrigendum link, and nothing yet acts on it: the archive keeps
saying what was published that day, which is correct as history and wrong as
current state.

This has to be settled before any finding is published, because a flag against a
superseded notice is a flag against something that no longer stands. Tracked as
[open-work #6](open-work.md#6-handle-corrected-and-withdrawn-notices) and issue [#15](https://github.com/cabral/serenata/issues/15).

## Whether an organisation is a person is often unknown

`efbc:NaturalPersonIndicator` is **absent from about 90% of notices**, and absent
is "not provided", never "false". Where it is present and true, the organisation's
identifying values are suppressed. Where it is absent, the record is kept and
whether that organisation is a company or a private individual trading in their
own name is not known from the notice.

Ingestion cannot resolve this. Whether a flag may be *published* about such an
entity is [open-work #11](open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status),
and issue [#14](https://github.com/cabral/serenata/issues/14); it blocks the first finding rather than the pipeline.

## Parse is slower and heavier than the survey

Per daily package of 3,190 notices: parse takes about 54s and peaks at 89 MB,
against the survey's 21s and 4.3 MB. Both stream; neither holds the document.
The difference is that parse keeps every value it extracts while the survey keeps
counts, and that it maintains sibling indices for repeat pairing — `child_counts`
allocates a dictionary per element, roughly 1.7 million per package, which is the
likeliest remaining win if this ever matters.

At this cost a year of notices is a few hours, so it is recorded rather than
worked on.

## No command line for parse, and no committed sample

`serenata fetch` exists; parse is a library only, so exercising it means writing
Python. And `tests/fixtures/` and `data/sample/` are empty — the parse tests
build their notices in memory, which keeps a fixture and the test that reads it
in one file but means there is no end-to-end run against a real archived package
in CI.

Tracked as [open-work #7](open-work.md#7-commit-a-small-sample-package-for-end-to-end-tests)
and issue [#16](https://github.com/cabral/serenata/issues/16); the CLI command is noted in [#4](open-work.md#4-build-the-parse-stage).

## Sign-off is asked for, not enforced

[`CONTRIBUTING.md`](../CONTRIBUTING.md) requires a Developer Certificate of
Origin sign-off on every commit, which is how contributions are licensed. There
is **no CI check for it**: a pull request without one passes the build and gets
asked in review. Fine at this size, and worth automating before the project has
more contributors than reviewers.

## CI runs on deprecated action runtimes

`actions/checkout@v4` and `astral-sh/setup-uv@v6` target Node 20, which GitHub
now forces onto Node 24. CI is green and will break when that forcing stops.
Tracked as [issue #3](https://github.com/cabral/serenata/issues/3).
