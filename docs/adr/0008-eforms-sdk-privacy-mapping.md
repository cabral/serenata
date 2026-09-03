# ADR-0008: Vendor the eForms SDK's privacy mapping, and refuse what it cannot place

- Status: accepted
- Date: 2026-09-03

## Context

eForms lets a publisher mark a field non-public, and it does **not** omit the
value. It publishes a placeholder and records the withholding separately, in an
`efac:FieldsPrivacy` block that names its target with a code:

```xml
<efac:FieldsPrivacy>
  <efbc:FieldIdentifierCode>win-ten-val</efbc:FieldIdentifierCode>
  <cbc:ReasonCode>eo-int</cbc:ReasonCode>
</efac:FieldsPrivacy>
<cac:LegalMonetaryTotal>
  <cbc:PayableAmount currencyID="SEK">-1</cbc:PayableAmount>
</cac:LegalMonetaryTotal>
```

[ADR-0006](0006-absence-is-recorded-not-collapsed.md) provides for exactly this
with a `withheld` status, and until now the normalise stage could almost never
set it. It derived `withheld` only where containment proved the target — a
privacy block *inside* a statistics block marks that block — which covered the
bid count and nothing else. Everywhere else the code was recorded in
`field_privacy` and the column went on reading `present`.

Measured over the 3,190 notices of OJ S 157/2026: **215 privacy blocks, 14
distinct codes.** The largest group, 74 of them, withholds a winning tender's
payable amount. So the amount a classifier reads was published as `-1` and
labelled `present`, and every classifier author would have had to remember to
exclude it — which is precisely what ADR-0006 exists to make unnecessary.

Nothing in a notice says which element a code names. That relation is defined in
the **eForms SDK**, whose `fields/fields.json` gives each withholdable field a
`privacy.code`:

```json
"id": "BT-720-Tender",
"xpathAbsolute": "/*/…/efac:LotTender/cac:LegalMonetaryTotal/cbc:PayableAmount",
"privacy": { "code": "win-ten-val", … }
```

## Decision

**Vendor that relation, generated from the SDK, and refuse every code the join
cannot place unambiguously.**

- [`tools/generate_sdk_privacy.py`](../../tools/generate_sdk_privacy.py) fetches
  `fields.json` and writes `serenata/normalise/sdk_privacy.py`. The generator is
  the only thing that reaches the network; the file it writes is data, and the
  pipeline reads it offline (constraint 4).
- `serenata/normalise/privacy.py` joins that table onto the columns of
  `serenata/normalise/model.py` **at import**, rather than the generator writing
  column names into the vendored file. A renamed column changes the join instead
  of leaving a stale literal pointing at nothing, and a test asserts every
  resolved target still names a real column.
- A code resolves only when it is unambiguous. Two things stop it, and both are
  read from the SDK rather than guessed at:
  - **A predicate that mattered.** The SDK identifies a field by an XPath that
    may carry one, and `pro-acc` and `dir-awa-jus` are the *same element*
    distinguished only by `@listName`. This project's paths carry no predicates
    ([ADR-0005](0005-element-paths-as-provenance.md)), so where stripping a
    predicate merges two SDK fields the code is refused. The generator computes
    those collisions across all 1,256 fields and records them.
  - **No column.** Most withholdable fields are not in this model. A code naming
    one has nothing to mark.
- An unresolved code still produces a `field_privacy` row. Nothing is discarded;
  what is refused is only the inference from a code to a column.

**Four SDK versions are checked against each other, not one pinned.** Notices
published on a single day declare three: 1,993 on `eforms-sdk-1.13`, 906 on
1.14, 291 on 1.12. The generator fetches 1.12.0, 1.13.3, 1.14.2 and 1.15.1 and
refuses to write the file if any code's target moved between them. All 47 codes
and 61 fields are **identical across all four**, so one table serves every
notice in the archive.

## Consequences

- **143 of 215 privacy blocks now mark a column**, up from 2. In OJ S 157/2026:
  74 payable amounts, 42 variant indicators, 11 highest and 11 lowest tender
  amounts, 2 statistics blocks and 1 decision reason. The remaining 72 are all
  accounted for by name in `UNUSABLE`, with the reason.
- **Eleven of the SDK's 47 codes resolve here.** That the refusals are the
  larger half is stated rather than smoothed over, and there is a test asserting
  it stays that way, because a reader deciding whether to trust a `present`
  status needs to know the coverage is partial.
- **The bid count got more precise, not just more covered.** A statistics block
  was marked withheld in both columns because containment could not say which.
  Now `rec-sub-cou` names the number and `rec-sub-typ` the code. Where a code is
  missing or unresolvable, both are still marked — the conservative fallback is
  kept, so a code eForms adds tomorrow degrades to over-marking rather than to
  silence.
- **A block must sit at or above the field it names.** A privacy block
  elsewhere in the record is not applied, so a code cannot reach across a
  subtree and mark a column the block was never about.
- **The value is untouched.** A withheld amount still reads `-1`, exactly as
  published, because the archive is the ground truth and the status is where the
  interpretation belongs. Nothing is rewritten.
- **The declaration is the authority, not the shape of the value**, and the two
  do not always agree. In one publication day: two payable amounts declared
  non-public carry a value other than `-1`; one lot result carries `1` for both
  its declared-non-public highest and lowest tender amount; and two settled
  contracts carry a contract reference of `-1` that no block declares. Deriving
  the status from the value would have been wrong in six rows, in both
  directions.
  [`dataset-shape.md`](../dataset-shape.md) keeps counting `-1` by column, so
  the disagreement stays visible instead of being resolved by assumption.
- **Licence.** The SDK is published by the Publications Office of the European
  Union under **CC BY 4.0** — the same licence this project publishes its own
  data under ([ADR-0004](0004-dataset-licence.md)). It permits redistribution
  with attribution, which the generated file carries; the code stays AGPL-3.0
  and neither grant implies the other (constraint 1).
- The generator is a maintainer script, not a dependency. It runs by hand, and
  its output is reviewed as a diff like any other change.

## What would change this

- **A code that resolves to more than one column, in ordinary data.** Refused
  today. If a real notice needs one of them, the model has to carry the
  predicate that tells them apart, which is a change to
  [ADR-0005](0005-element-paths-as-provenance.md) and not a patch here.
- **The versions ceasing to agree.** The generator fails rather than writing,
  and the answer is then a mapping per declared `cbc:CustomizationID` rather
  than one table.
- **The model gaining the columns the refused codes name.** The notice's total
  amount is withheld 44 times in one day and has no column; adding it makes
  `not-val` resolve with no change here.
- **The SDK becoming needed for more than this.** Notice-subtype rules would
  make `not_applicable` derivable, which ADR-0006 declares and never produces.
  That is a larger dependency than one generated table and wants its own record.
