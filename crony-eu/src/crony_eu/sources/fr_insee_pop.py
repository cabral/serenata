# SPDX-License-Identifier: AGPL-3.0-only
"""INSEE populations de référence: how many people a commune has.

F1 needs this twice. Once for the base-rate bands, because a commune of four
hundred and a commune of four hundred thousand are not the same population and
a rate pooled over both describes neither. And once for Code pénal art. 432-12,
whose 3,500-inhabitant threshold changes what the offence requires, which is the
tag F1 sets on a hit.

**Not taken from DECP, although DECP has a column for it.** The consolidated
file publishes `acheteur_population`, and on the 2026-09-19 snapshot that column
is populated on 0.00% of its 3,281,288 rows. A band computed from it would have
been null for every commune in France. Even populated it would be the wrong
source: it would cover only the communes that bought something, and F1's
denominator is every commune in the slice.

INSEE renamed these figures **populations de référence** from the 2021 vintage;
"populations légales" is the older name and the one `crony-eu/docs/sources/
france.md` was written with. Same figures, and the file is published through
INSEE's Melodi service as a zipped CSV under the Licence Ouverte 2.0.

The vintage is part of the dataset's identity, not a detail: the 2023 vintage
takes legal effect on 1 January 2026, and a base rate computed against one
vintage and reported against another is off by three years of building. So the
vintage is in the resource id, staged into a column, and written into the
report.
"""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any

import pyarrow as pa

from crony_eu.http import SourceClient, download, read_manifest
from crony_eu.parquet import write
from crony_eu.paths import Layout

SOURCE = "fr-insee-pop"

LICENCE = "Licence Ouverte 2.0"

API = "https://www.data.gouv.fr/api/1/datasets"

#: INSEE publishes through data.gouv.fr with a single resource pointing at its
#: own Melodi service. Resolved through the API like every other source, so a
#: new vintage is picked up by refetching rather than by editing a URL here.
DATASET = "populations-de-reference"

#: The one resource, and the name it is stored under. A zip holding one CSV.
RESOURCE = "Populations de référence"
STORED = "populations-de-reference.zip"


class StageError(Exception):
    """A published file did not read the way this module says it reads."""


def resource_url(client: SourceClient, dataset: str, title: str) -> str:
    """The current URL of one resource, asked of the API rather than assumed."""
    payload = client.json(f"{API}/{dataset}/")
    for resource in payload.get("resources", []):
        if resource.get("title") == title:
            url: str = resource["url"]
            return url
    published = sorted(r.get("title", "") for r in payload.get("resources", []))
    raise StageError(
        f"{dataset} no longer publishes a resource titled {title!r}. "
        f"It lists: {published}"
    )


def fetch(client: SourceClient, layout: Layout, snapshot: str) -> list[dict[str, Any]]:
    """Download the populations archive. Safe to run twice."""
    destination = layout.raw(SOURCE, snapshot)
    manifest = layout.manifest(SOURCE, snapshot)
    already = {entry["path"] for entry in read_manifest(manifest)}

    if STORED in already:
        return []
    url = resource_url(client, DATASET, RESOURCE)
    return [download(client, url, destination / STORED, manifest, licence=LICENCE)]


#: The measure phase 1 uses. INSEE publishes three figures per commune, and they
#: are different numbers: `PMUN` counts people whose usual residence is in the
#: commune, `PCAP` counts people counted separately elsewhere (students, people
#: in institutions) and `PTOT` is the sum. The **population municipale** is the
#: one the law refers to, including the 3,500-inhabitant line in Code pénal
#: art. 432-12, so it is the one F1 bands on. All three are staged; picking one
#: is a decision a reader of the flag spec can check.
LEGAL_MEASURE = "PMUN"

#: The published columns, verbatim, and what they are called here.
COLUMNS = {
    "GEO": "geo_code",
    "GEO_OBJECT": "geo_object",
    "POPREF_MEASURE": "measure",
    "TIME_PERIOD": "vintage",
    "OBS_VALUE": "population",
}

POPULATIONS = pa.schema(
    [
        pa.field("geo_code", pa.string()),
        pa.field("geo_object", pa.string()),
        pa.field("measure", pa.string()),
        pa.field("vintage", pa.string()),
        pa.field("population", pa.int32()),
        pa.field("retrieved_at", pa.string()),
    ]
)


def _data_member(archive: zipfile.ZipFile) -> str:
    """The data CSV inside the archive, which is not the metadata one.

    The archive holds two files whose names differ by one word, and the
    metadata one sorts first. Picking by suffix rather than by position means a
    new vintage that adds a third file does not silently get read as the data.
    """
    members = [
        info.filename
        for info in archive.infolist()
        if info.filename.lower().endswith("_data.csv")
    ]
    if len(members) != 1:
        raise StageError(
            f"{STORED} holds {len(members)} files ending in `_data.csv` and this "
            f"module reads exactly one. It lists: "
            f"{sorted(info.filename for info in archive.infolist())}"
        )
    return members[0]


def stage(layout: Layout, snapshot: str) -> dict[str, int]:
    """Read the raw snapshot into `populations.parquet`. Offline, clock-free.

    Every published row is staged, not only the communes. The département and
    région totals cost nothing and they are the only free check on whether the
    commune rows were read correctly: they have to add up.
    """
    raw = layout.raw(SOURCE, snapshot)
    source = raw / STORED
    if not source.is_file():
        raise StageError(
            f"{SOURCE}: snapshot {snapshot} is missing {STORED}. Fetch it first."
        )

    retrieved = {
        entry["path"]: entry["retrieved_at"]
        for entry in read_manifest(layout.manifest(SOURCE, snapshot))
    }.get(STORED, "")

    rows: list[dict[str, Any]] = []
    with zipfile.ZipFile(source) as archive:
        member = _data_member(archive)
        with archive.open(member) as handle:
            reader = csv.DictReader(
                io.TextIOWrapper(handle, encoding="utf-8"), delimiter=";"
            )
            missing = set(COLUMNS) - set(reader.fieldnames or [])
            if missing:
                raise StageError(
                    f"{member} no longer publishes {sorted(missing)}. It has: "
                    f"{sorted(reader.fieldnames or [])}"
                )
            for number, published in enumerate(reader, start=2):
                row = {ours: published[theirs] for theirs, ours in COLUMNS.items()}
                try:
                    row["population"] = int(row["population"])
                except ValueError as error:
                    raise StageError(
                        f"{member}, data row {number}: the population is not a "
                        f"whole number. Column OBS_VALUE, value not shown."
                    ) from error
                row["retrieved_at"] = retrieved
                rows.append(row)

    written = write(
        rows,
        POPULATIONS,
        layout.staged(SOURCE, snapshot) / "populations.parquet",
        key=("geo_object", "geo_code", "measure"),
    )
    return {"populations": written}
