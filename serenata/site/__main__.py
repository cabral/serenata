"""``python -m serenata.site``: build the pages into a directory.

Not a pipeline stage and not a subcommand of ``serenata``: it reads documents,
not data, and takes no dataset, archive or flag path, on purpose (ADR-0014).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from serenata.site.build import build_site, default_repo
from serenata.site.docs import SourceError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m serenata.site",
        description="Render the project's status pages from its own documents.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        metavar="DIR",
        help="where to write the pages (default: site/ in the repository root)",
    )
    args = parser.parse_args(argv)

    repo = default_repo()
    out = args.out if args.out is not None else repo / "site"
    try:
        written = build_site(repo, out)
    except SourceError as error:
        print(f"The site cannot be built: {error}", file=sys.stderr)
        return 1
    for path in written:
        print(f"{path}  {path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
