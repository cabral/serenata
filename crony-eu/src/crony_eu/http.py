# SPDX-License-Identifier: AGPL-3.0-only
"""The only networked stage: polite, resumable, and vouching for what it wrote.

Three jobs, and they are separable so the tests can drive each without the
network. A **token bucket** keeps the request rate under what a source asks for.
A **retry policy** decides what is worth trying again and how long to wait. And
**`download`** streams bytes to disk, hashes them on the way past, renames
atomically, and appends an entry to the snapshot's `manifest.json` so that
every raw file can say where it came from and prove it has not changed.

**What counts as worth retrying.** HTTP 429 and 5xx, obviously, honouring
`Retry-After` when the server sends one. And **every transport error, DNS
failures included**, which is not defensive coding: while this project was being
specified, `recherche-entreprises.api.gouv.fr` intermittently failed to resolve
from the maintainer's machine while `data.gouv.fr` resolved fine throughout. A
client that retried only on status codes would have turned a name-resolution
blip into a failed run of several thousand requests.

**Why a clock and a random source are allowed here.** Constraint 4 forbids both
below fetch, and this is fetch. Nothing either of them touches reaches a staged
row: the sleeps affect timing only, and the single timestamp that does get
written is `retrieved_at`, which is a fact about the download and is recorded on
purpose. Both are injectable so the tests neither sleep nor flake.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import httpx

from crony_eu import __version__

#: Sent on every request. A source's operators can tell who is calling and where
#: to complain, which is the whole of the politeness contract that is in our
#: gift to keep.
USER_AGENT = (
    f"crony-eu/{__version__} (+https://github.com/cabral/serenata; "
    "public-interest research)"
)

#: What the slowest source tolerates, not what the fastest allows. The open
#: company API documents 7 requests per second; running at 5 leaves headroom for
#: the fact that our clock and theirs disagree.
DEFAULT_RATE_PER_SECOND = 5.0

#: Statuses worth trying again. 429 is the source asking us to slow down; 5xx is
#: the source having a bad moment. A 404 is an answer and is not retried.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

#: Bytes per chunk when streaming to disk. Large enough not to thrash, small
#: enough that a 250MB Parquet file does not arrive in memory.
CHUNK = 1 << 16


class Clock(Protocol):
    """Time, injectable, so a test for backoff does not take thirty seconds."""

    def monotonic(self) -> float: ...

    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    """The real one."""

    def monotonic(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


@dataclass
class RateLimiter:
    """A token bucket, refilling at `rate` tokens per second.

    Bursts up to `capacity` and then settles to the steady rate, which is what a
    source's published limit actually permits: fetching three SIRENs at once
    after an idle minute is fine, and sustaining forty a second is not.
    """

    rate: float = DEFAULT_RATE_PER_SECOND
    capacity: float = DEFAULT_RATE_PER_SECOND
    clock: Clock = field(default_factory=SystemClock)
    _tokens: float = field(init=False, default=0.0)
    _updated: float = field(init=False, default=0.0)

    def __post_init__(self) -> None:
        self._tokens = self.capacity
        self._updated = self.clock.monotonic()

    def take(self) -> float:
        """Wait until a token is available, take it, return how long that took."""
        now = self.clock.monotonic()
        self._tokens = min(
            self.capacity, self._tokens + (now - self._updated) * self.rate
        )
        self._updated = now

        waited = 0.0
        if self._tokens < 1.0:
            waited = (1.0 - self._tokens) / self.rate
            self.clock.sleep(waited)
            self._updated = self.clock.monotonic()
            self._tokens = 1.0

        self._tokens -= 1.0
        return waited


@dataclass(frozen=True)
class RetryPolicy:
    """Exponential backoff with jitter, capped, and bounded in attempts.

    `attempts` counts the first try, so 5 means one request and four retries.
    """

    attempts: int = 5
    base_seconds: float = 0.5
    cap_seconds: float = 30.0

    def backoff(self, attempt: int, jitter: float) -> float:
        """Seconds to wait before `attempt` (1-based), given jitter in [0, 1).

        Full jitter: a uniform draw from the whole interval rather than a fixed
        delay plus noise. Two clients that started together stay apart instead
        of colliding again on every retry.
        """
        ceiling = min(self.cap_seconds, self.base_seconds * 2.0 ** (attempt - 1))
        return ceiling * jitter


def retry_after(response: httpx.Response) -> float | None:
    """The server's own instruction, in seconds, when it sent one we understand.

    Only the numeric form. `Retry-After` may also carry an HTTP date, and
    parsing that means trusting the two clocks to agree; a source that sends one
    gets our own backoff instead, which is never longer than the cap.
    """
    raw = response.headers.get("Retry-After", "").strip()
    try:
        seconds = float(raw)
    except ValueError:
        return None
    return seconds if seconds >= 0 else None


class FetchError(Exception):
    """Every attempt failed, or the response said something final and bad."""


@dataclass
class SourceClient:
    """One client per source, carrying that source's rate limit and its name.

    The source name is not decoration: it is the directory raw bytes land in and
    the key a manifest entry is filed under, so it travels with the client
    rather than being passed to every call.
    """

    source: str
    client: httpx.Client
    limiter: RateLimiter = field(default_factory=RateLimiter)
    policy: RetryPolicy = field(default_factory=RetryPolicy)
    clock: Clock = field(default_factory=SystemClock)
    rng: random.Random = field(default_factory=random.Random)

    def _wait(self, attempt: int, response: httpx.Response | None) -> None:
        """Sleep before a retry: the server's instruction, or our own backoff."""
        told = retry_after(response) if response is not None else None
        if told is not None:
            delay = min(told, self.policy.cap_seconds)
        else:
            delay = self.policy.backoff(attempt, self.rng.random())
        self.clock.sleep(delay)

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """One request, retried while retrying could plausibly help.

        Raises `FetchError` naming the last thing that went wrong, because a
        caller handling a failed fetch wants to know whether the source said no
        or the network did.
        """
        last = "no attempt was made"
        for attempt in range(1, self.policy.attempts + 1):
            self.limiter.take()
            try:
                response = self.client.request(method, url, **kwargs)
            except httpx.TransportError as error:
                # Connection refused, timeouts, and name resolution, which is
                # the one that actually bit us.
                last = f"{type(error).__name__}: {error}"
                if attempt < self.policy.attempts:
                    self._wait(attempt, None)
                continue

            if response.status_code not in RETRY_STATUSES:
                return response

            last = f"HTTP {response.status_code}"
            if attempt < self.policy.attempts:
                self._wait(attempt, response)

        raise FetchError(
            f"{self.source}: {self.policy.attempts} attempts at {url} all "
            f"failed, last was {last}"
        )

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def json(self, url: str, **kwargs: Any) -> Any:
        response = self.get(url, **kwargs)
        if response.status_code >= 400:
            raise FetchError(f"{self.source}: HTTP {response.status_code} for {url}")
        return response.json()

    def stream(self, url: str, **kwargs: Any) -> Iterator[bytes]:
        """Body bytes, one chunk at a time, retried until the first byte.

        DECP is a 247MB file, so this needs the same retry loop as `request`
        rather than one attempt and a shrug.

        **Retried only before any bytes have been handed out.** Once a caller
        has written the first chunk to disk, starting the response again would
        append a second copy of the body to a file that already holds part of
        one, and the result would be a corrupt archive vouched for by a correct
        checksum of the wrong bytes. So a failure after that point is raised.
        `download` leaves a `.partial` and no manifest entry, which is the state
        a rerun recovers from.
        """
        last = "no attempt was made"
        for attempt in range(1, self.policy.attempts + 1):
            self.limiter.take()
            started = False
            try:
                with self.client.stream("GET", url, **kwargs) as response:
                    if response.status_code in RETRY_STATUSES:
                        last = f"HTTP {response.status_code}"
                        if attempt < self.policy.attempts:
                            self._wait(attempt, response)
                        continue
                    if response.status_code >= 400:
                        raise FetchError(
                            f"{self.source}: HTTP {response.status_code} for {url}"
                        )
                    for chunk in response.iter_bytes(CHUNK):
                        started = True
                        yield chunk
                    return
            except httpx.TransportError as error:
                if started:
                    raise FetchError(
                        f"{self.source}: {url} failed after the body had begun "
                        f"({type(error).__name__}: {error}). Rerunning refetches "
                        "it; resuming would append to a half-written file."
                    ) from error
                last = f"{type(error).__name__}: {error}"
                if attempt < self.policy.attempts:
                    self._wait(attempt, None)

        raise FetchError(
            f"{self.source}: {self.policy.attempts} attempts at {url} all "
            f"failed, last was {last}"
        )


