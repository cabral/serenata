# SPDX-License-Identifier: AGPL-3.0-only
"""The fetch stage: politeness, retries, and a manifest that can be checked.

Every test here drives a stand-in through `httpx.MockTransport` and a clock that
moves only when told to. Nothing sleeps and nothing resolves a hostname, which
is enforced rather than intended: `conftest.py` refuses a socket.

The retry tests are the ones worth reading. The transport-error case is not
hypothetical: `recherche-entreprises.api.gouv.fr` intermittently failed to
resolve from the maintainer's machine while this was being specified, and a
client that retried only on status codes would have lost a run of several
thousand requests to it.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

import httpx
import pytest
from crony_eu.http import (
    CHUNK,
    DEFAULT_RATE_PER_SECOND,
    RETRY_STATUSES,
    USER_AGENT,
    FetchError,
    RateLimiter,
    RetryPolicy,
    SourceClient,
    SystemClock,
    append_manifest,
    build_client,
    download,
    now,
    read_manifest,
    retry_after,
)
from fakes import FakeClock


def client_for(
    handler: object,
    clock: FakeClock,
    *,
    attempts: int = 5,
    rate: float = 1000.0,
) -> SourceClient:
    """A client wired to a scripted transport, a fake clock and a fixed seed."""
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    return SourceClient(
        source="stand-in",
        client=httpx.Client(transport=transport, headers={"User-Agent": USER_AGENT}),
        limiter=RateLimiter(rate=rate, capacity=rate, clock=clock),
        policy=RetryPolicy(attempts=attempts, base_seconds=0.5, cap_seconds=30.0),
        clock=clock,
        rng=random.Random(0),
    )


class TestRateLimiter:
    def test_a_full_bucket_does_not_wait(self, clock: FakeClock) -> None:
        limiter = RateLimiter(rate=5.0, capacity=5.0, clock=clock)
        assert [limiter.take() for _ in range(5)] == [0.0] * 5
        assert clock.slept == []

    def test_the_sixth_request_waits_for_a_token(self, clock: FakeClock) -> None:
        limiter = RateLimiter(rate=5.0, capacity=5.0, clock=clock)
        for _ in range(5):
            limiter.take()

        waited = limiter.take()

        # One token at five per second is a fifth of a second.
        assert waited == pytest.approx(0.2)
        assert clock.slept == [pytest.approx(0.2)]

    def test_the_bucket_refills_while_nothing_is_happening(
        self, clock: FakeClock
    ) -> None:
        limiter = RateLimiter(rate=5.0, capacity=5.0, clock=clock)
        for _ in range(5):
            limiter.take()
        clock.advance(1.0)

        assert limiter.take() == 0.0
        assert clock.slept == []

    def test_it_never_exceeds_its_capacity(self, clock: FakeClock) -> None:
        # An hour idle does not buy an hour's worth of burst.
        limiter = RateLimiter(rate=5.0, capacity=5.0, clock=clock)
        clock.advance(3600.0)

        assert [limiter.take() for _ in range(5)] == [0.0] * 5
        assert limiter.take() > 0.0

    def test_the_steady_rate_holds_over_many_requests(self, clock: FakeClock) -> None:
        # The property that matters to a source's operators. Note what it is
        # not: the average over the whole window exceeds the rate, because the
        # first `capacity` requests were free. What is bounded is everything
        # after the burst, which is what a limiter promises.
        limiter = RateLimiter(rate=5.0, capacity=5.0, clock=clock)
        for _ in range(100):
            limiter.take()

        after_the_burst = 100 - 5
        assert after_the_burst / clock.now <= 5.0 + 1e-9


class TestBackoff:
    def test_it_grows_with_each_attempt(self) -> None:
        policy = RetryPolicy(base_seconds=0.5, cap_seconds=30.0)
        ceilings = [policy.backoff(attempt, 1.0) for attempt in range(1, 6)]
        assert ceilings == [0.5, 1.0, 2.0, 4.0, 8.0]

    def test_it_is_capped(self) -> None:
        policy = RetryPolicy(base_seconds=0.5, cap_seconds=3.0)
        assert policy.backoff(20, 1.0) == 3.0

    def test_jitter_spans_the_whole_interval(self) -> None:
        # Full jitter, not a fixed delay plus noise: two clients that collided
        # once should not collide again on every retry.
        policy = RetryPolicy(base_seconds=0.5, cap_seconds=30.0)
        ceiling = policy.backoff(3, 1.0)

        assert policy.backoff(3, 0.0) == 0.0
        assert 0.99 * ceiling <= policy.backoff(3, 0.999) < ceiling


class TestRetryAfter:
    def test_it_reads_a_number_of_seconds(self) -> None:
        assert retry_after(httpx.Response(429, headers={"Retry-After": "7"})) == 7.0

    def test_it_ignores_an_http_date(self) -> None:
        # Parsing the date form means trusting two clocks to agree. Our own
        # backoff is never longer than the cap, so declining is the safe answer.
        response = httpx.Response(
            429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
        )
        assert retry_after(response) is None

    def test_it_ignores_a_missing_header(self) -> None:
        assert retry_after(httpx.Response(429)) is None

    def test_it_ignores_a_negative_value(self) -> None:
        assert retry_after(httpx.Response(429, headers={"Retry-After": "-5"})) is None


class TestRetrying:
    def test_a_429_is_retried_and_its_retry_after_honoured(
        self, clock: FakeClock
    ) -> None:
        seen: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(1)
            if len(seen) == 1:
                return httpx.Response(429, headers={"Retry-After": "7"})
            return httpx.Response(200, text="through")

        response = client_for(handler, clock).get("https://example.invalid/x")

        assert response.status_code == 200
        assert clock.slept == [7.0], "the server said seven seconds and we waited seven"

    def test_two_503s_then_a_200(self, clock: FakeClock) -> None:
        codes = iter([503, 503, 200])

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(next(codes))

        response = client_for(handler, clock).get("https://example.invalid/x")

        assert response.status_code == 200
        assert len(clock.slept) == 2

    def test_a_name_resolution_failure_is_retried(self, clock: FakeClock) -> None:
        # The case this project actually hit. A DNS blip is a transport error,
        # not a status code, and it has to be inside the retry loop.
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) < 3:
                raise httpx.ConnectError("[Errno -2] Name or service not known")
            return httpx.Response(200, text="resolved eventually")

        response = client_for(handler, clock).get("https://example.invalid/x")

        assert response.status_code == 200
        assert len(attempts) == 3

    def test_a_timeout_is_retried(self, clock: FakeClock) -> None:
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) < 2:
                raise httpx.ReadTimeout("too slow")
            return httpx.Response(200)

        assert (
            client_for(handler, clock).get("https://example.invalid/x").status_code
            == 200
        )

    def test_a_404_is_an_answer_and_is_not_retried(self, clock: FakeClock) -> None:
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            return httpx.Response(404)

        response = client_for(handler, clock).get("https://example.invalid/x")

        assert response.status_code == 404
        assert attempts == [1], "retrying a 404 is asking the same question again"

    def test_exhausted_attempts_raise_naming_the_last_failure(
        self, clock: FakeClock
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        with pytest.raises(FetchError, match=r"3 attempts.*HTTP 503"):
            client_for(handler, clock, attempts=3).get("https://example.invalid/x")

    def test_exhausted_transport_errors_say_which_error(self, clock: FakeClock) -> None:
        # A caller handling a failed fetch wants to know whether the source said
        # no or the network did.
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Name or service not known")

        with pytest.raises(FetchError, match="ConnectError"):
            client_for(handler, clock, attempts=2).get("https://example.invalid/x")

    def test_the_retry_set_is_not_vacuous(self) -> None:
        # If this set were emptied, every test above would still pass by never
        # entering the retry branch at all.
        assert {429, 503} <= RETRY_STATUSES
        assert 404 not in RETRY_STATUSES


class TestUserAgent:
    def test_it_names_the_project_and_where_to_complain(self, clock: FakeClock) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers["User-Agent"])
            return httpx.Response(200)

        client_for(handler, clock).get("https://example.invalid/x")

        assert "crony-eu" in seen[0]
        assert "github.com/cabral/serenata" in seen[0]


class TestJson:
    def test_it_returns_the_parsed_body(self, clock: FakeClock) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"total_results": 2, "results": []})

        body = client_for(handler, clock).json("https://example.invalid/search")

        assert body["total_results"] == 2

    def test_a_client_error_raises_rather_than_returning_nothing(
        self, clock: FakeClock
    ) -> None:
        # A 404 is not retried, so without this it would fall out of `request`
        # as a response and be handed to `.json()`, which would raise something
        # about decoding rather than about the source saying no.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="no such dataset")

        with pytest.raises(FetchError, match="HTTP 404"):
            client_for(handler, clock).json("https://example.invalid/search")


class TestBuildClient:
    def test_it_carries_the_project_user_agent(self) -> None:
        built = build_client(
            "fr-decp", transport=httpx.MockTransport(lambda r: httpx.Response(200))
        )
        try:
            assert built.source == "fr-decp"
            assert "crony-eu" in built.client.headers["User-Agent"]
            assert built.limiter.rate == DEFAULT_RATE_PER_SECOND
        finally:
            built.client.close()


class TestSystemClock:
    def test_it_moves_forward(self) -> None:
        clock = SystemClock()
        first = clock.monotonic()
        clock.sleep(0.0)

        assert clock.monotonic() >= first


class TestManifest:
    def test_a_new_snapshot_reads_as_empty(self, tmp_path: Path) -> None:
        assert read_manifest(tmp_path / "manifest.json") == []

    def test_an_entry_survives_a_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        append_manifest(path, {"url": "https://example.invalid/a", "bytes": 1})

        assert read_manifest(path) == [{"url": "https://example.invalid/a", "bytes": 1}]

    def test_entries_accumulate(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        append_manifest(path, {"url": "a"})
        append_manifest(path, {"url": "b"})

        assert [entry["url"] for entry in read_manifest(path)] == ["a", "b"]

    def test_it_leaves_no_partial_behind(self, tmp_path: Path) -> None:
        path = tmp_path / "manifest.json"
        append_manifest(path, {"url": "a"})

        assert list(tmp_path.iterdir()) == [path]


class TestDownload:
    def body(self) -> bytes:
        return b"commune,supplier,amount\n" * 500

    def client(self, clock: FakeClock) -> SourceClient:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=self.body())

        return client_for(handler, clock)

    def test_it_writes_the_bytes_and_records_their_hash(
        self, tmp_path: Path, clock: FakeClock
    ) -> None:
        import hashlib

        destination = tmp_path / "raw" / "file.csv"
        manifest = tmp_path / "raw" / "manifest.json"

        entry = download(
            self.client(clock),
            "https://example.invalid/file.csv",
            destination,
            manifest,
            licence="Licence Ouverte 2.0",
        )

        assert destination.read_bytes() == self.body()
        assert entry["sha256"] == hashlib.sha256(self.body()).hexdigest()
        assert entry["bytes"] == len(self.body())
        assert entry["licence"] == "Licence Ouverte 2.0"

    def test_the_entry_reaches_the_manifest(
        self, tmp_path: Path, clock: FakeClock
    ) -> None:
        manifest = tmp_path / "raw" / "manifest.json"

        download(
            self.client(clock),
            "https://example.invalid/file.csv",
            tmp_path / "raw" / "file.csv",
            manifest,
            licence="Licence Ouverte 2.0",
        )

        recorded = json.loads(manifest.read_text(encoding="utf-8"))["files"]
        assert len(recorded) == 1
        assert recorded[0]["url"] == "https://example.invalid/file.csv"
        assert recorded[0]["source"] == "stand-in"

    def test_a_second_download_appends_rather_than_replaces(
        self, tmp_path: Path, clock: FakeClock
    ) -> None:
        # Refetching the same URL is how a corrected source file arrives. The
        # manifest is a history, not a current state.
        manifest = tmp_path / "raw" / "manifest.json"
        for name in ("a.csv", "b.csv"):
            download(
                self.client(clock),
                f"https://example.invalid/{name}",
                tmp_path / "raw" / name,
                manifest,
                licence="Licence Ouverte 2.0",
            )

        assert len(read_manifest(manifest)) == 2

    def test_it_leaves_no_partial_file(self, tmp_path: Path, clock: FakeClock) -> None:
        destination = tmp_path / "raw" / "file.csv"

        download(
            self.client(clock),
            "https://example.invalid/file.csv",
            destination,
            tmp_path / "raw" / "manifest.json",
            licence="Licence Ouverte 2.0",
        )

        assert not list(destination.parent.glob("*.partial"))

    def test_an_interrupted_download_records_nothing(
        self, tmp_path: Path, clock: FakeClock
    ) -> None:
        # The state a rerun can recover from is a partial file and no manifest
        # entry. A truncated file under the real name, vouched for by an entry,
        # is the state it could not.
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadError("connection dropped mid-body")

        manifest = tmp_path / "raw" / "manifest.json"
        with pytest.raises((httpx.ReadError, FetchError)):
            download(
                client_for(handler, clock, attempts=1),
                "https://example.invalid/file.csv",
                tmp_path / "raw" / "file.csv",
                manifest,
                licence="Licence Ouverte 2.0",
            )

        assert not (tmp_path / "raw" / "file.csv").exists()
        assert read_manifest(manifest) == []


class TestStreamingIsRetriedButNotResumed:
    """A 247MB download needs retries. It must not need them mid-body."""

    def test_a_503_before_the_body_is_retried(
        self, tmp_path: Path, clock: FakeClock
    ) -> None:
        codes = iter([503, 200])

        def handler(request: httpx.Request) -> httpx.Response:
            code = next(codes)
            return httpx.Response(code, content=b"payload" if code == 200 else b"")

        destination = tmp_path / "raw" / "file.bin"
        download(
            client_for(handler, clock),
            "https://example.invalid/file.bin",
            destination,
            tmp_path / "raw" / "manifest.json",
            licence="Licence Ouverte 2.0",
        )

        assert destination.read_bytes() == b"payload"

    def test_a_404_raises_and_writes_nothing_to_the_manifest(
        self, tmp_path: Path, clock: FakeClock
    ) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, text="no such resource")

        manifest = tmp_path / "raw" / "manifest.json"
        with pytest.raises(FetchError, match="HTTP 404"):
            download(
                client_for(handler, clock),
                "https://example.invalid/gone.bin",
                tmp_path / "raw" / "gone.bin",
                manifest,
                licence="Licence Ouverte 2.0",
            )

        assert not (tmp_path / "raw" / "gone.bin").exists()
        assert read_manifest(manifest) == []

    def test_a_failure_after_the_first_byte_is_not_retried(
        self, tmp_path: Path, clock: FakeClock
    ) -> None:
        # The hazard this guards against: restarting the response would append
        # a second copy of the body to a file already holding part of one, and
        # the sha256 recorded would correctly describe the wrong bytes.
        calls: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)

            def body() -> object:
                # A whole chunk, so that `iter_bytes` hands it to the caller
                # before pulling again. A short first yield would be buffered
                # and the failure would arrive before any byte was written,
                # which is the safe-to-retry case rather than this one.
                yield b"x" * CHUNK
                raise httpx.ReadError("dropped")

            return httpx.Response(200, content=body())

        with pytest.raises(FetchError, match="after the body had begun"):
            download(
                client_for(handler, clock),
                "https://example.invalid/big.bin",
                tmp_path / "raw" / "big.bin",
                tmp_path / "raw" / "manifest.json",
                licence="Licence Ouverte 2.0",
            )

        assert calls == [1], "the body was requested again after bytes were written"
        assert not (tmp_path / "raw" / "big.bin").exists()

    def test_a_name_resolution_failure_before_the_body_is_retried(
        self, tmp_path: Path, clock: FakeClock
    ) -> None:
        # The scenario the retry loop exists for, on the path where it matters
        # most: a 247MB file, and DNS that comes and goes.
        attempts: list[int] = []

        def handler(request: httpx.Request) -> httpx.Response:
            attempts.append(1)
            if len(attempts) < 3:
                raise httpx.ConnectError("[Errno -2] Name or service not known")
            return httpx.Response(200, content=b"decp")

        destination = tmp_path / "raw" / "decp.parquet"
        download(
            client_for(handler, clock),
            "https://example.invalid/decp.parquet",
            destination,
            tmp_path / "raw" / "manifest.json",
            licence="Licence Ouverte 2.0",
        )

        assert destination.read_bytes() == b"decp"
        assert len(attempts) == 3
        assert len(clock.slept) == 2

    def test_exhausted_attempts_raise(self, tmp_path: Path, clock: FakeClock) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        with pytest.raises(FetchError, match=r"2 attempts"):
            download(
                client_for(handler, clock, attempts=2),
                "https://example.invalid/file.bin",
                tmp_path / "raw" / "file.bin",
                tmp_path / "raw" / "manifest.json",
                licence="Licence Ouverte 2.0",
            )


class TestRetrievedAt:
    def test_it_is_utc_to_the_second(self) -> None:
        stamp = now()
        assert stamp.endswith("+00:00")
        assert "." not in stamp, "sub-second precision is noise in a provenance record"
