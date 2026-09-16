# SPDX-License-Identifier: AGPL-3.0-only
"""The four rules on the data directory, and the symlink that gets round three.

Constraint 1 is the one this project would be embarrassing to break, because the
repository is public and the data is about named people. `config.py` is the
cheap half of enforcing it: catching the configuration rather than the file that
configuration let in.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from crony_eu.config import (
    DATA_DIR_VARIABLE,
    ConfigError,
    data_dir,
    is_inside,
    repository_root,
)


def environment(value: str | None) -> dict[str, str]:
    return {} if value is None else {DATA_DIR_VARIABLE: value}


class TestTheFourRules:
    def test_it_is_refused_when_unset(self) -> None:
        with pytest.raises(ConfigError, match="is not set"):
            data_dir(environ={})

    def test_it_is_refused_when_empty_or_whitespace(self) -> None:
        # An exported-but-empty variable is the shape a half-finished shell
        # profile leaves behind, and it is not the same mistake as forgetting.
        with pytest.raises(ConfigError, match="is not set"):
            data_dir(environ=environment("   "))

    def test_it_is_refused_when_relative(self, tmp_path: Path) -> None:
        with pytest.raises(ConfigError, match="relative"):
            data_dir(environ=environment("crony-data"), root=tmp_path)

    def test_it_is_refused_when_inside_the_repository(self, tmp_path: Path) -> None:
        repository = tmp_path / "repo"
        inside = repository / "data"
        inside.mkdir(parents=True)
        with pytest.raises(ConfigError, match="inside the repository"):
            data_dir(environ=environment(str(inside)), root=repository)

    def test_the_repository_itself_is_refused(self, tmp_path: Path) -> None:
        repository = tmp_path / "repo"
        repository.mkdir()
        with pytest.raises(ConfigError, match="inside the repository"):
            data_dir(environ=environment(str(repository)), root=repository)

    def test_a_symlink_pointing_into_the_repository_is_refused(
        self, tmp_path: Path
    ) -> None:
        # The rule that needs a test most. An absolute path outside the
        # repository, which writes into it. Someone sets this up when a disk
        # fills and nobody notices until the data is committed.
        repository = tmp_path / "repo"
        (repository / "data").mkdir(parents=True)
        link = tmp_path / "elsewhere"
        link.symlink_to(repository / "data")

        with pytest.raises(ConfigError, match="inside the repository"):
            data_dir(environ=environment(str(link)), root=repository)

    def test_a_good_path_is_accepted_and_resolved(self, tmp_path: Path) -> None:
        repository = tmp_path / "repo"
        repository.mkdir()
        wanted = tmp_path / "crony-data"

        assert (
            data_dir(environ=environment(str(wanted)), root=repository)
            == wanted.resolve()
        )

    def test_it_creates_the_directory(self, tmp_path: Path) -> None:
        repository = tmp_path / "repo"
        repository.mkdir()
        wanted = tmp_path / "deep" / "crony-data"
        assert not wanted.exists()

        data_dir(environ=environment(str(wanted)), root=repository)

        assert wanted.is_dir()

    def test_it_is_idempotent(self, tmp_path: Path) -> None:
        # Every state change in this project has to be safe to run twice.
        repository = tmp_path / "repo"
        repository.mkdir()
        wanted = tmp_path / "crony-data"

        first = data_dir(environ=environment(str(wanted)), root=repository)
        second = data_dir(environ=environment(str(wanted)), root=repository)

        assert first == second

    def test_it_is_refused_when_it_cannot_be_created(self, tmp_path: Path) -> None:
        # A path whose parent is a file, which is what a typo in a shell profile
        # usually produces. The message has to say "could not be created" rather
        # than raising a bare OSError from four frames down.
        repository = tmp_path / "repo"
        repository.mkdir()
        blocker = tmp_path / "not-a-directory"
        blocker.write_text("", encoding="utf-8")

        with pytest.raises(ConfigError, match="could not be created"):
            data_dir(environ=environment(str(blocker / "data")), root=repository)

    def test_it_is_refused_when_not_writable(self, tmp_path: Path) -> None:
        repository = tmp_path / "repo"
        repository.mkdir()
        locked = tmp_path / "locked"
        locked.mkdir(mode=0o500)
        try:
            with pytest.raises(ConfigError, match="not writable"):
                data_dir(environ=environment(str(locked)), root=repository)
        finally:
            locked.chmod(0o700)

    def test_every_message_names_the_variable(self, tmp_path: Path) -> None:
        # "Invalid configuration" sends a reader to the source. Naming the
        # variable and the rule it broke does not.
        repository = tmp_path / "repo"
        repository.mkdir()
        for value in (None, "crony-data", str(repository)):
            with pytest.raises(ConfigError) as raised:
                data_dir(environ=environment(value), root=repository)
            assert DATA_DIR_VARIABLE in str(raised.value)


class TestIsInside:
    def test_a_directory_is_inside_itself(self, tmp_path: Path) -> None:
        assert is_inside(tmp_path, tmp_path)

    def test_a_child_is_inside(self, tmp_path: Path) -> None:
        assert is_inside(tmp_path / "a" / "b", tmp_path)

    def test_a_sibling_is_not(self, tmp_path: Path) -> None:
        assert not is_inside(tmp_path / "a", tmp_path / "b")

    def test_a_prefix_match_is_not_enough(self, tmp_path: Path) -> None:
        # `/x/repo-backup` starts with `/x/repo` as a string and is not inside
        # it. Comparing paths rather than strings is what makes that true.
        assert not is_inside(tmp_path / "repo-backup", tmp_path / "repo")


class TestRepositoryRoot:
    def test_it_finds_this_repository(self) -> None:
        root = repository_root()
        assert (root / "crony-eu" / "CLAUDE.md").is_file()
        assert (root / "scope.md").is_file()

    def test_it_gives_an_answer_with_no_repository_at_all(self, tmp_path: Path) -> None:
        # An installed package with no source tree. Every path is outside the
        # repository because there is not one, which is the right answer: the
        # alternative is a rule that raises instead of applying.
        loose = tmp_path / "somewhere" / "pkg"
        loose.mkdir(parents=True)

        assert repository_root(loose) == loose.resolve()

    def test_it_falls_back_when_git_is_unavailable(self, tmp_path: Path) -> None:
        # A source tree downloaded rather than cloned still has to produce an
        # answer, because the alternative is a data directory rule that
        # silently stops applying.
        nested = tmp_path / "checkout" / "src" / "pkg"
        nested.mkdir(parents=True)
        (tmp_path / "checkout" / ".git").mkdir()

        assert repository_root(nested) == (tmp_path / "checkout").resolve()
