# SPDX-License-Identifier: AGPL-3.0-only
"""The `crony` command.

`argparse` rather than typer, for the reason in
[ADR-0006](../../docs/adr/0006-standard-library-only.md): phase 1 asks for
subcommands and flags, which is what argparse is.

Only `doctor` exists so far. The other subcommands named in CLAUDE.md arrive
with the stages they drive, and a subcommand that parsed its arguments and then
printed "not implemented" would be worse than its absence, because `--help`
would list it as though it worked.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from crony_eu import __version__
from crony_eu.config import ConfigError, data_dir, repository_root
from crony_eu.paths import Layout


@dataclass(frozen=True)
class Check:
    """One doctor check and what it found.

    `ok` is three-valued on purpose. `None` means the check could not run yet —
    there is nothing to check — and it is reported as such rather than as a
    pass, because a green line for a check that did nothing is how a suite of
    checks stops meaning anything.
    """

    name: str
    ok: bool | None
    detail: str

    @property
    def mark(self) -> str:
        return {True: "ok", False: "FAIL", None: "n/a"}[self.ok]


def check_data_dir() -> tuple[Check, Path | None]:
    """The four rules in `config.py`, reported as one line."""
    try:
        root = data_dir()
    except ConfigError as error:
        return Check("data directory", False, str(error)), None
    return Check("data directory", True, str(root)), root


def check_layout(root: Path | None) -> Check:
    if root is None:
        return Check("data directory layout", None, "no usable data directory")
    layout = Layout(root)
    layout.create()
    return Check(
        "data directory layout",
        True,
        f"{root}/raw, staged, matched, flags, cases, logs",
    )


def check_no_data_in_tree() -> Check:
    """Constraint 1, asked of the actual git tree rather than assumed."""
    repository = repository_root()
    script = repository / "crony-eu" / "scripts" / "check_no_data.py"
    if not script.is_file():
        return Check("no data in the repository", False, f"{script} is missing")

    completed = subprocess.run(
        [sys.executable, str(script), "--all"],
        cwd=repository,
        capture_output=True,
        text=True,
    )
    if completed.returncode == 0:
        return Check("no data in the repository", True, "the tracked tree is clean")
    first = (completed.stderr or completed.stdout).strip().splitlines()
    return Check("no data in the repository", False, first[0] if first else "blocked")


def check_encryption(root: Path | None) -> Check:
    """Deliberately not a pass.

    CLAUDE.md asks for an encrypted volume and no portable check establishes
    that a path sits on one. Saying so is the honest output; printing a tick
    would be a claim this command cannot support.
    """
    if root is None:
        return Check("encrypted volume", None, "no usable data directory")
    return Check(
        "encrypted volume",
        None,
        f"not checked; confirm yourself that {root} is on an encrypted volume",
    )


def check_export_template() -> Check:
    """The CSP check, which has nothing to read yet."""
    return Check(
        "export template CSP",
        None,
        "no template yet; arrives with the case packet (work order, session 6)",
    )


def doctor(_: argparse.Namespace) -> int:
    """Report on the environment, and say which checks did not run."""
    data, root = check_data_dir()
    checks = [
        data,
        check_layout(root),
        check_encryption(root),
        check_no_data_in_tree(),
        check_export_template(),
    ]

    width = max(len(check.name) for check in checks)
    for check in checks:
        print(f"  {check.mark:<4} {check.name:<{width}}  {check.detail}")

    failed = [check for check in checks if check.ok is False]
    skipped = [check for check in checks if check.ok is None]
    print()
    print(
        f"{len(checks) - len(failed) - len(skipped)} passed, "
        f"{len(failed)} failed, {len(skipped)} not checked"
    )
    return 1 if failed else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crony",
        description=(
            "Links between office holders, companies and public money, from "
            "official open data, confirmed by a person before anything leaves "
            "this machine."
        ),
    )
    parser.add_argument(
        "--version", action="version", version=f"crony-eu {__version__}"
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    described = subcommands.add_parser(
        "doctor",
        help="check the data directory, the repository and the environment",
    )
    described.set_defaults(run=doctor)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    run: Callable[[argparse.Namespace], int] = arguments.run
    return run(arguments)


if __name__ == "__main__":  # pragma: no cover - exercised through the console script
    os.environ.setdefault("COLUMNS", "100")
    raise SystemExit(main())
