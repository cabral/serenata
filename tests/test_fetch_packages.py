"""The fetch stage end to end, against a stand-in TED."""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime

import httpx
import pytest

from serenata.fetch.archive import ArchiveConflict, RawArchive
from serenata.fetch.ojs import OjsIssue
from serenata.fetch.packages import Outcome, fetch_range

from .support import PACKAGE_ID, make_package, search_body

ISSUE = OjsIssue(year=2026, number=157)
FIXED_NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def frozen_now() -> datetime:
    return FIXED_NOW


def run(client, archive, start, end=None, **kwargs):
    return fetch_range(
        client=client,
        archive=archive,
        start=start,
        end=end or start,
        now=frozen_now,
        **kwargs,
    )


class TestFetchingADay:
    def test_it_archives_the_package_and_records_its_provenance(
        self, client_factory, ted_handler, tmp_path
    ):
        archive = RawArchive(tmp_path)
        with client_factory(ted_handler) as client:
            results = run(client, archive, date(2026, 8, 17))

        assert [r.outcome for r in results] == [Outcome.FETCHED]

        package = archive.package_path(ISSUE)
        assert package.is_file()
        assert package.read_bytes() == make_package()

        manifest = archive.read_manifest(ISSUE)
        assert manifest.package_id == PACKAGE_ID
        assert manifest.ojs_number == "157/2026"
        assert manifest.publication_date == "2026-08-17"
        assert manifest.source_url.endswith(PACKAGE_ID)
        assert manifest.sha256 == hashlib.sha256(make_package()).hexdigest()
        assert manifest.size_bytes == len(make_package())
        assert manifest.member_prefix == "20260817_157"
        assert manifest.fetched_at == FIXED_NOW.isoformat()

    def test_the_archived_bytes_verify_against_the_manifest(
        self, client_factory, ted_handler, tmp_path
    ):
        archive = RawArchive(tmp_path)
        with client_factory(ted_handler) as client:
            run(client, archive, date(2026, 8, 17))

        assert archive.verify(ISSUE) is not None

    def test_a_clean_fetch_carries_no_note(self, client_factory, ted_handler, tmp_path):
        with client_factory(ted_handler) as client:
            results = run(client, RawArchive(tmp_path), date(2026, 8, 17))

        assert results[0].note is None


class TestIdempotence:
    def test_a_second_run_skips_what_is_already_archived(
        self, client_factory, ted_handler, tmp_path
    ):
        archive = RawArchive(tmp_path)
        downloads = 0

        def counting_handler(request: httpx.Request) -> httpx.Response:
            nonlocal downloads
            if "/packages/daily/" in request.url.path:
                downloads += 1
            return ted_handler(request)

        with client_factory(counting_handler) as client:
            run(client, archive, date(2026, 8, 17))
            second = run(client, archive, date(2026, 8, 17))

        assert downloads == 1, "the package is downloaded once, not once per run"
        assert [r.outcome for r in second] == [Outcome.SKIPPED]
        assert second[0].note == "already archived"

    def test_a_tampered_archive_stops_the_run_instead_of_being_overwritten(
        self, client_factory, ted_handler, tmp_path
    ):
        archive = RawArchive(tmp_path)
        with client_factory(ted_handler) as client:
            run(client, archive, date(2026, 8, 17))
            archive.package_path(ISSUE).write_bytes(b"tampered")

            with pytest.raises(ArchiveConflict, match="immutable"):
                run(client, archive, date(2026, 8, 17))


class TestQuietDays:
    def test_a_day_that_published_nothing_is_recorded_not_fetched(
        self, client_factory, tmp_path
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/notices/search"):
                return httpx.Response(200, json=search_body(count=0))
            raise AssertionError("no package should be requested for a quiet day")

        with client_factory(handler) as client:
            results = run(client, RawArchive(tmp_path), date(2026, 8, 15))

        assert [r.outcome for r in results] == [Outcome.NOT_PUBLISHED]
        assert results[0].issue is None


class TestRanges:
    def test_every_date_in_the_range_is_considered(
        self, client_factory, ted_handler, tmp_path
    ):
        with client_factory(ted_handler) as client:
            results = run(
                client, RawArchive(tmp_path), date(2026, 8, 17), date(2026, 8, 19)
            )

        assert [r.publication_date for r in results] == [
            date(2026, 8, 17),
            date(2026, 8, 18),
            date(2026, 8, 19),
        ]

    def test_results_are_reported_as_each_date_settles(
        self, client_factory, ted_handler, tmp_path
    ):
        seen: list[date] = []
        with client_factory(ted_handler) as client:
            results = run(
                client,
                RawArchive(tmp_path),
                date(2026, 8, 17),
                date(2026, 8, 19),
                on_result=lambda r: seen.append(r.publication_date),
            )

        assert seen == [r.publication_date for r in results]


class TestDryRun:
    def test_it_resolves_packages_without_downloading_them(
        self, client_factory, tmp_path
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/notices/search"):
                return httpx.Response(200, json=search_body())
            raise AssertionError("a dry run must not download")

        archive = RawArchive(tmp_path)
        with client_factory(handler) as client:
            results = run(client, archive, date(2026, 8, 17), dry_run=True)

        assert [r.outcome for r in results] == [Outcome.PLANNED]
        assert results[0].note.endswith(PACKAGE_ID)
        assert not archive.package_path(ISSUE).exists()


class TestIntegrityNotes:
    def test_a_package_for_the_wrong_day_is_flagged_but_still_archived(
        self, client_factory, tmp_path
    ):
        # TED serves a package whose internal directory is a different date.
        package = make_package(prefix="20260101_001")

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/notices/search"):
                return httpx.Response(200, json=search_body())
            return httpx.Response(200, content=package)

        archive = RawArchive(tmp_path)
        with client_factory(handler) as client:
            results = run(client, archive, date(2026, 8, 17))

        assert results[0].outcome == Outcome.FETCHED
        assert "expected 20260817_157" in results[0].note
        assert archive.package_path(ISSUE).is_file(), "the served bytes are still truth"
        assert archive.read_manifest(ISSUE).member_prefix == "20260101_001"


class TestDayResultDescription:
    def test_it_names_the_date_and_the_issue(
        self, client_factory, ted_handler, tmp_path
    ):
        with client_factory(ted_handler) as client:
            results = run(client, RawArchive(tmp_path), date(2026, 8, 17))

        line = results[0].describe()
        assert "2026-08-17" in line
        assert "OJ S 157/2026" in line

    def test_a_quiet_day_describes_itself_without_an_issue(
        self, client_factory, tmp_path
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=search_body(count=0))

        with client_factory(handler) as client:
            results = run(client, RawArchive(tmp_path), date(2026, 8, 15))

        assert results[0].describe() == "2026-08-15  not-published"