def build_client(source: str, **kwargs: Any) -> SourceClient:
    """A client for one source, with the project's User-Agent and timeouts."""
    return SourceClient(
        source=source,
        client=httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=httpx.Timeout(30.0, connect=10.0),
            follow_redirects=True,
            **kwargs,
        ),
    )


def now() -> str:
    """The retrieval timestamp, UTC and to the second.

    The one clock reading that reaches a file. Everything downstream of fetch
    reads this value rather than asking the time again, which is what lets a
    rerun over the same snapshot produce the same bytes.
    """
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def read_manifest(path: Path) -> list[dict[str, Any]]:
    """Every entry recorded for a snapshot, or an empty list for a new one."""
    if not path.exists():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    entries: list[dict[str, Any]] = loaded["files"]
    return entries


def append_manifest(path: Path, entry: dict[str, Any]) -> None:
    """Add one entry, written whole and renamed into place.

    A download interrupted midway must not leave a manifest that is neither the
    old one nor the new one, because the manifest is what the next run reads to
    decide what it can skip.
    """
    entries = read_manifest(path)
    entries.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps({"files": entries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def download(
    client: SourceClient,
    url: str,
    destination: Path,
    manifest: Path,
    licence: str,
) -> dict[str, Any]:
    """Fetch one file into a raw snapshot, and record what arrived.

    Streams to a `.partial` beside the destination, hashes as it goes, and only
    then renames. An interrupted download leaves a partial file and no manifest
    entry, which is the state a rerun can recover from; a truncated file under
    the real name with an entry vouching for it is the state it could not.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")

    digest = hashlib.sha256()
    size = 0
    with partial.open("wb") as handle:
        for chunk in client.stream(url, follow_redirects=True):
            digest.update(chunk)
            size += len(chunk)
            handle.write(chunk)
    os.replace(partial, destination)

    entry = {
        "source": client.source,
        "url": url,
        "path": destination.name,
        "sha256": digest.hexdigest(),
        "bytes": size,
        "retrieved_at": now(),
        "licence": licence,
        "status": 200,
    }
    append_manifest(manifest, entry)
    return entry
