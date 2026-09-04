# 001 — Single bid on a competitive procedure

**Status: rejected at gate 3 (base rate).** The signal exists, it is legal to
compute, and it is falsifiable. It fires on **36.8%** of the population it would
be applied to, so it is not an anomaly — it is what a third of the European
procurement market looks like. The comparative form it points to is
[002](002-single-bid-against-its-segment.md).

Measured 2026-09-04 against five archived publication days of 2026 (OJ S 52, 94,
113, 157, 168; 19,180 notices). Nothing here names an entity: every figure is an
aggregate, and the sample-composition figures below are **not a country
ranking** — see [Limits of this measurement](#limits-of-this-measurement).

## Origin

The single-bidder indicator is the most established red flag in the procurement
integrity literature. It is a component of the DIGIWHIST/Fazekas index of procurement integrity risk
(its authors' name for it uses a word this project does not apply to anyone:
"corruption risk index"), it appears in the Open Contracting Partnership's
red-flag guidance, and
the European Commission tracks it directly: the Single Market Scoreboard
publishes a "single bidder" indicator per member state and reports that the
proportion rose in 2022 to its highest level in a decade.

It is therefore the obvious first classifier for this project — not because it
is novel, but because it is the best-validated indicator there is, which makes
it the right one to calibrate a new pipeline against.

## Gate 1 — Data

**Passes.** Every field is structured, and all of it is already in the
normalised model.

| What | Where | Coverage |
|---|---|---|
| Bids received per lot outcome | `lot_result_statistic` where `statistic_kind = 'received_submissions'` and `statistic_code = 'tenders'` (eForms BT-759/BT-760) | 19,587 blocks over five days |
| Procedure type | `procedure.procedure_code` (BT-105) | 91.5% of notices |
| Framework or DPS | `lot.contracting_system_codes` | 93.8% of lots |
| Buyer country | `organisation.country_code` via `organisation_role.role = 'buyer'` | 100% of the population below |

Two properties of the field matter more than its presence.

**A withheld count is published, not omitted.** Where a buyer withholds the
number, eForms publishes the code `unpublished` with the value `-1`. In these
five days that is 123 blocks marked `withheld` and 26 more carrying the code
without the marking. Reading the number without its status turns a lawful
deferral into a negative bid count, which is why
[ADR-0006](../adr/0006-absence-is-recorded-not-collapsed.md) exists. **Every
query below filters on `statistic_value_status = 'present'`.**

**Zero is not one.** 1,653 lot results record a bid count of zero — a call that
attracted nothing. That is a different fact from a single bid and is excluded
rather than folded in.

## Gate 2 — Legal

**Passes for detection. Publication is governed by an open decision.**

- **No person-level data.** The classifier reads counts, a procedure code, a
  CPV code and a country. Nothing in it touches a name, an address or a contact
  field, and nothing is joined that could reconstruct one.
- **Aggregates name nobody.** The measurements in this file are counts by
  country, CPV division and procedure type. No notice, buyer or supplier is
  named anywhere in it.
- **Publication about a specific entity is not settled here.** A flag on one
  lot result names a buyer, and whether that buyer is an organisation or a
  natural person trading under their own name is unknown for about 90% of
  notices — `efbc:NaturalPersonIndicator` is absent, and absent is "not
  provided", never "false". That is
  [open-work #11](../open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status),
  and it blocks the first published finding rather than this classifier.
- **A flag is an anomaly, never an accusation** (constraint 3). A single bid is
  lawful, ordinary and usually innocent. This file argues about how often it
  happens, not about what it means for anyone.

## Gate 3 — Base rate

**Fails.** The population is lot results on a competitive procedure whose bid
count is published and at least one. Competitive means `procedure_code` in
`open`, `restricted`, `comp-dial`, `comp-tend`, `innovation`, `neg-w-call` —
negotiation *without* a prior call is excluded, since a single bid there is the
procedure working as designed, not a surprise.

| Population | Lot results | Single bid | Rate | Notices |
|---|---:|---:|---:|---:|
| All competitive | 16,873 | 6,210 | **36.8%** | 5,267 |
| Frameworks and DPS excluded | 8,159 | 3,435 | **42.1%** | 3,790 |
| Frameworks and DPS only | 8,714 | 2,775 | 31.8% | 1,480 |

The second row is the comparable one: the Commission's Scoreboard indicator
excludes framework agreements because their reporting patterns differ. Excluding
them here **raises** the rate rather than lowering it.

The distribution says the same thing without a threshold. Among competitive lot
results with a published count, the modal number of bids is one, and it is not
close:

| Bids | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11+ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Lot results | 6,210 | 3,246 | 2,381 | 1,666 | 1,214 | 664 | 447 | 228 | 186 | 131 | 500 |

**A flag firing on two in five contract awards is not a flag.** It would hand a
verifier 3,435 cases from five days of notices, almost all of them ordinary, and
publishing it would say nothing a reader could act on. This is the gate working:
the case is rejected here rather than after someone builds it.

The observation is worth publishing on its own terms — that European procurement
awards a large minority of its competitive lots on a single bid is a fact about
the market, and the project can state it with a reproducible query behind it.
That is a data note, not a classifier.

## Gate 4 — Falsifiability

**Passes**, and is worth writing down because the successor case inherits it.

> This flag is wrong if a published count of one does not mean one bidder
> competed: if the count excludes bids recorded under another statistics code,
> if the lot is one of many in a framework whose competition happened at
> call-off, if the notice was later corrected or withdrawn, or if the procedure
> was lawfully non-competitive but coded as though it were not.

## Comparator scan

- **opentender.eu / DIGIWHIST** compute a single-bidder indicator across 35
  jurisdictions from TED and national portals, and process eForms-era
  publications. **The pattern is covered.**
- **The European Commission's Single Market Scoreboard** publishes it per member
  state, framework agreements excluded.
- **ARACHNE** is an internal Commission risk tool, not publicly reproducible.
- **OCP / Kingfisher** carry single-bid red flags in several national
  implementations.

**No delta for the standalone indicator.** This project would be computing a
well-covered number less often and less completely than the people already
computing it. That is a second, independent reason to reject the standalone
form, and it is recorded here so nobody re-proposes it.

Where a delta plausibly exists is per-notice traceability — every flag linked to
the source notice, with the query that produced it published and the run
reproducible byte for byte — rather than in the indicator itself. That claim
belongs to [002](002-single-bid-against-its-segment.md), which has to earn it.

## Limits of this measurement

- **Five days, not a year.** March to September 2026. Publication volume is not
  uniform across member states, and the sample is heavily weighted toward the
  countries that publish the most award notices with statistics.
- **These are not country rankings.** The population includes 6,180 lot results
  with a Romanian buyer and 268 with a Greek one. A rate computed on 268 rows
  from five days says almost nothing about a country and must not be quoted as
  though it did.
- **Lots are not notices.** One award notice contributed 247 lot results. Every
  rate above weights that notice 247 times. Weighting each notice equally
  instead gives 31.9% rather than 36.8%, which is the same conclusion by a
  different route.
- **A publisher that omits the count is invisible here.** The population is what
  was published, not what was procured.

## The queries

Against the dataset `serenata normalise` writes, with DuckDB:

```sql
CREATE VIEW population AS
SELECT s.source_publication_id,
       TRY_CAST(s.statistic_value AS BIGINT) AS n_bids
FROM lot_result_statistic s
JOIN procedure p ON p.source_publication_id = s.source_publication_id
WHERE s.statistic_kind = 'received_submissions'
  AND s.statistic_code = 'tenders'
  AND s.statistic_value_status = 'present'
  AND p.procedure_code_status = 'present'
  AND p.procedure_code IN ('open','restricted','comp-dial','comp-tend',
                           'innovation','neg-w-call')
  AND TRY_CAST(s.statistic_value AS BIGINT) >= 1;

SELECT count(*)                                AS lot_results,
       count(*) FILTER (WHERE n_bids = 1)      AS single_bid
FROM population;
```

The framework split joins `lot_result` to `lot` on `lot_ref` and tests
`contracting_system_codes` for `fa-wo-rc`, `fa-w-rc`, `fa-mix`, `dps-list` or
`dps-nlist`.
