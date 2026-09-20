# Sources: France

Every source the pipeline may touch in France. Field lists marked "expected" come from documentation or older files. The adapter session replaces them with the observed schema: column names, types and null rates only, never sample values (CLAUDE.md, constraint 13).

Three sources have been fetched and staged: the élus register (session 1), and
DECP and the INSEE populations (session 2). Their sections carry an observed
schema and the "expected" lists above them are kept as a record of what the
documentation led this project to believe, which was wrong in specific ways each
time. The lists that still decide whether phase 1 can produce anything at all are
the officer fields, and they are unverified: birth month precision, and dated
role history.

A source not listed here is not allowed until the maintainer approves a new section.

## fr-rne-elus: Répertoire national des élus

- Publisher: Ministère de l'Intérieur
- Landing page: https://www.data.gouv.fr/datasets/repertoire-national-des-elus-1
- Pre-election extract (councils in office on 23 February 2026, before the March 2026 municipal elections): https://www.data.gouv.fr/datasets/elections-municipales-2026-maires-et-conseillers-municipaux-sortants
- Licence: Licence Ouverte 2.0
- Updates: quarterly. The August 2026 update reflects the March 2026 municipal elections. Dates have been ISO 8601 since that update; older files used DD/MM/YYYY, so the parser accepts both.
- Access: CSV files. Resolve resource URLs through the data.gouv.fr API (`/api/1/datasets/<slug>/`) instead of hardcoding them.
- Phase 1 files: conseillers municipaux and maires. Later: conseillers communautaires, départementaux and régionaux, députés, sénateurs, représentants au Parlement européen.
- Expected columns (seen in older files; verify): Code du département, Libellé du département, Code de la commune, Libellé de la commune, Nom de l'élu, Prénom de l'élu, Code sexe, Date de naissance, Code de la catégorie socio-professionnelle, Libellé de la catégorie socio-professionnelle, Date de début du mandat, Libellé de la fonction, Date de début de la fonction.
- Gotchas:
  - an élu with two functions appears twice in the same file; an élu with two mandates appears in two files
  - profession is self-declared
  - the files don't say whether `Nom de l'élu` is the birth name or the usage name. Session 4 answers this with aggregate match counts per surname variant, split by sex, and records the answer here.
  - corrections go through prefectures and show up in the next quarterly file
- History: Regards Citoyens keeps a change history of the register at https://github.com/regardscitoyens/rne-history (phase 2, for replacements during a term).

### Observed schema, session 1, fetched 2026-09-16

Four files, semicolon-delimited, UTF-8. 1,066,291 rows staging into 994,761
people. Row and person identifiers are unique.

| file | rows | people | communes |
|---|---|---|---|
| elus-conseillers-municipaux-cm.csv | 511,225 | 510,704 | 34,926 |
| elus-maires-mai.csv | 34,826 | 34,826 | 34,826 |
| mun2026-cm-sortants-20260227.csv | 485,351 | 484,056 | 34,953 |
| mun2026-maires-sortants-20260227.csv | 34,889 | 34,889 | 34,888 |

Published columns, verbatim. The conseillers files have 16, the maires files 14.

    Code du département                              both
    Libellé du département                           both      not read
    Code de la collectivité à statut particulier     both      not read
    Libellé de la collectivité à statut particulier  both      not read
    Code de la commune                               both
    Libellé de la commune                            both
    Nom de l'élu                                     both
    Prénom de l'élu                                  both
    Code sexe                                        both
    Date de naissance                                both
    Code de la catégorie socio-professionnelle       both
    Libellé de la catégorie socio-professionnelle    both      not read
    Date de début du mandat                          both
    Libellé de la fonction                           conseillers only
    Date de début de la fonction                     both
    Code nationalité                                 conseillers only

**Four corrections to what this document predicted.**

1. The two `collectivité à statut particulier` columns were not expected. They
   carry Paris, Lyon, Marseille and Corsica.
2. `Code nationalité` is in the conseillers files and not the maires files.
3. **The maires files carry no function column at all.** The function is the
   file. `function_label` is supplied as `Maire` for those rows rather than left
   null, which would make a mayor indistinguishable from a councillor holding no
   delegated function and would quietly stop F1's 432-12 tag firing.
4. **The two vintages publish dates differently, and the difference is
   dangerous.** The current files are ISO 8601, `9999-99-99`. The pre-election
   extracts are `99/99/99`, a **two-digit year**. Reading the second with
   `%d/%m/%Y` parses without error and returns the year 71 for `03/04/71`. Doing
   exactly that put all 520,240 pre-election rows in the first century, with
   mandates starting in the year 20. A mandate beginning in the year 20 precedes
   every contract ever notified, so F1's `mandate_overlap` would have been true
   for half the population and the flag would have looked like it worked. The
   parser now chooses the format by matching the whole string, and a two-digit
   year takes the century that does not put the date in the future.

**Null rates.** Everything is populated except three columns.

| column | null |
|---|---|
| `Code du département` | 0.66% |
| `Libellé de la fonction` | 64.86% |
| `Code nationalité` | 6.54% |
| everything else read | 0.00% |

The département code is empty for commune codes beginning `97` (3,140 rows) and
`98` (3,848 rows), the overseas départements and collectivities, which fill the
collectivity columns instead. **A `--scope dep:<code>` run therefore cannot
reach an overseas commune**, and the capability record has to say so rather than
leave a silent gap. Phase 1 targets a metropolitan département, so this does not
block it. The function label is null because most councillors hold no delegated
function, and the nationality code because the maires files lack that column
(34,826 + 34,889 = 69,715 rows, exactly 6.54%).

**Date ranges after the century rule**, which is the check that the rule worked:

| | earliest birth | latest birth | earliest mandate | latest mandate |
|---|---|---|---|---|
| current | 1072 | 2008 | 2026-03-15 | 2026-08-04 |
| pre-election | 1927 | 2026 | 2020-05-18 | 2026-01-16 |

The mandate windows are the March 2026 and March 2020 municipal elections, which
is what they should be.

**What is left wrong, measured rather than claimed away.** One row in cm_current
has a birth year in the 1000s: a typo in the register, marked
`dates_plausible = false` and carried rather than dropped. One row in the
pre-election files has a birth date after its own mandate start, which is the
century rule's known limit: a two-digit year cannot distinguish 1926 from 2026.
Both are harmless in the safe direction, because a birth key of `2026-xx` or
`1072-xx` matches no officer. That is one row in 520,240 and one in 511,225.

**The birth key the matching rule needs is present on 100% of people**, in both
vintages. `FR-NAME-BIRTHYM-v1` and ADR-0003 assume year and month on the élu
side, and the élu side delivers it.

**The maires files are redundant with the conseillers files** for the current
term: 34,826 rows in the maires file, and exactly 34,826 rows in the conseillers
file carrying the function `Maire`. They are kept because they cost 8MB and
provide a cross-check, and because nothing establishes the same holds for a
future refresh. 69,714 people appear in two files; the rest in one.

**Top function labels**, a controlled vocabulary rather than personal data:
`Maire` 139,429, `1er adjoint au Maire` 69,134, `2ème adjoint au Maire` 63,180,
then the numbered deputies down a long tail. 691,605 people hold no function,
301,384 hold one, 1,756 hold two, 17 hold three or four.

## fr-decp: Données essentielles de la commande publique, consolidated

- Dataset: https://www.data.gouv.fr/datasets/donnees-essentielles-de-la-commande-publique-consolidees-format-tabulaire
- Processing code: https://github.com/ColinMaudry/decp-processing
- Format: Parquet and CSV. Use Parquet.
- Updates: roughly daily
- Licence: check the dataset page and record it here
- Model: one row per contract version. `donneesActuelles` marks the latest version. A modification can change `titulaire_*`, `montant` and `dureeMois`, and carries its own `dateNotification`.
- Phase: 1
- Expected fields (verify): id, acheteur_id (SIRET), acheteur_nom, titulaire_id, titulaire_typeIdentifiant, titulaire_denominationSociale, montant, dateNotification, datePublicationDonnees, procedure, nature, objet, codeCPV, dureeMois, modification_id, donneesActuelles
- Gotchas:
  - for framework agreements `montant` is a ceiling, not money spent
  - duplicate contracts across publishing platforms, implausible amounts, and some platforms have published dates in the future
  - a contract can have several titulaires (consortia)
  - DECP only covers contracts at or above the publication threshold set by the arrêtés of 22 December 2022. Record the current threshold here; F1's small-commune tag depends on it.

### Observed schema, session 2, fetched 2026-09-19

One Parquet file, 247,431,565 bytes, 66 columns, **3,281,288 rows**, consolidated
from 10,897 published resources across 63 platforms. The publisher's own
`schema.json` is archived beside it in the snapshot, because it is the only way a
later reader can tell a column this project misread from a column that changed.

**The publication threshold**, which F1's small-commune tag depends on. Code de
la commande publique art. R2196-1: the buyer publishes the données essentielles
of a marché meeting a need worth **40,000 EUR HT or more**, on the national open
data portal, within two months of notification. The arrêté of 22 December 2022
(ECOM2235715A) sets the formats and the list of fields and took effect on
1 January 2024; contracts notified before then follow the 2019 arrangements. The
same article also covers marchés concluded under art. R2122-8 worth 25,000 EUR
HT or more, but for those the buyer may instead publish an annual list in the
first quarter, on a medium of its choosing, which is not this file.

So **a commune that never signs a contract worth 40,000 EUR HT appears nowhere in
DECP**, and that is a fact about the denominator rather than about the commune.
It shows up directly in the survey: of 18,269 communes of up to 500 inhabitants,
3,360 appear as buyers, against 129 of the 133 communes above 50,000.

**Two column families, and they are not the same kind of fact.** The `uid`, `id`,
`acheteur_id`, `titulaire_id`, `objet`, `montant`, `dateNotification` and the
rest of the DECP fields are what a buyer declared. The `acheteur_*` and
`titulaire_*` geography, category and activity columns are **enrichment the
consolidator computed**, not anything a buyer published. Both are staged, in
separate columns, and a case packet citing one of the second kind has to cite
the consolidator for it. The buyer declared a SIRET; the commune code beside it
is somebody's join.

[ADR-0007](../adr/0007-consolidator-derived-attributes.md) accepts export of
these attributes with explicit derived provenance. It separately requires a
maintainer check of archived official buyer-SIRET evidence before the mapping
can support an exported F1 relationship. Attribution is not verification; the
review and export gates are specified, not implemented.

That enrichment is also what removed SIRENE from this session (see below).

**Grain.** One row is one contract version, per titulaire, per lot.
`(uid, modification_id, titulaire_id)` is **not** unique: 8,485 groups have more
than one row, and in 8,267 of them the rows differ in `objet`, which makes them
separate lots rather than duplicates. Collapsing them would lose money.
`decp_row_id` is a hash of the 20 published fields staged here, and it is unique
over the file. `titulaire_typeIdentifiant` is in that hash because without it 218
pairs of rows are identical on every other published field and differ only in
the case of that one value.

**Choosing the latest version, and why not by the published flag.**

| | rows |
|---|---|
| `donneesActuelles` true | 2,114,178 |
| `donneesActuelles` false | 1,135,302 |
| `donneesActuelles` null | 31,808 |

Every flagged row does carry the highest `modification_id` for its contract, so
the flag is never wrong. It is **absent**: 70,277 (contract, titulaire) groups
have no row flagged at all, 43,726 of them because the flag is false on every
row including the highest-numbered one, and 26,551 because the group has neither
a modification id nor a flag. Filtering on the flag drops all of those contracts
without a word, so staging takes the highest `modification_id` per
(contract, titulaire) instead, counting a null as zero. That gives
`contracts.parquet` **2,188,458** rows against `contract_versions.parquet`'s
3,281,288.

**Vocabularies**, controlled lists rather than data.

| `acheteur_categorie` | rows | | `titulaire_categorie` | rows |
|---|---|---|---|---|
| Commune | 1,111,211 | | PME | 1,840,384 |
| Groupement de communes | 613,434 | | ETI | 669,606 |
| (null) | 482,936 | | GE | 579,324 |
| Département | 407,654 | | (null) | 191,974 |
| EPIC | 189,745 | | | |
| Établissement hospitalier | 180,103 | | | |
| Syndicat mixte | 141,402 | | | |
| Région | 87,101 | | | |
| État | 54,764 | | | |
| Département outre-mer | 12,938 | | | |

**`titulaire_categorie` is the INSEE size band, not the catégorie juridique.**
That matters: the work order expected this session to build F1's exclusion list
(SEM, SPL, public bodies, and the rest of the entities where élus sit as the
commune's own representatives) from a legal category, and no column here carries
one. The exclusion list cannot be built from DECP. It needs the legal category
per supplier SIREN, which the open company API carries, so it moves to session 3.

**Identifier types.** `titulaire_typeIdentifiant` carries case and punctuation
variants of the same few types, so staging normalises them and keeps the raw
value beside the normalised one. The published spellings folded together are
`SIRET`/`Siret`/`siret` (227 rows in the two lowercase forms) and
`HORS_UE`/`HORS-UE`/`HORS UE` (one row in the spaced form). A type this project has no name for passes
through under its own: the file carries `FRW` (37), `RCI` (2) and `AUTRE` (6),
which are nobody's identifier scheme, and inventing a mapping would be worse.

| staged type | rows | | staged type | rows |
|---|---|---|---|---|
| SIRET | 3,181,558 | | IREP | 622 |
| (null) | 82,444 | | UE | 403 |
| TVA | 8,182 | | RIDET | 77 |
| HORS_UE | 7,897 | | TAHITI | 43 |

**Identifier quality.** 96.45% of rows carry a supplier SIREN and 96.22% a SIRET
that passes its checksum; 7,572 rows carry a fourteen-digit SIRET that fails one.
A failed checksum marks the row and never drops it: a contract is still a
contract, and constraint 9 keeps an unverifiable link out of a packet anyway. Of
206,055 distinct supplier SIRETs, 2,166 (1.05%) fail. The buyer side is cleaner:
99.91% of rows carry a valid `acheteur_id`, and only 340 are not fourteen digits.

**The La Poste rule, measured rather than assumed.** INSEE documents that La
Poste's establishments (SIREN 356000000) sit outside the Luhn series and that the
rule for them is that the fourteen digits sum to a multiple of five. The snapshot
holds 25 of them: 20 satisfy that rule, 2 satisfy plain Luhn instead, 3 satisfy
neither, and none satisfies both. Staging applies the documented rule only, so
those 5 are marked invalid. La Poste's **SIREN** needs no exception; it passes
Luhn like any other, and the first version of this code special-cased it for
nothing.

**Dates.** `dateNotification` runs from `0001-01-01` to the snapshot date, with no
future date at all, which is the opposite of what this document predicted. 928
rows (0.028%) fall before 1900, which is a platform's empty date rather than a
misread column, so they are marked `dates_plausible = false` and carried under
the same 1% rule the élus register taught. 31,808 rows have no notification date.

| notification year | rows |
|---|---|
| 2022 | 455,293 |
| 2023 | 485,691 |
| 2024 | 542,961 |
| 2025 | 582,070 |
| 2026 (to 19 September) | 348,126 |

**Amounts** fit DECIMAL(18,2) with room to spare: the largest is 99,999,999,999.99
and the smallest is -2,676,107.00, so negative amounts exist. The consolidator
publishes its own `montant_rationalise` and `montant_anomalie`, both staged. The
top 0.1% of contracts by amount start at 610,000,000 EUR and number 1,397; they
are listed by contract id in the snapshot's report.

**Buyers and communes.** 12,798 distinct communes appear as buyers, under 12,815
distinct SIRENs. Four of those SIRENs carry more than one commune code and one
carries sixteen, so `commune_buyers.parquet` holds one row per (SIREN, commune)
with a `commune_code_count` rather than a single value that would invent a fact.

**Paris, Lyon and Marseille buy under arrondissement codes** (`75112`, not
`75056`), which INSEE publishes as `ARM` and not `COM`. Of 318,582 distinct
(commune, supplier) pairs nationally, 305,426 land on a commune, 10,779 on an
arrondissement and 2,377 on a code INSEE does not publish in this vintage, of
which 2,118 are Mayotte. `crony survey departements` reports all three rather
than showing those three cities as communes that bought nothing.

## fr-sirene: SIRENE stock (INSEE)

- Dataset: "Base Sirene des entreprises et de leurs établissements (SIREN, SIRET)" on data.gouv.fr. Pin the URLs in session 2 through the data.gouv.fr API. Some SIRENE files moved to new storage in February 2026, and old links return 404.
- Licence: Licence Ouverte
- Phase: 1
- Use: legal category (catégorie juridique) of buyers and suppliers, commune code of a unit's head office, administrative status, creation date, headcount band, diffusion status
- Needed mappings:
  - buyer SIREN -> commune INSEE code, for units whose legal category is "commune" (pin the code from INSEE's nomenclature)
  - supplier legal category, to separate SEM, SPL, public bodies and other entities where élus sit as the commune's representatives (pin the codes and list them in `crony-eu/docs/flags/F1-same-body.md`)
- Gotchas: the stock files are large, so read only the needed columns with DuckDB. Record the name and values of the diffusion status field here.

**Not ingested. No `fr_sirene.py` exists and none is planned for phase 1.**

Session 2 was to fetch the stock for two things. The first, mapping a buyer SIREN
to a commune INSEE code, is already in the consolidated DECP file as
`acheteur_commune_code`, on 99.39% of rows and 100% of the rows whose buyer is a
commune. Fetching a multi-gigabyte national stock to recompute a column that is
already there would be work for its own sake.

The second, the supplier's **catégorie juridique** for F1's exclusion list, is
not in DECP: `titulaire_categorie` is the INSEE size band (PME, ETI, GE). So the
exclusion list moves to session 3, which queries the open company API once per
supplier SIREN in the slice and gets the legal category with the officers. That
is a narrower request than the national stock and it is a call this project was
making anyway.

What this costs: the commune mapping now comes from a **consolidator's join**
rather than from INSEE directly, and that is recorded as its provenance wherever
it is used. If a finding ever turns on which commune a buyer belongs to, the
check is the buyer's SIRET against the annuaire, not this column.

Observed schema: not applicable; nothing is read from it.

## fr-insee-pop: Populations légales

- Publisher: INSEE, populations légales, latest vintage, commune level
- Licence: record it here in session 2
- Phase: 1
- Use: population band of the buying commune, for F1 base rates and the 3,500-inhabitant threshold in Code pénal art. 432-12

### Observed schema, session 2, fetched 2026-09-19

**INSEE renamed these figures.** They are published as **populations de
référence** from the 2021 vintage onward; "populations légales" is the older name
and the one this section was written with. Same figures.

- Dataset: `populations-de-reference` on data.gouv.fr, published by INSEE
- Resource: one link to INSEE's Melodi service,
  `https://api.insee.fr/melodi/file/DS_POPULATIONS_REFERENCE/DS_POPULATIONS_REFERENCE_2023_CSV_FR`,
  resolved through the data.gouv.fr API like every other source so that a new
  vintage is picked up by refetching rather than by editing a URL
