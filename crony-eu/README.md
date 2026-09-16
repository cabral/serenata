# crony-eu (working name)

Links between elected officials, companies and public contracts, built from official open data and checked by a person before anyone else sees them.

The idea comes from Sophie E. Hill's [My Little Crony](https://github.com/sophieehill/my-little-crony), an interactive network of UK politicians and the firms that won government contracts during the pandemic. Her network was assembled by hand from investigative journalism. This project uses public registries to propose links, and a person confirms or rejects each one.

## Status: specified, not built

**There is no code yet.** This directory holds the specification, the decision
records and the source list. There is no `crony` command to run, no package to
install, and nothing to point at a data directory. The sections below say what
phase 1 is specified to do, in the future tense they deserve.

Building it starts at session 0 of
[`crony-eu/docs/work-order-phase-1.md`](docs/work-order-phase-1.md).

This directory also sits inside a repository that is in the middle of being
handed over to it. The canonical scope is [`scope.md`](../scope.md) at the root,
and [ADR-0014](../docs/adr/0014-replace-serenata-with-crony.md) records why the
project previously living here is retiring.

## What phase 1 will do (France)

1. Download the Répertoire national des élus, the consolidated public procurement data (DECP), SIRENE, INSEE population figures, and company officer data including dated officer roles.
2. Propose matches between municipal councillors and company officers, using name and month of birth.
3. Show each proposed match to a person, who confirms or rejects it.
4. Check whether a confirmed councillor held a company office, at the time it was held, in a company that won a contract from their own commune (flag F1).
5. Build a case packet: a standalone HTML network, the edge list, and the source of every edge.

Step 1's officer role dates are the piece phase 1 cannot proceed without and
nobody has measured yet. If no French source carries them at usable coverage,
phase 1 produces counts and no case packets, and says so.

A flag is a question, never a finding. Most hits have ordinary explanations, and
the flag specs in [`crony-eu/docs/flags/`](docs/flags/) list them.

## What will be in this directory

Code, documentation, and test fixtures generated from invented names. No real
data and no results. The tool will run on your machine and download public
datasets into a directory you choose, outside the repository.

## Requirements (once there is something to run)

- Python 3.12 or newer and [uv](https://docs.astral.sh/uv/)
- an encrypted disk for the data directory
- room for large public files

## Legal notes

The French sources are published under the Licence Ouverte. Two rules will be
enforced in code rather than left to care: companies that are not publicly
diffusible never appear in outputs, and parliamentarians' asset declarations are
never ingested (Code électoral, art. LO 135-2).

Two things this project does not claim. Running locally is not a privacy
control: a case packet handed to a journalist is a disclosure, and the rules
about what may go in one are in
[`crony-eu/CLAUDE.md`](CLAUDE.md). An aggregate is not automatically person-free
either, because a share computed over a commune of four hundred people can name
someone to anyone who lives there.

If you run this tool, you are responsible for how you process and share what it
produces.

## Credits

- Sophie E. Hill, My Little Crony (MIT)
- vis-network (Apache-2.0 or MIT)
- DECP consolidation: [decp-processing](https://github.com/ColinMaudry/decp-processing)
- Data: Ministère de l'Intérieur, INSEE, INPI, DINUM (API Recherche d'entreprises)

## License

AGPL-3.0-or-later is the intent. The repository's [`LICENSE`](../LICENSE) is the
plain AGPL-3.0 text, and reconciling the two is a licensing decision with its
own record rather than a one-word edit.
