# SPDX-License-Identifier: AGPL-3.0-only
"""The data guard, which is the last thing standing between a mistake and a
public repository full of elected officials' birth dates.

Constraint 1 in three layers: `config.py` refuses a data directory inside the
repository, this script refuses a data file inside the tree, and the pre-commit
hook refuses the commit. This tests the middle one, including the part that the
handover made necessary: it guards `crony-eu/` rather than the whole repository,
because the repository also holds Serenata Europa's synthetic TED fixtures,
which are legitimate under that project's rules and are XML.
"""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType

import pytest

REPO = Path(__file__).resolve().parent.parent.parent
SCRIPT = REPO / "crony-eu" / "scripts" / "check_no_data.py"


def load() -> ModuleType:
    """Import the script by path; it is a script, not part of the package."""
    spec = importlib.util.spec_from_file_location("check_no_data", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load()


class TestBlockedFormats:
    @pytest.mark.parametrize(
        "path",
        [
            "crony-eu/src/crony_eu/elus.parquet",
            "crony-eu/fixture.csv",
            "crony-eu/docs/notes.xlsx",
            "crony-eu/scratch.duckdb",
            "crony-eu/notebook.ipynb",
            "crony-eu/export.html",
            "crony-eu/dump.json",
        ],
    )
    def test_a_data_format_is_blocked(self, path: str) -> None:
        assert guard.check([path], REPO), f"{path} was allowed through"

    def test_a_template_suffix_is_not_a_data_format(self) -> None:
        # Only the last suffix is read, so network.html.j2 passes and
        # contracts.csv.gz is still caught by .gz.
        assert not guard.check(["crony-eu/src/crony_eu/network.html.j2"], REPO)
        assert guard.check(["crony-eu/contracts.csv.gz"], REPO)

    def test_ordinary_source_files_pass(self) -> None:
        assert not guard.check(
            [
                "crony-eu/src/crony_eu/cli.py",
                "crony-eu/docs/adr/0006-standard-library-only.md",
                "crony-eu/pyproject.toml",
                "crony-eu/.gitignore",
            ],
            REPO,
        )

    def test_the_allowlist_is_read(self) -> None:
        assert not guard.check(["crony-eu/.vscode/settings.json"], REPO)

    def test_the_allowlist_does_not_leak_across_the_tree(self) -> None:
        # An allowlist entry is a path inside the project, not a suffix pardon.
        assert guard.check(["crony-eu/docs/settings.json"], REPO)


class TestForbiddenDirectories:
    @pytest.mark.parametrize(
        "name", ["raw", "staged", "matched", "flags", "cases", "data"]
    )
    def test_a_data_directory_inside_the_project_is_blocked(self, name: str) -> None:
        problems = guard.check([f"crony-eu/{name}/anything.txt"], REPO)
        assert problems and "CRONY_DATA_DIR" in problems[0]

    def test_the_rule_reads_the_project_tree_not_the_repository_tree(self) -> None:
        # The bug this guards against: with repository-relative paths every
        # entry starts with `crony-eu`, so a naive first-component check would
        # never fire and the rule would be silently dead.
        assert guard.check(["crony-eu/flags/F1/run/hits.txt"], REPO)


class TestItGuardsItsOwnTreeOnly:
    def test_the_other_project_is_left_alone(self) -> None:
        # Serenata's six synthetic notices are XML, tracked, and legitimate
        # under its own rules. Blocking them would make `--all` permanently red
        # and the guard would be turned off rather than fixed.
        assert not guard.check(
            ["data/sample/20260817_157/00000001_2026.xml", "data/sample/README.md"],
            REPO,
        )

    def test_the_guarded_tree_is_derived_from_the_script(self) -> None:
        assert guard.guarded_tree(REPO) == "crony-eu"

    def test_within_matches_the_tree_and_its_contents(self) -> None:
        assert guard.within("crony-eu", "crony-eu")
        assert guard.within("crony-eu/src/x.py", "crony-eu")
        assert not guard.within("crony-eu-notes/x.py", "crony-eu")
        assert not guard.within("serenata/cli.py", "crony-eu")

    def test_an_empty_tree_guards_everything(self) -> None:
        # What happens once Crony is the repository.
        assert guard.within("anything/at/all.py", "")


class TestSizeLimit:
    def test_a_large_file_is_blocked(self, tmp_path: Path) -> None:
        big = tmp_path / "crony-eu" / "big.txt"
        big.parent.mkdir(parents=True)
        big.write_bytes(b"x" * (guard.MAX_BYTES + 1))

        problems = guard.check(["crony-eu/big.txt"], tmp_path)

        assert problems and "over the" in problems[0]

    def test_a_small_file_passes(self, tmp_path: Path) -> None:
        small = tmp_path / "crony-eu" / "small.txt"
        small.parent.mkdir(parents=True)
        small.write_bytes(b"x" * 10)

        assert not guard.check(["crony-eu/small.txt"], tmp_path)

    def test_the_vendored_asset_allowance_is_gone(self) -> None:
        # ADR-0006 removed vis-network. An allowance for a file nobody will
        # commit is a hole waiting for something else to be put in it.
        assert not any("vis-network" in entry for entry in guard.ALLOWED_LARGE)


class TestAgainstThisRepository:
    def test_the_tracked_tree_is_clean(self) -> None:
        # The check CI runs. It fails the moment someone commits a data file
        # here, which is the whole point of having it.
        assert guard.check(guard.tracked_files(REPO), REPO) == []

    def test_it_actually_looked_at_something(self) -> None:
        # A guard that listed no files would pass the test above forever.
        tracked = guard.tracked_files(REPO)
        assert len(tracked) > 10
        assert all(path.startswith("crony-eu/") for path in tracked)


class TestCommandLine:
    def test_a_clean_path_exits_zero(self) -> None:
        completed = subprocess.run(
            ["python3", str(SCRIPT), "crony-eu/src/crony_eu/cli.py"],
            cwd=REPO,
            capture_output=True,
        )
        assert completed.returncode == 0

    def test_a_blocked_path_exits_one_and_says_why(self) -> None:
        completed = subprocess.run(
            ["python3", str(SCRIPT), "crony-eu/elus.parquet"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 1
        assert "data format" in completed.stderr
        assert "constraint 1" in completed.stderr

    def test_all_exits_zero_on_this_repository(self) -> None:
        completed = subprocess.run(
            ["python3", str(SCRIPT), "--all"],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr
