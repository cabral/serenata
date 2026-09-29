# ADR-0014: A site that shows the project and cannot show a flag

- Status: proposed
- Date: 2026-09-29
- Enforced by: `tests/test_site.py::TestTheSiteCannotPublishFlags` and
  `tests/test_site.py::TestTheBuildIsReproducible`. Hosting, and whether the
  pages may be indexed, are not enforced by anything: nothing is deployed.

## Context

The project has a pipeline, a measured rule and a set of open legal questions,
and everything a reader could look at is Markdown or a terminal. Counsel cannot
review what the project holds from a terminal. A journalist deciding whether the
output can be trusted, and a funder deciding whether to back it, have nothing
that shows the method working.

The obvious frontend is the milestone 5 verification interface: every flag, its
hypothesis, its source notice. It cannot be built as that yet. No flag may be
published while [ADR-0010](0010-raw-archive-retention.md) and open-work items
11, 14, 17 and 18 are unresolved, and a page that rendered real flags would be
the publish stage arriving before its gates.

The visual reference is the original Serenata site: black and white bands,
monospace type, one purple. Its layout and palette can be borrowed. Its words
cannot: it describes "artificial intelligence" and "suspicions", which
constraints 3 and 5 rule out here, and its logo, mascot and partner marks
belong to that project and its partners.

Three alternatives were considered. A documentation generator adds a dependency
and gives the documents' own shape back, not a designed view for counsel. A
client-side app over Parquet would put the dataset in the reader's browser,
which is publication. Hand-written pages would hold every figure a second time,
and the second copy would be wrong within a month.

## Decision

**`python -m serenata.site` builds five self-contained HTML pages from the
repository's Markdown and from constants in code. It reads documents, never
data.**

- No dataset, archive or flag path is an input, and the package imports nothing
  that reads Parquet, DuckDB or the network.
- Every figure is read from a generated report or a hypothesis file by a reader
  that raises when the document changes shape, and the build stops when two
  documents disagree about the same corpus.
- The only flag records on any page are produced by running the real rule over an
  invented market. Every identifier says `SYNTHETIC`.
- Pages request nothing from a third party: no font, script, style or analytics.
  Each carries a strip saying no flag has been published, and asks not to be
  indexed.
- The design borrows the original site's layout, palette and type style. It uses
  none of its text, logos, mascot or partner marks.
- Nothing is deployed. Where the pages are hosted is a separate decision.

## Consequences

- Counsel, journalists, funders and contributors each get a page written for
  them, and no fact on it has a second home.
- The documents the site reads become interfaces. Renaming a heading the site
  reads fails the build with the document and heading named. That is the price of
  having no second copy.
- The rule explainer cannot describe a rule the code no longer implements. The
  thresholds are imported, the example is the rule's own output, and the script
  that lets a reader move the numbers is run against the Python over the same
  grid by a test.
- The site is not the `publish` stage. Real flags reaching a page needs its own
  ADR, and needs the gates above to have closed. The guard test is then replaced
  on purpose, not worked around.
- serenata.ai serves the original project's site. Nothing here assumes this
  project may use that domain. The independence statement from the README is in
  the footer of every page, and resemblance to the original is disclosed by it.
  If Open Knowledge Brasil raises the resemblance, that is a relationship question
  and an escalation, not a call to make in a session.
- Analytics, cookies, a font loaded from a third party or removing `noindex` each
  need a privacy assessment first. The argument this project is having about
  lawful basis applies to its own front page.

## Revisit triggers

- The release gates in the README clear and a publish stage is designed.
- A host is chosen for the pages.
- A second language is needed.
- The site outgrows a handful of pages or needs state in the browser. Then a
  static site generator is worth its dependency, after the licence check.
- A page needs a figure that lives in no document. The figure should move into a
  generated report first.
