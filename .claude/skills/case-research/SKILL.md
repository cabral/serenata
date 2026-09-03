---
name: case-research
description: Use when evaluating anything new before it becomes code or a publication. That includes a new anomaly pattern or red-flag idea, a new data source, a journalist or patron tip, a lead from academic literature, or a specific finding being considered for publication. If the question is "should we detect this" or "is this specific flag real", this skill applies. It carries the four intake gates (data, legal, base rate, falsifiability), the starting library of established procurement red flags, the comparator scan against opentender/DIGIWHIST/ARACHNE/Kingfisher, the false-positive taxonomy, and the verification protocol for individual findings.
---

# Case research

Every idea gets a file in `docs/cases/NNN-slug.md` with a status line: idea, scoped, measured, building, live, or rejected. Rejected cases keep their file and the reason for rejection. Half the value of this directory is the record of what was considered and why it didn't fly, both for future contributors and for grant reviewers who want to see method rather than luck.

## Where cases come from

The procurement red-flag literature (the DIGIWHIST corpus and Fazekas's integrity indicators, the Open Contracting Partnership's red flags guidance), European Court of Auditors and OLAF reports, Odilla's and RESPOND's academic work, journalists, patrons, and patterns noticed in the data itself. Record the origin in the case file; a case sourced from peer-reviewed literature starts with more credibility than a hunch, and reviewers can tell the difference.

## The four gates

Run them in order. Fail one, stop, set status to rejected, and record which gate and why.

1. Data. The needed signal must exist as a structured field in eForms/TED (name the BT codes) or another already-approved source. A signal that only lives in free text fails the core-classifier constraint. Either find a structured proxy or park the case with a note about what field would unlock it; eForms coverage improves over time and parked cases come back.

2. Legal. Load the legal skill and answer its questions in the case file. Does detection require person-level data? Does publication of this pattern create naming risk? A case can pass by redesign (aggregate one level up) or escalate.

3. Base rate. Define the denominator, write the query, run it on historical data, record the number and date in the file. If the denominator can't be defined, the case isn't measurable yet. If the flag fires on a large share of the population, that's a property of the market or the data standard, not an anomaly, and the case file should say so; sometimes that observation is itself worth publishing as a data-quality note.

4. Falsifiability. Complete the sentence "this flag is wrong if..." in the file. If the sentence can't be written, what exists is a narrative, not a classifier.

A case that passes all four gates graduates to a hypothesis file and enters the coding skill workflow.

## Starting library

Established red-flag families from the literature, each still requiring its own gates and comparator scan before building:

- Single bid received on a competitive procedure.
- Submission period shorter than the norm for the procedure type and category.
- High share of negotiated procedures without prior publication, per buyer.
- Repeated buyer-supplier pairs; supplier concentration per buyer over time.
- Contract values sitting just under EU or national thresholds; signs of award splitting.
- Post-award modifications that substantially raise contract value.
- Award decision unusually fast after the submission deadline.
- Price outliers within a CPV category. Handle with care: framework agreements and lot structures distort values badly.
- Supplier registered shortly before the award. Needs a company-registry join, which is a new data source and a fresh legal gate.

## Comparator scan

Before building anything, check whether opentender.eu, the DIGIWHIST indicators, ARACHNE, or OCP Kingfisher implementations already cover the pattern, and record the answer in the case file. If they do, state the delta: fresher data, a jurisdiction they don't cover, published and reproducible methodology where theirs is opaque, or a corrected flaw in their definition. "They compute it but nobody can verify how; we publish the query" is a legitimate delta and happens to be the project's core pitch. "No delta" is a legitimate rejection.

## False-positive taxonomy

Check every specific finding against this list before it goes anywhere near publication. These are the boring explanations that kill exciting flags:

- Framework agreements and lots: totals, counts, and values mean different things than they appear to.
- Currency and unit errors in the source data.
- CPV misclassification putting a notice in the wrong comparison group.
- Legitimate national rules: some member states lawfully allow shorter periods or direct awards below national thresholds, so a cross-country flag needs country-aware baselines.
- Emergency procedures with a stated legal basis, including the COVID-era confound in any historical baseline spanning 2020-2022.
- A correction or amendment notice that supersedes the flagged notice.

## Verification protocol for one specific finding

1. Re-derive the flag from the raw source notice, not from the pipeline output. This catches pipeline bugs and stale data at the moment it matters most.
2. Read the full notice, then check TED for corrections and amendments.
3. Walk the false-positive taxonomy above and note each item as checked.
4. Archive the source: screenshot plus archive link.
5. Hand off: communication skill for drafting, legal pre-publication checklist for clearance.

A finding that fails at any step goes back into the file with the reason. Findings the project chose not to publish, and why, are part of the method too.