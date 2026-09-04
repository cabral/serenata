# Glossary

EU procurement has a precise vocabulary and eForms adds its own. Most of it is
not guessable, and several terms mean something narrower than they sound. This
is what the words mean **as this project uses them**.

If a term here disagrees with [`data-model.md`](data-model.md), that document
wins and this one needs fixing.

## The publication chain

**TED** — Tenders Electronic Daily, the EU's procurement publication service and
this project's only data source. Publishes roughly 700,000 notices a year.

**OJ S / OJS** — the *Supplement* to the Official Journal of the European Union,
where procurement notices appear. Issues are numbered per year: `157/2026` is
issue 157 of 2026. One issue is one publication day.

**Daily package** — a gzipped tar of every notice in one OJ S issue, which is
what this project archives. About 20 MB and 3,000 notices.

**Notice** — one published document about one procurement. The unit of
everything here. Several kinds matter:

- **Prior information notice (PIN)** — an early signal that a procurement is
  coming. May or may not be followed by anything.
- **Contract notice** — the actual call for tenders. What bidders respond to.
- **Contract award notice** — what happened: who won, for how much, how many
  bid. Most classifier inputs live here.
- **Corrigendum** — a correction to a notice already published. A flag raised
  against a notice later corrected may no longer stand, which is why handling
  these is open work rather than an afterthought.

**eForms** — the UBL-based XML schema mandatory for notices from late 2024.
Everything this pipeline parses.

**Legacy TED** — the pre-2024 XML schemas. Refused rather than parsed, because
the mapping has never been measured against real notices.

**eForms SDK** — the Publications Office's machine-readable definition of eForms
fields: which element each field is, what may be withheld, which notice types
require it. Not a runtime dependency here; the one relation this project needs
is generated into `serenata/normalise/sdk_privacy.py`.

**BT code** — a "business term" identifier from the eForms specification, like
`BT-720-Tender` for a tender's value. This project records provenance as
**element paths** instead, because mapping a path to its BT code needs the SDK
([ADR-0005](adr/0005-element-paths-as-provenance.md)).

## Who is who

**Contracting authority** — the public body buying something. In this dataset it
plays the **buyer** role. Under the procurement directives this is the State, a
regional or local authority, or a body governed by public law — so it is an
institution by definition, never a private individual.

**Economic operator** — anyone who might sell: a company, a consortium, or a
sole trader. Becomes a **tenderer** when they bid.

**Tendering party** — who submitted one bid. Not the same as one company: a
consortium bids as a single tendering party made of several organisations, which
is why the model has a table for it.

**Sole trader** — a natural person trading under their own name. eForms flags
them with `efbc:NaturalPersonIndicator`, and where it is true this project
suppresses the organisation's identifying values, **including its registration
identifier** — in Sweden a sole trader's `organisationsnummer` is their
`personnummer`. The indicator is absent from 97% of organisation records, and
absent means "not provided", never "false".

**Ultimate beneficial owner (UBO)** — the natural person who ultimately owns or
controls a company. Dropped outright at ingestion. Analytically valuable and
deliberately given up; see [open-work #15](open-work.md#15-decide-whether-beneficial-ownership-can-be-analysed-at-all).

## The structure of a procurement

These four nest, and mixing them up is the most common way to misread the
dataset.

**Procedure** — the whole procurement, one per notice. Says what is being bought
and how it is being bought.

**Lot** — a divisible part of a procedure that can be bid for and awarded
separately. Most notices have exactly one; one measured notice had 271. *A lot
is the thing being sold.*

**Lot tender** — one bid for one lot, with its price. *A lot tender is an
offer.* Several per lot is the normal case, and exactly one is the signal the
first classifier will look for.

**Lot result** — the outcome for one lot: who won, the highest and lowest bids
received, how many bids arrived. *A lot result is the decision.* It references
the lot tenders that won.

**Settled contract** — the contract actually signed, with its date. One result
can produce several, and a framework can produce many.

So: a **procedure** contains **lots**; each lot receives **lot tenders**;
each lot has a **lot result**; a result yields **settled contracts**.

**Framework agreement** — an arrangement setting terms with one or more
suppliers, against which contracts are called off later. The declared maximum
value and what is actually spent are different numbers, and both are carried.

**Dynamic purchasing system (DPS)** — an open-ended electronic list of qualified
suppliers, which suppliers can join at any time.

## Classification

**CPV** — Common Procurement Vocabulary, the EU's ~9,500-code taxonomy of what
is being bought. The standard way to compare like with like.

**NUTS** — the EU's hierarchical geography codes, from country down to small
region. How "where was this performed" is recorded.

## This project's own vocabulary

**Flag** — a record a classifier marked as statistically unusual. **Never an
accusation.** Every flag has innocent explanations, links to its source notice,
and states its base rate. The words `corrupt`, `fraud` and `guilty` do not
appear in output about a flagged record, and a test enforces that.

**Anomaly** — a deviation from what is typical for comparable procurements. The
project's working word.

**Classifier** — a pure function from normalised rows to flag rows. Reads
structured fields only. Never touches the network, the clock, free text, or a
model.

**Hypothesis** — the written, falsifiable claim a classifier tests, in
`docs/hypotheses/`. Required before any detection code, and must state what
would prove it wrong.

**Base rate** — how often a pattern occurs across the whole population. Without
it a flag is meaningless: single bidding occurs in 31% of measured lot results,
so "this had one bid" describes the market rather than an anomaly until it is
conditioned on something.

**Case** — an idea under evaluation in `docs/cases/`, before it becomes a
hypothesis. Rejected cases keep their file and the reason.

## Data vocabulary

**Provenance** — the element path a value came from, carried so any row can be
traced to the notice and element that produced it.

**Absence status** — the companion column beside every value, saying *why* it
has the value it has: `present`, `empty`, `absent`, `withheld`,
`not_applicable`. Distinguishing these is the point
([ADR-0006](adr/0006-absence-is-recorded-not-collapsed.md)).

**Withheld** — the publisher lawfully declined to publish a field. eForms does
**not** omit it: it publishes a placeholder and declares the withholding
separately.

**Sentinel** — that placeholder. An amount arrives as `-1`, a bid count as the
code `unpublished` with the number `-1`. Read as a number it is a negative sum
of money, which is the failure the status column exists to prevent.

**Publication id** — the citable TED reference every row carries, and the key
every table is built on. Not the notice UUID: two UUIDs were measured appearing
twice in one publication day.
