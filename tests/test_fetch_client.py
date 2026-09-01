"""The HTTP client's contract: identify us, pace us, retry what is transient."""

from __future__ import annotations

import httpx
import pytest

from serenata.fetch.client import (
    MAX_SEARCH_LIMIT,
    USER_AGENT,
    FetchError,
    RetryPolicy,
)

from .support import search_body


def test_user_agent_names_the_project_and_its_repository(client_factory):
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers["User-Agent"])
        return httpx.Response(200, json=search_body())

    with client_factory(handler) as client:
        client.search(query="x", fields=["ojs-number"], limit=1)

    assert seen == [USER_AGENT]
    assert "github.com/cabral/serenata" in USER_AGENT


def test_search_rejects_an_empty_fields_list_without_a_round_trip(client_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made")

    with (
        client_factory(handler) as client,
        pytest.raises(ValueError, match="non-empty"),
    ):
        client.search(query="x", fields=[])


@pytest.mark.parametrize("limit", [0, MAX_SEARCH_LIMIT + 1])
def test_search_rejects_a_limit_the_service_would_refuse(client_factory, limit):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request should be made")

    with client_factory(handler) as client, pytest.raises(ValueError, match="limit"):
        client.search(query="x", fields=["ojs-number"], limit=limit)


def test_requests_are_spaced_by_the_minimum_interval(client_factory, clock):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=search_body())

    with client_factory(handler, min_interval=2.5) as client:
        client.search(query="x", fields=["ojs-number"], limit=1)
        client.search(query="y", fields=["ojs-number"], limit=1)

    # The first request sets the mark; the second waits out the interval.
    assert clock.slept == [2.5]


def test_no_wait_when_the_interval_already_elapsed(client_factory, clock):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=search_body())

    with client_factory(handler, min_interval=2.0) as client:
        client.search(query="x", fields=["ojs-number"], limit=1)
        clock.advance(5.0)
        client.search(query="y", fields=["ojs-number"], limit=1)

    assert clock.slept == []


def test_a_transient_server_error_is_retried_then_succeeds(client_factory, clock):
    statuses = iter([503, 500])

    def handler(request: httpx.Request) -> httpx.Response:
        status = next(statuses, None)
        if status is None:
            return httpx.Response(200, json=search_body())
        return httpx.Response(status, text="try later")

    with client_factory(
        handler, retry=RetryPolicy(attempts=3, base_delay=1.0)
    ) as client:
        body = client.search(query="x", fields=["ojs-number"], limit=1)

    assert body["totalNoticeCount"] == 1
    assert clock.slept == [1.0, 2.0]  # exponential, no jitter


def test_retry_after_overrides_the_backoff_schedule(client_factory, clock):
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "7"}, text="slow down")]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses, httpx.Response(200, json=search_body()))

    with client_factory(handler) as client:
        client.search(query="x", fields=["ojs-number"], limit=1)

    assert clock.slept == [7.0]


def test_an_unparsable_retry_after_falls_back_to_the_schedule(client_factory, clock):
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"})]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(responses, httpx.Response(200, json=search_body()))

    with client_factory(handler) as client:
        client.search(query="x", fields=["ojs-number"], limit=1)

    assert clock.slept == [1.0]


def test_a_client_error_is_not_retried(client_factory, clock):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(400, text='{"message":"Validation error"}')

    with client_factory(handler) as client, pytest.raises(FetchError, match="HTTP 400"):
        client.search(query="x", fields=["ojs-number"], limit=1)

    assert calls == 1
    assert clock.slept == []


def test_persistent_failure_exhausts_the_retry_budget_then_raises(client_factory):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, text="down")

    retry = RetryPolicy(attempts=3, base_delay=1.0)
    with (
        client_factory(handler, retry=retry) as client,
        pytest.raises(FetchError, match="after 3 attempts"),
    ):
        client.search(query="x", fields=["ojs-number"], limit=1)

    assert calls == 3


def test_a_transport_error_is_retried(client_factory):
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.ConnectError("connection reset")
        return httpx.Response(200, json=search_body())

    with client_factory(handler) as client:
        body = client.search(query="x", fields=["ojs-number"], limit=1)

    assert calls == 2
    assert body["totalNoticeCount"] == 1


def test_a_non_json_search_body_is_a_fetch_error(client_factory):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>maintenance</html>")

    with client_factory(handler) as client, pytest.raises(FetchError, match="non-JSON"):
        client.search(query="x", fields=["ojs-number"], limit=1)


def test_search_sends_iteration_mode_only_when_given_a_token(client_factory):
    payloads: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        payloads.append(json.loads(request.content))
        return httpx.Response(200, json=search_body())

    with client_factory(handler) as client:
        client.search(query="x", fields=["ojs-number"], limit=1)
        client.search(query="x", fields=["ojs-number"], limit=1, iteration_token="abc")

    assert "paginationMode" not in payloads[0]
    assert payloads[1]["paginationMode"] == "ITERATION"
    assert payloads[1]["iterationNextToken"] == "abc"


class TestDownload:
    def test_it_writes_the_bytes_and_reports_their_checksum(
        self, client_factory, tmp_path
    ):
        import hashlib

        payload = b"gzip-ish bytes"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=payload)

        destination = tmp_path / "nested" / "202600157.tar.gz"
        with client_factory(handler) as client:
            result = client.download("https://example.invalid/pkg", destination)

        assert destination.read_bytes() == payload
        assert result.size_bytes == len(payload)
        assert result.sha256 == hashlib.sha256(payload).hexdigest()

    def test_a_failed_download_leaves_no_partial_file(self, client_factory, tmp_path):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="boom")

        destination = tmp_path / "202600157.tar.gz"
        with client_factory(handler) as client, pytest.raises(FetchError):
            client.download("https://example.invalid/pkg", destination)

        assert not destination.exists()
        assert list(tmp_path.glob("*.part")) == []

    def test_a_missing_package_is_not_retried(self, client_factory, tmp_path):
        calls = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal calls
            calls += 1
            return httpx.Response(404, text="no such package")

        with (
            client_factory(handler) as client,
            pytest.raises(FetchError, match="HTTP 404"),
        ):
            client.download("https://example.invalid/pkg", tmp_path / "p.tar.gz")

        assert calls == 1
