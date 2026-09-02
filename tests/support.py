"""Builders for the fetch tests: a stand-in TED and a clock that never ticks.

Nothing here touches the network or a real clock. Package fixtures are built
in memory with obviously synthetic notice IDs, per ``tests/fixtures/README.md``.
"""

from __future__ import annotations

import io
import tarfile
from typing import Any

#: An impossible notice ID: real TED numbers are nowhere near this range.
SYNTHETIC_NOTICE = "00000001_2026.xml"

PACKAGE_PREFIX = "20260817_157"
OJS_NUMBER = "157/2026"
PACKAGE_ID = "202600157"


def make_package(
    prefix: str = PACKAGE_PREFIX, notices: tuple[str, ...] = (SYNTHETIC_NOTICE,)
) -> bytes:
    """A gzipped tar shaped like a TED daily package, with fake notices."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name in notices:
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<ContractNotice><SyntheticFixture>{name}</SyntheticFixture>"
                "</ContractNotice>"
            ).encode()
            info = tarfile.TarInfo(f"{prefix}/{name}")
            info.size = len(body)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def search_body(ojs_number: str | None = OJS_NUMBER, count: int = 1) -> dict[str, Any]:
    """A Search API response carrying ``count`` notices."""
    notice: dict[str, Any] = {} if ojs_number is None else {"ojs-number": ojs_number}
    return {
        "notices": [dict(notice) for _ in range(count)],
        "totalNoticeCount": count,
        "iterationNextToken": None,
        "timedOut": False,
    }


class FakeClock:
    """A monotonic clock that only moves when something sleeps on it."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds
