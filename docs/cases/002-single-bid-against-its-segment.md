# 002 — A single bid where single bids are rare

**Status: measured.** Passes all four gates. The successor to
[001](001-single-bid.md), which failed on its base rate: a single bid is
unremarkable across Europe as a whole and unusual inside particular markets, so
the question worth asking is not *was there one bid* but *was one bid surprising
here*.

Measured 2026-09-04 against five archived publication days of 2026 (OJ S 52, 94,
113, 157, 168; 19,180 notices). Nothing here names an entity.

## The idea

Compare a lot outcome against the segment it sits in — the buyer's country and
the CPV division — rather than against a European average. A single bid for
construction work in a market where 93% of comparable lots drew several bidders
is a different observation from a single bid in a market where half of them do.

This is the shape the literature uses. Fazekas and the DIGIWHIST work treat
single bidding as a risk *component normalised within a market*, not as a flag
in its own right, and the Commission's Scoreboard reports it per member state
for the same reason: the base rate is not a European constant.

## Gate 1 — Data

**Passes.** The same fields as [001](001-single-bid.md), plus the two that
define a segment, both already modelled and both fully populated in the
population below: `lot.cpv_code` and the buyer's `organisation.country_code`.

The baseline itself is **computed from the archive**, not fetched. That keeps
constraint 4 intact — same archive plus same classifier version gives the same
flags — but it makes the corpus part of the classifier's input, which the
hypothesis file has to state plainly: adding a publication day can change
whether a past lot is flagged. Freezing the baseline to a stated reference
period is the alternative, and choosing between them is the first thing the
hypothesis has to decide.

## Gate 2 — Legal

**Passes for detection, on the same terms as [001](001-single-bid.md).** No
person-level data, no join that could reconstruct any, aggregates that name
nobody. Publishing a flag about a specific buyer remains governed by
[open-work #11](../open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status).

One addition specific to this case: a segment can be small enough that naming it
identifies its participants. A cell of three lots in one country and one CPV
division is close to naming the buyer. The rule below sets a floor of 50 lot
results per cell, which is a statistical requirement first and a privacy
property second.

## Gate 3 — Base rate

**Passes.** Segments differ enormously, and a rule keyed to that difference
fires rarely.

Over the non-framework population — 8,159 lot results, the same definition
[001](001-single-bid.md) uses — there are **26 (country, CPV division) cells
holding at least 50 lot results**, covering 4,299 of them. Their single-bid
rates run from **6.5% to 78.2%, median 35.2%**. That spread is the case: no
single threshold on a raw bid count can be right in both tails.

A candidate rule — *one bid, in a cell of at least 50 lot results whose
single-bid rate is below a threshold* — fires like this:

| Cell rate below | Flags | Notices | Share of covered population |
|---|---:|---:|---:|
| 10% | 26 | 24 | 0.60% |
| 15% | 96 | 71 | 2.23% |
| 20% | 96 | 71 | 2.23% |

**2.23% against 42.1%** is the whole point of the redesign. It is also small
enough to verify by hand, which is what a flag has to be in a project that
verifies before publishing.

Two honest observations about that table. The 15% and 20% rows are identical
because no cell in this sample has a rate between them — with 26 cells, the
threshold is insensitive across a wide band, and that is a property of a small
sample rather than a robust choice. And the rule covers only **53% of the
non-framework population**; the rest sit in cells too small to have a baseline,
where the honest answer is that this classifier has nothing to say.

## Gate 4 — Falsifiability

**Passes.**

> This flag is wrong if a lot's segment does not predict its competition: if
> (country, CPV division) is the wrong grouping — too coarse to separate a
> specialist market from a commodity one, or too fine to be stable — or if the
> cells with low single-bid rates are low for a reason that has nothing to do
> with the flagged lot, such as one large buyer publishing most of them.
>
> It is also wrong for any lot where 001's falsification applies: a count that
> excludes bids recorded elsewhere, competition that happened at framework
> call-off, or a notice later corrected or withdrawn.

Both halves are testable. The first by re-running with a different grouping —
NUTS region instead of country, CPV group instead of division — and seeing
whether the same lots are flagged. The second per finding, by the verification
protocol.

## Comparator scan

The **indicator** is covered (see [001](001-single-bid.md)). The **comparative
form** — flag a specific lot outcome as surprising for its segment, link it to
the source notice, publish the query — is where the delta has to be, and it is
a delta of *form* rather than of arithmetic:

- opentender and the Scoreboard publish **rates**, per country and per period.
  Neither hands a reader a list of individual lots with a reason and a link.
- Neither is reproducible end to end by a third party. This project's promise is
  that the same archive and the same code produce the same flags, byte for byte,
  and that the archive is named with its checksum.

That is a legitimate delta and it is also an unproven one. **It is not a claim
this file gets to make; it is what the classifier has to demonstrate.**

## False-positive taxonomy

Checked against the project's standing list before anything is built:

- **Frameworks and lots** — excluded from the population outright. Competition
  in a framework happens at call-off, which the award notice does not report.
- **Currency and unit errors** — not applicable: this reads counts, not values.
- **CPV misclassification** — *unresolved and material*. A lot in the wrong CPV
  division is compared against the wrong market. The CPV is the buyer's own
  classification and nothing here validates it.
- **Legitimate national rules** — handled by construction: the baseline is
  per country, so a national norm moves the cell rate rather than the flag.
- **Emergency procedures** — partly handled by excluding `neg-wo-call`; a
  procedure with an emergency justification but a competitive code will still
  be flagged, and `procedure.process_reason_codes` is where a verifier checks.
- **Corrections and superseding notices** — *unresolved*. The pipeline records
  `notice.changed_notice_id` and acts on nothing
  ([open-work #6](../open-work.md#6-handle-corrected-and-withdrawn-notices)).
  A flag on a superseded notice is a flag on something that no longer stands,
  and **this must be settled before any finding from this classifier is
  published**.

## What has to happen next

This case graduates to a hypothesis file and enters the classifier workflow. The
hypothesis has to settle, before code:

1. **The baseline**: computed from the corpus, or frozen to a stated reference
   period. This decides what "the same flags" means when the archive grows.
2. **The grouping**: (country, CPV division) is the first guess, not a finding.
   The falsification test above is how it gets checked.
3. **The threshold**, on a bigger sample than 26 cells.
4. **The unit**: per lot result, or per notice. 001 shows the two give different
   headline numbers.
5. **Whether the flag is publishable at all** before
   [#6](../open-work.md#6-handle-corrected-and-withdrawn-notices) and
   [#11](../open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status)
   are answered. The classifier can be built and measured meanwhile; publishing
   is a separate gate.

## The query

```sql
CREATE VIEW cells AS
SELECT country, division, count(*) AS n,
       100.0 * count(*) FILTER (WHERE n_bids = 1) / count(*) AS cell_rate
FROM population           -- 001's population, frameworks and DPS excluded
GROUP BY 1, 2;

SELECT count(*) AS flags,
       count(DISTINCT p.source_publication_id) AS notices
FROM population p
JOIN cells USING (country, division)
WHERE cells.n >= 50 AND cells.cell_rate < 15 AND p.n_bids = 1;
```
