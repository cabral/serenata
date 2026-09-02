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
and choosing changes what "dropped at ingestion" means, which is a decision for
counsel rather than a regex added quietly. Tracked as
[open-work #14](open-work.md#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields)
and issue [#22](https://github.com/cabral/serenata/issues/22).

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
`-1` explicitly**. This is the first thing to build after the normalise stage:
[open-work #13](open-work.md#13-derive-the-withheld-status-from-the-eforms-field-identifiers)
and issue [#21](https://github.com/cabral/serenata/issues/21).

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

## What each stage costs, and how that was measured

One daily package, 3,190 notices, on one laptop. The method matters more than
the numbers: `tracemalloc` reports what Python allocated and **triples the
runtime while it is on**, so a figure measured under it is not comparable to one
that was not. Earlier versions of this file quoted times measured with it
running beside memory figures that needed it, which made the pipeline look four
times slower than it is.

| Stage | Wall clock | Peak RSS | Python allocations (under `tracemalloc`) |
|---|---:|---:|---:|
| survey | 6.0s | 41 MB | 9 MB |
| parse | 7.9s | 111 MB | 94 MB |
| normalise | 11.5s | 339 MB | 222 MB |

Each stage does strictly more than the one above it. The survey keeps counts;
parse keeps every value it extracts, plus the sibling indices that let repeated
blocks pair; normalise holds a package's rows as dictionaries so it can sort
them, and sorting is what makes the output byte-stable.

Two things worth knowing if this ever matters:

- Parse's `child_counts` allocates a dictionary per element, roughly 1.7 million
  per package. That is the likeliest remaining win.
- Normalise's peak is per package, not cumulative — packages are normalised one
  at a time — so a year of notices costs the same peak and about an hour of wall
  clock, not more memory. If a package ever arrives that does not fit,
  accumulating Arrow batches rather than dictionaries is the fix; the sort has to
  stay.

At this cost a year of notices is an hour or two, so this is recorded rather
than worked on.

## No committed sample package, so CI never reads a real notice

`tests/fixtures/` and `data/sample/` are empty: the parse and normalise tests
build their notices in memory, which keeps a fixture and the test that reads it
in one file but means **no test reads a package TED actually published**. The
rerun-identity test proves determinism over synthetic notices.

Tracked as [open-work #7](open-work.md#7-commit-a-small-sample-package-for-end-to-end-tests)
and issue [#16](https://github.com/cabral/serenata/issues/16).

## Some figures in these documents are measured by hand, and can rot

A claim about the data is only as good as the last time someone checked it, and
this repository makes many. They fall in two groups, and only one of them is
safe.

**Generated, and checked on every run.** Everything in
[`field-usage.md`](field-usage.md) — presence, countries, and how many times a
path repeats inside a record. `serenata.survey` produces that file from the
archive, regenerating it against the same packages reproduces it byte for byte,
and `tests/test_data_model.py` and `tests/test_normalise_model.py` fail if the
model stops agreeing with it.

**Measured by hand, and not checked by anything.** The normalise stage's
figures: 98,629 rows from one package, 4.2 MB, 46
email-shaped values in 7 columns, 72 payable amounts published as `-1`, two
notice UUIDs appearing twice. Each was measured against the local archive with a
throwaway script that is not in the repository. **They were true when written
and nothing will tell you when they stop being.** A second publication day would
move most of them.

The fix is the same one as above — a committed sample package makes a smaller
version of each measurement a test — plus promoting the useful ones into
generated output the way `field-usage.md` already is. Until then, treat an
unsourced number in these documents as a measurement with a date on it, not as a
property of the pipeline.

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
asked in review.

Fine at this size, and the reason to fix it is provenance rather than process —
an unsigned commit in the history is a contribution whose licensing nobody
recorded, and it is far easier to ask at the time than to chase later. The check
is a few lines in the existing workflow and costs nothing to run (GitHub Actions
is free for public repositories), so this is unstarted rather than blocked.

## CI runs on deprecated action runtimes

`actions/checkout@v4` and `astral-sh/setup-uv@v6` target Node 20, which GitHub
now forces onto Node 24. CI is green and will break when that forcing stops.
Tracked as [issue #3](https://github.com/cabral/serenata/issues/3).
