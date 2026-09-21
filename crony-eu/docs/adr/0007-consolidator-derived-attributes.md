# ADR-0007: Export consolidator-derived attributes with explicit provenance

Status: accepted, 2026-09-21, by the maintainer. **Amended 2026-09-21 by the
maintainer (Amendment 1, at the end of this record); the original decision below
stands unchanged and is not superseded.** Implementation pending.

## Context

Consolidated DECP includes buyer-declared fields and consolidator enrichment.
`acheteur_commune_code` and `acheteur_categorie` belong to the second family:
they are not the buyer's declarations. The distinction is recorded in
[France sources](../sources/france.md) and the DECP adapter, but not yet in an
export policy. Constraint 2 in [CLAUDE.md](../../CLAUDE.md) requires a source
dataset, the most specific available URL and a retrieval timestamp for every
exported attribute and edge.

Three alternatives remain: cite the consolidator, re-derive geography from
official evidence before export, or refuse to export derived geography.
Re-derivation would create a different assertion, potentially from a different
vintage; omission would not resolve F1's dependence on the buyer's commune.
Neither is required merely to attribute the value honestly. Attribution,
however, does not establish that a join is correct.

## Decision

**Allow derived attributes from approved consolidators, explicitly attributed
as derived.** Each attribute identifies its source field and source record,
the consolidator's dataset, the most specific available source URL and the
snapshot's fetch-time `retrieved_at`. Preserve the distinction between
buyer-declared fields and enrichment in the machine-readable export and sources
panel. A platform URL for the declaration is not provenance for enrichment;
never imply Crony retrieved the consolidator's upstream inputs when it did not.

**Verify F1 buyer identity separately, before export.** The maintainer reviews
archived official evidence for the contract's exact buyer SIRET, establishing
that it is the buying commune claimed by F1. Record the result separately from
the person-to-company judgment, bound to the DECP snapshot and row, the checked
category and commune values, and the official evidence's source, URL, retrieval
time and content hash. A SIREN-level head-office location alone is insufficient.
Unknown, missing, ambiguous or conflicting evidence blocks the packet; a newer
address is not by itself proof of the buyer's historical identity. Do not
silently replace the derived value or treat human review as an official source.

## Consequences

Staging and descriptive counts may retain consolidator geography. F1's
packet-eligible counts and packet builder must require the same buyer check.
The packet cites both the derived assertion and its verification evidence,
copies only cited records, and names the review it relies on. Changed inputs
require a new check; a superseded adverse review invalidates dependent packets.

Fetch archives evidence under `$CRONY_DATA_DIR`; review, transforms and export
make no network calls and add no wall-clock timestamps. Existing approved-source,
non-diffusion, judgment, overlap, calibration and disclosure rules still apply.
This decision approves neither a new source nor a real-data disclosure.

The [execution handoff](../work-order-phase-1.md#adr-0007-execution-handoff)
sets implementation gates and synthetic acceptance tests. No export enforcement
or buyer-review implementation is claimed by this record.

## Revisit triggers

Revisit if verified join errors make manual checking impractical, official
SIRET-level historical coverage supports deterministic re-derivation, or the
consolidator changes its enrichment semantics, provenance or reuse terms.

## Amendment 1, 2026-09-21: snapshot corroboration, with its limits named

Decided by the maintainer after the source gate in
[the handoff](../work-order-phase-1.md#adr-0007-execution-handoff) was answered.
The original decision above is preserved: derived attributes may be exported with
explicit derived provenance, and a separate maintainer check of the buyer stands
between the mapping and an exported relationship. What changes is **which
unknown blocks a packet**.

### Why

The decision as written required evidence that the buyer SIRET was the claimed
commune, and rejected "a newer address" as proof of historical identity. The
approved source, `fr-entreprises-api`, has no as-of parameter and no address
history, so read strictly that made the historical question `unknown` for every
contract notified before the snapshot. 53.3% of commune-buyer rows are notified
before 2024. The decision would have blocked essentially every packet on a
question the buyer check was never the right instrument for, while leaving the
question it *can* answer unrecorded.

### Decision

**Adopt snapshot corroboration as the standard for buyer identity.** The
historical DECP record identifies its buyer by SIRET. Archived official evidence
must do all four of these, and a failure of any of them is not a pass:

1. return that **exact** SIRET, not a near match and not its legal unit alone
2. link that SIRET to the expected legal unit
3. identify that legal unit as a commune
4. agree with the commune code DECP asserts

The maintainer then confirms the mapping. **Establishment location alone does not
establish which public body awarded a contract**, so a geographic match is not
the finding and cannot stand in for the confirmation.

**Record two facts, separately, and never collapse them.**

- `buyer_identity_corroborated`: whether identity was corroborated against the
  archived snapshot.
- `historical_geography`: `established`, `contradicted`, or `not_established`.

**Absence of address history alone no longer blocks a packet.** These still do:

- missing exact-identifier evidence
- conflicting identity
- ambiguous succession or merger
- unresolved contradictions

**`not_established` is never rewritten as true.** It is a third value, it
survives into the export, and a packet carries it rather than resolving it.

**Establishment dates are consistency checks, not historical proof.** Their
semantics are to be verified from documentation before any boundary is enforced;
field presence was observed, meaning was not. Until then no window is enforced.
Three rules hold whenever they are:

- a current closure does not disqualify a contract that predates the closure
- missing dates do not establish an existence window; absent is not open-ended
- a case that needs historical evidence to resolve a **specific** ambiguity stays
  blocked until that evidence exists from an approved source

### What every qualifying packet must say

Verbatim, in the status block, with the evidence retrieval date substituted:

> Buyer identity was corroborated against a registry snapshot retrieved on
> [date]. Historical commune-code continuity was not independently established.

The same limitation travels in machine-readable provenance, not only in prose.
This is **a deliberately limited evidentiary standard, not a disclaimer**: it
records what was checked and does not override contradictory evidence, and where
evidence conflicts the packet is refused rather than published with a caveat.

### What the evidence so far does and does not support

Five successful probes establish that the check is **feasible**. They do not
establish that the consolidator's join is **accurate**. The 26 buyer commune
codes absent from the population vintage bound nothing about mapping errors among
the 12,772 codes that are present; they were never a sample of that question.

In code, the resolution must match exactly rather than trust a search: a query
returning zero results, several results, or no result carrying the exact SIRET is
a refusal, not a best match.

### Consequences of the amendment

`historical_geography` joins the packet's status block and the machine-readable
provenance as a first-class value with three states. F1's packet-eligible count
follows export eligibility under this standard, and the losses at each gate are
reported separately rather than netted. Snapshot corroboration relaxes nothing
about officer-role or mandate overlap, which are unchanged and still govern
under constraint 9.

Engineering readiness and real-data feasibility are separated: the records,
review, refusals and export tests can be built and proven against generated
fixtures, and doing so is not a session 3 pass and does not permit a real packet.
