# Single bid in a segment where single bids are rare

Status: building

The classifier exists and runs, and its measured base rate reproduces: over
the five archived publication days, version 2 produces 96 flags from 8,159 lot
outcomes, the same numbers the [query](single_bid_in_segment.sql) beside this
file reports.

Version 2 tightened population integrity and three exclusions, and **measures
identically to version 1 on this archive** — every figure below was remeasured
under version 2 and none of them moved. That is a statement about this corpus,
not a general one: the tightened rules are guarantees about what the population
may contain, and on a corpus where they bind, they will change the numbers.

It is not `live`, because nothing it produces may be published yet — see the
legal check.

Governs `serenata/classify/single_bid_in_segment.py`. The argument that produced
it is [case 002](../cases/002-single-bid-against-its-segment.md); the form this
replaces, and why it was rejected, is [case 001](../cases/001-single-bid.md).

## Claim

A competitive procurement lot that receives exactly one bid, in a market where
comparable lots usually draw several, is anomalous relative to that market —
and more informative than a single bid measured against a European average,
because single bidding varies from 6.5% to 78.2% across the measured markets
and an average describes none of them.

"Market" is the buyer's country and the lot's CPV division. The comparison is
against lots in the same market in the same dataset.

This is a statistical anomaly with ordinary explanations, not a finding about
anyone. A single bid is lawful, common, and usually means what it looks like:
one supplier wanted the work.

## This flag is wrong if...

- **the segment does not predict competition** — if country plus CPV division is
  the wrong grouping, too coarse to separate a specialist market from a
  commodity one, or too fine to be stable. Testable: regroup by NUTS region or
  by CPV group and see whether the same lots are flagged.
- **a low-single-bid segment is low for a reason unrelated to the flagged lot**,
  such as one large buyer publishing most of its lots.
- **the bid count does not mean what it says** — bids recorded under another
  statistics code, competition that happened at a framework call-off rather
  than at award, or a count published under a privacy declaration.
- **the notice was corrected or withdrawn** after publication, in which case the
  flag is about something that no longer stands.

## Fields used

All structured, all already in the normalised model. No free text is read.

| Field | eForms | Model |
|---|---|---|
| Bids received | BT-759 `ReceivedSubmissionsCount`, with BT-760 `ReceivedSubmissionsType` = `tenders` | `lot_result_statistic.statistic_value` where `statistic_kind = 'received_submissions'` |
| Procedure type | BT-105 | `procedure.procedure_code` |
| Contracting system | BT-765 | `lot.contracting_system_codes` |
| Classification | BT-262 | `lot.cpv_code` |
| Buyer country | BT-514 | `organisation.country_code` via `organisation_role.role = 'buyer'` |
| Lot outcome identity | — | `lot_result.ordinal`, `lot_result.lot_ref` |

`lot.title` and `lot.description` are **not** read. Constraint 5 keeps the
classifier on structured fields, and the descriptions are carried as provenance
for a human verifier.

## Population and denominator

One row per lot result, included when all of these hold:

- the lot result carries a `received_submissions` statistic with code `tenders`,
  both its code and value statuses are `present`, and the value is an **exact
  whole count from 1 through 9223372036854775807**. The normalised string must
  match `[+]?[0-9]+([.]0*)?`: leading zeros, an optional plus and a zero-only
  decimal fraction are allowed; nonzero fractions, exponent notation, remaining
  whitespace and overflow are excluded, never rounded. A withheld code or count
  is excluded even if a usable-looking value remains, and zero is a different
  fact from one.
- the procedure code is present and competitive: `open`, `restricted`,
  `comp-dial`, `comp-tend`, `innovation` or `neg-w-call`. Negotiation without a
  prior call is excluded — a single bid there is the procedure working.
- the lot is **not** a framework agreement or dynamic purchasing system
  (`fa-wo-rc`, `fa-w-rc`, `fa-mix`, `dps-list`, `dps-nlist`). Competition in a
  framework happens at call-off, which the award notice does not report. The
  Commission's own single-bidder indicator excludes them for the same reason.
