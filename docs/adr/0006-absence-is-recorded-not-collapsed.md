# ADR-0006: Record why a value is missing, in a column beside it

- Status: accepted
- Date: 2026-09-02

## Context

CLAUDE.md requires that "not provided" and "not applicable" be different facts,
recorded explicitly. eForms makes that requirement sharper than it first sounds,
because a missing value in a notice has at least four distinguishable causes:

- the element was **present with a value**;
- the element was **present and blank** — the publisher emitted the tag and put
  nothing in it;
- the element was **absent** from the notice entirely;
- the publisher **withheld** it, marking the fact in `efac:FieldsPrivacy`.

A fifth, **not applicable**, follows from the notice subtype: an award field has
no meaning in a prior information notice.

The first three are directly observable. Two of them are also common; the
second turns out not to be. [`field-usage.md`](../field-usage.md) reports 296
paths appearing "only as containers or blank elements", which reads as though
blank elements occur — but the survey does not separate the two, and the parse
stage does. Across the 897,471 leaf elements in OJ S 157/2026 there are **zero**
blank leaves: all 296 are containers. That denominator is every leaf in the
package, the 32,135 the drop list removes included — it was measured by a
standalone pass applying no filter, not by the parser, which stops at a dropped
path before reading its text.

So `empty` is permitted by the schema and produced by the parser, and was not
observed in this package. It is kept as a distinct status because a state that
costs nothing to carry and would be silently wrong to conflate is worth
carrying — but it is **not** the case that justifies this decision, and saying
otherwise would be inventing evidence. The case is `withheld`, below, which is
observed.

The fourth is the dangerous one. `efac:FieldsPrivacy` is how a publisher records
that a field is deliberately non-public, sometimes with a date when it will be
released. It appears in 1.6% of notices — and among the fields observed withheld
in this package is `efac:ReceivedSubmissionsStatistics`, the bid count.

That field is the input to a single-bid classifier, the most cited red flag in
the procurement integrity literature and near-certain to be among this project's
first hypotheses. If a withheld bid count arrived as the same NULL as an absent
one, a classifier reading "no bids recorded" as "one bidder" would flag a buyer
who had done nothing but exercise a lawful deferral. The project would publish
an anomaly whose entire cause was its own data handling.

A single NULL cannot carry four meanings, and the cost of the collapse is not
theoretical.

## Decision

**Every nullable column carries a companion `<column>_status` column** taking
one of `present`, `empty`, `absent`, `withheld`, `not_applicable`.

Uniformly — every nullable column, with no per-field judgement about which ones
deserve the treatment. A rule applied everywhere is one a reviewer can check and
a parser can implement; a rule applied where someone thought it mattered is a
rule that will be missing exactly where it turns out to matter.

The alternative considered and rejected was a long-format provenance table, one
row per record per field. It expresses the same facts and would also satisfy the
constraint, but every classifier would then need a join to read a value
honestly, and a join that can be forgotten is a safeguard that will be. Putting
the status beside the value makes the honest read the easy one.

`withheld` is populated from the `field_privacy` table, which is parsed from
`efac:FieldsPrivacy` and keyed to the record it qualifies. `not_applicable`
needs the eForms notice-subtype rules, which live in the SDK the pipeline does
not carry; until it does, an inapplicable field is recorded `absent`. That is
imprecise in the conservative direction — it understates knowledge rather than
overstating it — and it is written down rather than left as a surprise.

## Consequences

- Roughly twice the columns. In a columnar format this is close to free: status
  values are low-cardinality strings, dictionary-encode to almost nothing, and
  are not read by queries that do not name them. This is the specific property
  that makes the uniform rule affordable, and it is why ADR-0001's choice of
  Parquet matters here.
- A classifier that reads a value without its status is a bug that review has to
  catch. The merge checklist covers it, and a classifier's hypothesis file has
  to state which statuses its population includes.
- Base rates must be computed over the population that actually carries the
  field, not over all notices. `award_date` at 20.4% presence against
  `issue_date` at 42.6% is the worked example: a naive denominator would halve
  a rate for no reason but absence.
- `not_applicable` is under-reported until the SDK question is settled. Nothing
  downstream may treat `absent` as proof a field was applicable.
- **`withheld` turned out to need the same SDK**, which this decision assumed it
  would not. Building the normalise stage showed that `efac:FieldsPrivacy` names
  its target with an eForms field identifier — `win-ten-val`, `ten-val-low` —
  rather than by sitting beside it, so the status can only be derived where
  containment proves the target: a privacy block inside an
  `efac:ReceivedSubmissionsStatistics` block marks that block, and the bid count
  is therefore covered. Elsewhere the fact is in the `field_privacy` table and
  the marked column reads `present`. Worse, the withheld value is *published*
  rather than omitted — as `-1`, on 72 payable amounts in one publication day —
  so the collapse this decision set out to prevent is currently a sentinel a
  classifier has to exclude by hand. Closing that is
  [open-work #13](../open-work.md#13-derive-the-withheld-status-from-the-eforms-field-identifiers),
  and it does not change the decision: the column is there, and filling it
  correctly is the work.
- Parse has to distinguish absent from blank, which means recording which
  elements it saw and not only which values it read. `serenata.survey` already
  does exactly this, so the mechanism is proven before parse needs it.

## What would change this

- **Column count becoming a real cost** — a table wide enough that the doubling
  hurts scan or write time. Measure before believing it; the reason to revisit
  would be a profile, not an intuition.
- **Adopting the eForms SDK**, which would make `not_applicable` derivable and
  turn the current conservative fallback into a genuine value.
- **A classifier needing a status this enum cannot express.** The list is five
  values because five causes were observed; a sixth would extend it rather than
  replace the design.
- **Publishing the dataset for external reuse**, where a consumer expecting
  plain nullable columns meets a schema with twice as many. That is a
  presentation problem, solved with a view, and it should not be solved by
  weakening what the stored data records.