- Licence: Licence Ouverte 2.0. Frequency: annual
- Format: a 985,016-byte zip holding two CSVs, semicolon-delimited, quoted, UTF-8.
  The metadata one sorts first, so the data one is picked by its `_data.csv`
  suffix rather than by position
- Vintage **2023**, which takes legal effect on 1 January 2026. The vintage is
  staged as a column, because a base rate computed against one vintage and
  reported against another is off by three years of building

**106,065 rows**, long format, six columns: `GEO`, `GEO_OBJECT`, `FREQ`,
`POPREF_MEASURE`, `TIME_PERIOD`, `OBS_VALUE`. Every row is staged.

| `GEO_OBJECT` | rows per measure | what it is |
|---|---|---|
| COM | 34,858 | communes |
| ARR | 333 | arrondissements départementaux |
| DEP | 100 | départements |
| ARM | 45 | arrondissements municipaux (Paris, Lyon, Marseille) |
| REG | 17 | régions |
| FRANCE | 2 | métropole, and France entière |

**Three measures per territory, and they are different numbers.** `PMUN` is the
population municipale, `PCAP` the population comptée à part, `PTOT` their sum.
`PMUN` is the one the law refers to, including the 3,500-inhabitant line in Code
pénal art. 432-12, so it is the one F1 bands on. All three are staged; the choice
is visible rather than baked in.

