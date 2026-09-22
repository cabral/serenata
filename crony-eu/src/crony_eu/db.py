# SPDX-License-Identifier: AGPL-3.0-only
"""The one way this project opens DuckDB: with its spill space in the data dir.

DuckDB spills to disk when a query outgrows memory, and for an in-memory
connection it spills to `.tmp/` **under the current working directory**. On
2026-09-22 the DECP stage ran from the repository root, spilled 455MB of real
contract data into the repository tree, and `git add -A` committed it. GitHub
refused the push for size, so it never left the machine; the commit was rewritten
and the objects purged. Constraint 1 was broken all the same, for as long as the
files sat in the tree: data belongs under `$CRONY_DATA_DIR`, on an encrypted
volume, and a spill of it is still it.

So every connection names its temp directory, inside the data directory, and a
test fails if any module in this package calls `duckdb.connect` directly.
"""

from __future__ import annotations

import duckdb

from crony_eu.paths import Layout


def connect(layout: Layout) -> duckdb.DuckDBPyConnection:
    """An in-memory connection that spills under `$CRONY_DATA_DIR/tmp/`."""
    scratch = layout.scratch()
    scratch.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(config={"temp_directory": str(scratch)})
