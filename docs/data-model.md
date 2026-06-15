# Data model

> **Not written yet.** This document is the contract for milestone 1's
> normalisation stage. The list below is its planned table of contents, not
> the model itself.

It will document, for the one relational model spanning eForms and legacy
TED notices:

- the entities: contracting authorities, companies, procedures/notices,
  lots, awards, and the relations between them;
- per-field provenance: which source field (eForms BT or legacy TED element)
  each value came from, and from which notice;
- absence semantics: "not provided" and "not applicable" are different
  facts and are recorded explicitly, never collapsed into NULL;
- fields excluded by design: everything that could carry a natural person's
  name is dropped at parse time and has no column here;
- keys: how every derived record traces back to its source notice ID.