**The cross-check that says the file was read right**: the commune rows, the
arrondissement rows, the département rows and the région rows each sum to
68,094,280, which is exactly the FRANCE row. That is why the non-commune rows are
staged instead of filtered out at read time.

**Two gaps worth stating.** This vintage excludes Mayotte (dep 976), which is why
2,118 commune-supplier pairs land on a code with no population. And the 34,858
communes here do not match the 34,953 in the élus register, because the two
publish on different geography dates.

## fr-entreprises-api: API Recherche d'entreprises (DINUM)

- Service page: https://www.data.gouv.fr/dataservices/api-recherche-dentreprises
- Endpoint: https://recherche-entreprises.api.gouv.fr/search. The OpenAPI specification (fetched 2026-09-21) publishes only `/search` and `/near_point`; there is no lookup-by-identifier path.
- An identifier goes in the free-text `q`. `?q=siren:<SIREN>` is **not** the syntax and returns nothing; a bare SIREN or SIRET works. This document said otherwise until 2026-09-21.
- Access: open, no key. The limit is 7 calls per second; the client runs at 5 or fewer.
- Phase: 1, one call per supplier SIREN in scope
- Content: company identity, officers (dirigeants) taken from INPI, and elected officials for public bodies
- Limits stated by the publisher: non-diffusible companies are excluded, predecessors and successors of establishments are not available, and it is not the full SIRENE base
- Expected officer fields (verify against the OpenAPI specification before coding): surname, given names, birth year and month, role (qualité), type (natural or legal person)
- **Not expected to carry role start and end dates.** The service exposes current officers taken from INPI, and a current-officer list is a snapshot rather than a history. Phase 1 needs the history, so this source alone is not enough (see `fr-inpi-rne` below).
- Two gates for session 3, both before the matcher is written:
  - if officer birth dates carry only the year, stop and tell the maintainer, because ADR-0003 assumes month precision
  - if no officer role start date is available from this source, stop and tell the maintainer, because F1 cannot build a case packet without one

