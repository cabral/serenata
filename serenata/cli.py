"""Command-line entry point: ``serenata fetch|normalise|classify``.

Each subcommand maps to one pipeline stage (parsing runs inside
``normalise``). ``fetch`` is implemented; the stages downstream of it are
still stubs while milestone 1 is under construction, and exit with status 2
saying so.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from serenata import __version__
from serenata.fetch import (
    ArchiveConflict,
    DayResult,
    FetchError,
    Outcome,
    RawArchive,
    RetryPolicy,
    TedClient,
    default_archive_root,
    fetch_range,
)

STAGES = {
    "fetch": "download notices from TED and archive the raw XML",
    "normalise": "parse archived notices into the documented model (Parquet)",
    "classify": "run hypothesis classifiers over the normalised dataset",
}

IMPLEMENTED = frozenset({"fetch"})


def _iso_date(raw: str) -> date:
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"expected a date as YYYY-MM-DD, got {raw!r}"
        ) from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="serenata",
        description="Anomaly detection pipeline for EU public procurement notices.",
    )
    parser.add_argument(
        "--version", action="version", version=f"serenata {__version__}"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, help_text in STAGES.items():
        stage = subparsers.add_parser(name, help=help_text, description=help_text)
        if name == "fetch":
            _add_fetch_arguments(stage)

    return parser


def _add_fetch_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--from",
        dest="start",
        type=_iso_date,
        required=True,
        metavar="YYYY-MM-DD",
        help="first publication date to fetch (inclusive)",
    )
    parser.add_argument(
        "--to",
        dest="end",
        type=_iso_date,
        metavar="YYYY-MM-DD",
        help="last publication date to fetch (inclusive; defaults to --from)",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        metavar="DIR",
        help=f"raw archive root (default: {default_archive_root()})",
    )
    parser.add_argument(
        "--min-interval",
        type=float,
        default=1.0,
        metavar="SECONDS",
        help="minimum delay between requests to TED (default: 1.0)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve which packages would be fetched, download nothing",
    )


def _open_client(min_interval: float) -> TedClient:
    """Build the client the fetch stage talks to TED through.

    Kept as a seam so the tests can drive the command against a stand-in TED;
    nothing else has a reason to substitute it.
    """
    return TedClient(min_interval=min_interval, retry=RetryPolicy())


def _run_fetch(
    args: argparse.Namespace,
    open_client: Callable[[float], TedClient] = _open_client,
) -> int:
    start: date = args.start
    end: date = args.end or start
    if end < start:
        print(
            f"serenata fetch: --to {end.isoformat()} precedes "
            f"--from {start.isoformat()}",
            file=sys.stderr,
        )
        return 2

    root = args.archive if args.archive is not None else default_archive_root()
    archive = RawArchive(root)

    def report(result: DayResult) -> None:
        print(result.describe())

    with open_client(args.min_interval) as client:
        try:
            results = fetch_range(
                client=client,
                archive=archive,
                start=start,
                end=end,
                dry_run=args.dry_run,
                on_result=report,
            )
        except (FetchError, ArchiveConflict) as exc:
            print(f"serenata fetch: {exc}", file=sys.stderr)
            return 1

    counts: dict[str, int] = {}
    for result in results:
        counts[result.outcome] = counts.get(result.outcome, 0) + 1
    summary = ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
    print(f"\n{len(results)} dates considered: {summary or 'nothing to do'}")

    fetched = counts.get(Outcome.FETCHED, 0) + counts.get(Outcome.PLANNED, 0)
    skipped = counts.get(Outcome.SKIPPED, 0)
    if fetched == 0 and skipped == 0:
        print("No notices were published in that range.", file=sys.stderr)
    return 0


def main(
    argv: list[str] | None = None,
    *,
    open_client: Callable[[float], TedClient] = _open_client,
) -> int:
    args = build_parser().parse_args(argv)

    if args.command in IMPLEMENTED:
        return _run_fetch(args, open_client)

    print(
        f"serenata {args.command}: not implemented yet; "
        "milestone 1 is in progress (see README).",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
