---
name: legal
description: Consult before publishing any finding, naming any company or institution in output, ingesting a new data source or field, changing a license, using the Serenata brand publicly, signing or drafting any agreement, or responding to a legal threat or data subject request. Also consult when a classifier design seems to need person-level data. This skill carries the project's operating guardrails on Swedish defamation law, GDPR, AGPL-3.0, data reuse, and brand, plus the pre-publication checklist and the escalation list. When in doubt whether something has legal weight, it does; load this skill.
---

# Legal guardrails

These are operating guardrails written to keep day-to-day work inside safe bounds. They are not legal advice, and this skill does not make Claude a lawyer. Everything on the escalation list at the bottom stops work until qualified counsel weighs in. The guardrails are deliberately more conservative than the law probably requires; the project's asset is credibility, and the cheapest legal strategy is to stay far from every line rather than litigate where it sits.

## Defamation

The operating rule: project channels publish institutional and aggregate patterns only. Any material pointing at an identifiable natural person routes to an established media partner and is never published, previewed, or teased on project channels. Not in a post, not in a tweet, not in a patron reply.

Why the rule is shaped this way: Felipe operates under Swedish law, where förtal (Brottsbalken ch. 5) covers pointing someone out as criminal or blameworthy, and truth alone is not an automatic defence; the publication also has to be justifiable. Established newsrooms have legal review, source protection, and the institutional standing to make that justifiability case. A one-person open-source project does not, so it doesn't try. Publishing about entities in other EU countries can also attract those countries' defamation regimes, so the rule holds regardless of where the flagged entity sits.

Companies and public institutions may be named, but only in mechanically factual, source-linked statements: "Buyer B awarded 14 contracts to Supplier S in 2025, 11 via single-bid procedures. Sources: [links]." No adjectives, no imputation of motive, no "suspicious", no rhetorical questions that imply what the sentence doesn't say. If a sentence about a named entity would need softening before a lawyer read it, rewrite it as arithmetic or cut it.

## GDPR and personal data

Names, emails, and phone numbers of contact persons in procurement notices are personal data even though the notices are public. Publication by an authority does not grant this project a free basis to reprocess and republish them. The design answer is the ingestion drop: those fields never enter storage.

**The drop list is `docs/personal-data.md`**, executable as `serenata/parse/personal_data.py`, with a test that fails if the two disagree. Every schema change updates both in the same PR. It is measured against real notices, not read off the specification, and two of its findings are worth carrying into any conversation about this:

- A contact e-mail and telephone number appear in **99.9%** of notices. This is not a rare edge case.
- A beneficial owner's *identifier* appears in 8.1% of notices while their surname appears in 0.8%. An identifier for a natural person is personal data whether or not a name sits beside it, which is why the rules match whole subtrees rather than name-shaped leaves.

The sole-trader edge case is now handled concretely: where `efbc:NaturalPersonIndicator` is true, the organisation's identifying values are suppressed — **including its registration identifier**, because in Sweden a sole trader's `organisationsnummer` is the owner's `personnummer`. The opaque intra-notice key is kept, so the record is anonymised rather than deleted.

**What is still open and has legal weight:** that indicator is absent from about 90% of notices, and absent is "not provided", not "false". So for most organisations, company-or-person is unknown. Ingestion cannot fix this; whether a flag may be *published* about an uncorroborated entity is open-work #11 and must be answered before the first finding.

Other edge cases to treat as personal data: named board members of small companies, and any free-text field that might embed a name. Aggregate above entity level, or route to media. If a classifier design seems to require person-level data, that is an escalation, not a judgment call to make in-session.

No re-identification, ever. No enrichment joins whose effect is to reconstruct a dropped field.

Patron data stays in Patreon; contributor data stays in GitHub. Neither gets exported into project storage. Any data subject request (access, erasure) that reaches the project is an escalation.

## Licensing and data reuse

Code is AGPL-3.0. Network use triggers the source offer, so anything deployed must run only published code; there is no such thing as a private production patch. New dependencies must be AGPL-compatible and source-available; check the license before adding, and record anything borderline in an ADR. Contributions come in under a DCO sign-off rather than a CLA, keeping the barrier low and the provenance clean. The repo is public with neither in place yet, so contribution provenance is currently unestablished; that is open-work #8.

Input data: TED and eForms content is reusable under EU open data rules with source acknowledgment. Keep the attribution line in the README and in every published dataset, and keep a note of the specific reuse terms in the docs so a reviewer can verify them.

Published findings and datasets default to CC BY 4.0. Confirm once (with counsel or with NLnet's preference) before the first public release, then record it in an ADR so it stops being a question.

## Brand

**Decided 2026-09-02: the project publishes under the Serenata name without seeking Open Knowledge Brasil's endorsement.** Felipe co-founded the original project, this is an independent European effort, and the previous rule — no public launch before a written endorsement is on file — was a caution, not a legal requirement. Do not re-raise it as a blocker.

What the decision does require, and what the README now carries: a plain statement that the project is independent, not affiliated with or endorsed by OKBr, and that OKBr bears no responsibility for what it publishes. The exposure here was never defamation or GDPR; it was a reader inferring a partnership that does not exist, and an explicit disclaimer removes it. Keep that disclaimer in place, and describe the lineage as shared history rather than as backing.

Still true: the TED and SIMAP logos may not be used (see data reuse). And if OKBr ever asks the project to stop using the name, that is a relationship question and an escalation — not a unilateral call to make in-session.

## Pre-publication checklist

Run this on every finding, post, or dataset before it goes public. All items, every time.

- No natural person is named or identifiable, directly or by trivial inference.
- Every claim about a named entity is mechanically phrased and source-linked.
- The base rate is stated next to the flag.
- Sources are archived (screenshot plus an archive link) at publication time, so the claim remains provable if the source changes or disappears.
- TED correction and amendment notices for the flagged notice have been checked; a superseded notice invalidates the flag.
- The standing disclaimer is present: these are statistical anomalies, not allegations, and the corrections policy is linked.

Publish a corrections policy before the first finding: errors get corrected in place with a dated note, quickly and without drama. It costs a paragraph and buys credibility precisely when something goes wrong.

## Escalation list

Stop and get qualified counsel before acting on any of these:

- Any output that would name or identify a natural person.
- A legal threat, takedown demand, cease-and-desist, or data subject request.
- Any contract: fiscal sponsorship, media partnership beyond informal terms, employment, anything with a signature line.
- Leaked or whistleblower material offered to the project. This sits under a separate legal regime entirely; do not accept files, do not confirm receipt of anything, refer the source to an established newsroom with source-protection infrastructure.
- Any processing beyond public procurement records and the already-approved sources.
- Any proposed change to the license or to the drop-at-ingestion rule.