"""Fixtures wiring the fetch tests to a stand-in TED instead of the network."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest

from serenata.fetch.client import RetryPolicy, TedClient

from .support import FakeClock, make_package, search_body


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client_factory(clock: FakeClock) -> Callable[..., TedClient]:
    """Build a :class:`TedClient` wired to a handler instead of the network."""

    def build(
        handler: Callable[[httpx.Request], httpx.Response],
        *,
        min_interval: float = 0.0,
        retry: RetryPolicy | None = None,
    ) -> TedClient:
        return TedClient(
            http=httpx.Client(transport=httpx.MockTransport(handler)),
            min_interval=min_interval,
            retry=retry
            if retry is not None
            else RetryPolicy(attempts=3, base_delay=1.0),
            sleep=clock.sleep,
            monotonic=clock.monotonic,
        )

    return build


@pytest.fixture
def ted_handler() -> Callable[[httpx.Request], httpx.Response]:
    """A stand-in TED: resolves any date to one OJ S issue and serves it."""
    package = make_package()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/notices/search"):
            return httpx.Response(200, json=search_body())
        if "/packages/daily/" in request.url.path:
            return httpx.Response(200, content=package)
        return httpx.Response(404, text="unexpected URL")

    return handler
