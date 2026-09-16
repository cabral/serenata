# SPDX-License-Identifier: AGPL-3.0-only
"""`crony doctor`, and the three-valued result that keeps it honest.

The interesting assertions here are about what doctor refuses to claim. Two of
its checks cannot run yet, and one of them may never run: no portable check
establishes that a path sits on an encrypted volume. A tick beside either would
be a report of a check that did not happen, which is how a page of green marks
stops meaning anything.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from crony_eu.cli import (
    build_parser,
    check_data_dir,
    check_encryption,
    check_export_template,
    check_layout,
    check_no_data_in_tree,
    doctor,
    main,
)
from crony_eu.config import DATA_DIR_VARIABLE


class TestParser:
    def test_it_takes_a_subcommand(self) -> None:
        assert build_parser().parse_args(["doctor"]).command == "doctor"

    def test_it_refuses_no_subcommand(self) -> None:
        # Bare `crony` printing usage and exiting non-zero beats it doing
        # something plausible.
        with pytest.raises(SystemExit):
            build_parser().parse_args([])

    def test_it_only_offers_what_exists(self) -> None:
        # A subcommand that parsed its flags and printed "not implemented"
        # would be listed by --help as though it worked.
        with pytest.raises(SystemExit):
            build_parser().parse_args(["case"])


class TestDoctor:
    def test_it_passes_on_a_good_data_directory(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))

        assert main(["doctor"]) == 0
        assert "failed" in capsys.readouterr().out

    def test_it_fails_when_the_data_directory_is_unset(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv(DATA_DIR_VARIABLE, raising=False)

        assert main(["doctor"]) == 1
        assert "FAIL" in capsys.readouterr().out

    def test_it_creates_the_layout(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))

        doctor(build_parser().parse_args(["doctor"]))
        capsys.readouterr()

        assert (outside_repo / "raw").is_dir()
        assert (outside_repo / "matched").is_dir()

    def test_it_is_safe_to_run_twice(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        assert main(["doctor"]) == 0
        assert main(["doctor"]) == 0
        capsys.readouterr()


class TestItDoesNotClaimWhatItCannotCheck:
    def test_encryption_is_reported_as_unchecked(self, outside_repo: Path) -> None:
        check = check_encryption(outside_repo)
        assert check.ok is None
        assert check.mark == "n/a"
        assert "not checked" in check.detail

    def test_the_template_check_says_there_is_no_template(self) -> None:
        check = check_export_template()
        assert check.ok is None
        assert "no template yet" in check.detail

    def test_a_skipped_check_is_not_counted_as_a_pass(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        main(["doctor"])

        summary = capsys.readouterr().out.strip().splitlines()[-1]
        assert "2 not checked" in summary

    def test_checks_that_depend_on_the_data_directory_skip_without_one(self) -> None:
        # Cascading a failure into three more failures buries the one that
        # matters. Each dependent check says it had nothing to work with.
        assert check_layout(None).ok is None
        assert check_encryption(None).ok is None


class TestTheDataGuardCheck:
    def test_a_blocked_tree_fails_doctor_and_says_what(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # The path that matters: doctor is how a maintainer finds out that a
        # data file reached the tree, so it has to report the reason rather
        # than a bare non-zero exit.
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        monkeypatch.setattr(
            "crony_eu.cli.subprocess.run",
            lambda *a, **k: subprocess.CompletedProcess(
                a[0], 1, "", "crony-eu/elus.parquet: '.parquet' is a data format\n"
            ),
        )

        assert main(["doctor"]) == 1
        assert "data format" in capsys.readouterr().out

    def test_a_missing_script_is_a_failure_not_a_pass(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        # A guard that cannot be found has not run. Reporting that as a tick
        # would be the worst outcome available.
        monkeypatch.setattr("crony_eu.cli.repository_root", lambda: tmp_path)

        check = check_no_data_in_tree()

        assert check.ok is False
        assert "missing" in check.detail


class TestDataDirCheck:
    def test_it_reports_the_resolved_path(
        self, outside_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        check, root = check_data_dir()

        assert check.ok is True
        assert root == outside_repo.resolve()

    def test_a_failure_carries_the_rule_it_broke(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, "relative/path")
        check, root = check_data_dir()

        assert check.ok is False
        assert root is None
        assert "relative" in check.detail
