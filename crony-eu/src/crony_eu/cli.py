# SPDX-License-Identifier: AGPL-3.0-only
"""The `crony` command.

`argparse` rather than typer, for the reason in
[ADR-0006](../../docs/adr/0006-standard-library-only.md): phase 1 asks for
subcommands and flags, which is what argparse is.

`doctor`, `fetch`, `stage` and `survey` exist. The other subcommands named in
CLAUDE.md arrive with the stages they drive, and a subcommand that parsed its
arguments and then printed "not implemented" would be worse than its absence,
because `--help` would list it as though it worked.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from crony_eu import __version__
from crony_eu.config import ConfigError, data_dir, repository_root
from crony_eu.http import build_client
from crony_eu.paths import Layout
from crony_eu.sources import REGISTRY, ScopedSource, Source, is_scoped, names
from crony_eu.survey import SurveyError
from crony_eu.survey import departements as survey_departements
from crony_eu.survey import pairs_by_band as survey_pairs_by_band
from crony_eu.survey import pairs_outside_the_commune_list as survey_pairs_outside
from crony_eu.survey import write_report as write_survey_report


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


def _layout() -> Layout:
    layout = Layout(data_dir())
    layout.create()
    return layout


def fetch(arguments: argparse.Namespace) -> int:
    """Download a source into a dated raw snapshot.

    The only networked subcommand. `--snapshot` defaults to today because fetch
    is allowed a clock (constraint 4 forbids one below it), and naming the
    snapshot explicitly is how a rerun targets the bytes it already has.
    """
    module = REGISTRY[arguments.source]
    snapshot = arguments.snapshot or date.today().isoformat()
    scoped = is_scoped(arguments.source)

    if scoped and not arguments.scope:
        print(
            f"{arguments.source} asks one question per supplier and per buyer in "
            "a slice, so it needs `--scope <departement code>`. Without one it "
            "would mean all of France.",
            file=sys.stderr,
        )
        return 1
    if arguments.scope and not scoped:
        print(
            f"{arguments.source} downloads the same published file whoever asks; "
            "`--scope` would not change what it fetches.",
            file=sys.stderr,
        )
        return 1

    layout = _layout()
    client = build_client(arguments.source)
    try:
        if scoped:
            scoped_module = cast("ScopedSource", module)
            entries = scoped_module.fetch(client, layout, snapshot, arguments.scope)
        else:
            entries = cast("Source", module).fetch(client, layout, snapshot)
    finally:
        client.client.close()

    if not entries:
        print(f"{arguments.source}: snapshot {snapshot} was already complete")
    for entry in entries:
        print(f"  {entry['bytes']:>12,} bytes  {entry['sha256'][:12]}  {entry['path']}")
    print(f"\n{arguments.source}: snapshot {snapshot}")
    print(f"  {layout.raw(arguments.source, snapshot)}")
    return 0


def stage(arguments: argparse.Namespace) -> int:
    """Read a raw snapshot into typed Parquet. Offline, and clock-free.

    Without `--snapshot` it stages the most recent one present rather than
    today's, so that staging the morning after a fetch works.
    """
    module = REGISTRY[arguments.source]
    layout = _layout()
    snapshot = arguments.snapshot or layout.latest_snapshot(arguments.source)
    if snapshot is None:
        print(
            f"{arguments.source}: nothing fetched yet. Run "
            f"`crony fetch {arguments.source}` first.",
            file=sys.stderr,
        )
        return 1

    written = module.stage(layout, snapshot)

    for table, rows in sorted(written.items()):
        print(f"  {rows:>10,} rows  {table}")
    print(f"\n{arguments.source}: staged {snapshot}")
    print(f"  {layout.staged(arguments.source, snapshot)}")
    return 0


def survey(arguments: argparse.Namespace) -> int:
    """Print what each département would give phase 1, and write the table out.

    The work order has the maintainer picking a département before session 1.
    Picking it from the staged data means the choice can be defended: two slices
    that look the same on a map differ by an order of magnitude in the only
    number that decides whether a base rate can be measured at all.
    """
    layout = _layout()
    try:
        rows, staged = survey_departements(layout)
        bands = survey_pairs_by_band(layout, arguments.scope)
    except SurveyError as error:
        print(str(error), file=sys.stderr)
        return 1

    columns = [
        ("departement_code", "dep", 5),
        ("communes", "communes", 9),
        ("population", "population", 12),
        ("communes_buying", "buying", 8),
        ("contracts", "contracts", 10),
        ("suppliers", "suppliers", 10),
        ("pairs", "pairs", 8),
        ("pairs_above_432_12", ">3500", 8),
        ("people", "people", 8),
        ("people_with_birth_key", "birth key", 10),
    ]
    header = "  ".join(f"{title:>{width}}" for _, title, width in columns)
    print(header)
    print("-" * len(header))
    for row in sorted(rows, key=lambda one: -int(one["pairs"] or 0)):
        print(
            "  ".join(
                f"{row[key] if row[key] is not None else 0:>{width},}"
                if key != "departement_code"
                else f"{row[key]:>{width}}"
                for key, _, width in columns
            )
        )

    cut = f" in {arguments.scope}" if arguments.scope else ""
    print(f"\n  pairs by population band{cut}")
    for band in bands:
        print(
            f"    {band['band']!s:<16} {band['communes']:>7,} communes  "
            f"{band['communes_buying']:>6,} buying  {band['pairs']:>8,} pairs"
        )

    outside = survey_pairs_outside(layout)
    print(
        f"\n  of {sum(outside.values()):,} commune-supplier pairs nationally, "
        f"{outside['on_a_commune']:,} land on a commune in the bands above,"
    )
    print(
        f"  {outside['on_an_arrondissement']:,} on an arrondissement municipal "
        "(Paris, Lyon and Marseille buy under those codes, so those three"
    )
    print(
        f"  read as zero in the table), and {outside['on_no_published_code']:,} "
        "on a code INSEE does not publish in this vintage."
    )

    destination = write_survey_report(layout, rows, staged)
    print(f"\n  staged snapshots read: {staged.as_dict()}")
    print(f"  {destination}")
    return 0


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

    downloader = subcommands.add_parser(
        "fetch",
        help="download a source into a dated raw snapshot (the networked stage)",
    )
    downloader.add_argument("source", choices=names())
    downloader.add_argument(
        "--snapshot",
        metavar="YYYY-MM-DD",
        help="the snapshot to write; defaults to today",
    )
    downloader.add_argument(
        "--scope",
        metavar="DEP",
        help="a departement code; required by sources that ask per identifier",
    )
    downloader.set_defaults(run=fetch)

    stager = subcommands.add_parser(
        "stage", help="read a raw snapshot into typed Parquet (offline)"
    )
    stager.add_argument("source", choices=names())
    stager.add_argument(
        "--snapshot",
        metavar="YYYY-MM-DD",
        help="the snapshot to read; defaults to the most recent one fetched",
    )
    stager.set_defaults(run=stage)

    surveyor = subcommands.add_parser(
        "survey",
        help="measure what each departement would give phase 1, before picking one",
    )
    surveyor.add_argument("subject", choices=["departements"])
    surveyor.add_argument(
        "--scope",
        metavar="DEP",
        help="a departement code, to cut the population bands to it",
    )
    surveyor.set_defaults(run=survey)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)
    run: Callable[[argparse.Namespace], int] = arguments.run
    return run(arguments)


if __name__ == "__main__":  # pragma: no cover - exercised through the console script
    os.environ.setdefault("COLUMNS", "100")
    raise SystemExit(main())
