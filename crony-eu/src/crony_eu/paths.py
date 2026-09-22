# SPDX-License-Identifier: AGPL-3.0-only
"""The layout under `$CRONY_DATA_DIR`, as functions rather than as strings.

CLAUDE.md draws this tree and this module is the executable copy of it, so a
stage that wants the staged directory for a source and a snapshot asks for it
instead of joining path fragments and getting one of them subtly wrong.

    raw/<source>/<snapshot>/       bytes exactly as downloaded, plus manifest.json
    staged/<source>/<snapshot>/    typed Parquet
    staged/_reports/               data-quality reports, aggregates only
    matched/judgments.parquet      append-only; latest revision per judgment_id wins
    matched/candidates/dep-<code>.parquet   rebuilt from staged data; not a log
    flags/<flag>/<run>/            flag output
    cases/<case>/                  a packet: network.html, the two tables, evidence
    logs/

Two properties the rest of the pipeline relies on. `raw/` is never modified
after writing, because it is the ground truth a result is checked against. And a
snapshot is a date the maintainer passes in, never `date.today()`: a stage that
read a clock would write a different path on a different day from the same
inputs, and constraint 4 says a run is reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: The file recording url, sha256, bytes, retrieved_at, licence and HTTP status
#: for everything in a raw snapshot directory.
MANIFEST = "manifest.json"

#: Data-quality reports live beside the staged data rather than in it, under a
#: name that cannot collide with a source: no source is called `_reports`.
REPORTS = "_reports"


@dataclass(frozen=True)
class Layout:
    """Every directory the pipeline writes, rooted at one data directory."""

    root: Path

    def raw(self, source: str, snapshot: str) -> Path:
        return self.root / "raw" / source / snapshot

    def manifest(self, source: str, snapshot: str) -> Path:
        return self.raw(source, snapshot) / MANIFEST

    def staged(self, source: str, snapshot: str) -> Path:
        return self.root / "staged" / source / snapshot

    def reports(self) -> Path:
        return self.root / "staged" / REPORTS

    def judgments(self) -> Path:
        return self.root / "matched" / "judgments.parquet"

    def candidates(self, scope: str) -> Path:
        """Candidate matches for one slice, rebuilt from staged data on demand.

        Not append-only, unlike the judgments: a candidate is a computed fact
        about two staged tables and a rule, and rebuilding it from the same
        inputs gives the same bytes. The decision about it is what must never
        be overwritten, and that lives in `judgments()`.
        """
        return self.root / "matched" / "candidates" / f"dep-{scope}.parquet"

    def flags(self, flag: str, run: str) -> Path:
        return self.root / "flags" / flag / run

    def case(self, case: str) -> Path:
        return self.root / "cases" / case

    def logs(self) -> Path:
        return self.root / "logs"

    def snapshots(self, source: str) -> list[str]:
        """Every raw snapshot of a source, oldest first. Empty when none."""
        directory = self.root / "raw" / source
        if not directory.is_dir():
            return []
        return sorted(child.name for child in directory.iterdir() if child.is_dir())

    def latest_snapshot(self, source: str) -> str | None:
        """The most recent snapshot, or `None`.

        How `crony stage` finds its input without reading a clock. Snapshot
        names are ISO dates, so lexical order is chronological order, and a
        transform that asked `date.today()` would stage nothing the morning
        after a fetch.
        """
        found = self.snapshots(source)
        return found[-1] if found else None

    def latest_staged(self, source: str, table: str) -> str | None:
        """The newest snapshot of `source` that has `<table>.parquet` staged.

        Not the newest *fetched* snapshot: a fetch that has not been staged yet
        must not make a later stage read nothing. Every consumer of staged data
        asks this rather than keeping its own loop.
        """
        for snapshot in reversed(self.snapshots(source)):
            if (self.staged(source, snapshot) / f"{table}.parquet").is_file():
                return snapshot
        return None

    def create(self) -> None:
        """Make the fixed directories. Safe to run twice, which is the point.

        The per-source and per-run directories are made by whatever writes into
        them; these are the ones that exist from the start so that `crony
        doctor` can report on a data directory nothing has run against yet.
        """
        for directory in (
            self.root / "raw",
            self.root / "staged",
            self.reports(),
            self.root / "matched",
            self.root / "flags",
            self.root / "cases",
            self.logs(),
        ):
            directory.mkdir(parents=True, exist_ok=True)
