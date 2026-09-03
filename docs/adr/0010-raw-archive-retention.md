# ADR-0010: A lawful basis and a retention rule for the raw archive

- Status: accepted
- Date: 2026-09-03

## Context

[ADR-0002](0002-fetch-daily-bulk-packages.md) settled *what* the raw archive is
— whole publication days, fetched byte-for-byte, immutable, the ground truth
every flag traces back to — and stated the boundary against constraint 2: a
local gitignored cache of already-public official documents, from which nothing
carrying a person's name reaches a record.

What it did not state is the part that matters if anyone asks: **on what basis
those bytes are held, and for how long.** Neither existed anywhere in this
repository, and the archive holds personal data today. A contact name, e-mail
and telephone appear in **99.9%** of notices. Measured on one publication day,
[`dropped-fields.md`](../dropped-fields.md) counts **32,135 leaf elements, 3.6%
of every leaf in the package**, that the drop list removes on the way out — all
of them present in the archive on the way in.

The question that surfaced this was a fair one: TED publishes this data openly,
so why not mirror it in full and filter only at publication? Three things
answer it, and the third is the one that binds.

- **Processing is not publishing.** GDPR Art. 4(2) counts collection, storage
  and structuring as processing. Mirroring is processing, and there is no
  public-data exemption to fall back on. Art. 9(2)(e)'s "manifestly made public"
  carve-out does not apply: it concerns special-category data, and it requires
  the *data subject* to have published it, whereas here a contracting authority
  did.
- **The instrument that grants the re-use right declines to override this.**
  Directive (EU) 2019/1024 on open data is expressly without prejudice to data
  protection law. "It is open data" and "we may reprocess it freely" are
  different propositions.
- **Minimisation is measurable here, and it decides the design.** Art. 5(1)(c)
  permits only what the purpose needs. `dropped-fields.md` checks every dropped
  path against the columns of the normalised model and finds **no overlap**:
  every removal is a contact block, a beneficial owner, a named committee
  member, or a free-text privacy reason — never an amount, a date, a code, a
  bid count or a company identifier. Since core classifiers read structured
  fields only (constraint 5), a pipeline that kept this data would compute the
  same flags. There is therefore no purpose that keeping it downstream serves.

## Decision

**Keep the drop at ingestion. Write down the basis and the retention rule for
the archive that precedes it.**

- **Purpose.** Reproducibility. A published flag must be checkable against the
  exact bytes it came from, by a stranger, years later. That is the project's
  central credibility claim and nothing weaker supports it.
- **Basis.** Legitimate interests, GDPR Art. 6(1)(f). The interest is public
  scrutiny of public procurement; the data is already published by an authority
  in an official journal; the persons concerned appear in a professional
  capacity as a contact point for a public tender; and the processing is
  storage of an unmodified official document with no profiling, no enrichment,
  no re-identification and no publication of the personal fields. The balancing
  test is recorded here so it is not reconstructed after the fact.
- **Minimisation.** The drop runs at parse, before the first derived record.
  Personal data exists only in the archive, never in a record, a Parquet file,
  an API response or a finding. `dropped-fields.md` measures this and a test
  asserts no dropped path reaches a record.
- **Retention.** Archived packages are kept while the datasets derived from
  them are published, because that is what the reproducibility purpose needs.
  When a derived dataset is withdrawn, the packages that only it depended on go
  with it. **Reviewed annually**, with the outcome recorded in
  `known-issues.md`. Indefinite retention without review is the failure mode
  this clause exists to prevent.
- **Security.** The archive is local, gitignored, never published, and never
  synchronised to a third-party service. It is not queryable as a dataset; it is
  compressed source documents addressed by checksum.
- **Erasure.** A request reaching the project is an escalation, per the legal
  guardrails. What makes it answerable cheaply is exactly this design: derived
  data carries nothing personal, so a request resolves against the archive
  alone. **This ADR does not decide the answer** — whether an official journal
  archive held for reproducibility must be redacted on request is a question for
  counsel, and the point here is to have the facts ready rather than to
  pre-empt it.

## Consequences

- **A full-fidelity fork is refused, and now for a measured reason rather than
  a cautious one.** Keeping personal data downstream to "benchmark clean against
  complete" would compare identical outputs, because nothing dropped is a
  classifier input. The same measurement that makes the comparison pointless
  makes the retention indefensible under minimisation.
- **Three costs the fork would carry**, recorded so the question does not have
  to be re-argued from scratch. An erasure request stops being answerable with
  "we do not hold it". A queryable, joinable store of contact names is a
  re-identification tool in a way a compressed source document is not, and a
  breach is notifiable within 72 hours (Art. 33) by a project with no security
  programme. And a clean/unclean fork makes a leak *possible but forbidden*,
  where the present design makes it *impossible* — which is the principle the
  rest of this repository is built on.
- **One real capability is given up, and it is named rather than buried.**
  `efac:UltimateBeneficialOwner` is 1,486 of the 32,135 removals in one
  publication day. Beneficial ownership is genuinely analysable — shell
  structures, conflicts of interest — and it is gone. A beneficial owner is a
  natural person by definition, so recovering any of it is a counsel question
  and probably an aggregate-only answer. Tracked in
  [`open-work.md`](../open-work.md) as a decision rather than left as a silent
  absence.
- **The claim is regenerable, not remembered.** `dropped-fields.md` is generated
  from archived packages and reproduces byte for byte, so "the drop costs the
  classifiers nothing" stops being a sentence someone wrote once.
- This ADR states a basis and a balancing test; **it is not legal advice and has
  not been reviewed by counsel.** It is the document to hand counsel, and the
  work it saves is the hour they would otherwise spend reconstructing what the
  pipeline does.

## What would change this

- **Counsel disagreeing with the balancing test**, in which case the retention
  clause tightens and this ADR gets a successor rather than an edit.
- **An erasure request that succeeds against the archive.** Then immutability
  and reproducibility are in real tension, and the answer is probably a recorded
  redaction with a published note — a bigger decision than this one.
- **A classifier that genuinely needs a dropped field.** That is an escalation
  under the legal guardrails, not a schema change, and beneficial ownership is
  the only candidate anyone has identified.
- **Publishing the archive itself**, which this ADR does not authorise and which
  would be a different decision entirely.
