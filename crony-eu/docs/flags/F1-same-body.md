# F1: same-body officer

Status: **implemented 2026-09-22, not calibrated.** `crony flag F1` and `crony base-rate F1` run, and the base-rate table has been computed for `dep:74` and shown to the maintainer, not written here: that is the session 5 STOP. Until the maintainer approves the table and `CALIBRATION` is set in `crony-eu/src/crony_eu/flags/f1_same_body.py`, every output row is `uncalibrated` (CLAUDE.md, constraint 8) and no case packet may be built from it.

Revised 2026-09-16 on two points, both recorded in [ADR-0014](../../../docs/adr/0014-replace-serenata-with-crony.md):

- officer role dates moved from phase 2 into phase 1, because this flag cannot produce a case packet without them
- the hypothesis and the measurement now use the same unit. They did not, which meant the flag was specified to test one thing and measure another

## The question for a journalist

An elected official of commune C, holding a company office at the time a contract was notified, is an officer of the company that won it. Did the official take part in the award or its supervision, and did the commune follow the rules that apply when that happens?

## What phase 1 claims, and what it does not

Phase 1 makes a **descriptive** claim and stops there.

**Descriptive statement (phase 1).** Among distinct (commune, supplier) pairs with at least one commune contract in scope, some share have a councillor of that commune as a dated officer of that supplier during the contract's notification. That share is measured per population band, with Wilson 95% intervals, and reported as what it is: how often this configuration occurs in one département's published contracting.

**Excess-risk statement (deferred).** The interesting claim is the comparative one: that the share is *higher* than would be expected from how often those councillors are officers of companies in the local supplier pool at all. That is a hypothesis about a baseline, and it is not attempted in phase 1.

The reason for splitting them is that the first bundle's hypothesis compared "the share of commune contracts won by companies that have a councillor as an officer" against an expected share, while its measurement counted (commune, supplier) pairs. Those are different denominators. A supplier with forty contracts from one commune is one pair and forty contracts, and the two framings disagree about that supplier by a factor of forty. The pair is the right unit for this question, because the thing being asked about is a relationship, not a transaction, and a framework agreement invoiced monthly is not forty relationships.

Phase 2 may make the excess-risk claim once the pair-level rate exists to compare against and the supplier pool is measured at national scale (INPI). Writing the comparison before the descriptive rate exists would produce a number nobody could interpret.

**Falsifiability, phase 1.** A descriptive rate is not falsifiable and this spec does not pretend otherwise. What is falsifiable in phase 1 is the flag's precision: the claim that a candidate hit, once reviewed, is usually a real person-company-commune configuration rather than a homonym or a stale role. That is measured on a seeded sample and reported below. A precision at or near chance falsifies the flag as a lead generator, whatever its rate.

## Definition (phase 1)

Scope: contracts in the consolidated DECP whose buyer is a commune, in the département being processed.

The buyer is identified by `acheteur_categorie = 'Commune'`, which is the consolidator's own classification and not a legal category code: DECP carries no catégorie juridique for buyers, and session 2 found none to pin. On the 2026-09-19 snapshot that selects 1,111,211 rows, 12,798 distinct communes and 12,815 distinct buyer SIRENs, and it is 100% populated with a commune code on those rows. It is somebody's join rather than a declaration, so a finding that turns on which commune a buyer is gets checked against the buyer's SIRET in the annuaire.

A contract enters F1 when all of these hold:

1. It is the latest version of the contract. Earlier versions are kept for amount history.

   **Not `donneesActuelles` = true**, although that is what this spec said before the file was read. The flag is never wrong where it is set, but 70,277 (contract, titulaire) groups on the real snapshot have no row carrying it, so selecting on it silently drops those contracts. The latest version is the highest `modification_id` per (contract, titulaire), counting a null as zero, and `contracts.parquet` is already cut that way.
