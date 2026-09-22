# SPDX-License-Identifier: AGPL-3.0-only
"""An append-only decision log, ordered by revision rather than by clock.

Two logs in this project record a person deciding something: `judgments` (is
this élu that officer?) and `buyer_verification` (is this contract's buyer the
commune the data says?). Both have to answer the same three questions, and the
answers have to agree, so the machinery is written once.

- **What do we believe now?** `latest`: the highest revision per id.
- **What did we believe then?** `history`: every revision of one id, in order.
  Constraint 11 depends on it. A packet names the decisions it was built on, and
  when one of them is later reversed the packet has to be findable and withdrawn,
  which only works if the reversed answer is still on disk.
- **What is waiting?** `decided`: the ids that have any answer at all.

**No clock.** Constraint 4 allows no timestamp inside data except `retrieved_at`,
so a revision is an integer counting up per id. The ordering is deterministic,
and rewriting the same decisions writes the same bytes, which a timestamp would
make impossible.

Appending rewrites the file whole and renames it into place, through
`parquet.write`. An interrupted append leaves the previous log intact rather
than a file that is neither the old one nor the new one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from crony_eu.parquet import write


@dataclass(frozen=True)
class Log:
    """One append-only log: where it lives, its columns, and its id column."""

    path: Path
    schema: pa.Schema
    key: str

    def read(self) -> list[dict[str, Any]]:
        """Every revision ever written, ordered by id then revision."""
        if not self.path.is_file():
            return []
        rows = [dict(row) for row in pq.read_table(self.path).to_pylist()]
        return sorted(rows, key=lambda row: (str(row[self.key]), int(row["revision"])))

    def append(self, decisions: Sequence[dict[str, Any]]) -> int:
        """Add revisions without touching any that exist. Returns the row count.

        The caller supplies everything but `revision`, which is one past the
        highest this id already has. Several decisions about one id in a single
        call get consecutive revisions in the order given.
        """
        rows = self.read()
        highest: dict[str, int] = {}
        for row in rows:
            identifier = str(row[self.key])
            highest[identifier] = max(highest.get(identifier, 0), int(row["revision"]))

        for decision in decisions:
            identifier = str(decision[self.key])
            highest[identifier] = highest.get(identifier, 0) + 1
            rows.append({**decision, "revision": highest[identifier]})

        return write(rows, self.schema, self.path, key=(self.key, "revision"))

    def latest(self) -> list[dict[str, Any]]:
        """The current answer for each id."""
        current: dict[str, dict[str, Any]] = {}
        for row in self.read():
            current[str(row[self.key])] = row
        return [current[identifier] for identifier in sorted(current)]

    def history(self, identifier: str) -> list[dict[str, Any]]:
        """Every revision of one id, oldest first."""
        return [row for row in self.read() if str(row[self.key]) == identifier]

    def decided(self) -> set[str]:
        """Ids with at least one answer."""
        return {str(row[self.key]) for row in self.read()}
