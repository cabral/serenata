# ADR-0002: Fetch whole daily packages, use the Search API only to address them

- Status: amended — the addressing decision stands; one assumption behind it was wrong
- Date: 2026-09-01
- Amendment: 2026-09-07
- Enforced by: `tests/test_constraints.py::TestNetworkIsolation`, `tests/test_ted_contract.py::TestTheDailyPackage`, `tests/test_ted_contract.py::TestTheSearchIndexFloor`, `tests/test_fetch_ojs.py::TestTheSearchIndexFloor`

## Context

Milestone 1 starts with the fetch stage: get TED notices onto disk as immutable
raw files that every derived record can point back to. TED offers reusers two
documented channels, both public and both without authentication. The facts
below were verified against the live service on 2026-09-01, not taken from
documentation alone, because the published docs are thin on specifics.

**Search API.** `POST https://api.ted.europa.eu/v3/notices/search`, no API key.
The request body takes `query` (an expert-search expression such as
`publication-date>=20260817 AND publication-date<=20260817`), a non-empty
`fields` list (the service rejects an empty one with HTTP 400), `limit`, and
either `page` or `paginationMode: "ITERATION"` with `iterationNextToken`. The
response is `{notices, totalNoticeCount, iterationNextToken, timedOut}`.
`limit` is capped at 250 — asking for more returns HTTP 400
`SEARCH_EXCEEDS_MAX_LIMIT`. Each notice carries per-notice links, including
`links.xml.MUL`, the single multilingual XML for that notice.

**Daily bulk packages.** `GET https://ted.europa.eu/packages/daily/{yyyynnnnn}`,
where `yyyynnnnn` is the OJ S issue: publication year followed by the
zero-padded issue number. The response is a gzipped tar (~15–20 MB compressed,
~160–210 MB extracted) containing one XML file per notice under a single
directory named `YYYYMMDD_NNN`. eForms notices are named with eight digits and
the year (`00566631_2026.xml`); legacy TED schema notices use six.

A representative publication day (2026-08-17) has 3,190 notices. Fetching that
day through the Search API costs 13 paginated calls plus 3,190 individual XML
downloads. The daily package costs one request for byte-identical content — a
cross-check confirmed the package for OJ S 157/2026 contains exactly the 3,190
notices the Search API reports for that date.

The remaining problem is addressing: the package URL is keyed by OJ S issue
number, but a backfill is expressed in calendar dates, and the mapping skips
weekends and holidays. Counting business days is guesswork. The Search API
exposes the mapping directly — the `ojs-number` field returns `"157/2026"` for
a notice published on 2026-08-17.

## Decision

Archive whole daily packages. Use the Search API only to resolve a calendar
date to its OJ S issue, with one `limit: 1`, `fields: ["ojs-number"]` request
per day. Never download notices one at a time.

- One request per publication day for the content, one for the address. A
  year's backfill is ~500 requests rather than ~700,000. This is the difference
  between a polite reuser and an abusive one, and TED publishes no rate-limit
  headers to negotiate against, so we set the bar ourselves: a configurable
  minimum interval between requests, exponential backoff honouring
  `Retry-After`, and a User-Agent naming the project and its repository.
- A day with no notices returns zero results and is recorded as having no
  package. Weekends and holidays therefore need no calendar of their own; the
  service is the authority on which days published. **Amended 2026-09-07 — see
  below: the service is the authority only within its index.**
- Packages are stored exactly as received, under
  `data/raw/ted/daily/{year}/{package_id}.tar.gz`, beside a
  `.manifest.json` recording the OJ S number, publication date, source URL,
  SHA-256, byte size, and fetch timestamp.
- Re-fetching is idempotent: a package whose bytes match its manifest checksum
  is skipped. A package whose bytes do **not** match is a conflict and raises,
  rather than being silently overwritten — raw files are ground truth and
  immutable once fetched.
- Downloads stream to a `.part` file and are renamed into place only after the
  checksum is computed, so an interrupted fetch never leaves a truncated
  archive that looks complete.

`httpx` (BSD-3-Clause, compatible with AGPL-3.0) is the HTTP client.

## Consequences

- The archive's unit is a publication day, not a notice. Fetching a single
  notice for debugging means fetching its day; acceptable at ~20 MB.
- Packages bundle eForms and legacy TED notices together. Distinguishing them
  is the parse stage's job, keyed on the filename digit count and the XML root
  element — fetch stays format-blind, which is what keeps it stable.
- Storage is roughly 5 GB compressed per year of backfill. Fine on one machine;
  worth revisiting if scope grows past TED.
- Manifests record a wall-clock `fetched_at`. This is provenance, not pipeline
  output: the determinism constraint binds transform and classify outputs, and
  no derived record may depend on a manifest timestamp. The tarball bytes,
  addressed by SHA-256, are what downstream stages are reproducible against.

## On raw archives and the no-personal-data constraint

Raw notices are official publications that TED has already made public, and
some contain contact-person names in their source XML. Archiving them
byte-for-byte is in tension with "no personal data, ever", so the boundary is
worth stating explicitly rather than leaving to a reader's charity.

The raw archive is a local, gitignored cache of already-public official
documents, kept so that every flag can be traced to the exact bytes it was
derived from. It is not the dataset, it is not republished by this project, and
nothing downstream of it carries a person's name: the parse stage drops those
fields on the way to intermediate records, so they never reach the normalised
model, the Parquet artefacts, the API, or any published finding. Constraint 2
governs what this project stores as data and publishes; it is not a
prohibition on reading the official journal.

## Amendment, 2026-09-07: the Search API is the authority only within its index

The decision above reads a date with no notices as a date that did not publish,
and treats that as the service speaking for its own calendar. That is true for
the period the Search API indexes and false before it, where the API answers
every date the way it answers a Sunday.

[`legacy-availability.md`](../legacy-availability.md) measured the edge without
downloading a package: the index reaches back to **2016-09-06** and no further,
while the package endpoint still serves **OJ S 170/2016**, the issue immediately
before it, along with issues from 2015 and 2012. So the limit is the addressing
channel, not TED's archive.

Nothing was ever archived wrongly — no date below the edge has been requested —
but the code would have done it silently, which is why this is corrected rather
than noted. `issue_for_date` now refuses a date below `SEARCH_INDEX_FLOOR`
instead of resolving it, before any request is made. An archive that recorded
"TED did not publish" about a day TED published on would be a false provenance
claim in the layer this project calls ground truth, and it would be
indistinguishable from a weekend once written.

**The floor is a measured constant, so it is watched rather than trusted.**
`TestTheSearchIndexFloor` in the weekly contract suite asserts both edges
against the live service: that the index still reaches the floor, and that the
day below it is still outside. A failure in the second direction is good news —
more of the legacy record becomes addressable by date — and still has to fail,
because nothing else in the suite would notice the constant going stale.

What this does not change: the addressing decision, the archive's unit, or
anything about what may be fetched. Reaching below the floor needs a
date-to-issue mapping that does not exist here, and fetching a pre-2024 package
at all remains subject to the review [ADR-0010](0010-raw-archive-retention.md)
leaves unresolved.

## What would change this

If TED introduces authenticated bulk access, per-reuser quotas, or an
incremental change feed, revisit — a change feed in particular would let the
pipeline follow corrections and withdrawals, which whole-day snapshots handle
only by refetching.
