# Scope

Status: accepted, 2026-09-16. The canonical scope of this repository.

This document supersedes the scope implied by `crony-eu/docs/adr/0004-france-first.md`, and it is the only copy: `crony-eu/docs/scope.md` is a pointer to this file.

It no longer leaves `crony-eu/CLAUDE.md` and `crony-eu/docs/work-order-phase-1.md` alone. Both are changed by it, and so is the rest of this repository: [ADR-0014](docs/adr/0014-replace-serenata-with-crony.md) makes this project what the repository is for, and retires Serenata Europa's TED pipeline rather than running the two side by side. [`docs/transition-ledger.md`](docs/transition-ledger.md) says what happens to each piece of it.

## What changed

The first bundle described a French project. The question that followed was whether the same thing works for Europe. The answer separates into layers, and only one layer forces a per-country answer.

Two layers are already European. Public money: TED covers above-threshold awards across the union, the Financial Transparency System covers beneficiaries of programmes under direct and indirect management, and Kohesio covers shared management with more than 1.5 million projects and roughly 500,000 beneficiaries, published in CSV, XLSX and RDF with per-country exports. Company identity: the Open Data Directive's high-value dataset rules put companies and company ownership among the six mandatory categories, free of charge and machine-readable through an API and, where appropriate, as bulk download, in force since 9 June 2024.

Office holders are half European. EveryPolitician, now run by OpenSanctions, holds close to 700,000 politicians across 261 countries and territories, is FollowTheMoney-native, and grants free API keys to journalists and public-interest users. Its coverage is built around national and senior positions. The same-body check bites hardest at municipal level, and municipal coverage is thin almost everywhere. France is the exception, because the Répertoire national des élus publishes every municipal councillor in one file.

The layer that decides is company officers, and it is national. Openness ranges from free bulk registers with directors (Denmark, Estonia, France) to paid extracts (Sweden) to per-document fees and restricted access elsewhere. Ownership data moved backwards after the 2022 CJEU ruling and now runs through legitimate-interest access. The second decider is worse: even where officers are public, the field that disambiguates a person differs by country. Full birth date, year and month, a partial identifier, or nothing beyond a name. There is no EU-wide person key for this, and there should not be one.

## The project, restated

One tool, a shared spine, a country adapter per jurisdiction, and a separate EU-institutions line that needs no adapter at all.

The tool proposes links between office holders, companies and public money from official open data. A person confirms every person-to-company link before it can appear in an output. The output is a case packet: a standalone HTML network, the edge list, and the source behind every edge. Nothing is published by the tool. The maintainer shows packets to journalists and research partners from his own machine.

"Europe" means the set of countries where the check can actually run, not one graph of the continent. Three reasons hold that line. Bulk republication of registry data is the shape courts are least comfortable with, even when every record is public. Nobody can verify a hundred thousand edges, and an unverified edge is a liability. My Little Crony, the project this follows, topped out at 197 nodes and 360 connections after a year of collective effort, which is roughly the size a person can still hold in their head.

## Two lines

### Line A: national, case-level

Seeds are office holders in a national or subnational body. The pipeline joins them to company officers and to money paid by the body they sit in. This is the line that needs matching, human review, calibrated base rates and a per-country legal module. France is the first implementation.

### Line B: EU institutions, pan-European by construction

Seeds are MEPs. Every MEP has had to publish their meetings with interest representatives since November 2023, and those meetings are also attached to each procedure in the Legislative Observatory. The Transparency Register adds each organisation's declared lobbying spend. MEP declarations of interests add outside activities and holdings. TED, the Financial Transparency System and Kohesio supply the money.

The important property: the meeting edges are already person-to-organisation and published by the institution itself. Line B needs no name matching and no judgments table for its core network. That makes it cheap, EU-wide on day one, and the natural piece for a research collaborator to own rather than the maintainer. It is also the line that would carry an EU-level funding application.

Line B does not replace line A. It answers a different question and produces a different flag family, and its specs do not exist yet.

## Trunk decision

France, line A, stays the trunk. Phase 1 proceeds as written in `crony-eu/docs/work-order-phase-1.md`.

The reasoning: line A contains every hard part of the machinery, which is matching, review, judgments, base rates and case packets. Line B exercises none of it. Starting with line B would mean building the easy half first and leaving the calibration machinery untested, then discovering its problems later with a collaborator waiting. France is also fully specified already, and a trunk switch means re-specifying from zero, which is the cost that was nearly paid once.

