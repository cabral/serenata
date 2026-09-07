# Known issues and limitations

What the pipeline does not do, does incompletely, or does in a way that can
surprise. Each entry says whether it is planned work, a deliberate limit, or an
open question, and links to where it is tracked.

This is the list a reader should check before trusting an output or building on
the code. [`open-work.md`](open-work.md) is the companion — what is being built
and what each piece needs — and every open item there has an issue mirroring it.
[`CONTRIBUTING.md`](../CONTRIBUTING.md) is how to work on any of it.

## One classifier exists, and nothing it produces may be published

`classify` runs, and it runs one rule:
[`single_bid_in_segment`](hypotheses/single_bid_in_segment.md), which flags a
lot that drew a single bid in a market where single bids are rare. The measured
run over five archived publication days produces **96 flags from 8,132 lot
outcomes**. Eligible segments cover 4,283 outcomes (52.7%); 3,849 (47.3%) are
below the segment-size floor. These are base-rate and coverage measurements, not
empirical error rates.

**Version 4 is implemented and measured.** It rejects duplicate structural/join
keys, ambiguous and fractional tender counts, requires a present statistic code,
requires every buyer reference to resolve to a present, agreed country, and
excludes both corrected notices and notices announcing their own cancellation
(ADR-0013). The writer stages replacements and removes stale rule files on
success; multi-year replacement is not transactional. The two exclusions remove
27 lot outcomes here and no flags — a fact about this corpus, not a guarantee
about a larger one. The mandatory CI
`--require-current-measurements` check passes; passing it is metadata sanity,
not proof of the measurement. Any further real-data measurement still needs the
unresolved processing review.

**No flag has been published, and release remains blocked.** Open gates include:

- Corrections and withdrawals are handled — version 4 excludes notices another
  notice in the corpus corrects, and notices announcing their own cancellation,
  intended cancellation or suspension
  ([ADR-0013](adr/0013-correction-and-withdrawal-semantics.md)) — but the
  mechanism is **unexercised against real corrigenda**: only 1.6% of links
  resolve within a five-day archive, so a corrected notice whose corrigendum was
  published on an unheld day is still classified as live —
  [open-work #18](open-work.md#18-validate-correction-handling-against-a-continuous-archive).
- Whether an entity may be named at all when its natural-person status is
  unknown, and whether current processing is permitted —
  [open-work #11](open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status).
  The question is drafted for counsel at
  [`docs/counsel/11-natural-person-status.md`](counsel/11-natural-person-status.md),
  which asks for the processing half to be answered first; it is not sent and
  answers nothing yet.
- Privacy remediation, rebuilding affected datasets, and counsel review of
  current raw and derived holdings —
  [open-work #14](open-work.md#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields).
- Empirical false-positive assessment and full verification —
  [open-work #17](open-work.md#17-build-the-first-classifier).

The flag's false-positive profile is **predicted, not observed**: the hypothesis
lists potential innocent explanations and failure modes. One flag's arithmetic
has been re-derived from its archived notice; **none has
completed the verification protocol**. **No empirical false-positive rate has
been measured.**

Statements in this repository about what the data shows remain measurements of
the archive, not findings.

Tracked as milestone 2 in the [README](../README.md).

## Personal data can arrive in a field that is not a contact field

Constraint 2's drop list is **structural**: it rejects paths through
`cac:Contact`, `efac:UltimateBeneficialOwner` and `cac:TechnicalCommitteePerson`
wherever they appear. It does not catch a
publisher who types a contact address into a field that is not one.

They do. [`dataset-shape.md`](dataset-shape.md) counts it, regenerated from the
archive rather than remembered: across five publication days, **427
address-shaped values in 7 columns** that should hold a city, a registration
number, a street, a website or a description — and **139 shaped like a person's
own address** (`firstname.lastname@`). These pattern counts demonstrate a
retained-field leakage problem, not a complete inventory or a legal
classification of every value. That report carries counts, not the values.

**Widening the evidence changed where the problem is.** One day suggested a
scattering across identity columns; five days put **359 of the 427 in
`lot.description` and `procedure.description`** — free text, where a buyer
writes "questions to firstname.lastname@example.org". Those two columns are
carried as provenance and no classifier reads them (constraint 5), which bounds
their use in classification but does not remove them from current storage.

The explicit-natural-person Company/TouchPoint `WebsiteURI` suppression gap is
now fixed in code. **Stored datasets have not been rebuilt**, and that fix does
not address all retained-field leakage or unknown natural-person status.

Nonpublication limits dissemination; it does not remove processing obligations
or security risks. Collection and storage are processing under
[GDPR Article 4(2)](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng).
The value-level problem needs a counsel-reviewed policy, implementation, tests
and remediation of existing copies. Rejecting values, redacting matches or
holding rows for review have different consequences; neither a regex nor a
successful rebuild proves anonymity. Tracked as
[open-work #14](open-work.md#14-decide-what-to-do-about-personal-data-in-fields-that-are-not-contact-fields)
and issue [#22](https://github.com/cabral/serenata/issues/22).

## The notice UUID is not unique, and looks like it should be

`notice/cbc:ID` is a UUID and reads like a primary key. It is not one: **two
UUIDs each appear twice in OJ S 157/2026**, published the same day under
different notice numbers, with the same contract folder, issue date and
subtype — one notice published twice.

Nor is it a same-day artefact. Across the five days now measured, **six UUIDs
carry two publications each, and one of those six spans two different
publication dates** — so a date does not disambiguate them either.

Every table is therefore keyed on `source_publication_id`, which is unique
across all 19,180 notices measured. `source_notice_id` is kept on every row
because it is what links a corrigendum to what it corrects, and **anything
joining on it may match more rows than it means to**.

## Legacy TED notices are refused, not parsed

Notices published before eForms became mandatory during 2024 use the legacy TED
schemas, and `parse` **raises rather than reading them**. The mapping from legacy
elements into the data model has never been measured, because no archived
package contains a legacy notice, and guessing which of those fields can carry a
person's name is the guess constraint 2 exists to forbid.

The eForms prototype can run without legacy support, but the broader
ingestion/normalisation milestone remains incomplete. Coverage is limited to
eForms notices; it is not the full historical TED record.

Tracked as [open-work #3](open-work.md#3-document-and-drop-the-fields-that-can-name-a-natural-person)
and issue [#13](https://github.com/cabral/serenata/issues/13).

## Two thirds of withheld fields are marked; the rest are named, not marked

A publisher may withhold a field through `efac:FieldsPrivacy`, and eForms
publishes the withheld value rather than omitting it — an amount as `-1`, a bid
count as the code `unpublished` with the number `-1`. A classifier reading those
as numbers reads a lawful deferral as a negative price or a negative bid count.

The eForms SDK says which element each privacy code names, and that table is
generated into `serenata/normalise/sdk_privacy.py`
([ADR-0008](adr/0008-eforms-sdk-privacy-mapping.md)). **212 of the 215 privacy
blocks in OJ S 157/2026 set a column's status to `withheld`** — 74 payable
amounts, 44 notice totals, 42 variant indicators, 28 framework values, 22
highest and lowest tender amounts, 2 statistics blocks and 1 decision reason.

**The remaining 3 are recorded but not acted on.** All three are told apart from
another field only by an XPath predicate this project's paths do not carry, so
acting on them would mark the wrong column. Sixteen of the SDK's 47 codes
resolve here; the rest name fields this model has no column for. Every block is
a `field_privacy` row either way, and `privacy.UNUSABLE` names each gap with its
reason.

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

Related: [`field-usage.md`](field-usage.md) reports 323 paths appearing "only as
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
superseded notice is a flag against something that no longer stands. An ADR
alone is insufficient: deterministic code must apply correction/version links
to the eligible population, baselines and affected flags. Tests must cover
corrections, withdrawals, supersession, ambiguous/missing links, stale-output
removal and rerun identity. Tracked as
[open-work #6](open-work.md#6-handle-corrected-and-withdrawn-notices) and issue [#15](https://github.com/cabral/serenata/issues/15).

## Whether an organisation is a person is often unknown

`efbc:NaturalPersonIndicator` is **absent from about 90% of notices**, and absent
is "not provided", never "false". Where it is present and true, the organisation's
specified identifying values are suppressed. Where it is absent, the record is kept and
whether that organisation is a company or a private individual trading in their
own name is not known from the notice.

Even when names are suppressed, notice-scoped opaque keys and source links can
identify people indirectly. Under GDPR Article 4(1) and Recital 26, removing a
name is not sufficient where reasonably likely linkage identifies the person.
The notice-level absence rate is not an organisation-level prevalence estimate.

Current ingestion and storage require assessment, not just publication of a
flag. Processing and publication rules remain
[open-work #11](open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status)
and issue [#14](https://github.com/cabral/serenata/issues/14). Neither official
publication nor a role code proves that an entity is a legal person.

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
this repository makes many. Generated measurements, manual measurements and
classifier-version evidence have different limits; none is a privacy or legal
certification.

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

**Measured by hand, not continuously checked.** The performance figures above
depend on the machine as well as the data; they are not byte-reproducible.
Each was measured with a throwaway script, and the method is stated beside it
so it can be repeated rather than trusted.

**Classifier measurements are version-specific.** The hypothesis retains the
historical v1 measurement and its query revision. The current companion SQL
targets v2; neither rerunning that SQL nor passing fixture tests reproduces or
updates the historical measurement by itself.

The *properties* behind the generated numbers are also asserted, over notices
carrying each case deliberately: `tests/test_sample_package.py` checks that a
withheld count is not a number, that the notice UUID is not unique, that a sole
trader's specified identity fields are suppressed while its notice-scoped key is
kept, and that every table's key is unique in those fixtures. These are bounded
checks, not proof of all possible inputs or anonymity: the key remains
source-linkable, and other retained fields can carry personal data.

## A published dataset would carry the writer's version

Parquet files record which library wrote them, so upgrading pyarrow changes the
bytes without changing a row. `uv.lock` pins it and the rerun test compares
outputs written by one version, which is what determinism means here: the same
code and the same data produce the same bytes. A dependency bump is a change of
code, and it will show up as one.

## The raw archive and derived holdings need a lawful-basis and retention review

A contact name, e-mail and telephone appear in **99.9%** of notices, and the
archive keeps whole publication days byte-for-byte for reproducibility. It holds
personal data; retained-field leakage means derived datasets can too. Private,
gitignored storage does not establish a lawful basis or effective security.

[ADR-0010, amended 2026-09-05](adr/0010-raw-archive-retention.md), withdraws its
earlier anonymity and legal-basis assurances. Article 6(1)(f) is a proposed
basis, not a completed necessity/balancing assessment. **Counsel review remains
unresolved for current private holdings**, including raw and derived data,
retention under Article 5, Article 14 transparency and any exception, and whether
Article 35 requires a DPIA. No completed DPIA or compliance certification is
claimed. The [TED reuse terms](https://ted.europa.eu/en/legal-notice) do not
supply this project's GDPR basis.

The original policy linked retention to published datasets but did not settle
today's unpublished holdings. Its first annual review date, **2027-09-03**, is
not permission to retain until then or to defer current assessment. Record the
counsel-reviewed retention decision and disposition of existing copies here.
Rights requests and incidents require assessment across all affected holdings,
not only the archive. ADR-0010 records the distinct Article 33 and 34 breach
notification thresholds; nonpublication does not remove those duties.

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
