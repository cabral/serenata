# SPDX-License-Identifier: AGPL-3.0-only
"""Stand-ins the tests drive the pipeline with.

A module rather than the conftest so that test files can import the types they
annotate with. It is named `fakes` rather than `support` on purpose: this
repository holds a second test suite with its own `tests/support.py`, and two
top-level modules with one name is a collision waiting for whichever suite
pytest imports second.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeClock:
    """A clock that moves only when told to.

    Backoff and rate limiting are both about durations, and a test that measured
    them against the real clock would either take half a minute or flake on a
    loaded machine. `slept` is the record the assertions actually read.
    """

    now: float = 0.0
    slept: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        """Move time forward without anyone having waited for it."""
        self.now += seconds
