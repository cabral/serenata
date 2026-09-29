"""Ask TED whether it still serves daily packages from before eForms.

**This script reaches the network. It transfers no notice content.** Open work
#3 needs a pre-2024 package to measure which legacy TED fields can name a
natural person, and whether TED still serves one that far back has never been
checked. This checks it, and nothing else.

    uv run python tools/probe_legacy_packages.py

Two questions per date, asked separately because they can fail separately:

**Does the Search API know the date?** One ``limit: 1``, ``fields:
["ojs-number"]`` request resolves a calendar date to its OJ S issue — the same
request the fetch stage makes, through the same client (ADR-0002). A date the
API does not index cannot be addressed, whatever the package endpoint holds.

**Does the package endpoint serve that issue?** A bodyless request against
``/packages/daily/{yyyynnnnn}``: ``HEAD`` first, and where the service refuses
the method, ``GET`` with ``Range: bytes=0-0``. What comes back is a status code
and two headers. No package is downloaded, nothing is written to disk, and no
notice — legacy or eForms — is read.

That boundary is the point. Fetching a pre-2024 package is processing under the
review [ADR-0010](../docs/adr/0010-raw-archive-retention.md) leaves unresolved;
asking whether one *could* be fetched is not, and answering it decides whether
that review is worth asking for. A served package is not permission to fetch it.

The first date is a control: a publication day this project already archived. If
the control fails, the probe is broken and the other rows say nothing about TED.

``--issue 109/2016`` skips the first question and asks the second on its own.
The two limits are different facts: a date the Search API does not index is
unaddressable *by this pipeline*, which is not the same as a package the archive
no longer holds, and only the second would make the legacy record unreachable.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date

from serenata.fetch.client import FetchError, TedClient
from serenata.fetch.ojs import OjsIssue, issue_for_date

#: Publication dates to ask about, oldest question last. The first is the
#: control — OJ S 157/2026, the package `data/raw/` already holds. The rest are
#: Wednesdays, which publish, spread across the years of the legacy record: the
#: last full year before eForms became mandatory, then roughly every second
#: year back, far enough to find the edge of what TED still serves.
PROBE_DATES = (
    date(2026, 8, 17),
    date(2024, 6, 5),
    date(2023, 6, 7),
    date(2022, 6, 8),
    date(2020, 6, 10),
    date(2018, 6, 6),
    date(2015, 6, 10),
)

#: Pulled out of the client's error text, which is the only place a refused
#: status is reported. A probe wants the number; the pipeline wants the raise.
_STATUS = re.compile(r"HTTP (?P<status>\d{3})")


@dataclass(frozen=True)
class Probe:
    """What one publication date answered."""

    day: date | None
    issue: OjsIssue | None
    note: str
    package: str | None = None

    def describe(self) -> str:
        day = self.day.isoformat() if self.day is not None else "not asked"
        issue = f"OJ S {self.issue}" if self.issue is not None else "—"
        package = self.package or "—"
        return f"| {day} | {issue} | {package} | {self.note} |"


def _status_of(exc: FetchError) -> str:
    """Name the refusal by its status code, or by its transport failure."""
    match = _STATUS.search(str(exc))
    if match is not None:
        return f"HTTP {match['status']}"
    return "no response"


def _probe_package(client: TedClient, issue: OjsIssue) -> str:
    """Ask whether ``issue``'s package is served, without downloading it.

    ``HEAD`` is the honest request for this question. Where the service rejects
    the method rather than the resource, a one-byte range asks the same thing
    of the same URL — still bodyless in every sense that matters, since one
    byte of a gzip stream is not a notice.
    """
    try:
        response = client.request("HEAD", issue.package_url)
    except FetchError as exc:
        head_status = _status_of(exc)
        if head_status not in {"HTTP 403", "HTTP 405", "HTTP 501"}:
            return f"not served ({head_status})"
        try:
            response = client.request(
                "GET", issue.package_url, headers={"Range": "bytes=0-0"}
            )
        except FetchError as ranged:
            return f"not served ({head_status} to HEAD, {_status_of(ranged)} to GET)"

    content_type = response.headers.get("Content-Type", "no content type")
    length = response.headers.get("Content-Length")
    size = f"{int(length):,} bytes" if length is not None else "length not stated"
    return f"served ({content_type}, {size})"


def probe(client: TedClient, day: date) -> Probe:
    """Resolve ``day`` to its issue, then ask whether that issue is served."""
    try:
        issue = issue_for_date(client, day)
    except FetchError as exc:
        return Probe(day=day, issue=None, note=f"search refused ({_status_of(exc)})")

    if issue is None:
        return Probe(day=day, issue=None, note="no notice indexed for this date")

    return Probe(
        day=day,
        issue=issue,
        package=issue.package_id,
        note=_probe_package(client, issue),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "dates",
        nargs="*",
        type=date.fromisoformat,
        help="publication dates to probe (default: the dates in PROBE_DATES)",
    )
    parser.add_argument(
        "--issue",
        action="append",
        default=[],
        metavar="NNN/YYYY",
        type=OjsIssue.parse,
        help="probe a package by OJ S issue, without asking the Search API",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=1.0,
        help="seconds between requests (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    days = () if args.issue and not args.dates else tuple(args.dates) or PROBE_DATES
    print("| Publication date | Issue | Package id | Daily package |")
    print("|---|---|---|---|")
    with TedClient(min_interval=args.min_interval) as client:
        for day in days:
            print(probe(client, day).describe(), flush=True)
        for issue in args.issue:
            print(
                Probe(
                    day=None,
                    issue=issue,
                    package=issue.package_id,
                    note=_probe_package(client, issue),
                ).describe(),
                flush=True,
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
