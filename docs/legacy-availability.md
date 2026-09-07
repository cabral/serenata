# Whether TED still serves pre-eForms daily packages

[Open work #3](open-work.md#3-document-and-drop-the-fields-that-can-name-a-natural-person)
is blocked on a pre-2024 package to measure, and said the first step was to
check whether TED still serves one rather than to assume it. This is that check.
It asks about availability and nothing else.

The probe is [`tools/probe_legacy_packages.py`](../tools/probe_legacy_packages.py),
so the answer can be rechecked without taking this file's word for it. Measured
**2026-09-07**.

> © European Union, 1998–2026. Source: [TED](https://ted.europa.eu), the
> Supplement to the Official Journal of the European Union. Reuse authorised
> under Commission Decision 2011/833/EU; see [data-reuse.md](data-reuse.md).
> This report carries HTTP response metadata — status codes, content types and
> stated lengths — and OJ S issue numbers. It carries no notice content.

## What was asked, and what was not

Two questions per date, asked separately because they fail separately:

1. **Does the Search API resolve the date to an OJ S issue?** One `limit: 1`,
   `fields: ["ojs-number"]` request, the same one the fetch stage makes
   (ADR-0002).
2. **Does `/packages/daily/{yyyynnnnn}` serve that issue?** A bodyless request —
   `HEAD`, with a one-byte range as the fallback the service never needed.

**No package was downloaded.** Nothing was written to disk, and no notice was
read. That boundary is deliberate: fetching a pre-2024 package is processing
under the review [ADR-0010](adr/0010-raw-archive-retention.md) leaves
unresolved, and asking whether one could be fetched is not. Thirty-two requests
across five runs, through the project's throttled client and User-Agent.

The first row is a control — the publication day `data/raw/` already holds. Had
it failed, the rest of the table would say nothing about TED.

## Dates resolved through the Search API

| Publication date | Issue | Package id | Daily package |
|---|---|---|---|
| 2026-08-17 (control) | OJ S 157/2026 | 202600157 | served, application/gzip, 19,980,923 bytes |
| 2024-06-05 | OJ S 108/2024 | 202400108 | served, application/gzip, 15,168,707 bytes |
| 2023-06-07 | OJ S 108/2023 | 202300108 | served, application/gzip, 9,593,822 bytes |
| 2022-06-08 | OJ S 109/2022 | 202200109 | served, application/gzip, 8,312,265 bytes |
| 2020-06-10 | OJ S 111/2020 | 202000111 | served, application/gzip, 6,569,656 bytes |
| 2018-06-06 | OJ S 106/2018 | 201800106 | served, application/gzip, 7,380,121 bytes |
| 2017-06-07 | OJ S 107/2017 | 201700107 | served, application/gzip, 5,984,275 bytes |
| 2017-01-04 | OJ S 2/2017 | 201700002 | served, application/gzip, 6,948,711 bytes |
| 2016-12-07 | OJ S 236/2016 | 201600236 | served, application/gzip, 5,225,266 bytes |
| 2016-09-07 | OJ S 172/2016 | 201600172 | served, application/gzip, 6,138,584 bytes |
| 2016-08-31 | — | — | no notice indexed for this date |
| 2016-08-17 | — | — | no notice indexed for this date |
| 2016-08-03 | — | — | no notice indexed for this date |
| 2016-07-06 | — | — | no notice indexed for this date |
| 2016-06-15 | — | — | no notice indexed for this date |
| 2016-06-08 | — | — | no notice indexed for this date |
| 2015-06-10 | — | — | no notice indexed for this date |
| 2014-06-11 | — | — | no notice indexed for this date |

**Every issue the API resolved, the package endpoint served.** Not one refusal
in ten years of publication dates.

## Issues addressed directly, without the Search API

| Issue | Package id | Daily package |
|---|---|---|
| OJ S 109/2016 | 201600109 | served, application/gzip, 5,927,344 bytes |
| OJ S 111/2015 | 201500111 | served, application/gzip, 6,373,046 bytes |
| OJ S 107/2012 | 201200107 | served, application/gzip, 3,344,262 bytes |

These three issue numbers were **chosen as plausible for their year, not
resolved from a date**. What they establish is that the endpoint serves issues
of those years — including 2015 and 2016 issues the Search API would not address
by date. Which calendar day each one published is not known from this probe.

## What this establishes

**The blocker on #3 is not availability.** TED serves daily packages from well
before eForms, back to at least 2012, and the fetch stage needs no change to
retrieve one. The remaining gate is the unresolved processing review, which is a
different kind of gate and is not lifted by anything here.

**There are two limits, and only one of them is TED's archive.** They are
usually conflated and behave differently:

- The **Search API index** stops between **2016-08-31 and 2016-09-07** — six
  probed Wednesdays from June to August 2016 return nothing, and every date from
  2016-09-07 onward resolves. Bounded by bisection on publication days, not read
  from documentation, and an index edge can move.
- The **package archive** goes back at least to 2012 and was never observed to
  refuse.

So the pipeline as built — resolve a date to an issue, then fetch the issue —
reaches back to **early September 2016** unchanged. Reaching further is an
addressing problem, not a retrieval one: the packages are there, and only the
date-to-issue mapping is missing.

**The fetch stage would answer a pre-September-2016 date wrongly, and quietly.**
`issue_for_date` returns `None` when the Search API returns no notice, and
`iter_fetch_range` records that as `NOT_PUBLISHED` — the same outcome as a
weekend. TED published on 2016-06-08; the archive would record that it did not.
That is safe today because nothing has asked for those dates, and it is a trap
for whoever asks first. It should be fixed before, not during, a legacy
backfill.

## What this does not establish

- **Nothing about content.** No package was opened. This says nothing about
  whether a 2018 package contains legacy-schema notices, whether they parse,
  or which of their fields can name a natural person. That is the measurement
  #3 needs, and it is a different act with different obligations.
- **Not permission to fetch.** A served package is an availability fact.
  Lawful basis, retention, Article 14 transparency and DPIA necessity for a
  legacy backfill remain unresolved under ADR-0010.
- **Not a survey.** One date per year, on Wednesdays, is enough to answer a
  yes-or-no question about availability and not enough to characterise a year.
- **Not verified bodies.** Sizes are what the response headers stated. Nothing
  read a byte to confirm the packages are what they claim.
