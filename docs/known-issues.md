# Known issues and limitations

What the pipeline does not do, does incompletely, or does in a way that can
surprise. Each entry says whether it is planned work, a deliberate limit, or an
open question, and links to where it is tracked.

This is the list a reader should check before trusting an output or building on
the code. [`open-work.md`](open-work.md) is the companion — what is being built
and what each piece needs — and every open item there has an issue mirroring it.
[`CONTRIBUTING.md`](../CONTRIBUTING.md) is how to work on any of it.

## The pipeline stops after normalise

There is **no classifier and no flag**. `fetch` archives packages, `parse` turns
them into typed records, `normalise` writes those as Parquet, and nothing yet
evaluates anything. Statements in this repository about what the data shows are
measurements of the archive, not findings.

Tracked as milestone 2 in the [README](../README.md).

## Personal data can arrive in a field that is not a contact field

Constraint 2's drop list is **structural**: it rejects paths through
`cac:Contact`, `efac:UltimateBeneficialOwner` and `cac:TechnicalCommitteePerson`
wherever they appear. That is the right shape for the rule and it cannot catch a
publisher who types a contact address into a field that is not one.

They do. Scanning the normalised package for email-shaped values finds **46 of
them in 7 columns** that should hold a city, a registration number, a street, a
website or a description — and **13 are shaped like a person's own address**
(`firstname.lastname@`), which is personal data landing in the dataset through a
field the drop list has no reason to reject.

Nothing is published yet, so this is not yet an exposure; it is one before the
first dataset release. It also cannot be fixed by adding paths to the list,
because the problem is the value rather than the field. The options — reject the
value, redact the match, or flag the row for review — differ in what they lose,
and choosing needs a decision recorded rather than a regex added quietly. Not
yet tracked as an issue.

## The notice UUID is not unique, and looks like it should be

`notice/cbc:ID` is a UUID and reads like a primary key. It is not one: **two
UUIDs each appear twice in OJ S 157/2026**, published the same day under
different notice numbers, with the same contract folder, issue date and
subtype — one notice published twice.

Every table is therefore keyed on `source_publication_id`, which is unique
across all 3,190. `source_notice_id` is kept on every row because it is what
links a corrigendum to what it corrects, and **anything joining on it may match
more rows than it means to**.

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

## A withheld value is published as `-1`, and only sometimes marked

A publisher may withhold a field through `efac:FieldsPrivacy`, and eForms
publishes the withheld value rather than omitting it: **72 tender payable
amounts, 42 notice total amounts, 10 highest and 10 lowest tender amounts in
OJ S 157/2026 carry `-1`**, and a withheld bid count carries the code
`unpublished` with the number `-1`. A classifier reading those as numbers reads a
lawful deferral as a negative price or a negative bid count.

The `field_privacy` table records every such block with the element it sits
inside. The **status** is derived only where containment proves the target — a
privacy block inside a statistics block marks that block, so those rows read
`withheld`. Everywhere else the block names its target with an eForms field
identifier (`win-ten-val`, `ten-val-low`, `max-val`), and mapping those to
columns needs the eForms SDK this pipeline does not carry.

Until it does, a withheld amount reads `present` with the value `-1`. Amounts
are stored as published strings rather than numbers, so nothing silently turns
the sentinel into a price, but **a classifier reading an amount must exclude
`-1` explicitly**. This is the first thing to build after the normalise stage.

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
them. `company_ids` — the national registration numbers, present in 99.9% of
notices — is the obvious candidate and is carried as an attribute, **not as a
key**: national schemes differ, the same body appears under variant numbers, and
402 organisations in one package carry more than one number.

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

## Normalise holds a whole package in memory

The stage accumulates one package's rows as Python dictionaries and sorts them
before writing, because sorting is what makes the output byte-stable and a
stable sort is what keeps ties in document order. One daily package peaks at
**360 MB** for 98,629 rows, against parse's 89 MB, and takes 12 seconds.

A year of notices is ~250 packages, and they are normalised one at a time, so
the peak is per package rather than cumulative. If a package ever arrives that
does not fit, the fix is to accumulate Arrow batches rather than dictionaries;
the sort has to stay.

## Parse is slower and heavier than the survey

Per daily package of 3,190 notices: parse takes about 54s and peaks at 89 MB,
against the survey's 21s and 4.3 MB. Both stream; neither holds the document.
The difference is that parse keeps every value it extracts while the survey keeps
counts, and that it maintains sibling indices for repeat pairing — `child_counts`
allocates a dictionary per element, roughly 1.7 million per package, which is the
likeliest remaining win if this ever matters.

At this cost a year of notices is a few hours, so it is recorded rather than
worked on.

## No committed sample package

`tests/fixtures/` and `data/sample/` are empty: the parse and normalise tests
build their notices in memory, which keeps a fixture and the test that reads it
in one file but means **no test reads a real archived package**. The rerun
identity test proves determinism over synthetic notices, and the figures quoted
here for the real package were measured by hand rather than in CI.

Tracked as [open-work #7](open-work.md#7-commit-a-small-sample-package-for-end-to-end-tests)
and issue [#16](https://github.com/cabral/serenata/issues/16).

## A published dataset would carry the writer's version

Parquet files record which library wrote them, so upgrading pyarrow changes the
bytes without changing a row. `uv.lock` pins it and the rerun test compares
outputs written by one version, which is what determinism means here: the same
code and the same data produce the same bytes. A dependency bump is a change of
code, and it will show up as one.

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
