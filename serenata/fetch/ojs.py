"""Resolve calendar dates to the OJ S issues that address daily packages.

Daily packages are keyed by Official Journal S issue (``157/2026``), but a
backfill is expressed in dates. The mapping skips weekends and holidays, so
it cannot be computed by counting business days. The Search API knows it: any
notice published on a date carries that date's ``ojs-number``, so one
``limit: 1`` query per day resolves it, and a day that returns nothing simply
did not publish (ADR-0002).
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

    Weekends, holidays and any other quiet day come back as ``None``: the
    service is the authority on which dates published, so we never need a
    calendar of our own.
    """
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
