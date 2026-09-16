# ADR-0004: France first, and how the next country is chosen

Status: accepted, 2026-09-10

## Context

The same-body check needs three open layers that share a key: who holds office where, who runs which company, and which company got money from which public body.

Sweden, where the maintainer lives, fails the second layer for now. Bolagsverket's free high-value API covers basic company data and filed annual reports; board members come through paid services.

France has all three:

- the Répertoire national des élus lists every mandate holder, under an open licence, updated quarterly, and was refreshed in August 2026 after the March municipal elections
- company officers are available through the open API Recherche d'entreprises, and through INPI's register (free with an account) for national scale in phase 2
- the consolidated DECP data covers contracts with buyer and supplier identifiers

France does not publish the names of party donors, so the donation edges My Little Crony had stay empty here.

## Decision

- France is the pilot. Phase 1 covers communes only and runs one département at a time.
- Phase 1 fetches officers only for companies that won contracts in the slice. Bulk register data waits for phase 2.
- A country joins when it passes three tests:
  1. an official list of office holders with a birth date or a national identifier
  2. open company officer data carrying a comparable key
  3. contract or payment data with supplier identifiers
- Czechia and Denmark get checked against the three tests first. Sweden comes back once the cost of Bolagsverket's paid data is known.

## Consequences

- Sources, field names and legal rules are French in phase 1: Code électoral LO 135-2, INPI's non-diffusion rule, and Code pénal 432-12 as context for F1.
- Country specifics stay inside `crony-eu/src/crony_eu/sources/` modules and rule ids, so adding a second country doesn't mean rewriting matching or flags.
- Fetching officers only for suppliers in scope keeps the personal data processed to the people who matter for the question.

## Amendment, 2026-09-16: there are five tests, and France has not passed the fifth

This record listed three tests a country has to pass. [`scope.md`](../../../scope.md) raised it to four by adding a person who can read the local law. It is five.

4. A person who can read the local law and say what is forbidden and which offence the flag maps to.
5. Officer role history: dated starts and ends, at coverage high enough that `unknown` is the exception rather than the rule.

France passes 1 to 4. **Test 5 is unmeasured**, including for France, and it is the first gate in phase 1 (session 3 of `crony-eu/docs/work-order-phase-1.md`). The open API Recherche d'entreprises exposes current officers, which is a snapshot rather than a history; INPI's register is expected to carry dates and nobody has checked what those dates mean.

The country shortlist in `scope.md` inherits the same hole. Denmark and Estonia are listed as likely on the strength of free registers including directors, and "including directors" is a statement about test 2, not test 5.

This record is otherwise unchanged: France is still the pilot, phase 1 still covers communes one département at a time, and country specifics still stay inside source modules and rule ids.