Officer fields, role dates and their coverage: _session 3_

### Verified for ADR-0007, 2026-09-21: buyer-SIRET evidence

[ADR-0007](../adr/0007-consolidator-derived-attributes.md) requires a maintainer
check of the contract's exact buyer SIRET against archived official evidence
before DECP's derived commune code can support an exported relationship. The
work order's handoff asks first whether an approved source can supply that
evidence at all. This is that answer, from read-only probes of the published
OpenAPI specification and eleven live queries. Nothing was archived and no
`$CRONY_DATA_DIR` snapshot was written.

**A SIRET resolves, and that is the part the ADR turns on.** `q=<14 digits>`
returns exactly one result whose `matching_etablissements` holds that same SIRET
with the fields a buyer check needs:

| field | where | what it gives the check |
|---|---|---|
| `siret` | `matching_etablissements[]` | the exact establishment, not its legal unit |
| `commune` | `matching_etablissements[]` | the INSEE commune code for that establishment |
| `nature_juridique` | top level | the catégorie juridique code; a commune is `7210` |
| `etat_administratif` | `matching_etablissements[]` | `A` open, `F` closed |
| `date_creation`, `date_fermeture` | `matching_etablissements[]` | the window the establishment existed in |
| `statut_diffusion_etablissement` | `matching_etablissements[]` | constraint 7's non-diffusion check |

