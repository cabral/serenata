"""Reading notices out of an archived daily package.

Shared by the parse stage and the field survey, which otherwise each decided
for themselves what counts as a notice file. They had already drifted — one
filtered members by filename, the other did not — and a disagreement about
which members are notices is a disagreement about what the dataset contains.

The archive is read-only input. Nothing here writes back into it, because raw
files are ground truth (ADR-0002).
"""

from __future__ import annotations

import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO


def notice_members(package: Path) -> Iterator[tuple[str, IO[bytes]]]:
    """Yield ``(member name, open handle)`` for every notice in ``package``.

    Members are streamed out of the tarball rather than extracted to disk: a
    package holds a few thousand notices and roughly 200 MB uncompressed, and
    one notice in a real package is 40 MB on its own.

    Each handle is valid only until the next member is taken, which is what
    keeps the whole package from being held at once. A caller that needs a
    notice after moving on has to have read it.
    """
    with tarfile.open(package, "r:gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".xml"):
                continue
            handle = archive.extractfile(member)
            if handle is None:  # pragma: no cover - a directory entry named .xml
                continue
            yield member.name, handle
