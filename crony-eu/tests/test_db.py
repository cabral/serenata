# SPDX-License-Identifier: AGPL-3.0-only
"""DuckDB spills into the data directory, and only `crony_eu.db` opens it.

The rule exists because it was broken: a DECP stage run from the repository root
spilled 455MB of real contract data into `.tmp/` there, and it was committed.
"""

from __future__ import annotations

import re
from pathlib import Path

from crony_eu import db
from crony_eu.paths import Layout

SOURCE_TREE = Path(__file__).resolve().parent.parent / "src" / "crony_eu"


def test_a_connection_spills_inside_the_data_directory(outside_repo: Path) -> None:
    layout = Layout(outside_repo)
    connection = db.connect(layout)
    try:
        (configured,) = connection.execute(
            "SELECT current_setting('temp_directory')"
        ).fetchone() or ("",)
    finally:
        connection.close()
    assert Path(configured).resolve() == layout.scratch().resolve()
    assert Path(configured).resolve().is_relative_to(outside_repo.resolve())


def test_nothing_else_in_the_package_opens_duckdb_directly() -> None:
    # A direct `duckdb.connect()` spills into whatever directory the command was
    # run from, which is how real data reached the repository tree.
    offenders = [
        str(path.relative_to(SOURCE_TREE))
        for path in sorted(SOURCE_TREE.rglob("*.py"))
        if path.name != "db.py"
        and re.search(r"\bduckdb\.connect\(", path.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"open DuckDB through crony_eu.db.connect: {offenders}"


def test_the_repository_ignores_the_spill_directory() -> None:
    root = SOURCE_TREE.parent.parent.parent
    ignored = (root / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".tmp/" in ignored