2. The supplier has a SIREN (titulaire identifier of type SIRET or SIREN).
3. The supplier's legal category is not on the exclusion list below.
4. An élu of the buying commune was in office on the notification date:
   - élus in the current file: mandate start on or before the notification date
   - élus found only in the pre-election extract: in office until the earliest mandate start of that commune's new council in the current file
   - when neither can be established: `mandate_overlap = unknown`

   So `mandate_overlap` is `true` or `unknown` and never `false`, and that is
   deliberate. The register records a mandate's start and nothing before it, so
   it can place someone in office but cannot establish that they were not: an
   élu first recorded in 2026 may have sat on the council in 2014. A contract
   notified before the recorded start is therefore `unknown`, and an `unknown`
   cannot reach a packet (constraint 9).
5. A judgment, pending or confirmed, links that élu to a natural-person officer of the supplier.
6. That officer role covers the notification date: role start on or before it, and role end absent or on or after it. When either date is missing: `role_overlap = unknown`.

Each hit row carries: contract id, buyer SIREN and commune code, supplier SIREN, amount, notification date, procedure, the élu's function, judgment id, judgment status, rule id, `mandate_overlap`, `role_overlap`, population band, supplier legal category and headcount band, the yearly total per (élu, commune, supplier), `key_collision`, and `possible_432_12_exception`.

### Eligibility for a case packet

A hit may be **counted** whatever its overlaps say. A hit may enter a case packet only when `mandate_overlap` and `role_overlap` are both `true`, the judgment is `confirmed`, the supplier may be redistributed, and this spec's base-rate tables are filled. That is CLAUDE.md constraint 11, restated here because this is the flag it was written for.

[ADR-0007](../adr/0007-consolidator-derived-attributes.md) also requires a
separate maintainer verification of the contract's buyer SIRET as the claimed
commune, against archived official evidence. The review is bound to the DECP
snapshot, row and derived values and to the official evidence. A confirmed
person-company judgment cannot substitute for this check. Exported enrichment
still cites the consolidator, alongside the separate verification evidence. This
gate is not implemented yet.

**Amendment 1 to that record (2026-09-21) sets the standard as snapshot
corroboration**, and it turns one question into two that are recorded apart:

| fact | values | blocks a packet |
|---|---|---|
| `buyer_identity_corroborated` | `true`, `false`, `unknown` | anything but `true` |
| `historical_geography` | `established`, `contradicted`, `not_established` | `contradicted` only |

Corroboration needs archived official evidence that returns the **exact** buyer
SIRET, links it to the expected legal unit, identifies that unit as a commune,
and agrees with the commune code DECP asserts. All four, and the maintainer
confirms the mapping on top. An establishment's location is not on its own
evidence of which public body awarded a contract.

`not_established` no longer blocks, because no approved source carries address
history and blocking on it would have cost every packet. What still blocks:
missing exact-identifier evidence, conflicting identity, ambiguous succession or
merger, and unresolved contradictions. **`not_established` is never rewritten as
`true`**; it travels into the packet as itself.

Establishment dates are consistency checks and not proof, and no boundary is
enforced from them until their semantics are read from documentation rather than
inferred from their presence. A closure today does not disqualify a contract that
predates it, and a missing date establishes no window.

Every qualifying packet carries this sentence, with the retrieval date filled in,
in the status block and in machine-readable provenance:

> Buyer identity was corroborated against a registry snapshot retrieved on
> [date]. Historical commune-code continuity was not independently established.

`role_overlap = unknown` is expected to be common, and how common is one of the numbers session 3 reports. A département where it is the usual answer is a département where F1 can describe a rate and cannot produce a single packet, and that outcome is reported rather than worked around.

## Exclusion list (reported separately, never flagged)

Suppliers where élus usually sit because the commune appoints them: sociétés d'économie mixte (SEM), sociétés publiques locales (SPL), public bodies and public establishments, and other legal categories where a board seat is held on the commune's behalf.

