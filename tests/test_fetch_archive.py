"""The archive's promise: fetched bytes are ground truth and never rewritten."""

from __future__ import annotations

import hashlib
import json
from datetime import date

import pytest

from serenata.fetch.archive import (
    ArchiveConflict,
    PackageManifest,
    RawArchive,
    expected_member_prefix,
    package_member_prefix,
    sha256_of,
)
from serenata.fetch.ojs import OjsIssue

from .support import PACKAGE_PREFIX, make_package

ISSUE = OjsIssue(year=2026, number=157)


def manifest_for(payload: bytes, **overrides) -> PackageManifest:
    fields = {
        "package_id": ISSUE.package_id,
        "ojs_number": str(ISSUE),
        "publication_date": "2026-08-17",
        "source_url": ISSUE.package_url,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "member_prefix": PACKAGE_PREFIX,
        "fetched_at": "2026-09-01T00:00:00+00:00",
    }
    return PackageManifest(**{**fields, **overrides})


class TestLayout:
    def test_packages_are_filed_by_year_under_the_archive_root(self, tmp_path):
        archive = RawArchive(tmp_path)
        assert archive.package_path(ISSUE) == (
            tmp_path / "ted" / "daily" / "2026" / "202600157.tar.gz"
        )

    def test_the_manifest_sits_beside_its_package(self, tmp_path):
        archive = RawArchive(tmp_path)
        package = archive.package_path(ISSUE)
        manifest = archive.manifest_path(ISSUE)
        assert manifest.parent == package.parent
        assert manifest.name == "202600157.manifest.json"


class TestManifest:
    def test_it_round_trips_through_the_archive(self, tmp_path):
        archive = RawArchive(tmp_path)
        payload = make_package()
        original = manifest_for(payload)

        archive.write_manifest(ISSUE, original)

        assert archive.read_manifest(ISSUE) == original

    def test_it_is_written_as_sorted_diffable_json(self, tmp_path):
        archive = RawArchive(tmp_path)
        path = archive.write_manifest(ISSUE, manifest_for(make_package()))
        text = path.read_text(encoding="utf-8")

        assert text.endswith("\n")
        keys = list(json.loads(text))
        assert keys == sorted(keys)

    def test_reading_an_absent_manifest_gives_nothing(self, tmp_path):
        assert RawArchive(tmp_path).read_manifest(ISSUE) is None

    def test_an_unreadable_manifest_is_a_conflict(self, tmp_path):
        archive = RawArchive(tmp_path)
        path = archive.manifest_path(ISSUE)
        path.parent.mkdir(parents=True)
        path.write_text("{not json", encoding="utf-8")

        with pytest.raises(ArchiveConflict, match="unreadable"):
            archive.read_manifest(ISSUE)

    def test_it_records_the_manifest_version(self, tmp_path):
        assert manifest_for(make_package()).manifest_version == 1


class TestChecksums:
    def test_it_hashes_a_file_the_same_way_hashlib_does(self, tmp_path):
        payload = make_package()
        path = tmp_path / "package.tar.gz"
        path.write_bytes(payload)

        assert sha256_of(path) == hashlib.sha256(payload).hexdigest()

    def test_it_handles_a_file_larger_than_one_read_chunk(self, tmp_path):
        payload = b"x" * ((1 << 20) + 17)
        path = tmp_path / "big.bin"
        path.write_bytes(payload)

        assert sha256_of(path) == hashlib.sha256(payload).hexdigest()


class TestMemberPrefix:
    def test_it_reads_the_directory_the_notices_sit_under(self, tmp_path):
        path = tmp_path / "package.tar.gz"
        path.write_bytes(make_package(prefix="20260817_157"))

        assert package_member_prefix(path) == "20260817_157"

    def test_a_file_that_is_not_a_tarball_reads_as_unknown(self, tmp_path):
        path = tmp_path / "package.tar.gz"
        path.write_bytes(b"this is not gzip")

        assert package_member_prefix(path) is None

    def test_an_empty_archive_reads_as_unknown(self, tmp_path):
        path = tmp_path / "package.tar.gz"
        path.write_bytes(make_package(notices=()))

        assert package_member_prefix(path) is None

    def test_the_expected_prefix_pads_the_issue_number_to_three_digits(self):
        assert (
            expected_member_prefix(OjsIssue(year=2026, number=7), date(2026, 1, 12))
            == "20260112_007"
        )


class TestVerify:
    def test_matching_bytes_verify_and_return_the_manifest(self, tmp_path):
        archive = RawArchive(tmp_path)
        payload = make_package()
        archive.package_path(ISSUE).parent.mkdir(parents=True)
        archive.package_path(ISSUE).write_bytes(payload)
        archive.write_manifest(ISSUE, manifest_for(payload))

        assert archive.verify(ISSUE).sha256 == hashlib.sha256(payload).hexdigest()

    def test_altered_bytes_raise_rather_than_being_refetched_over(self, tmp_path):
        archive = RawArchive(tmp_path)
        payload = make_package()
        archive.package_path(ISSUE).parent.mkdir(parents=True)
        archive.write_manifest(ISSUE, manifest_for(payload))
        archive.package_path(ISSUE).write_bytes(b"tampered")

        with pytest.raises(ArchiveConflict, match="needs a human"):
            archive.verify(ISSUE)

    def test_a_manifest_without_its_package_is_a_conflict(self, tmp_path):
        archive = RawArchive(tmp_path)
        archive.write_manifest(ISSUE, manifest_for(make_package()))

        with pytest.raises(ArchiveConflict, match="no package beside it"):
            archive.verify(ISSUE)

    def test_verifying_nothing_at_all_is_a_conflict(self, tmp_path):
        with pytest.raises(ArchiveConflict, match="no manifest"):
            RawArchive(tmp_path).verify(ISSUE)


class TestHolds:
    def test_it_needs_both_the_package_and_the_manifest(self, tmp_path):
        archive = RawArchive(tmp_path)
        assert archive.holds(ISSUE) is False

        archive.package_path(ISSUE).parent.mkdir(parents=True)
        archive.package_path(ISSUE).write_bytes(make_package())
        assert archive.holds(ISSUE) is False, "bytes without provenance do not count"

        archive.write_manifest(ISSUE, manifest_for(make_package()))
        assert archive.holds(ISSUE) is True
