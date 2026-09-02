"""Resolving calendar dates to the OJ S issues that address daily packages."""

from __future__ import annotations

from datetime import date

import httpx
import pytest

from serenata.fetch.client import FetchError
from serenata.fetch.ojs import OjsIssue, dates_in_range, issue_for_date

from .support import search_body


class TestOjsIssue:
    def test_it_parses_the_api_form_number_then_year(self):
        issue = OjsIssue.parse("157/2026")
        assert (issue.number, issue.year) == (157, 2026)

    def test_the_package_id_is_the_year_then_a_padded_issue_number(self):
        assert OjsIssue.parse("157/2026").package_id == "202600157"
        assert OjsIssue.parse("1/2026").package_id == "202600001"
        assert OjsIssue.parse("12345/2026").package_id == "202612345"

    def test_the_package_url_is_built_from_the_id(self):
        url = OjsIssue.parse("157/2026").package_url
        assert url == "https://ted.europa.eu/packages/daily/202600157"

    def test_it_round_trips_through_its_string_form(self):
        assert str(OjsIssue.parse("157/2026")) == "157/2026"

    def test_surrounding_whitespace_is_tolerated(self):
        assert OjsIssue.parse("  157/2026 ") == OjsIssue(year=2026, number=157)

    @pytest.mark.parametrize(
        "raw", ["", "157", "2026/157/1", "157-2026", "abc/2026", "157/26", "/2026"]
    )
    def test_a_malformed_number_is_rejected(self, raw):
        with pytest.raises(ValueError, match="malformed OJ S number"):
            OjsIssue.parse(raw)

    def test_issues_sort_by_year_then_number(self):
        issues = [
            OjsIssue(year=2026, number=9),
            OjsIssue(year=2025, number=200),
            OjsIssue(year=2026, number=1),
        ]
        assert sorted(issues) == [
            OjsIssue(year=2025, number=200),
            OjsIssue(year=2026, number=1),
            OjsIssue(year=2026, number=9),
        ]


class TestIssueForDate:
    def test_it_asks_for_one_notice_on_exactly_that_date(self, client_factory):
        payloads: list[dict] = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            payloads.append(json.loads(request.content))
            return httpx.Response(200, json=search_body())

        with client_factory(handler) as client:
            issue = issue_for_date(client, date(2026, 8, 17))

        assert issue == OjsIssue(year=2026, number=157)
        assert payloads[0]["limit"] == 1, "one notice is enough to read the issue"
        assert payloads[0]["fields"] == ["ojs-number"]
        assert payloads[0]["query"] == (
            "publication-date>=20260817 AND publication-date<=20260817"
        )

    def test_a_day_with_no_notices_resolves_to_nothing(self, client_factory):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=search_body(count=0))

        with client_factory(handler) as client:
            assert issue_for_date(client, date(2026, 8, 15)) is None

    def test_a_missing_ojs_field_is_an_error_not_a_silent_skip(self, client_factory):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=search_body(ojs_number=None))

        with (
            client_factory(handler) as client,
            pytest.raises(FetchError, match="no 'ojs-number' field"),
        ):
            issue_for_date(client, date(2026, 8, 17))

    def test_an_unparsable_ojs_field_is_an_error(self, client_factory):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=search_body(ojs_number="not-a-number"))

        with (
            client_factory(handler) as client,
            pytest.raises(FetchError, match="could not read the OJ S issue"),
        ):
            issue_for_date(client, date(2026, 8, 17))


class TestDatesInRange:
    def test_both_ends_are_included(self):
        days = list(dates_in_range(date(2026, 8, 17), date(2026, 8, 19)))
        assert days == [date(2026, 8, 17), date(2026, 8, 18), date(2026, 8, 19)]

    def test_a_single_day_range_yields_that_day(self):
        assert list(dates_in_range(date(2026, 8, 17), date(2026, 8, 17))) == [
            date(2026, 8, 17)
        ]

    def test_it_crosses_a_month_boundary(self):
        days = list(dates_in_range(date(2026, 8, 30), date(2026, 9, 2)))
        assert days[0] == date(2026, 8, 30)
        assert days[-1] == date(2026, 9, 2)
        assert len(days) == 4

    def test_a_backwards_range_is_rejected(self):
        with pytest.raises(ValueError, match="precedes"):
            list(dates_in_range(date(2026, 8, 19), date(2026, 8, 17)))
