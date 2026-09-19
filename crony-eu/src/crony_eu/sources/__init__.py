# SPDX-License-Identifier: AGPL-3.0-only
"""One module per source, and the registry the CLI looks a name up in.

Every source module exposes the same three things, so that `crony fetch` and
`crony stage` do not grow a branch per source:

    SOURCE   the name used in `$CRONY_DATA_DIR/raw/<source>/` and on the CLI
    fetch()  networked; writes bytes and a manifest entry, changes nothing else
    stage()  offline; reads that snapshot and writes typed Parquet

A source is usable only once it has an approved section in
`crony-eu/docs/sources/france.md` (constraint 6). Adding a module here without
one is the mistake the constraint exists to prevent, so the registry is a
handful of explicit imports rather than a directory scan: a module nobody
deliberately listed cannot be fetched by typing its name.
"""

from __future__ import annotations

from typing import Any, Protocol

from crony_eu.http import SourceClient
from crony_eu.paths import Layout
from crony_eu.sources import fr_decp, fr_insee_pop, fr_rne_elus


class Source(Protocol):
    """What every source module provides. Checked structurally, not inherited.

    Stated as a Protocol so that mypy fails a module missing one of the three,
    rather than the CLI failing at the moment someone types its name.
    """

    SOURCE: str

    def fetch(
        self, client: SourceClient, layout: Layout, snapshot: str
    ) -> list[dict[str, Any]]: ...

    def stage(self, layout: Layout, snapshot: str) -> dict[str, int]: ...


#: Name -> module. The CLI's whole knowledge of which sources exist.
REGISTRY: dict[str, Source] = {
    fr_decp.SOURCE: fr_decp,
    fr_insee_pop.SOURCE: fr_insee_pop,
    fr_rne_elus.SOURCE: fr_rne_elus,
}


def names() -> list[str]:
    return sorted(REGISTRY)
