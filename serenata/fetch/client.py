"""Polite HTTP access to TED's two public reuse channels (ADR-0002).

This is the only module in the project that opens a network connection. It
does two things: run expert queries against the Search API, and stream a
daily package to disk. Both go through one request path that throttles,
retries with exponential backoff, honours ``Retry-After``, and identifies the
project in its User-Agent.

TED publishes no rate-limit headers, so the ceiling is ours to set: requests
are spaced by ``min_interval`` seconds and the caller is expected to leave the
default alone unless it has a reason.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from serenata import __version__

SEARCH_URL = "https://api.ted.europa.eu/v3/notices/search"
PACKAGE_URL_TEMPLATE = "https://ted.europa.eu/packages/daily/{package_id}"

USER_AGENT = (
    f"SerenataEuropa/{__version__} "
    "(+https://github.com/cabral/serenata; open procurement anomaly detection)"
)

#: The Search API rejects a larger ``limit`` with HTTP 400.
MAX_SEARCH_LIMIT = 250

#: Statuses worth retrying: rate limiting and transient server faults.
RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

_DOWNLOAD_CHUNK_BYTES = 1 << 16


class FetchError(RuntimeError):
    """A TED request failed in a way that retrying did not fix."""


@dataclass(frozen=True)
class RetryPolicy:
    """Deterministic exponential backoff.

    No jitter: a single-writer pipeline is not a thundering herd, and keeping
    the delays predictable keeps the tests honest about what they assert.
    """

    attempts: int = 4
    base_delay: float = 1.0
    factor: float = 2.0
    max_delay: float = 60.0

    def delay_for(self, attempt: int) -> float:
        """Seconds to wait after a failed ``attempt`` (zero-indexed)."""
        return min(self.base_delay * self.factor**attempt, self.max_delay)


@dataclass(frozen=True)
class Download:
    """What a completed download turned out to be."""

    path: Path
    size_bytes: int
    sha256: str


def _retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse a ``Retry-After`` header, ignoring the HTTP-date form.

    TED sends the delay-seconds form when it sends the header at all; a date
    we cannot parse is better ignored than guessed at, since the backoff
    schedule is a safe fallback.
    """
    raw = response.headers.get("Retry-After")
    if raw is None:
        return None
    try:
        seconds = float(raw.strip())
    except ValueError:
        return None
    return max(seconds, 0.0)


