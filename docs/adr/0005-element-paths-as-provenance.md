# ADR-0005: Record provenance as element paths, not eForms BT codes

- Status: accepted
- Date: 2026-09-02

## Context

Every value in the normalised dataset has to say where it came from — which
source field, in which notice. The question is what vocabulary names the field.

There are two candidates, and they are not equivalent.

**eForms BT codes** (`BT-105`, `BT-756`) are what the specification names fields
by, what the eForms documentation is written in, and what other tools —
opentender, DIGIWHIST, the Publications Office's own material — speak. A
reviewer comparing this project's output to another's will be holding BT codes.

**Element paths** (`notice/cac:ProcurementProject/cbc:Name`) are what is
actually in the XML. `serenata.survey` already reports them, and
[`field-usage.md`](../field-usage.md) measured 456 of them across 3,190 notices.

The difficulty is that the mapping between the two is not derivable from a
notice. It lives in the **eForms SDK**, a versioned artefact published separately
from the notices themselves. Taking BT codes as the primary vocabulary means
taking on the SDK: a dependency to vendor or fetch, a version to track against
the `cbc:CustomizationID` each notice declares, and a mapping that can change
between SDK releases — for a pipeline whose parse and normalise stages are
required to be offline and deterministic.

[Open-work #2](../open-work.md#2-survey-which-eforms-fields-notices-actually-populate)
left this open explicitly: the survey reports paths, and the data model has to
decide which of the two it is written against.

## Decision

**Provenance is recorded as the element path.** The data model's source column
for every field is the path observed in the XML, and
[`data-model.md`](../data-model.md) is written in that vocabulary throughout.

A BT code is an **annotation that may be added later**, not a replacement. It
attaches to a field's provenance record without changing any column, any key or
any classifier, because provenance is data about a field rather than the field's
own name.

Three things decided it.

**It is observable.** A path can be verified by opening the notice. Nobody has
to trust a mapping table, and a stranger rerunning the pipeline sees the same
paths this project saw. That is the same reasoning that put measurements rather
than the specification behind the data model in the first place.

**It keeps parse and normalise offline.** Constraint 4 requires those stages to
be reproducible from archived inputs alone. An SDK lookup is either a network
call, which is prohibited outright, or a vendored artefact whose version becomes
part of the pipeline's output identity. Neither is worth paying before anything
downstream needs BT codes.

**It has no ambiguity to resolve.** Several BT codes map to the same element in
different contexts, and the context is the path. Starting from the path and
annotating upward loses nothing; starting from the BT code requires resolving
the context first.

## Consequences

- The dataset is legible to anyone who can read the XML, and slightly less
  legible to someone who thinks in BT codes. That is a real cost and it lands on
  the audience — reviewers and comparison tools — that matters most.
- Adding BT codes later is additive. It needs the SDK, a version pinned against
  `cbc:CustomizationID`, and an ADR recording how that version is tracked. It
  does not need a migration.
- Paths are verbose. `data-model.md` uses documented shorthands (`<ext>`,
  `<org>`) that expand mechanically, and a test expands them and checks each
  path against the survey's measured set, so a typo in the model is a failing
  build rather than a column nobody can trace.
- Comparison against opentender or DIGIWHIST requires the mapping this ADR
  defers. That work belongs with the comparator scan, not with ingestion.
- Legacy TED notices have no BT codes at all, so a BT-first model would have
  needed a second vocabulary for them regardless. Paths cover both formats with
  one mechanism.

## What would change this

- **A classifier or a published dataset that needs BT codes to be useful.** The
  first consumer who cannot work without them is the trigger, and the answer is
  to add the annotation, not to change the model.
- **Comparator work against a BT-keyed dataset** becoming a milestone rather
  than a background question.
- **TED publishing an authoritative path↔BT mapping inside the notices**, which
  would remove the dependency argument entirely.
- **The eForms SDK becoming a dependency for another reason** — the
  `not_applicable` derivation in [ADR-0006](0006-absence-is-recorded-not-collapsed.md)
  is the likeliest — at which point the cost of BT codes drops to near zero and
  this should be revisited rather than assumed.
