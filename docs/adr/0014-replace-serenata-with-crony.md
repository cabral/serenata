# ADR-0014: Crony replaces Serenata Europa in this repository

- Status: accepted — scope reconciled; no code retired yet
- Date: 2026-09-16
- Enforced by: `tests/test_transition.py::TestTheReplacementIsRecorded` for the
  canonical scope and the disposition of every earlier record, and
  `tests/test_docs.py::TestClaimsAboutFiles` now that the Crony tree is inside
  the roots it reads. Neither can hold the legal obligations in
  [ADR-0010](0010-raw-archive-retention.md) true; nothing mechanical can

## Context

Serenata Europa reads TED's eForms notices and flags statistical anomalies in
company-level and institution-level data, with no natural person in the model.
It has an ingestion and normalisation prototype, one measured classifier, and
two release blockers that are legal rather than technical: an unresolved lawful
basis for the archive already held ([ADR-0010](0010-raw-archive-retention.md)),
and an undecided publication rule for records whose natural-person status is
unknown ([open work #11](../open-work.md#11-decide-the-publication-rule-for-unknown-natural-person-status)).
No counsel is engaged for either.

Crony is a different project with a different question. It proposes links
between office holders, companies and public money from official open data, a
person confirms every person-to-company link, and the output is a case packet
shown to a journalist from the maintainer's own machine. It publishes nothing.
Its scope is [`scope.md`](../../scope.md); its handover tree arrived as
`crony-eu/` and a zip of the same bytes.

Two projects, one maintainer. The handover bundle assumed both would run: its
scope document says the relationship to Serenata Europa is "unchanged", and that
anything computable without personal data "belongs upstream in Serenata Europa
rather than here". That sentence quietly makes Serenata a dependency of Crony,
which is the opposite of retiring it, and it is the specific claim this record
exists to contradict.

The maintainer's decision is that Crony becomes this repository's purpose and
Serenata is retired rather than maintained alongside it.

## Decision

**Crony is what this repository is for.** [`scope.md`](../../scope.md) at the
root is the canonical scope. The identical copy that arrived at
`crony-eu/docs/scope.md` becomes a pointer to it, because two files that must
agree eventually will not.

**Serenata's TED pipeline is retired, not maintained.** It is not deleted in
this record. Retirement happens in coherent groups as the Crony check that
replaces each group becomes available, and the inventory that says which group
each file is in is [`docs/transition-ledger.md`](../transition-ledger.md). An
unfinished TED feature is not finished merely to preserve it; a branch and the
tag `serenata-europa-pre-transition` preserve it already.

**Serenata is not a dependency of Crony.** Nothing in Crony's phase 1 reads a
Serenata table, calls a Serenata module, or waits on a Serenata milestone. The
scope document's TED cross-check is a phase 2 idea and reads TED directly if it
happens at all.

**Earlier decision records keep their numbers and gain a disposition.** ADR-0001
to ADR-0013 are history and none is renumbered or deleted. Each carries a
`- Transition:` line with one of three values:

- **carried** — the decision governs Crony too, and is restated in Crony's own
  records rather than inherited silently
- **retired** — it governed the TED pipeline and goes with it
- **continuing obligation** — it binds the maintainer regardless of which
  project occupies the repository, and retiring code does not discharge it

The third is the category that matters. ADR-0009's DCO requirement, ADR-0012's
disabled automation boundary and, above all, ADR-0010's unresolved lawful basis
for an archive that still exists on disk are obligations, not features.
**Retiring the code that reads the archive does not dispose of the archive.**

**The two projects' licence terms are not merged by relabelling.** Serenata's
code is AGPL-3.0 and its published datasets would have been CC BY 4.0
([ADR-0004](0004-dataset-licence.md)); no dataset was ever published under that
grant. Crony's handover states AGPL-3.0-or-later. The repository `LICENSE` file
is the plain AGPL-3.0 text and is not edited by this record. Aligning the two
statements is a licensing change with its own consequences for every existing
contributor's DCO sign-off, and it needs its own record rather than a
search-and-replace during a scope reconciliation.

**Crony's documentation is brought under this repository's documentation
checks.** `tests/test_docs.py` reads `crony-eu/` as a document root from now on,
which is what turns "the docs describe a tool that does not exist yet" from a
matter of opinion into a failing test. Documents describing files not yet built
say so, with a marker a reader can tell from a claim.

**No automation is activated.** The agent profiles, issue templates and the
bounded-automation lane are reconciled in wording only. ADR-0012 stays proposed
and disabled, and nothing in this transition grants an agent authority it did
not have on 2026-09-15.

## Consequences

**Public commitments are not settled by this record.** The Serenata Europa name
appears in an NLnet application, a Patreon campaign and a README that funders,
journalists and contributors read. Retiring the project they were told about is
a communication with those people, and it is owed to them before the retirement
is announced rather than after. This record makes the engineering decision; the
[`communication`](../../.claude/skills/communication/SKILL.md) and
[`patreon`](../../.claude/skills/patreon/SKILL.md) rules govern how it is said.

**The README now describes two things at once** — a pipeline that still runs and
is retiring, and a tool that is specified and not started. That is honest and it
is also confusing, and it stays that way only until phase 1 has something to
show. A reader who cannot tell which is which is a bug in the README.

**Milestones 2 to 6 of Serenata's plan will not happen.** Entity resolution, the
public API, the verification interface and the bulk data releases were the
project's answer to "why should anyone trust this", and Crony answers that
question differently: nothing is published, and a person confirms every edge
before anyone sees it. That is a smaller claim, and it is one a single
maintainer can actually honour.

**Two legal blockers are inherited, not escaped.** Crony processes personal data
by design, where Serenata processed it by accident. Sweden's journalistic
exemption in dataskyddslagen 1 kap. 7 § is the ground Crony's
[ADR-0001](../../crony-eu/docs/adr/0001-local-first-data-outside-repo.md) stands
on, and that exemption is an argument, not a ruling. The counsel question in
[`docs/counsel/`](../counsel/README.md) gets broader, not narrower.

**Two ADR series now coexist**, this one under `docs/adr/` and Crony's under
`crony-eu/docs/adr/`, both starting at 0001. They are kept apart by directory
rather than renumbered, because renumbering would break every citation in both
sets. A record in either series that cites the other says which series it means.

## Revisit triggers

Phase 1 failing its feasibility gate — French officer role history turning out
to be unavailable or too sparse to establish overlap — which would leave Crony
unable to produce a case packet at all and would put the trunk decision back on
the table. Counsel engaging, and answering the ADR-0010 question in a way that
either unblocks Serenata's publication route or forecloses Crony's. A decision
about the repository's name or location, which is the point at which the nested
`crony-eu/` tree stops being the sensible layout. Any funding commitment made on
Serenata's milestone plan, which would make retiring it a matter for the funder
rather than for this record.
