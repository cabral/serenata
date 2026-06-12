"""Command-line entry point: ``serenata fetch|normalise|classify``.

Each subcommand maps to one pipeline stage (parsing runs inside
``normalise``). All of them are stubs while milestone 1 is under
construction: they exit with status 2 and say so.
"""

from __future__ import annotations

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version

STAGES = {
    "fetch": "download notices from TED and archive the raw XML",
    "normalise": "parse archived notices into the documented model (Parquet)",
    "classify": "run hypothesis classifiers over the normalised dataset",
}


def _version() -> str:
    try:
        return version("serenata-europa")
    except PackageNotFoundError:  # running from an uninstalled source tree
        return "unknown"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="serenata",
        description="Anomaly detection pipeline for EU public procurement notices.",
    )
    parser.add_argument("--version", action="version", version=f"serenata {_version()}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name, help_text in STAGES.items():
        subparsers.add_parser(name, help=help_text)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(
        f"serenata {args.command}: not implemented yet; "
        "milestone 1 is in progress (see README).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
