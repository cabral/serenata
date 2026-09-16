# SPDX-License-Identifier: AGPL-3.0-only
"""Fixtures for Crony's suite, and the guard that keeps it offline.

The same arrangement as the repository's other suite (`tests/conftest.py`), with
one word changed: the marker that buys an exception is `live` here rather than
`contract`. Two trees, two conftests, one promise.
"""

from __future__ import annotations

import socket
from pathlib import Path

import pytest
from fakes import FakeClock


@pytest.fixture(autouse=True)
def no_network(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail any test that tries to open a socket.

    Fetch is the only networked stage and its tests drive it through
    `httpx.MockTransport`. A test that reached data.gouv.fr would be slow, rude,
    and dependent on a government service being up to tell us whether our own
    retry loop works.

    The exception has to be asked for twice: a test marked `live` is also
    excluded from the default run by `-m 'not contract and not live'` in
    pyproject.toml, so reaching the network takes the marker and an explicit
    `-m live`.
    """
    if request.node.get_closest_marker("live"):
        return

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError(
            "this test tried to open a network connection; fetch is the only "
            "networked stage and its tests use httpx.MockTransport"
        )

    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def outside_repo(tmp_path: Path) -> Path:
    """A data directory that satisfies every rule in `config.py`.

    `tmp_path` is under the system temporary directory, which is outside the
    repository on every machine this runs on. That is the property being relied
    on, so it is named here rather than left as an accident of pytest.
    """
    directory = tmp_path / "crony-data"
    directory.mkdir()
    return directory
