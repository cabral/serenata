# SPDX-License-Identifier: AGPL-3.0-only
"""Staging INSEE's populations de référence.

A small file, and the two things that can go wrong with it are both about
picking the right rows. The archive holds a metadata file next to the data one,
and the data file holds three different population figures per commune under a
column nobody reads twice. Taking the wrong one gives a number that is the right
order of magnitude and wrong, which is the worst kind.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from crony_eu.http import RateLimiter, SourceClient
from crony_eu.paths import Layout
from crony_eu.sources import fr_insee_pop
from fakes import write_populations

SNAPSHOT = "2026-09-19"

ROWS = [
    ("93001", "COM", "PMUN", 1200),
    ("93001", "COM", "PCAP", 30),
    ("93001", "COM", "PTOT", 1230),
    ("93002", "COM", "PMUN", 4000),
    ("75112", "ARM", "PMUN", 150000),
    ("93", "DEP", "PMUN", 5200),
]


@pytest.fixture
def layout(outside_repo: Path) -> Layout:
    made = Layout(outside_repo)
    made.create()
    return made


def stage(layout: Layout) -> dict[str, int]:
    write_populations(
        layout.raw(fr_insee_pop.SOURCE, SNAPSHOT) / fr_insee_pop.STORED, ROWS
    )
    return fr_insee_pop.stage(layout, SNAPSHOT)


def staged(layout: Layout) -> list[dict[str, object]]:
    path = layout.staged(fr_insee_pop.SOURCE, SNAPSHOT) / "populations.parquet"
    return [dict(row) for row in pq.read_table(path).to_pylist()]


class TestStage:
    def test_every_published_row_is_staged(self, layout: Layout) -> None:
        assert stage(layout) == {"populations": len(ROWS)}

    def test_the_three_measures_stay_apart(self, layout: Layout) -> None:
        stage(layout)
        commune = {
            str(row["measure"]): row["population"]
            for row in staged(layout)
            if row["geo_code"] == "93001"
        }
        assert commune == {"PMUN": 1200, "PCAP": 30, "PTOT": 1230}

    def test_the_legal_measure_is_the_municipal_population(
        self, layout: Layout
    ) -> None:
        # The figure art. 432-12's 3,500 line refers to, and the one F1 bands on.
        assert fr_insee_pop.LEGAL_MEASURE == "PMUN"

    def test_arrondissements_are_kept_apart_from_communes(self, layout: Layout) -> None:
        # Paris, Lyon and Marseille buy under these codes, so losing them here
        # would make three cities disappear from the survey rather than show up
        # wrong, which is harder to notice.
        stage(layout)
        kinds = {str(row["geo_object"]) for row in staged(layout)}
        assert kinds == {"COM", "ARM", "DEP"}

    def test_the_vintage_is_carried_on_every_row(self, layout: Layout) -> None:
        stage(layout)
        assert {str(row["vintage"]) for row in staged(layout)} == {"2023"}

    def test_staging_twice_gives_the_same_bytes(self, layout: Layout) -> None:
        stage(layout)
        path = layout.staged(fr_insee_pop.SOURCE, SNAPSHOT) / "populations.parquet"
        first = path.read_bytes()
        stage(layout)
        assert path.read_bytes() == first


class TestRefusals:
    def test_staging_without_fetching_says_so(self, layout: Layout) -> None:
        with pytest.raises(fr_insee_pop.StageError, match="Fetch it first"):
            fr_insee_pop.stage(layout, SNAPSHOT)

    def test_a_missing_column_stops_the_stage(self, layout: Layout) -> None:
        import zipfile

        path = layout.raw(fr_insee_pop.SOURCE, SNAPSHOT) / fr_insee_pop.STORED
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "DS_POPULATIONS_REFERENCE_2023_data.csv", "GEO;OBS_VALUE\n93001;1200\n"
            )
        with pytest.raises(fr_insee_pop.StageError, match="no longer publishes"):
            fr_insee_pop.stage(layout, SNAPSHOT)

    def test_two_data_files_stop_the_stage(self, layout: Layout) -> None:
        import zipfile

        path = layout.raw(fr_insee_pop.SOURCE, SNAPSHOT) / fr_insee_pop.STORED
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("a_data.csv", "GEO\n")
            archive.writestr("b_data.csv", "GEO\n")
        with pytest.raises(fr_insee_pop.StageError, match="exactly one"):
            fr_insee_pop.stage(layout, SNAPSHOT)

    def test_a_population_that_is_not_a_number_stops_the_stage(
        self, layout: Layout
    ) -> None:
        import zipfile

        path = layout.raw(fr_insee_pop.SOURCE, SNAPSHOT) / fr_insee_pop.STORED
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "DS_POPULATIONS_REFERENCE_2023_data.csv",
                "GEO;GEO_OBJECT;POPREF_MEASURE;TIME_PERIOD;OBS_VALUE\n"
                "93001;COM;PMUN;2023;n/a\n",
            )
        with pytest.raises(fr_insee_pop.StageError, match="not a whole number"):
            fr_insee_pop.stage(layout, SNAPSHOT)


def client_for(
    handler: Callable[[httpx.Request], httpx.Response],
) -> SourceClient:
    """A client wired to a scripted data.gouv.fr. No socket is opened."""
    return SourceClient(
        source=fr_insee_pop.SOURCE,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        limiter=RateLimiter(rate=1000.0, capacity=1000.0),
    )


class TestFetch:
    def handler(self, calls: list[str]) -> Callable[[httpx.Request], httpx.Response]:
        def respond(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "/api/1/datasets/" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "resources": [
                            {
                                "title": fr_insee_pop.RESOURCE,
                                "url": "https://api.insee.invalid/populations",
                            }
                        ]
                    },
                )
            return httpx.Response(200, content=b"zip bytes")

        return respond

    def test_it_downloads_the_archive_and_records_it(self, layout: Layout) -> None:
        calls: list[str] = []
        entries = fr_insee_pop.fetch(client_for(self.handler(calls)), layout, SNAPSHOT)

        assert [entry["path"] for entry in entries] == [fr_insee_pop.STORED]
        assert entries[0]["licence"] == fr_insee_pop.LICENCE
        raw = layout.raw(fr_insee_pop.SOURCE, SNAPSHOT)
        assert (raw / fr_insee_pop.STORED).read_bytes() == b"zip bytes"

    def test_fetching_twice_downloads_nothing_the_second_time(
        self, layout: Layout
    ) -> None:
        calls: list[str] = []
        handler = self.handler(calls)
        fr_insee_pop.fetch(client_for(handler), layout, SNAPSHOT)
        before = len(calls)

        assert fr_insee_pop.fetch(client_for(handler), layout, SNAPSHOT) == []
        assert len(calls) == before

    def test_a_renamed_resource_says_what_the_dataset_now_lists(
        self, layout: Layout
    ) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"resources": [{"title": "Populations 2099"}]}
            )

        with pytest.raises(fr_insee_pop.StageError, match="Populations 2099"):
            fr_insee_pop.fetch(client_for(respond), layout, SNAPSHOT)
