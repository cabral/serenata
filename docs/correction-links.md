# Correction links in archived notices

How TED notices in the archive point at the notices they correct, measured
before designing anything that acts on them. [Open work
#6](open-work.md#6-handle-corrected-and-withdrawn-notices) requires this order:
measure the structure, then map it. [ADR-0013](adr/0013-correction-and-withdrawal-semantics.md)
is the design this report is evidence for.

The query is [`correction-links.sql`](correction-links.sql) beside this file, so
the numbers can be checked without running the pipeline. It selects counts and
shapes only — never an identifier, a notice or a field value.

> © European Union, 1998–2026. Source: [TED](https://ted.europa.eu), the
> Supplement to the Official Journal of the European Union. Reuse authorised
> under Commission Decision 2011/833/EU; see [data-reuse.md](data-reuse.md).
> This report is a derived measurement — it carries frequencies and identifier
> shapes, never field values.

## What was measured

The five archived publication days of 2026 already used elsewhere in this
repository — OJ S 52, 94, 113, 157 and 168, **19,180 notices**. Measured
2026-09-05 against `data/normalised/`.

This is a structural measurement of one field. It is **not** a verification of
correction semantics, not evidence about withdrawals, and not a measurement of
any notice's content.

## What the field holds

**2,840 notices (14.8%)** carry `efac:Changes/efbc:ChangedNoticeIdentifier` with
status `present`; 16,340 record it as absent. That matches the independent path
survey in [field-usage.md](field-usage.md), which counts the same element at
14.8% across the same packages.

**The column is polymorphic.** Two unrelated identifier namespaces share it:

| Shape | Links | Share |
|---|---:|---:|
| eForms notice UUID + `-NN` version suffix (39 chars) | 1,752 | 61.7% |
| Digits + `-` + digits (11, 10 or 9 chars) | 1,088 | 38.3% |

The first is this project's own `source_notice_id` with a two-digit version
appended; nine distinct suffixes appear. The second matches no identifier the
normalised model carries. A mapping must therefore **detect which namespace a
link uses and record that**, rather than assume one and silently drop the rest —
38.3% is too large a share to treat as noise.

## What resolves, and what that does not mean

| Resolution against `source_notice_id` | Links |
|---|---:|
| Raw value | 0 of 2,840 |
| After removing the trailing `-NN` | 45 of 2,840 (1.6%) |

Zero raw resolution is the version suffix, not a broken link: the identifier is
the target notice plus the version being corrected, so it cannot equal a notice
identifier as stored.

**The 1.6% is a statement about corpus coverage, not about the mapping.** A
corrigendum published on one of five sampled days usually corrects a notice
published on a day the archive does not hold. Correction handling cannot be
demonstrated end to end on a sampled archive, and this report is not evidence
that it works. A continuous archive spanning the corrected notices' publication
dates is a prerequisite for that demonstration, and does not exist yet.

## Ambiguity and chains

| Property | Count |
|---|---:|
| Distinct targets referenced | 2,832 |
| Targets referenced by more than one notice | 7 |
| Chains of depth 2 within the corpus | 0 |
| Self-references | 0 |

Seven contested targets in five days is small but nonzero, and the data alone
does not order two notices correcting the same target. Zero observed chains is
a consequence of the same coverage limit as above, not evidence that chains do
not occur.

## Which notices are corrected

| Root element | Corrected notices |
|---|---:|
| `ContractNotice` | 2,695 |
| `ContractAwardNotice` | 118 |
| `PriorInformationNotice` | 27 |

The single-bid rule reads award notices, so **118** bounds how much of its input
carries a correction link at all in this corpus.

`cbc:VersionID` is populated on every notice and does move: 18,153 at `01`, 699
at `02`, 123 at `03`, 58 at `04`, 27 at `05`.

## What this does not establish

- **Withdrawals.** Nothing here distinguishes a correction from a withdrawal.
  `efac:Changes/efac:ChangeReason/cbc:ReasonCode` appears on 14.2% of notices in
  [field-usage.md](field-usage.md) against the link's 14.8%, so some links carry
  no reason code — but that survey records path presence, never values, and the
  normalised model does not carry the reason code at all. Distinguishing the two
  needs a further measurement and probably a schema change.
- **Contract modifications are a different relation.**
  `efac:ContractModification/efbc:ChangedNoticeIdentifier` appears on 6.0% of
  notices, up to 46 times in a single notice. It is not a corrigendum link and
  the normalised model does not read it. Conflating the two would be a
  correctness bug, not a shortcut.
- **Current flags.** None of the 96 flags the single-bid rule produces sits on a
  notice corrected by another notice in this corpus, and none is itself a
  corrigendum. At 1.6% resolution that is not evidence the flags are current; it
  is the absence of evidence that they are stale.
