# Sources: France

Every source the pipeline may touch in France. Field lists marked "expected" come from documentation or older files. The adapter session replaces them with the observed schema: column names, types and null rates only, never sample values (CLAUDE.md, constraint 13).

Nothing here has been fetched yet. Every "expected" list is a reading of documentation, and the ones that decide whether phase 1 can produce anything at all are the officer fields: birth month precision, and dated role history.

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

Observed schema and threshold: _session 2_

## fr-sirene: SIRENE stock (INSEE)

- Dataset: "Base Sirene des entreprises et de leurs établissements (SIREN, SIRET)" on data.gouv.fr. Pin the URLs in session 2 through the data.gouv.fr API. Some SIRENE files moved to new storage in February 2026, and old links return 404.
- Licence: Licence Ouverte
- Phase: 1
- Use: legal category (catégorie juridique) of buyers and suppliers, commune code of a unit's head office, administrative status, creation date, headcount band, diffusion status
- Needed mappings:
  - buyer SIREN -> commune INSEE code, for units whose legal category is "commune" (pin the code from INSEE's nomenclature)
  - supplier legal category, to separate SEM, SPL, public bodies and other entities where élus sit as the commune's representatives (pin the codes and list them in `crony-eu/docs/flags/F1-same-body.md`)
- Gotchas: the stock files are large, so read only the needed columns with DuckDB. Record the name and values of the diffusion status field here.

Observed schema: _session 2_

## fr-insee-pop: Populations légales

- Publisher: INSEE, populations légales, latest vintage, commune level
- Licence: record it here in session 2
- Phase: 1
- Use: population band of the buying commune, for F1 base rates and the 3,500-inhabitant threshold in Code pénal art. 432-12

Observed schema: _session 2_

## fr-entreprises-api: API Recherche d'entreprises (DINUM)

- Service page: https://www.data.gouv.fr/dataservices/api-recherche-dentreprises
- Endpoint: https://recherche-entreprises.api.gouv.fr/search (for example `?q=siren:<SIREN>`)
- Access: open, no key. The limit is 7 calls per second; the client runs at 5 or fewer.
- Phase: 1, one call per supplier SIREN in scope
- Content: company identity, officers (dirigeants) taken from INPI, and elected officials for public bodies
- Limits stated by the publisher: non-diffusible companies are excluded, predecessors and successors of establishments are not available, and it is not the full SIRENE base
- Expected officer fields (verify against the OpenAPI specification before coding): surname, given names, birth year and month, role (qualité), type (natural or legal person)
- **Not expected to carry role start and end dates.** The service exposes current officers taken from INPI, and a current-officer list is a snapshot rather than a history. Phase 1 needs the history, so this source alone is not enough (see `fr-inpi-rne` below).
- Two gates for session 3, both before the matcher is written:
  - if officer birth dates carry only the year, stop and tell the maintainer, because ADR-0003 assumes month precision
  - if no officer role start date is available from this source, stop and tell the maintainer, because F1 cannot build a case packet without one

Observed schema: _session 3_

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