class TedClient:
    """A throttled, retrying HTTP client for TED's public endpoints.

    ``http``, ``sleep`` and ``monotonic`` are injectable so the tests can
    exercise the retry and throttle logic without a network or a real clock.
    """

    def __init__(
        self,
        *,
        http: httpx.Client | None = None,
        min_interval: float = 1.0,
        retry: RetryPolicy | None = None,
        timeout: float = 120.0,
        sleep: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._http = http if http is not None else httpx.Client(timeout=timeout)
        self._owns_http = http is None
        self._min_interval = max(min_interval, 0.0)
        self._retry = retry if retry is not None else RetryPolicy()
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request_at: float | None = None

    def __enter__(self) -> TedClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_http:
            self._http.close()

    # -- request plumbing ------------------------------------------------

    def _throttle(self) -> None:
        """Space request starts at least ``min_interval`` apart."""
        if self._last_request_at is not None:
            waited = self._monotonic() - self._last_request_at
            remaining = self._min_interval - waited
            if remaining > 0:
                self._sleep(remaining)
        self._last_request_at = self._monotonic()

    def _attempt_delay(self, attempt: int, response: httpx.Response | None) -> float:
        if response is not None:
            retry_after = _retry_after_seconds(response)
            if retry_after is not None:
                return retry_after
        return self._retry.delay_for(attempt)

    def _describe(self, response: httpx.Response) -> str:
        # Bodies are error JSON here, not notices; a prefix is enough to
        # identify the fault without dumping a page into the logs.
        return f"HTTP {response.status_code}: {response.text[:200]}"

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Perform a request, retrying transient failures.

        Raises ``FetchError`` on a non-2xx response that retrying did not
        clear, or on a transport error that outlasted the retry budget.
        """
        headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
        last_failure = "no attempt was made"

        for attempt in range(self._retry.attempts):
            self._throttle()
            response: httpx.Response | None = None
            try:
                response = self._http.request(method, url, headers=headers, **kwargs)
            except httpx.TransportError as exc:
                last_failure = f"{type(exc).__name__}: {exc}"
            else:
                if response.is_success:
                    return response
                last_failure = self._describe(response)
                if response.status_code not in RETRYABLE_STATUS:
                    raise FetchError(f"{method} {url} failed — {last_failure}")

            if attempt + 1 < self._retry.attempts:
                self._sleep(self._attempt_delay(attempt, response))

        raise FetchError(
            f"{method} {url} failed after {self._retry.attempts} attempts — "
            f"{last_failure}"
        )

    # -- the two channels ------------------------------------------------

    def search(
        self,
        *,
        query: str,
        fields: Sequence[str],
        limit: int = MAX_SEARCH_LIMIT,
        iteration_token: str | None = None,
    ) -> dict[str, Any]:
        """Run one expert query against the Search API.

        ``fields`` must be non-empty; the service rejects an empty list, and
        failing here costs a round trip less than learning it from a 400.
        """
        if not fields:
            raise ValueError("the Search API requires a non-empty 'fields' list")
        if not 1 <= limit <= MAX_SEARCH_LIMIT:
            raise ValueError(f"limit must be within 1..{MAX_SEARCH_LIMIT}, got {limit}")

        payload: dict[str, Any] = {
            "query": query,
            "fields": list(fields),
            "limit": limit,
        }
        if iteration_token is not None:
            payload["paginationMode"] = "ITERATION"
            payload["iterationNextToken"] = iteration_token

        response = self.request("POST", SEARCH_URL, json=payload)
        try:
            body = response.json()
        except ValueError as exc:
            raise FetchError(f"Search API returned a non-JSON body: {exc}") from exc
        if not isinstance(body, dict):
            raise FetchError(
                f"Search API returned {type(body).__name__}, not an object"
            )
        return body

    def download(self, url: str, destination: Path) -> Download:
        """Stream ``url`` to ``destination``, checksumming as it goes.

        The bytes land in a sibling ``.part`` file and are renamed into place
        only once the transfer completes, so an interrupted fetch can never
        leave a truncated archive that looks whole.
        """
        destination.parent.mkdir(parents=True, exist_ok=True)
        partial = destination.with_name(destination.name + ".part")
        headers = {"User-Agent": USER_AGENT}
        last_failure = "no attempt was made"

        for attempt in range(self._retry.attempts):
            self._throttle()
            response: httpx.Response | None = None
            try:
                digest = hashlib.sha256()
                size = 0
                with self._http.stream("GET", url, headers=headers) as response:
                    if not response.is_success:
                        response.read()
                        last_failure = self._describe(response)
                        if response.status_code not in RETRYABLE_STATUS:
                            raise FetchError(f"GET {url} failed — {last_failure}")
                    else:
                        with partial.open("wb") as handle:
                            for chunk in response.iter_bytes(_DOWNLOAD_CHUNK_BYTES):
                                handle.write(chunk)
                                digest.update(chunk)
                                size += len(chunk)
                        os.replace(partial, destination)
                        return Download(
                            path=destination,
                            size_bytes=size,
                            sha256=digest.hexdigest(),
                        )
            except httpx.TransportError as exc:
                last_failure = f"{type(exc).__name__}: {exc}"
            finally:
                partial.unlink(missing_ok=True)

            if attempt + 1 < self._retry.attempts:
                self._sleep(self._attempt_delay(attempt, response))

        raise FetchError(
            f"GET {url} failed after {self._retry.attempts} attempts — {last_failure}"
        )