**A SIREN query is not a substitute, which is what ADR-0007 already says.** The
same request with the nine-digit SIREN returns the legal unit and
`matching_etablissements: []`. One commune in the sample has 109 establishments,
so a head-office location would have answered a different question from the one
asked.

**What this source cannot do: tell you the commune code at notification time.**
There is no as-of parameter, no address history, and the publisher states the
service exists "uniquement de rechercher une entreprise par sa dénomination ou
son adresse" rather than to return complete SIRENE records. So a passing check
establishes the mapping **as of the snapshot**, not on the notification date, and
ADR-0007's own rule is that a newer address is not proof of historical identity.

What is available instead is a bracket rather than a history:
`[date_creation, date_fermeture]` says when the establishment existed, so a
contract notified outside that window **refutes** the mapping even though a
contract inside it cannot confirm it.

**Measured exposure, on the 2026-09-19 DECP snapshot.** 14,816 distinct buyer
SIRETs carry a `Commune` category nationally, which is 49 minutes of calls at 5
per second for all of France and about a minute for one département. 26 of the
12,798 buyer commune codes have no row in the current INSEE commune list, and
they are two different problems:

| cause | codes | contract rows |
|---|---|---|
| Mayotte, which this population vintage excludes | 17 | 5,086 |
| establishments closed or merged since | 9 | 642 |

