# ADR-0007: Export consolidator-derived attributes with explicit provenance

Status: accepted, 2026-09-21, by the maintainer. Implementation pending.

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