# SPDX-License-Identifier: AGPL-3.0-only
"""Where the data lives, and the four rules that say whether it may live there.

Constraint 1 is that no data enters the repository. The data guard in
`crony-eu/scripts/check_no_data.py` catches a file that got in; this catches the
configuration that would have put it there, which is the cheaper of the two.

`$CRONY_DATA_DIR` must be **set**, **absolute**, **outside the repository** and
**writable**. Each failure raises with the rule it broke named, because "invalid
data directory" tells you to go and read this file and "CRONY_DATA_DIR is inside
the repository" does not.

The interesting rule is the third, and the interesting part of it is
`Path.resolve()`. A symlink at `./scratch` pointing into the repository is an
absolute path outside the repository right up until something writes through it,
and that is exactly the arrangement someone sets up when a disk fills. So the
comparison is made on the resolved path, and `tests/test_config.py` builds that
symlink and checks it is refused.

Encryption is not checked here. CLAUDE.md asks for an encrypted volume and no
portable check establishes that a given path sits on one; `crony doctor` says so
rather than implying it has been verified.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class ConfigError(Exception):
    """The data directory configuration breaks one of the four rules."""


#: The variable, named once so the message text and the lookup cannot drift.
DATA_DIR_VARIABLE = "CRONY_DATA_DIR"


def repository_root(start: Path | None = None) -> Path:
    """The top of the working tree, resolved.

    Git first, because a worktree or a submodule makes walking up for `.git`
    give the wrong answer. Walking up is the fallback for a source tree that was
    downloaded rather than cloned, where there is no git to ask.
    """
    here = (start or Path(__file__)).resolve()
    directory = here if here.is_dir() else here.parent

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=directory,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        found = [parent for parent in directory.parents if (parent / ".git").exists()]
        if found:
            # The outermost, so a nested checkout does not shrink the exclusion.
            return found[-1].resolve()
        # No repository to be inside. Every path is outside it, which is the
        # right answer for an installed package with no source tree.
        return directory.resolve()

    return Path(completed.stdout.strip()).resolve()


def is_inside(path: Path, directory: Path) -> bool:
    """Whether `path` is `directory` or sits under it, both already resolved."""
    return path == directory or directory in path.parents


def data_dir(
    environ: dict[str, str] | None = None,
    root: Path | None = None,
) -> Path:
    """The configured data directory, created if it does not exist yet.

    Both arguments exist so the tests can drive this without setting a process
    environment variable or needing a second git repository on disk.
    """
    values = os.environ if environ is None else environ
    configured = values.get(DATA_DIR_VARIABLE, "").strip()

    if not configured:
        raise ConfigError(
            f"{DATA_DIR_VARIABLE} is not set. It is the absolute path, outside "
            "this repository and on an encrypted volume, where downloaded and "
            "derived data lives. Nothing is written inside the repository "
            "(CLAUDE.md, constraint 1)."
        )

    path = Path(configured)
    if not path.is_absolute():
        raise ConfigError(
            f"{DATA_DIR_VARIABLE} is {configured!r}, which is relative. It has "
            "to be absolute, so that what it means does not depend on which "
            "directory a command was run from."
        )

    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise ConfigError(
            f"{DATA_DIR_VARIABLE} is {configured!r}, which could not be "
            f"created: {error}."
        ) from error

    resolved = path.resolve()
    repository = repository_root() if root is None else root.resolve()
    if is_inside(resolved, repository):
        raise ConfigError(
            f"{DATA_DIR_VARIABLE} is {configured!r}, which resolves to "
            f"{resolved} and is inside the repository at {repository}. Data "
            "never lives in the repository, and a symlink pointing back into "
            "it is the way that usually happens by accident (constraint 1)."
        )

    if not os.access(resolved, os.W_OK):
        raise ConfigError(
            f"{DATA_DIR_VARIABLE} is {configured!r}, which exists but is not "
            "writable by this user."
        )

    return resolved