Five of them were probed. All five resolved, including two whose establishment is
closed (`etat = F`, `date_fermeture` 2025-01-01), and in all five the API's
commune code **agreed** with the code DECP derived. The two closed ones carry
contracts notified before their closure date, so the bracket check passes them.
That is five records and not a validation of the consolidator's join; it is
enough to say the check is implementable and not enough to say it is unnecessary.

## fr-inpi-rne: INPI, Registre national des entreprises

- Portal: https://data.inpi.fr (free account; API and SFTP access are managed from the account page)
- API login: https://registre-national-entreprises.inpi.fr/api/sso/login
- Format: JSON since 1 January 2023; daily updates
- Phase: **1 for officer role history**, 2 for national scale. The split changed on 2026-09-16: F1 needs a dated officer role to establish overlap, and nothing else in the French stack is expected to carry one. Phase 1 queries it per supplier SIREN in the slice, the same narrow scope as the open API, not in bulk.
- Unverified, and the first thing session 3 checks: whether the RNE record carries a role start date and a role end date, how often each is populated, and whether the date recorded is when the role began or when the filing was made. A filing date is not a role start date, and a packet claiming otherwise would be wrong in the way that matters most.
- Access is an account and a registration, not an open endpoint, so the gate is also practical: the account has to exist before session 3 can run.
- Rules: INPI states that reusers may not redistribute companies marked non-diffusible (`diffusionINSEE` = "N"). Confidential data is reserved for authorised bodies; don't request it. Beneficial ownership data is out of scope.