The call flips only under one condition: a funding deadline that requires EU-wide coverage before phase 1 can finish. In that case line B starts first and phase 1 waits, in that order, not both at once.

Line B may start at any time after phase 1 ships, in its own repository, sharing the spine and the constraints.

## The country adapter contract

A country joins line A by supplying six things. Nothing else in the pipeline is country-specific.

### 1. Seeds: office holders

| field | notes |
|---|---|
| person_key_fields | surname variants, given names, and whatever disambiguating attribute the country provides |
| birth_key_precision | full date, year and month, year only, or none |
| body_id | the public body where the office is held |
| body_level | municipal, intermunicipal, regional, national |
| mandate_type, function_label | as published |
| mandate_start, mandate_end | dates or null |
| provenance | dataset, URL, retrieval date, licence |

`birth_key_precision` is the gate. A country that reports `none` cannot run line A with the deterministic rule, and waits for a probabilistic approach with its own ADR.

### 2. Bodies

`body_id`, name, level, population where the level is local, and a mapping from the identifier used in the money data to `body_id`. Population is needed wherever the local offence framework has a size threshold.

### 3. Officers

`company_id`, officer name fields, birth key at the declared precision, role label, role start and end, and officer type (natural or legal person).

Role start and end are **required, not "where available"**. A hit is a claim that a person held a company office at the time their commune paid that company, and a source that cannot date the office cannot support the claim. Missing role dates mean `role_overlap = unknown`, never `true`, and an `unknown` overlap cannot reach a case packet. A country whose officer source carries no role history can still run matching and produce aggregate counts; it cannot produce a packet, and its capability record says so.

This is a change from the first bundle, which postponed role dates to phase 2 while phase 1's own flag needed them. See `crony-eu/docs/flags/F1-same-body.md`.

### 4. Companies

`company_id`, legal form or category code, status, head office locality, size band where available, and a publication restriction flag for entities that may not be redistributed.

### 5. Money

Contract or payment records with buyer identifier (mappable to `body_id`), supplier `company_id`, amount in EUR, date, procedure where available, contract id, and a version marker where the source publishes amendments.

### 6. Legal module

Forbidden sources for that country, redistribution restrictions, the categories of entity excluded from exports, the list of legal forms where an office holder sits as the body's representative, and the offence framework that the same-body flag maps to locally. France needed three of these written before a line of code (LO 135-2 on asset declarations, INPI's non-diffusion rule, and Code pénal 432-12 with its small-commune exception).

### Capability declaration

Each adapter publishes a capability record stating which of the six exist, at which body levels, and what is missing. A flag runs for a country only when every layer it needs is present at the same body level. A country with national office holders and municipal money cannot run the same-body check, and the capability record says so instead of producing a silent gap.

## Entry tests

ADR-0004 listed three tests. There are four.

1. An official list of office holders at the body level being checked, carrying a disambiguating attribute.
2. Open company officer data with a comparable attribute.
3. Contract or payment data with supplier identifiers, mappable to the body.
4. A person who can read the local law and say what is forbidden and which offence the flag maps to.
5. Officer role history: dated starts and ends, at coverage high enough that `unknown` is the exception rather than the rule.

The fourth test is a person, not a dataset, and it is the one that will hold up a country longest. The fifth is the one France has not actually passed yet: the open officer API is not known to carry role dates, INPI is expected to, and neither has been measured. Phase 1 measures it before anything downstream is built.

## Country shortlist

A hypothesis to check, not a finding. The openness claims behind tiers 2 and 3 come partly from commercial due-diligence vendors, so each country needs the four tests run properly before it is scheduled.

| tier | countries | why |
|---|---|---|
| 1, confirmed | France | tests 1 to 4 passed; **test 5 unmeasured**, and it is phase 1's first gate |
| 1, likely | Denmark, Estonia | free registers including directors; office-holder granularity and birth key to verify |
| 2, to check | Czechia, Latvia, Poland, Ireland | officers reportedly open; municipal office-holder data unknown |
| 3, blocked on cost or access | Sweden, Netherlands, Italy, Spain, Austria, Germany | officer data paid or restricted; Sweden returns once Bolagsverket's paid data is priced |

Realistic ceiling: four to six countries for one maintainer plus collaborators. That number goes into any funding application instead of implying 27.

## Phases