- the lot's CPV code is present. Every buyer reference resolves within the
  publication to an organisation with a present, nonempty country, and all
  buyers agree on that country. Multiple buyers in one country are allowed;
  conflicting countries, unresolved references and absent or withheld countries
  exclude the publication rather than selecting an arbitrary buyer.

**Version-2 integrity gate, before the population is read.** Duplicate
structural keys in any of the six input tables reject the whole run, even for
identical rows or overlaps across year partitions. The join keys
`(source_publication_id, lot_id)` and `(source_publication_id, org_local_id)`
must also be unique when the local identifier is non-null. A lot result may
carry at most one `received_submissions` block with a present `tenders` code,
regardless of the value status; multiple such blocks are ambiguous, even if
their counts agree. Other statistics codes remain separate observations and do
not multiply this population. Errors report no data values. The classifier
neither deduplicates nor guesses which conflicting row is authoritative.

The gate is **scoped to what the rule reads**: the publications the population
draws from, and for the tender check the lot results in it. A publication that
contributes no lot outcome contributes to no segment either, so its duplicates
cannot move a flag. This is not hypothetical — one framework lot result in the
measured archive carries its bid count four times, in four blocks with one
repeated value, and the source XML repeats it, so it is the publisher's and not
the pipeline's. Validating whole tables let a row the rule excludes anyway stop
every measurement, and "repair belongs upstream" has no upstream to go to: the
archive is immutable ground truth. Eligibility deliberately stops short of the
buyer country, so a publication cannot escape the check by carrying the very
duplicate organisations that would exclude it.

A lot result is **flagged** when its bid count is exactly 1, its segment holds
at least **50** lot results in the dataset, and that segment's single-bid rate
is below **15%**.

Both parameters were chosen after measuring, not before, and version 2's
remeasurement leaves them where they were. Under an independent Bernoulli
model, 50 observations at a 15% rate give a standard error of about 5 percentage
points. Procurement lots can be clustered within notices and buyers, so that
independence assumption is not established: the floor is a heuristic, not a
precision guarantee or a significance test. Dropping the floor to 30 admits
noisier segments and 22% more flags. The 15% cutoff is roughly a third of the
population's own single-bid rate. **The sample cannot distinguish 15% from
20%** at the floor of 50: no eligible segment has a rate between them, so the
lower, more conservative number is used, and this is the parameter most likely
to move when the dataset grows.

## Measurement metadata