INSEE codes and labels, **pinned 2026-09-22** from `nature_juridique` on the
3,425 suppliers of the `dep:74` slice. DECP could not supply these: its only
supplier category is the INSEE size band (PME, ETI, GE), and it publishes no
catégorie juridique for anyone. The open company API does, as the 4-digit INSEE
code, which is why pinning them moved to session 3's source rather than waiting
for SIRENE.

| code | label | in the slice | of those, with a natural-person officer |
|---|---|---|---|
| 5415 | SARL d'économie mixte | 0 | 0 |
| 5515 | SA d'économie mixte à conseil d'administration | 7 | 7 |
| 5615 | SA d'économie mixte à directoire | 1 | 1 |
| 4xxx | personne morale de droit public soumise au droit commercial | 2 | 2 |
| 7xxx | personne morale soumise au droit administratif | 11 | 0 |

21 suppliers of 3,425, which is 0.61% of the slice, and **10 of them carry a
natural-person officer**. Those 10 are the point of the list. A SEM whose board
seats are held by councillors on the commune's behalf is the exact shape F1 looks
for, so without the exclusion they would be its most confident hits and its
wrongest.

The 7xxx family carries no natural-person officers here at all, which is what it
should look like: a commune appears in the register as an institution, and the
API returns élus for public bodies rather than officers. It stays on the list
because "none this quarter" is not a rule.

**The gap, and it does not close with more codes.** There is no INSEE catégorie
juridique for a **société publique locale**. An SPL is a société anonyme, and the
register files it as one: a probe on 2026-09-21 returned `5599`, "Autre SA à
conseil d'administration", which 64 suppliers in this slice also carry. So an SPL
cannot be told from an ordinary SA by legal category, and the exclusion list
cannot catch it.

That leaves SPLs to the reviewer rather than to the rule. `crony review` shows
the company name and SIREN, and an SPL usually says so in its name; a hit on one
is a hit the maintainer rejects with a note. Recording the limit here because a
list that looks complete and is not is worse than one that says where it stops.

## Tag: possible_432_12_exception

Code pénal art. 432-12, second paragraph: in communes of 3,500 inhabitants or fewer, the mayor, deputy mayors and councillors with delegated powers (or acting for the mayor) may each deal with their commune for the transfer of goods or the supply of services, up to an annual amount of EUR 16,000. The council has to authorise it by a reasoned deliberation, and the élu has to stay out of that deliberation.

Two readings affect the tag. According to the Haute-Savoie mayors' association, a 1996 Cour de cassation ruling applies the cap to the total amount of the contract rather than to the élu's lot. Whether the cap is before or after VAT has not been settled.

Set the tag when all of these hold:

- commune population <= 3,500
- the élu's function is maire, adjoint, or conseiller délégué
- the yearly total of contract amounts for (élu, commune, supplier) <= 16,000

If the DECP publication threshold recorded in `crony-eu/docs/sources/france.md` is above EUR 16,000, no DECP contract can fit under this exception on its own amount, and the tag will almost never fire. That is the expected result, not a bug.

**Checked on Légifrance on 2026-09-22**, in the version in force since
24 December 2025: "dans les communes comptant 3 500 habitants au plus, les maires,
adjoints ou conseillers municipaux délégués ou agissant en remplacement du maire
peuvent chacun traiter avec la commune dont ils sont élus pour le transfert de
biens mobiliers ou immobiliers ou la fourniture de services dans la limite d'un
montant annuel fixé à 16 000 euros." The amount is 16,000 and the population
bound is inclusive.

Two limits the implementation found, recorded rather than worked around:

- **The register publishes no `conseiller délégué`.** Its function labels are
  `Maire`, `Maire délégué` and the numbered `adjoint au Maire`; a councillor
  holding a delegation is indistinguishable from one who does not. The tag cannot
  fire for them and under-fires for that reason alone. `Maire délégué`, the mayor
  of a commune déléguée inside a commune nouvelle, is treated as a maire, because
  the tag marks a possible innocent explanation and setting it too broadly errs
  toward caution about the person rather than against it.
