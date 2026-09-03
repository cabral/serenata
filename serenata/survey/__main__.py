"""``python -m serenata.survey`` — survey archived packages into a document.

Two reports, both deterministic and both committed under ``docs/``. ``fields``
measures the notices going in: which element paths carry a value, in how many
member states, and how often a path repeats inside one record. ``shape``
measures the rows coming out: how many, how populated, and how often the
sentinels and leaks this project warns about actually occur.

Deliberately not a subcommand of ``serenata``: that CLI names pipeline stages,
and this is an analysis tool that reads their output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from serenata.survey.report import Survey, render, survey_package
from serenata.survey.shape import Shape, shape_package
from serenata.survey.shape import render as render_shape


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m serenata.survey",
        description="Measure which eForms fields archived notices populate.",
    )
    parser.add_argument(
        "packages",
        nargs="+",
        type=Path,
        metavar="PACKAGE",
        help="archived daily package(s), as fetched into the raw archive",
    )
    parser.add_argument(
        "--report",
        choices=("fields", "shape"),
        default="fields",
        help=(
            "fields: which element paths notices populate (docs/field-usage.md). "
            "shape: what the normalised rows look like (docs/dataset-shape.md). "
            "Default: fields."
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        metavar="FILE",
        help="write the report here instead of standard output",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    missing = [path for path in args.packages if not path.is_file()]
    if missing:
        print(
            f"no such package: {', '.join(str(path) for path in missing)}",
            file=sys.stderr,
        )
        return 2

    if args.report == "shape":
        shape = Shape()
        # Sorted so the report does not depend on the order a shell expanded a
        # glob; the same packages must give the same document.
        for package in sorted(args.packages):
            shape_package(package, into=shape)
            print(
                f"measured {package.name}: {shape.notices:,} notices so far",
                file=sys.stderr,
            )
        if not shape.notices:
            print("no eForms notices found in those packages", file=sys.stderr)
            return 1
        shape.finish()
        document = render_shape(shape)
    else:
        survey = Survey()
        # Sorted for the same reason.
        for package in sorted(args.packages):
            survey_package(package, into=survey)
            print(
                f"surveyed {package.name}: {survey.notices:,} notices so far",
                file=sys.stderr,
            )

        if not survey.notices:
            print("no eForms notices found in those packages", file=sys.stderr)
            return 1

        document = render(survey)
    if args.output:
        args.output.write_text(document, encoding="utf-8")
        print(f"wrote {args.output}", file=sys.stderr)
    else:
        print(document, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
