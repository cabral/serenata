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

They do. [`dataset-shape.md`](dataset-shape.md) counts it, regenerated from the
archive rather than remembered: **46 address-shaped values in 7 columns** that
should hold a city, a registration number, a street, a website or a description
— and **13 shaped like a person's own address** (`firstname.lastname@`), which
is personal data landing in the dataset through a field the drop list has no
reason to reject. That report carries counts and never values, for the same
reason this entry does.

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

## Two thirds of withheld fields are marked; the rest are named, not marked

A publisher may withhold a field through `efac:FieldsPrivacy`, and eForms
publishes the withheld value rather than omitting it — an amount as `-1`, a bid
count as the code `unpublished` with the number `-1`. A classifier reading those
as numbers reads a lawful deferral as a negative price or a negative bid count.

The eForms SDK says which element each privacy code names, and that table is
generated into `serenata/normalise/sdk_privacy.py`
([ADR-0008](adr/0008-eforms-sdk-privacy-mapping.md)). **143 of the 215 privacy
blocks in OJ S 157/2026 now set a column's status to `withheld`** — 74 payable
amounts, 42 variant indicators, 11 highest and 11 lowest tender amounts, 2
statistics blocks and 1 decision reason.

**The remaining 72 are recorded but not acted on.** Sixty-nine name a field this
model has no column for — the notice's total amount, withheld 44 times in one
day, and the framework-agreement values — and three are told apart from another
field only by an XPath predicate this project's paths do not carry, so acting on
them would mark the wrong column. Eleven of the SDK's 47 codes resolve here.
Every block is a `field_privacy` row either way, and `privacy.UNUSABLE` names
each gap with its reason.

**A value that looks withheld and a value that was declared withheld are
different facts, and they do not always agree.** In one publication day: two
payable amounts declared non-public carry a value other than `-1`, one lot
result carries `1` for both its declared-non-public highest and lowest tender
amount, and two settled contracts carry a contract reference of `-1` that no
block declares. The status follows the declaration;
[`dataset-shape.md`](dataset-shape.md) counts `-1` by column independently, so a
classifier author can see both. **An amount still has to be read with its
status**, and amounts are stored as published strings so nothing silently turns
a sentinel into a price.

What would close the gap is the model gaining the columns the refused codes
name, which makes most of them resolve with no other change.

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

## No test reads a notice TED actually published

`data/sample/` now carries six notices in the layout a real package uses, and
`tests/test_sample_package.py` runs the whole pipeline over them — archive
layer, parse, normalise, Parquet, DuckDB. That closed the larger gap: something
in CI reads a package rather than a notice built inside the test that reads it.

What it does not close is the tripwire. **Those notices are synthetic**, written
by this project to be structurally faithful, so a change in what TED emits — a
renamed element, a new code list, a shape nobody anticipated — would not fail
this build. Real notices cannot be committed for it: a contact name, e-mail and
telephone appear in 99.9% of them, and putting one in a public repository to
test that the pipeline removes personal data would leave the data in the
repository permanently.

The tripwire for that now exists: `tests/test_ted_contract.py` asserts TED's
documented interfaces — the `limit` cap, the `ojs-number` field, the shape of a
daily package — against the live service, weekly, outside the offline suite
(`uv run pytest -m contract`).

**It runs on a schedule, so it tells you within a week, not on the commit.** And
it watches the *interfaces*, not the notices: a new eForms element, a code list
gaining a value, a member state populating a field nobody has seen would all
pass it. Those show up when the archive is re-surveyed, which is a reason to
re-run `python -m serenata.survey` over new packages rather than to trust the
last report.

## Which figures are generated, and which are not

A claim about the data is only as good as the last time someone checked it, and
this repository makes many. They fall in two groups, and only one of them is
safe.

**Generated from the archive, and regenerable by anyone who has one.** Two
documents, both produced by `python -m serenata.survey`, both byte-reproducible
against the same packages, and both naming the packages they measured with their
SHA-256:

- [`field-usage.md`](field-usage.md) — which element paths notices populate, in
  how many member states, and how many times a path repeats inside one record.
  `tests/test_data_model.py` and `tests/test_normalise_model.py` fail if the
  model stops agreeing with it.
- [`dataset-shape.md`](dataset-shape.md) — rows per table, how populated every
  column is, withheld sentinels, address-shaped values in columns that should
  not hold them, and whether any table has rows sharing a key.

**Measured by hand, and not checked by anything.** What is left is the cost
table above — wall clock, peak memory, bytes on disk — which cannot be
byte-reproducible because it is a property of the machine as much as of the
data. Each figure there was measured with a throwaway script, and the method is
stated beside it so it can be reproduced rather than trusted.

The *properties* behind the generated numbers are also asserted, over notices
carrying each case deliberately: `tests/test_sample_package.py` checks that a
withheld count is not a number, that the notice UUID is not unique, that a sole
trader keeps only an opaque key, and that every table's key is unique. So the
shape of the data the pipeline promises to handle is checked on every push, and
the counts from a real publication day are a command away.

## A published dataset would carry the writer's version

Parquet files record which library wrote them, so upgrading pyarrow changes the
bytes without changing a row. `uv.lock` pins it and the rerun test compares
outputs written by one version, which is what determinism means here: the same
code and the same data produce the same bytes. A dependency bump is a change of
code, and it will show up as one.

## 65 commits in the history carry no sign-off

[`CONTRIBUTING.md`](../CONTRIBUTING.md) asks for a Developer Certificate of
Origin sign-off on every commit, and until 2026-09-03 nothing checked it: **one
commit out of 66 carried the trailer**, the one that added the rule.

It is enforced now. A hook adds the trailer, `.github/workflows/dco.yml` fails a
pull request whose commits lack it, and
[ADR-0009](adr/0009-contribution-provenance.md) records what signing means on a
patch written with an assistant.

**What stays true is the history.** The check is scoped to the commits a pull
request adds, so those 65 remain unsigned — rewriting published history to
satisfy a policy adopted afterwards would change every hash and prove nothing.
They are all by the maintainer, who holds the copyright in them, so the
provenance question they leave open is narrow. Anyone auditing licensing should
read the sign-off record as starting on 2026-09-03 rather than covering the
project.

## CI runs on deprecated action runtimes

`actions/checkout@v4` and `astral-sh/setup-uv@v6` target Node 20, which GitHub
now forces onto Node 24. CI is green and will break when that forcing stops.
Tracked as [issue #3](https://github.com/cabral/serenata/issues/3).