Package IDs are those listed in
[dataset shape](../dataset-shape.md#what-was-measured). The period is a
**bounding window**, from the start of the recorded corpus year through the
measurement date, not the observed first and last publication dates or a claim
of continuous coverage. Only the five listed issues were measured. The query
revision is `working-tree`: the companion SQL was run from the working tree in
the same change that produced these numbers. The admission test checks metadata
sanity, not the data, the query's results, or approval to release or publish.

```toml
[admission]
current_rule_version = 2
current_measurement = "measured"

[measurement]
rule_version = 2
measured_on = 2026-09-05
period_start = 2026-01-01
period_end = 2026-09-05
package_ids = ["202600052", "202600094", "202600113", "202600157", "202600168"]
query_file = "single_bid_in_segment.sql"
query_revision = "working-tree"
notice_count = 19180
population_count = 8159
population_notice_count = 3790
covered_count = 4299
uncovered_count = 3860
flagged_count = 96
flagged_notice_count = 71
```

A measurement satisfies the CI gate. It is not clearance to process real data
beyond this archive, nor to publish anything computed from it.

## Base rate

Measured 2026-09-05 under version 2, against five archived publication days of
2026 — OJ S 52, 94, 113, 157 and 168, 19,180 notices. The query is
`single_bid_in_segment.sql` beside this file, including its integrity gate.
Version 1 measured the same figures on the same archive.

- **Population**: 8,159 lot results, from 3,790 notices.
- **Single bid anywhere in it**: 3,435, or 42.1%. That is the rate case 001 was
  rejected on: a flag firing on two in five awards describes the market.
- **Segments with at least 50 lot results**: 26, covering 4,299 of the
  population. Their single-bid rates run from 6.5% to 78.2%, median 35.2%.
- **Flags**: **96, in 71 notices — 2.23% of the population the rule can speak
  about**, and 1.18% of the whole population.

Sensitivity, same dataset, flags at each parameter pair:

| Segment floor | Segments | Covered | <10% | <15% | <20% | <25% |
|---:|---:|---:|---:|---:|---:|---:|
| 30 | 47 | 5,051 | 33 | 117 | 123 | 160 |
| 50 | 26 | 4,299 | 26 | 96 | 96 | 133 |
| 75 | 11 | 3,409 | 20 | 76 | 76 | 76 |
| 100 | 8 | 3,155 | 20 | 64 | 64 | 64 |

**Coverage is a narrow majority, not a minority.** 4,299 of 8,159 lot results
(52.7%) are in eligible segments; the other 3,860 (47.3%) sit in segments below
the floor. The honest output there is silence, not a flag.

**Anticipated false-positive profile.** Not yet verified case by case — no
finding has been through the verification protocol, so the profile below is what
the design predicts rather than what has been observed:

- CPV misclassification puts a lot in the wrong segment. The CPV is the buyer's
  own and nothing validates it. Unmitigated.
- An emergency or otherwise justified procedure that is nonetheless coded
  competitive will be flagged; `procedure.process_reason_codes` is where a
  verifier looks.
- A corrected or withdrawn notice will still be flagged, because the pipeline
  records the corrigendum link and acts on nothing yet. This is the one that
  must be closed before publication.
- A segment dominated by one buyer makes its rate a fact about that buyer.
  Unmitigated, and the reason the flag carries its segment's size.

## Comparators

The indicator is well covered: opentender.eu and the DIGIWHIST work compute
single-bidder rates across 35 jurisdictions, the Commission's Single Market
Scoreboard publishes them per member state, and ARACHNE is a Commission-internal
risk tool. Case 001 rejected the standalone form partly for that reason.

The delta claimed here is form rather than arithmetic. Those sources publish
**rates**, per country and per period. None hands a reader an individual lot
outcome with the comparison that produced it, a link to the source document, and
a rerunnable query. Each flag this classifier emits carries its own segment, the
segment's size and rate, and the notice it came from.

That is a claim about usefulness, and it is unproven until someone verifies a
flag end to end.

## Legal check

- **Structured inputs, not anonymity.** The rule reads counts, procedure and
  contracting-system codes, CPV and country codes, and notice-scoped identifiers.
  It does not read names or descriptions, but the identifiers and source links
  can still identify natural persons. A structured-only query does not establish
  a lawful basis for processing its inputs or storing its outputs.
- **Naming.** A flag names a buyer by implication, through the notice it links
  to. Whether a flag may be published about an entity whose natural-person
  status is unknown is [open-work #11](../open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status),
  unanswered. [ADR-0010](../adr/0010-raw-archive-retention.md) also records
  unresolved questions for current collection, storage and analysis; these are
  not limited to publication.
- **Segment size and identifiability.** Fifty lots need not mean fifty buyers
  or suppliers. The floor is a statistical heuristic, not an anonymity
  guarantee, and does not remove the naming gate.
- **Framing.** Constraint 3: the flag is an anomaly with innocent explanations,
  and every user-facing string says so.

**Nothing computed by this classifier may be published** until
[open-work #6](../open-work.md#6-handle-corrected-and-withdrawn-notices)
settles what a flag on a superseded notice does, and #11 settles who may be
named. Synthetic development can continue. Real-data measurement and remediation
require the unresolved processing review in ADR-0010; neither this hypothesis
nor a passing test suite authorizes them.
