# ADR-0015: Publish the pages on GitHub Pages, by hand

- Status: proposed
- Date: 2026-09-30
- Enforced by: `tests/test_workflows.py::TestPagesWorkflow` keeps the workflow
  manual, limited to main, and pinned. That the repository setting is off, or that
  nobody has run the workflow, is nothing mechanical: those are two acts by the
  owner.

## Context

[ADR-0014](0014-a-site-that-cannot-show-a-flag.md) built the pages and left
hosting open, with "a host is chosen" as a revisit trigger. The maintainer
proposed GitHub Pages.

Publishing the pages is publication in the sense this project's rules use the
word: a person says so. The pages carry no flag and nothing that is not already in
this public repository. They do gather it. The page for counsel is a single
account of what the project holds and has not yet cleared, and making that easy to
find is a decision, not a side effect of a merge.

Other hosts, and a custom domain, add an account, a cost and for a domain the
question of whose it is. serenata.ai serves the original project's site and is not
this project's. Deploying on every push to main is convenient and turns "merge"
into "publish", which is the coupling ADR-0014 exists to avoid.

## Decision

**Host the pages on GitHub Pages at the repository's own address, deployed by a
workflow that only a person can start.**

- `.github/workflows/pages.yml` has one trigger, `workflow_dispatch`. It builds
  with `python -m serenata.site` from the locked environment and deploys the
  result. It runs only from main.
- Two acts by the owner publish: setting the Pages source to "GitHub Actions" in
  the repository settings, and starting the workflow. Merging does neither.
- The pages keep `noindex`. Nothing else in ADR-0014 changes: no analytics,
  cookies, fonts or scripts from anyone else, and no custom domain.
- Action references are pinned by commit, like the rest of CI.

## Consequences

- Published pages age. Nothing redeploys when a document changes, so a figure on
  the pages is as old as the last run. Each page shows the date its measurement
  was taken. That is acceptable while no flag is published. It stops being
  acceptable the day a page is described as current.
- `noindex` asks and does not restrict. Anyone with the address can read the
  pages. What they contain is already in the public repository.
- GitHub, as the host, sees visitors' IP addresses under its own privacy
  statement, as any host would. The pages add no cookies, analytics or third-party
  request of their own, which `tests/test_site.py` checks. Whether counsel wants a
  view on the host is for the maintainer to put to them. This ADR does not answer
  it.
- Links from the pages go to the default branch, so the workflow refuses other
  branches and the pages should be deployed after a merge, not before.
- To withdraw the pages, switch Pages off in the repository settings. Copies
  already fetched or cached elsewhere are out of the project's hands. No flag is
  on the pages, so nothing needs retracting under the corrections policy.
- The pages are static output of code published in this repository at the commit
  deployed, and their footer links to it. That is what the AGPL asks of anything
  the project runs for others: there is no private production patch.

## Revisit triggers

- The release gates clear and the pages should be indexed, redeployed
  automatically, or carry real flags. That is a new ADR, as ADR-0014 says.
- A custom domain, analytics or any measurement of visitors is proposed.
- Someone besides the maintainer gets write access. Then require reviewers on the
  `github-pages` environment.
- GitHub changes the terms of Pages, or an action used here stops being
  maintained.