- **The exception names goods and services, not works.** "Le transfert de biens
  … ou la fourniture de services" does not mention a marché de travaux. The tag
  as specified does not look at the contract's type and is implemented as
  specified; whether it should is a question for the maintainer, not an edit.

## Innocent explanations to rule out

- the élu holds the board seat as the commune's representative (the exclusion list should catch this; check anyway)
- homonym: same name and birth month, different person
- the role dates in the register are stale, or record a filing date rather than the date the role began
- the élu declared the interest, left the room, and the award followed the rules
- the small-commune exception applies
- the supplier is a large company and the élu is one director among many (look at the headcount band)
- the commune's staff ran an open competition and no councillor took part in the decision

## What a journalist verifies

- identity: the élu and the officer are the same person (a confirmed judgment is a lead, not proof)
- role dates, against the company's own filings, since the packet's dates come from a register that records filings rather than events
- the council's deliberations and minutes: was the élu present, did they vote, was a deliberation required
- the award procedure and its notice (BOAMP or TED where applicable)
- the money actually paid, for framework agreements
- the élu's own account, before anything is published

## Base rate

Unit: distinct (commune, supplier) pairs with at least one contract meeting conditions 1 to 3. One pair, however many contracts it carries. Every **rate** below uses this unit, so that nothing in this spec compares two denominators. Precision is the exception, and says so: it is measured on sampled candidate *judgments*, as ADR-0003 and the precision line below define it and as `crony review --sample` draws it. An earlier version of this paragraph put the precision sample in the pair unit too, which contradicted the line that specifies it.

Method (session 5):

- population bands: up to 500; 501 to 3,500; 3,501 to 10,000; 10,001 to 50,000; above 50,000
- observed rate: pairs with an F1 hit divided by all pairs, per band, with Wilson 95% intervals
- reported three times over, because they answer different questions: pairs with a **candidate** judgment, pairs with a **confirmed** judgment, and pairs meeting every case-packet eligibility condition above, including buyer verification under ADR-0007. The gap between the second and third reflects all export gates, not role-date coverage alone; report buyer-verification coverage separately without changing the common denominator
- **losses are reported per gate, not netted.** One line per gate saying how many pairs it removed: role overlap unknown, mandate overlap unknown, judgment not confirmed, buyer identity not corroborated, buyer identity contradicted, supplier not redistributable, flag uncalibrated. A single eligible count with a single shortfall hides which gate is actually binding, and after the 2026-09-21 amendment `historical_geography = not_established` is expected on nearly every row while removing none of them, so it is reported as coverage and never as a loss
- `role_overlap` coverage: the share of candidate pairs where role dates resolve at all, per band. A low number here is the headline result, not a footnote
- precision: a seeded random sample of 100 candidate judgments reviewed by the maintainer; report confirmed divided by reviewed, with the sample size and seed

No expected rate is computed in phase 1. The two comparators the first bundle proposed, the département's whole supplier pool and the subset with a head office in the commune, both need officer data for companies that won nothing, which is INPI at national scale and therefore phase 2.

Query: `crony-eu/src/crony_eu/flags/sql/f1_base_rate.sql`, run by `crony base-rate F1 --scope dep:<code>`. The precision sample is 100 judgments with seed 1, the same draw `crony review --scope dep:<code> --sample 100 --seed 1` puts in front of the maintainer.

Measured values: _computed for `dep:74` on 2026-09-22 and awaiting the maintainer's review; not filled in until approved_

| band | pairs | F1 pairs (candidates) | F1 pairs (confirmed) | packet-eligible | role dates resolved |
|---|---|---|---|---|---|
| up to 500 | | | | | |
| 501 to 3,500 | | | | | |
| 3,501 to 10,000 | | | | | |
| 10,001 to 50,000 | | | | | |
| above 50,000 | | | | | |

Precision: _not measured yet_: the sample (100 judgments, seed 1) has not been reviewed. Report sample size, seed, confirmed, rejected, ambiguous
