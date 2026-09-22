# SPDX-License-Identifier: AGPL-3.0-only
"""The id of a run: what it read, and what read it.

`crony-eu/CLAUDE.md`: "A `run_id` is a hash of the input manifests plus the
package version." A run that read the same bytes with the same code gets the same
id, which is what lets a judgment or a flag row say which run produced it without
recording when that run happened. Constraint 4 allows no clock in data.

The manifests, not the staged files, because the manifests are what vouch for
the raw bytes, and a staged table is by construction a function of those bytes
and this code.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

from crony_eu import __version__
from crony_eu.http import read_manifest
from crony_eu.paths import Layout


def run_id(layout: Layout, inputs: Sequence[tuple[str, str]]) -> str:
    """sha256 over each input's manifest hashes and the package version.

    `inputs` is (source, snapshot) pairs. Order does not matter: they are sorted,
    and so are the entries inside each manifest, because two runs over the same
    snapshots must agree however the caller happened to list them.
    """
    digest = hashlib.sha256(f"crony-eu {__version__}".encode())
    for source, snapshot in sorted(inputs):
        digest.update(f"|{source}@{snapshot}".encode())
        hashes = sorted(
            f"{entry['path']}:{entry['sha256']}"
            for entry in read_manifest(layout.manifest(source, snapshot))
        )
        for line in hashes:
            digest.update(f"|{line}".encode())
    return digest.hexdigest()