Observed schema, role date coverage and date semantics: _session 3_

## fr-hatvp: HATVP open data (phase 2)

- Page: https://www.hatvp.fr/open-data/
- Content: declarations published since July 2017, as XML under the Etalab licence, plus one global XML file and a CSV list of published declarations
- Use: declarations of interests and activities of MPs, senators and ministers: directorships, direct shareholdings, the spouse's professional activity
- Rules:
  - parliamentarians' asset declarations are not published online and must never be ingested from any source (Code électoral art. LO 135-2)
  - HATVP never publishes spouses' names or personal addresses; don't fill them in from elsewhere

## fr-ted: TED awards (phase 2)

Above-threshold French awards, used to cross-check DECP. Company-level data only.

This section used to say "through Serenata Europa". It no longer does: that project is retiring ([ADR-0014](../../../docs/adr/0014-replace-serenata-with-crony.md)) and nothing here depends on it. If the cross-check happens, it reads TED directly and gets its own section before a line of code, like every other source.

## Not allowed

- parliamentarians' asset declarations from any source, including press articles and leaks that quote them, unless the parliamentarian published the declaration themselves (LO 135-2)
- commercial aggregators and their APIs (for example Pappers or Societe.com)
- scraping pages of annuaire-entreprises.data.gouv.fr; use the API
- the beneficial ownership register
- leaked datasets
- anything else until the maintainer approves a new section above
