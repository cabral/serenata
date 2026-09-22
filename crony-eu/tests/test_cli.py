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


class TestFetchAndStage:
    """The two subcommands session 1 added, driven without a socket."""

    def scripted(self, monkeypatch: pytest.MonkeyPatch) -> list[str]:
        """Replace the real client with one answering a stand-in data.gouv.fr."""
        import httpx
        from crony_eu.http import RateLimiter, SourceClient
        from crony_eu.sources import fr_rne_elus

        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "/api/1/datasets/" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "resources": [
                            {
                                "title": f.title,
                                "url": f"https://files.invalid/{f.title}",
                            }
                            for f in fr_rne_elus.FILES
                        ]
                    },
                )
            return httpx.Response(200, content=b"Code du departement\n")

        monkeypatch.setattr(
            "crony_eu.cli.build_client",
            lambda source: SourceClient(
                source=source,
                client=httpx.Client(transport=httpx.MockTransport(handler)),
                limiter=RateLimiter(rate=1000.0, capacity=1000.0),
            ),
        )
        return calls

    def test_fetch_writes_a_dated_snapshot(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        self.scripted(monkeypatch)

        assert main(["fetch", "fr-rne-elus", "--snapshot", "2026-09-16"]) == 0

        assert (
            outside_repo / "raw" / "fr-rne-elus" / "2026-09-16" / "manifest.json"
        ).is_file()
        assert "2026-09-16" in capsys.readouterr().out

    def test_fetch_defaults_to_today(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Fetch is allowed a clock; constraint 4 forbids one below it.
        from datetime import date

        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        self.scripted(monkeypatch)

        main(["fetch", "fr-rne-elus"])
        capsys.readouterr()

        assert (
            outside_repo / "raw" / "fr-rne-elus" / date.today().isoformat()
        ).is_dir()

    def test_fetching_twice_downloads_nothing_the_second_time(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        self.scripted(monkeypatch)
        main(["fetch", "fr-rne-elus", "--snapshot", "2026-09-16"])
        capsys.readouterr()

        assert main(["fetch", "fr-rne-elus", "--snapshot", "2026-09-16"]) == 0
        assert "already complete" in capsys.readouterr().out

    def test_stage_without_a_fetch_says_so(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))

        assert main(["stage", "fr-rne-elus"]) == 1
        assert "nothing fetched yet" in capsys.readouterr().err

    def test_stage_defaults_to_the_latest_snapshot(
        self,
        outside_repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Not to today's date. Staging the morning after a fetch has to work.
        from fakes import Elu, write_rne_snapshot

        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        write_rne_snapshot(outside_repo, "2026-09-16", cm_current=[Elu()])

        assert main(["stage", "fr-rne-elus"]) == 0

        output = capsys.readouterr().out
        assert "2026-09-16" in output
        assert "elus" in output

    def test_an_unknown_source_is_refused_by_the_parser(self) -> None:
        # Constraint 6: a source with no approved section cannot be fetched by
        # typing its name.
        with pytest.raises(SystemExit):
            build_parser().parse_args(["fetch", "fr-made-up"])


class TestSurvey:
    """`crony survey departements`, which ends in a person making a choice.

    The command's whole output is counts, so what is checked here is that it
    reaches them from staged data and says clearly when it cannot, rather than
    printing an empty table that reads like a département with nothing in it.
    """

    def stage_everything(self, root: Path) -> None:
        from crony_eu.paths import Layout
        from crony_eu.sources import fr_decp, fr_insee_pop, fr_rne_elus
        from fakes import (
            Elu,
            decp_row,
            write_decp,
            write_populations,
            write_rne_snapshot,
        )

        layout = Layout(root)
        layout.create()

        write_decp(
            layout.raw(fr_decp.SOURCE, "2026-09-19") / "decp.parquet",
            [decp_row(uid="A", acheteur_commune_code="93001")],
        )
        fr_decp.stage(layout, "2026-09-19")

        write_populations(
            layout.raw(fr_insee_pop.SOURCE, "2026-09-19") / fr_insee_pop.STORED,
            [("93001", "COM", "PMUN", 1200)],
        )
        fr_insee_pop.stage(layout, "2026-09-19")

        write_rne_snapshot(root, "2026-09-16", cm_current=[Elu(commune_code="93001")])
        fr_rne_elus.stage(layout, "2026-09-16")

    def test_it_prints_a_row_per_departement_and_writes_the_table(
        self,
        monkeypatch: pytest.MonkeyPatch,
        outside_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        self.stage_everything(outside_repo)

        assert main(["survey", "departements"]) == 0

        output = capsys.readouterr().out
        assert "pairs by population band" in output
        assert "93" in output
        assert (
            outside_repo / "staged" / "_reports" / "survey-departements.json"
        ).is_file()

    def test_it_says_which_command_to_run_when_nothing_is_staged(
        self,
        monkeypatch: pytest.MonkeyPatch,
        outside_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))

        assert main(["survey", "departements"]) == 1
        assert "crony fetch fr-decp" in capsys.readouterr().err

    def test_an_unknown_subject_is_refused_by_the_parser(self) -> None:
        with pytest.raises(SystemExit):
            build_parser().parse_args(["survey", "communes"])


class TestScopedFetch:
    """`--scope` is required by some sources and refused by others.

    The published-file sources download the same bytes whoever asks. The company
    API asks one question per supplier and per buyer in a département, so a run
    without a scope would quietly mean all of France at five requests a second.
    Both mistakes fail loudly rather than doing something defensible-looking.
    """

    def test_a_scoped_source_without_a_scope_is_refused(
        self,
        monkeypatch: pytest.MonkeyPatch,
        outside_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        assert main(["fetch", "fr-entreprises-api"]) == 1
        assert "all of France" in capsys.readouterr().err

    def test_a_scope_on_an_unscoped_source_is_refused(
        self,
        monkeypatch: pytest.MonkeyPatch,
        outside_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        assert main(["fetch", "fr-decp", "--scope", "74"]) == 1
        assert "would not change what it fetches" in capsys.readouterr().err

    def test_a_scoped_fetch_passes_the_scope_through(
        self,
        monkeypatch: pytest.MonkeyPatch,
        outside_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setenv(DATA_DIR_VARIABLE, str(outside_repo))
        from crony_eu.sources import fr_entreprises_api as api

        seen: list[str] = []

        def fake_fetch(
            client: object, layout: object, snapshot: str, scope: str
        ) -> list[dict[str, object]]:
            seen.append(scope)
            return []

        monkeypatch.setattr(api, "fetch", fake_fetch)
        assert main(["fetch", "fr-entreprises-api", "--scope", "74"]) == 0
        assert seen == ["74"]
        assert "already complete" in capsys.readouterr().out
