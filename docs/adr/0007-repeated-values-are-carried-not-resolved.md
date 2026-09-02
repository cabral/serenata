# ADR-0007: Carry repeated values, never pick one

- Status: accepted
- Date: 2026-09-02

## Context

[`data-model.md`](../data-model.md) gave most of its columns one source path
each, which reads as a promise that one notice yields one value per column. The
first attempt to build those columns from real records showed how often that is
false. Measured over the 3,190 notices of OJ S 157/2026:

| Path | Repeats in |
|---|---|
| `cbc:ContractingSystemTypeCode` (lot) | 8,028 of 8,624 lots, always exactly 2 |
| `efac:LotTender/cbc:ID` (lot result) | 989 lot results, up to **683** in one |
| `efac:SettledContract/cbc:ID` (lot result) | 584 lot results, up to 679 |
| `efac:ReceivedSubmissionsStatistics` | 2,866 lot results, up to 12 blocks |
| `cac:RealizedLocation` (lot, notice) | 431 records, up to 59 country codes |
| `cbc:CompanyID` (organisation) | 402 organisations, up to 5 |
| `cbc:Name` / `cbc:Description` (title, description) | 77 procedures, 115 organisations |
| `efac:Tenderer/cbc:ID` (tendering party) | 130 parties, up to 15 |

None of this is exotic data. A framework awarded to many suppliers is one lot
result naming many tenders; a lot performed in many places carries many
locations; a bilingual member state publishes a title twice.

`Record.value()` already refuses to resolve these — it raises rather than
returning an arbitrary one of several, for the reason that a classifier reading
an arbitrary bid count or award criterion is the failure this project cannot
afford. That refusal moved the question rather than answering it: the normalise
stage still has to put something in a column.

Three shapes of repetition turned up, and they do not want the same answer:

- **A bare repeated value.** Several contracting-system codes, several
  registration numbers, several tender references. Order matters, pairing does
  not.
- **A repeated block with structure inside it.** A statistic is a code *and* a
  number; a location is a country *and* a NUTS code; a privacy entry is an
  identifier, a reason and sometimes a date. The pairing is the information.
- **The same value published once per language.** Not really a repeat: one
  fact, several renderings. In all 37,498 title, description and organisation
  name fields measured, the notice's own `cbc:NoticeLanguageCode` is among the
  languages offered.

## Decision

**A repeated path is carried, never resolved by picking one.** Three
representations, chosen by which shape the repetition has:

1. **A bare repeated value becomes a `SET` column**: a Parquet `list<string>`
   in document order, named plurally — `contracting_system_codes`,
   `company_ids`, `winning_tender_refs`, `contract_refs`, `tender_refs`. Its
   status column describes the set: `present` if it holds a value, `absent` if
   the path never appeared.

2. **A repeated block becomes its own table**, one row per block, keyed by the
   record it sits in plus the block's position in document order:
   `lot_result_statistic`, `realized_location`, `field_privacy`, and
   `organisation_role`, which was already an edge table for the same reason.
   Each row keeps the pairing the block gave it.

3. **Free text takes the notice's own language**, and says which it took in a
   `<column>_language` companion. Where the notice's language is not among
   those offered — not observed, but definable — the first in document order
   wins.

**A column declared to hold one value raises `RepeatedValue` when it meets
several.** It does not pick, and it does not silently drop. That case did not
occur once across the package after the columns above were reshaped, so raising
reports drift between the model and the data rather than rejecting ordinary
notices. The notice is counted as `unnormalised` and named; the run continues.

## Consequences

- Classifiers reading a set column unnest it. `list_contains(company_ids, …)`
  and `UNNEST` are ordinary DuckDB, and the alternative was a column whose value
  depended on which sibling the publisher wrote first.
- Four tables exist that the original nine did not describe. The model is
  twelve tables, and `data-model.md` says why each of the new ones is a table
  rather than a column.
- **Two parallel list columns were considered and rejected** for the code/value
  pairs. They would preserve the values and lose the guarantee: pairing by list
  position is correct only while both lists stay aligned, and nothing in the
  format enforces that. A row per block cannot come unpaired.
- **A long-format value table was considered and rejected**, for the reason
  ADR-0006 gives for rejecting it for statuses: every read of an ordinary
  column would need a join, and a join that can be forgotten is a safeguard that
  will be.
- A title in a set of languages is stored once, in the notice's language. The
  others are in the archived source, which is the ground truth; the dataset does
  not claim to be a translation memory. Anything comparing titles across
  languages reads the archive, not this.
- The measurements above are one publication day. A repeat appearing in a
  column this ADR left scalar shows up as a `RepeatedValue` rather than as a
  wrong number, which is the failure mode this design is chosen for.

## What would change this

- **A `RepeatedValue` in ordinary data.** Then that column joins the set or
  block treatment, and the measurement that found it goes in `data-model.md`.
- **A classifier needing every language of a title.** The rule above stores one
  and names it; storing all of them means a `procedure_title` table, and that is
  a bigger change than a column.
- **Sets becoming a query burden.** If unnesting turns out to be where
  classifier bugs live, a child table per set column is the fallback — more
  rows, no lists. Measure before believing it.
