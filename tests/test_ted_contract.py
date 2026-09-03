"""What this project assumes about TED, asserted against the live service.

**These tests reach the network and are excluded from the default suite.** Run
them on purpose:

    uv run pytest -m contract

Everything else in `tests/` runs offline against a stand-in TED shaped from
observed behaviour, which catches regressions in our logic and cannot catch a
change in TED's. If `ojs-number` were renamed, or the `limit` cap dropped below
250, the offline suite would stay green and the next backfill would fail. This
is the tripwire for that, and its only job is to fail loudly naming which
assumption broke.

The assumptions are [ADR-0002](../docs/adr/0002-fetch-daily-bulk-packages.md)'s,
verified against the service on 2026-09-01 and asserted here:

1. `POST https://api.ted.europa.eu/v3/notices/search` answers unauthenticated.
2. `fields` must be non-empty — an empty list is rejected with HTTP 400.
3. `limit` is capped at 250; above that the service says so.
4. A notice carries `ojs-number` in the form `"157/2026"`.
5. `GET https://ted.europa.eu/packages/daily/{yyyynnnnn}` returns a gzipped tar
   whose members sit under one `YYYYMMDD_NNN` directory.

**Politeness is part of the design.** One run makes a handful of `limit: 1`
requests through the project's own throttled client, and reads only the first
member of a package rather than pulling twenty megabytes to check a directory
name. It runs weekly on a schedule, not on every push.
"""

from __future__ import annotations

import re
import tarfile
from collections.abc import Iterator
from datetime import date, timedelta

import httpx
import pytest

from serenata.fetch import FetchError, OjsIssue, TedClient, issue_for_date
from serenata.fetch.client import MAX_SEARCH_LIMIT, SEARCH_URL, USER_AGENT
from serenata.fetch.ojs import OJS_FIELD

pytestmark = pytest.mark.contract

#: How far back to look for a publication day. Weekends and holidays publish
#: nothing; a fortnight of silence would itself be the news.
LOOKBACK_DAYS = 14

#: Members of a daily package sit under one directory named for the publication
#: date and the issue number.
MEMBER_PREFIX = re.compile(r"^\d{8}_\d+/")


@pytest.fixture(scope="module")
def client() -> Iterator[TedClient]:
    """The project's own client, unmocked. Throttled by its own defaults."""
    with TedClient() as live:
        yield live


@pytest.fixture(scope="module")
def issue(client: TedClient) -> OjsIssue:
    """The most recent publication day TED will admit to.

    Resolved rather than hardcoded: a fixed date would eventually age out of
    whatever window the service keeps, and this test would then fail for a
    reason that has nothing to do with the contract it exists to watch.
    """
    day = date.today()
    for _ in range(LOOKBACK_DAYS):
        day -= timedelta(days=1)
        found = issue_for_date(client, day)
        if found is not None:
            return found
    raise AssertionError(
        f"TED published nothing in the {LOOKBACK_DAYS} days before "
        f"{date.today().isoformat()}. Either the Search API's query syntax or "
        f"its {OJS_FIELD!r} field has changed, or something is very wrong."
    )


class TestTheSearchApi:
    """Assumptions 1 to 4: what the Search API accepts and what it returns."""

    def test_it_answers_without_authentication(self, client: TedClient) -> None:
        body = client.search(
            query="publication-date>=20240101", fields=[OJS_FIELD], limit=1
        )
        assert "notices" in body, (
            f"the Search API no longer returns a 'notices' key: {sorted(body)}"
        )
        assert "totalNoticeCount" in body

    def test_an_empty_fields_list_is_rejected(self, client: TedClient) -> None:
        # Asserted against the service rather than through `client.search`,
        # which refuses an empty list itself to save a round trip. The point is
        # whether the service still needs it to.
        with pytest.raises(FetchError) as raised:
            client.request(
                "POST",
                SEARCH_URL,
                json={"query": "publication-date>=20240101", "fields": [], "limit": 1},
            )
        assert "HTTP 400" in str(raised.value), (
            "an empty 'fields' list is no longer rejected with HTTP 400; "
            "TedClient.search refuses it locally on the strength of that"
        )

    def test_the_limit_is_still_capped_at_250(self, client: TedClient) -> None:
        with pytest.raises(FetchError) as raised:
            client.request(
                "POST",
                SEARCH_URL,
                json={
                    "query": "publication-date>=20240101",
                    "fields": [OJS_FIELD],
                    "limit": MAX_SEARCH_LIMIT + 1,
                },
            )
        message = str(raised.value)
        assert "SEARCH_EXCEEDS_MAX_LIMIT" in message or "HTTP 400" in message, (
            f"a limit above {MAX_SEARCH_LIMIT} was not rejected: {message}. "
            "Paging assumes that cap"
        )

    def test_the_cap_itself_is_accepted(self, client: TedClient) -> None:
        # The other half of the same assumption: 250 has to still work, or every
        # backfill silently pages 250 at a time against a smaller ceiling.
        body = client.search(
            query="publication-date>=20240101",
            fields=[OJS_FIELD],
            limit=MAX_SEARCH_LIMIT,
        )
        assert len(body.get("notices") or []) <= MAX_SEARCH_LIMIT

    def test_a_notice_carries_its_ojs_number(self, issue: OjsIssue) -> None:
        # `issue` resolved through the production path, so reaching here means
        # the field exists, is populated, and parses as "157/2026".
        assert issue.number > 0
        assert issue.year >= 2024
        assert str(issue) == f"{issue.number}/{issue.year}"


class TestTheDailyPackage:
    """Assumption 5: the package endpoint, and the shape of what it serves."""

    def test_a_package_is_a_gzipped_tar_under_one_directory(
        self, issue: OjsIssue
    ) -> None:
        with httpx.stream(
            "GET",
            issue.package_url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=120.0,
        ) as response:
            assert response.status_code == 200, (
                f"{issue.package_url} answered {response.status_code}; daily "
                "packages are how this project fetches anything at all"
            )
            # Read only the first member. A package is ~20 MB and the directory
            # name is in the first few kilobytes; pulling the rest to check a
            # prefix would be rude and would prove nothing more.
            stream = _Reader(response.iter_bytes())
            with tarfile.open(fileobj=stream, mode="r|gz") as archive:
                first = next(iter(archive))

        assert MEMBER_PREFIX.match(first.name), (
            f"package members no longer sit under a YYYYMMDD_NNN directory: "
            f"{first.name!r}"
        )
        assert first.name.endswith(".xml")

    def test_the_package_id_is_built_the_way_the_url_expects(
        self, issue: OjsIssue
    ) -> None:
        assert issue.package_url.endswith(f"/{issue.package_id}")
        assert len(issue.package_id) == 9, (
            f"the package id {issue.package_id!r} is not yyyynnnnn"
        )


class _Reader:
    """A file-like view over an httpx byte iterator.

    `tarfile` in stream mode reads forward only, which is exactly what a
    response body offers; this adapts one to the other so the transfer can be
    abandoned after the first member.
    """

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks
        self._buffer = b""

    def read(self, size: int = -1) -> bytes:
        while size < 0 or len(self._buffer) < size:
            try:
                self._buffer += next(self._chunks)
            except StopIteration:
                break
        if size < 0:
            taken, self._buffer = self._buffer, b""
            return taken
        taken, self._buffer = self._buffer[:size], self._buffer[size:]
        return taken
