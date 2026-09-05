"""Command-line entry point: ``serenata fetch|normalise|classify``.

Each subcommand maps to one pipeline stage; parsing runs inside ``normalise``.
All three are implemented. ``classify`` runs every rule the classify package
carries over the normalised dataset and writes the flags each one produced.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path

from serenata import __version__
from serenata.classify import (
    Classified,
    classify_dataset,
    default_flag_root,
)
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
from serenata.normalise import (
    Normalised,
    default_dataset_root,
    normalise_package,
)

STAGES = {
    "fetch": "download notices from TED and archive the raw XML",
    "normalise": "parse archived notices into the documented model (Parquet)",
    "classify": "run hypothesis classifiers over the normalised dataset",
}

IMPLEMENTED = frozenset({"fetch", "normalise", "classify"})


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
        elif name == "normalise":
            _add_normalise_arguments(stage)
        elif name == "classify":
            _add_classify_arguments(stage)

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


def _add_normalise_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "packages",
        nargs="*",
        type=Path,
        metavar="PACKAGE",
        help="archived .tar.gz packages (default: every package under --archive)",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        metavar="DIR",
        help=f"raw archive root (default: {default_archive_root()})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="DIR",
        help=(
            f"where the Parquet dataset is written (default: {default_dataset_root()})"
        ),
    )


def _add_classify_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dataset",
        type=Path,
        default=None,
        metavar="DIR",
        help=f"normalised dataset to classify (default: {default_dataset_root()})",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="DIR",
        help=f"where flags are written (default: {default_flag_root()})",
    )


def _run_classify(args: argparse.Namespace) -> int:
    dataset = args.dataset if args.dataset is not None else default_dataset_root()
    if not dataset.is_dir():
        print(
            f"serenata classify: no dataset at {dataset}; "
            "normalise some packages first (serenata normalise)",
            file=sys.stderr,
        )
        return 2

    out = args.out if args.out is not None else default_flag_root()
    results: list[Classified] = classify_dataset(dataset, out)
    for result in results:
        print(result.describe())

    flags = sum(result.flags for result in results)
    rules = f"{len(results)} rule" + ("" if len(results) == 1 else "s")
    print(f"\n{rules}: {flags} flags -> {out}")
    # Constraint 3, in the one place a reader meets the output first.
    print(
        "A flag is a statistical anomaly with possible innocent explanations, "
        "never an accusation. Each one names the notice it came from and the "
        "baseline it was measured against; see docs/hypotheses/.",
        file=sys.stderr,
    )
    return 0


def _run_normalise(args: argparse.Namespace) -> int:
    root = args.archive if args.archive is not None else default_archive_root()
    packages: list[Path] = list(args.packages) or sorted(root.rglob("*.tar.gz"))
    if not packages:
        print(
            f"serenata normalise: no packages found under {root}; "
            "fetch some first (serenata fetch --from YYYY-MM-DD)",
            file=sys.stderr,
        )
        return 2

    missing = [package for package in packages if not package.is_file()]
    if missing:
        for package in missing:
            print(f"serenata normalise: no such package: {package}", file=sys.stderr)
        return 2

    out = args.out if args.out is not None else default_dataset_root()
    results: list[Normalised] = []
    for package in packages:
        result = normalise_package(package, out)
        results.append(result)
        print(result.describe())

    notices = sum(result.notices for result in results)
    rows = sum(sum(result.rows.values()) for result in results)
    lost = sum(len(result.unparsed) + len(result.unnormalised) for result in results)
    counted = f"{len(results)} package" + ("" if len(results) == 1 else "s")
    print(f"\n{counted}: {notices} notices, {rows} rows -> {out}")
    if lost:
        # Named rather than summarised away: a run that lost notices must not
        # read like a run that had none to lose.
        print(f"{lost} notices were not written:", file=sys.stderr)
        for result in results:
            for unparsed in result.unparsed:
                print(f"  {unparsed.member}: {unparsed.reason}", file=sys.stderr)
            for unnormalised in result.unnormalised:
                print(
                    f"  {unnormalised.notice_id}: {unnormalised.reason}",
                    file=sys.stderr,
                )
        return 1
    return 0


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

    if args.command == "fetch":
        return _run_fetch(args, open_client)
    if args.command == "normalise":
        return _run_normalise(args)
    return _run_classify(args)


if __name__ == "__main__":
    raise SystemExit(main())