| phase | content | status |
|---|---|---|
| 1 | France, communes, one département, end to end, **including officer role history** | specified, not started |
| 2 | France depth: INPI at national scale, intermunicipal and departmental buyers, co-officers one to two hops, HATVP declarations, hand-entered reported edges, TED cross-check | outline only |
| 3 | Second country, which proves the adapter contract. Denmark or Estonia unless the four tests say otherwise | outline only |
| 4 | Line B, EU institutions, separate repository, sharing the spine | not specified |
| 5 | Third and fourth countries, if the adapter held without changes to the spine | not specified |

Phase 3 is where the adapter contract earns its keep or gets rewritten. Expect the first real adapter to force changes to the contract above, and treat that as the point of doing it.

## Relationship to Serenata Europa

**This project replaces it.** The first version of this section said the relationship was "unchanged", which was written when both projects were expected to run. They are not. [ADR-0014](docs/adr/0014-replace-serenata-with-crony.md) retires the TED pipeline, and [`docs/transition-ledger.md`](docs/transition-ledger.md) is the inventory of what goes when.

Three consequences follow, and the first is the one the old wording got backwards.

**Nothing here depends on Serenata Europa.** The old text sent anything computable without personal data "upstream in Serenata Europa rather than here", which made a retiring project a dependency of this one. Phase 1 reads no Serenata table and calls no Serenata module. The TED cross-check in phase 2 reads TED directly, if it happens at all.

**Serenata's obligations do not retire with its code.** Its raw TED archive still exists on disk, its lawful basis and retention period are unresolved, and no counsel is engaged. `docs/adr/0010-raw-archive-retention.md` and `docs/counsel/README.md` stay live, and this project widens that question rather than escaping it: it processes personal data by design, where Serenata processed it by accident.

**Its name is a commitment to people.** An NLnet application, a Patreon campaign and a public README describe Serenata Europa to funders, journalists and contributors. Retiring it is something they are owed an account of.

### Aggregates are not automatically person-free

The old text said aggregate outputs "are person-free once computed" and can be shared without a case packet. That is true of the arithmetic and not of the aggregate.

An aggregate over a small group re-identifies it. "The share of local contract value going to companies with an office holder on the board" is a safe sentence for a département and an unsafe one for a commune of four hundred people with one supplier, where the share names a person to anyone who lives there. Small-cell disclosure is the ordinary failure of statistical publication, not an exotic one.

So: an aggregate may be shared when it is computed over a population large enough that no cell identifies anyone, the cell sizes are reported alongside it, and the maintainer has looked at the small cells. Below that, it is a case packet or it is nothing. Running the tool locally and computing a number rather than printing a name are both real protections and neither of them is this one.

## What never leaves the machine

Local operation is not a privacy control on its own: what is exported is what matters, and a packet handed to a journalist has left the machine as completely as a website would have.

An export refuses, rather than filters afterwards:

- entities their register forbids redistributing (in France, INSEE/INPI non-diffusion)
- any person-to-company edge without a `confirmed` judgment
- any hit whose mandate or role overlap is `unknown`
- any flag whose base rate has not been measured
- evidence beyond the records the packet's own edges cite

A packet is invalidated when a judgment behind it changes. It records the judgment ids and the rule id it was built under, so a later `rejected` or `ambiguous` decision can be traced to every packet that relied on it, and the maintainer is told which packets to withdraw. Judgments are append-only precisely so this is answerable.

## Not in scope

Beneficial ownership registers. Parliamentarians' asset declarations from any source. Real estate. Family relationships derived by inference rather than published by an official register. Any public or searchable database of people. A hosted service. Cross-country person resolution. Machine learning, embeddings or LLM calls anywhere in the pipeline.

## Open questions

Blocking phase 1:

- which département (maintainer picks before session 1)
- **whether any French officer source carries dated role history, and at what coverage** (gate in session 3). If it does not, phase 1 produces aggregates and no case packets, and the trunk decision goes back on the table
- whether officer records carry birth month as well as year (gate in session 3; if year only, the matching rule needs a new ADR)
- whether the RNE surname field holds the birth name or the usage name (answered in session 4 with aggregate counts)
- the current DECP publication threshold, which decides whether the small-commune exception tag can ever fire

Blocking phase 3:

- the four tests run properly for Denmark and Estonia
- who reads the law for country two

Blocking phase 4:

- whether line B gets a collaborator owner, which changes its repository, its legal controller and its publication route
