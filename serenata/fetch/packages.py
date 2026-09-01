"""Fetch a date range of daily packages into the raw archive.

The stage's whole job, in order: resolve each date to its OJ S issue, skip
what the archive already holds and can vouch for, download the rest, and
record a manifest for each. Nothing here parses a notice — fetch stays
format-blind so that it does not need changing when eForms does.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from serenata.fetch.archive import (
    PackageManifest,
    RawArchive,
    expected_member_prefix,
    package_member_prefix,
)
from serenata.fetch.client import TedClient
from serenata.fetch.ojs import OjsIssue, dates_in_range, issue_for_date


class Outcome:
    """What happened to one publication date."""

    FETCHED = "fetched"
    SKIPPED = "skipped"
    NOT_PUBLISHED = "not-published"
    PLANNED = "planned"


@dataclass(frozen=True)
class DayResult:
    """The result of considering one date."""

    publication_date: date
    outcome: str
    issue: OjsIssue | None = None
    manifest: PackageManifest | None = None
    note: str | None = None

    def describe(self) -> str:
        day = self.publication_date.isoformat()
        if self.issue is None:
            return f"{day}  {self.outcome}"
        line = f"{day}  {self.outcome}  OJ S {self.issue}"
        if self.note:
            line = f"{line}  ({self.note})"
        return line


def _utcnow() -> datetime:
    return datetime.now(UTC)


def fetch_range(
    *,
    client: TedClient,
    archive: RawArchive,
    start: date,
    end: date,
    dry_run: bool = False,
    now: Callable[[], datetime] = _utcnow,
    on_result: Callable[[DayResult], None] | None = None,
) -> list[DayResult]:
    """Fetch every daily package published between ``start`` and ``end``.

    Results are reported through ``on_result`` as each date is settled, so a
    long backfill shows progress rather than going quiet for an hour, and are
    also returned together for callers that want the summary.
    """
    results: list[DayResult] = []
    for result in iter_fetch_range(
        client=client,
        archive=archive,
        start=start,
        end=end,
        dry_run=dry_run,
        now=now,
    ):
        if on_result is not None:
            on_result(result)
        results.append(result)
    return results


def iter_fetch_range(
    *,
    client: TedClient,
    archive: RawArchive,
    start: date,
    end: date,
    dry_run: bool = False,
    now: Callable[[], datetime] = _utcnow,
) -> Iterator[DayResult]:
    """Stream :class:`DayResult` values as each date is settled."""
    for day in dates_in_range(start, end):
        issue = issue_for_date(client, day)
        if issue is None:
            yield DayResult(publication_date=day, outcome=Outcome.NOT_PUBLISHED)
            continue

        if archive.holds(issue):
            # verify() raises on a checksum mismatch: an archived package that
            # no longer matches its manifest is a fact for a human, not
            # something to silently refetch over.
            manifest = archive.verify(issue)
            yield DayResult(
                publication_date=day,
                outcome=Outcome.SKIPPED,
                issue=issue,
                manifest=manifest,
                note="already archived",
            )
            continue

        if dry_run:
            yield DayResult(
                publication_date=day,
                outcome=Outcome.PLANNED,
                issue=issue,
                note=issue.package_url,
            )
            continue

        yield _fetch_one(client=client, archive=archive, day=day, issue=issue, now=now)


def _fetch_one(
    *,
    client: TedClient,
    archive: RawArchive,
    day: date,
    issue: OjsIssue,
    now: Callable[[], datetime],
) -> DayResult:
    destination = archive.package_path(issue)
    download = client.download(issue.package_url, destination)

    prefix = package_member_prefix(destination)
    note = _prefix_note(prefix, issue, day)

    manifest = PackageManifest(
        package_id=issue.package_id,
        ojs_number=str(issue),
        publication_date=day.isoformat(),
        source_url=issue.package_url,
        sha256=download.sha256,
        size_bytes=download.size_bytes,
        member_prefix=prefix,
        fetched_at=now().isoformat(),
    )
    archive.write_manifest(issue, manifest)

    return DayResult(
        publication_date=day,
        outcome=Outcome.FETCHED,
        issue=issue,
        manifest=manifest,
        note=note,
    )


def _prefix_note(prefix: str | None, issue: OjsIssue, day: date) -> str | None:
    """Flag a package whose internal directory is not the day we asked for.

    Recorded rather than raised: the bytes TED served are still ground truth,
    and the manifest keeps both the expectation and what arrived, so a
    mismatch can be investigated instead of discarded.
    """
    if prefix is None:
        return "package listing unreadable"
    expected = expected_member_prefix(issue, day)
    if prefix != expected:
        return f"contains {prefix}, expected {expected}"
    return None


def default_archive_root() -> Path:
    """Where the raw archive lives unless the caller says otherwise."""
    return Path("data") / "raw"
