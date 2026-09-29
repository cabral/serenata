"""Resolve calendar dates to the OJ S issues that address daily packages.

Daily packages are keyed by Official Journal S issue (``157/2026``), but a
backfill is expressed in dates. The mapping skips weekends and holidays, so
it cannot be computed by counting business days. The Search API knows it: any
notice published on a date carries that date's ``ojs-number``, so one
``limit: 1`` query per day resolves it (ADR-0002).

**The API is the authority only within its index.** ADR-0002 originally read a
date with no notices as a date that did not publish, which is true above the
index floor and false below it: TED answers an unindexed date exactly as it
answers a Sunday. Measured in `docs/legacy-availability.md` — the index reaches
back to 2016-09-06 and no further, while the package endpoint still serves the
issue immediately before it. So a date below the floor is refused here rather
than resolved, because the alternative is writing a day TED published on into
the archive as a day it did not.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

from serenata.fetch.client import PACKAGE_URL_TEMPLATE, FetchError, TedClient

_OJS_NUMBER = re.compile(r"^(?P<number>\d{1,5})/(?P<year>\d{4})$")

#: The field carrying the OJ S issue on every notice.
OJS_FIELD = "ojs-number"

#: The earliest publication date the Search API indexes. Measured 2026-09-07 by
#: bisection on publication days and recorded in `docs/legacy-availability.md`:
#: 2016-09-05 is a Monday the API reports as empty, 2016-09-06 resolves to
#: OJ S 171/2016, and OJ S 170/2016 — the issue immediately before it — is
#: still served by the package endpoint.
#:
#: This is a refusal floor, not a claim about what TED keeps. Packages exist
#: back to at least 2012; what stops here is the only way this project has of
#: addressing one, which is by date.
SEARCH_INDEX_FLOOR = date(2016, 9, 6)


class DateNotIndexed(ValueError):
    """A publication date the Search API cannot resolve to an OJ S issue.

    Kept distinct from a date that published nothing because they are
    different facts and only one of them is about TED's calendar. Below the
    floor the API answers every date the way it answers a Sunday, so the two
    are indistinguishable from the response alone — and guessing costs more
    than refusing: an archive whose whole job is to be ground truth would be
    recording, permanently and silently, that TED did not publish on a day it
    did.
    """


@dataclass(frozen=True, order=True)
class OjsIssue:
    """One issue of the Official Journal, S series."""

    year: int
    number: int

    @classmethod
    def parse(cls, raw: str) -> OjsIssue:
        """Parse the API's ``"157/2026"`` form (issue number, then year)."""
        match = _OJS_NUMBER.match(raw.strip())
        if match is None:
            raise ValueError(f"malformed OJ S number: {raw!r}")
        return cls(year=int(match["year"]), number=int(match["number"]))

    @property
    def package_id(self) -> str:
        """The ``yyyynnnnn`` identifier used in the package URL."""
        return f"{self.year:04d}{self.number:05d}"

    @property
    def package_url(self) -> str:
        return PACKAGE_URL_TEMPLATE.format(package_id=self.package_id)

    def __str__(self) -> str:
        return f"{self.number}/{self.year}"


def issue_for_date(client: TedClient, day: date) -> OjsIssue | None:
    """Return the OJ S issue published on ``day``, or ``None`` if none was.

    Weekends, holidays and any other quiet day come back as ``None``: within
    the indexed period the service is the authority on which dates published,
    so we need no calendar of our own.

    Outside it there is no authority to consult, and a date below
    :data:`SEARCH_INDEX_FLOOR` raises :class:`DateNotIndexed` rather than
    reporting a quiet day. Nothing is requested for such a date, so a refused
    backfill costs no traffic.
    """
    if day < SEARCH_INDEX_FLOOR:
        raise DateNotIndexed(
            f"{day.isoformat()} is before {SEARCH_INDEX_FLOOR.isoformat()}, the "
            "earliest publication date TED's Search API indexes, and this "
            "project addresses a package only by date. The API reports an "
            "unindexed date as empty, exactly as it reports a Sunday, so "
            "continuing would archive a day TED published on as a day it did "
            "not. See docs/legacy-availability.md."
        )

    stamp = day.strftime("%Y%m%d")
    body = client.search(
        query=f"publication-date>={stamp} AND publication-date<={stamp}",
        fields=[OJS_FIELD],
        limit=1,
    )

    notices = body.get("notices") or []
    if not notices:
        return None

    raw = notices[0].get(OJS_FIELD)
    if not raw:
        raise FetchError(
            f"notice published on {day.isoformat()} carries no {OJS_FIELD!r} field"
        )
    try:
        return OjsIssue.parse(str(raw))
    except ValueError as exc:
        raise FetchError(
            f"could not read the OJ S issue for {day.isoformat()}"
        ) from exc


def dates_in_range(start: date, end: date) -> Iterator[date]:
    """Every calendar date from ``start`` to ``end``, inclusive."""
    if end < start:
        raise ValueError(
            f"end date {end.isoformat()} precedes start {start.isoformat()}"
        )
    day = start
    while day <= end:
        yield day
        day += timedelta(days=1)
