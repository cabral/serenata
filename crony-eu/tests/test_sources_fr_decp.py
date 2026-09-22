# SPDX-License-Identifier: AGPL-3.0-only
"""Staging the consolidated contracts file.

Three behaviours carry the weight here, and each one is a mistake the real file
would have let through quietly.

**Choosing the latest version.** The published `donneesActuelles` flag looks
like the answer and is not, because 70,277 contract groups on the real file have
no row flagged at all. A stage that filtered on it would drop them.

**Telling a lot from a duplicate.** One contract can have several rows at the
same version: separate lots, each with its own subject and amount. They are not
versions of each other and collapsing them loses money.

**Knowing what an identifier is.** A supplier identifier that fails its checksum
is still a contract, so it is marked and carried, never dropped.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from crony_eu.http import RateLimiter, SourceClient, append_manifest
from crony_eu.paths import Layout
from crony_eu.sources import fr_decp
from fakes import decp_row, siret, write_decp, write_populations  # noqa: F401

SNAPSHOT = "2026-09-19"


def staged(layout: Layout, table: str) -> list[dict[str, object]]:
    path = layout.staged(fr_decp.SOURCE, SNAPSHOT) / f"{table}.parquet"
    return [dict(row) for row in pq.read_table(path).to_pylist()]


@pytest.fixture
def layout(outside_repo: Path) -> Layout:
    made = Layout(outside_repo)
    made.create()
    return made


def stage(layout: Layout, rows: list[dict[str, object]]) -> dict[str, int]:
    write_decp(layout.raw(fr_decp.SOURCE, SNAPSHOT) / "decp.parquet", rows)
    return fr_decp.stage(layout, SNAPSHOT)


class TestVersions:
    def test_every_published_row_reaches_contract_versions(
        self, layout: Layout
    ) -> None:
        written = stage(
            layout,
            [
                decp_row(uid="A", modification_id=0, donneesActuelles=False),
                decp_row(uid="A", modification_id=1, donneesActuelles=True),
            ],
        )
        assert written["contract_versions"] == 2

    def test_only_the_highest_modification_reaches_contracts(
        self, layout: Layout
    ) -> None:
        stage(
            layout,
            [
                decp_row(uid="A", modification_id=0, montant=100.0),
                decp_row(uid="A", modification_id=1, montant=200.0),
                decp_row(uid="A", modification_id=2, montant=300.0),
            ],
        )
        kept = staged(layout, "contracts")
        assert [row["modification_id"] for row in kept] == [2]

    def test_a_contract_nobody_flagged_as_current_is_still_staged(
        self, layout: Layout
    ) -> None:
        # The case that makes this whole rule necessary: on the real file 70,277
        # groups have no row flagged, 43,726 of them with a modification_id on
        # every row. Filtering on the flag loses the contract entirely.
        stage(
            layout,
            [
                decp_row(uid="B", modification_id=0, donneesActuelles=False),
                decp_row(uid="B", modification_id=1, donneesActuelles=False),
            ],
        )
        kept = staged(layout, "contracts")
        assert [row["modification_id"] for row in kept] == [1]
        assert kept[0]["published_as_current"] is False

    def test_a_group_with_no_version_information_survives(self, layout: Layout) -> None:
        stage(
            layout,
            [decp_row(uid="C", modification_id=None, donneesActuelles=None)],
        )
        kept = staged(layout, "contracts")
        assert len(kept) == 1
        assert kept[0]["is_latest_version"] is True

    def test_versions_are_counted_per_supplier_not_per_contract(
        self, layout: Layout
    ) -> None:
        # A consortium: two suppliers on one contract, each with its own
        # modification history. Taking the maximum across the contract would
        # drop the supplier whose history is shorter.
        other = siret("81230002")
        stage(
            layout,
            [
                decp_row(uid="D", modification_id=0, titulaire_id=siret("81230001")),
                decp_row(uid="D", modification_id=1, titulaire_id=siret("81230001")),
                decp_row(uid="D", modification_id=0, titulaire_id=other),
            ],
        )
        kept = staged(layout, "contracts")
        assert len(kept) == 2
        assert {str(row["supplier_siret"]) for row in kept} == {
            siret("81230001"),
            other,
        }

    def test_two_lots_at_one_version_are_both_kept(self, layout: Layout) -> None:
        # 8,267 groups on the real file look like duplicates and are lots: the
        # same contract, the same version, a different subject and amount.
        stage(
            layout,
            [
                decp_row(uid="E", objet="Lot 1 voirie", montant=10.0),
                decp_row(uid="E", objet="Lot 2 eclairage", montant=20.0),
            ],
        )
        kept = staged(layout, "contracts")
        assert len(kept) == 2
        assert {str(row["subject"]) for row in kept} == {
            "Lot 1 voirie",
            "Lot 2 eclairage",
        }


class TestIdentifiers:
    def test_a_valid_siret_is_split_into_siret_and_siren(self, layout: Layout) -> None:
        stage(layout, [decp_row(titulaire_id=siret("81230001"))])
        row = staged(layout, "contracts")[0]
        assert row["supplier_siret"] == siret("81230001")
        assert row["supplier_siren"] == siret("81230001")[:9]
        assert row["supplier_siret_valid"] is True
        assert row["supplier_has_siren"] is True

    def test_a_failed_checksum_is_marked_and_the_contract_kept(
        self, layout: Layout
    ) -> None:
        good = siret("81230001")
        broken = good[:13] + str((int(good[13]) + 1) % 10)
        stage(layout, [decp_row(titulaire_id=broken)])
        row = staged(layout, "contracts")[0]
        assert row["supplier_siret"] == broken
        assert row["supplier_siret_valid"] is False
        assert row["supplier_has_siren"] is True

    def test_a_supplier_with_no_siret_stays_with_the_flag_false(
        self, layout: Layout
    ) -> None:
        stage(
            layout,
            [decp_row(titulaire_id="FR12345678901", titulaire_typeIdentifiant="TVA")],
        )
        row = staged(layout, "contracts")[0]
        assert row["supplier_has_siren"] is False
        assert row["supplier_siren"] is None
        assert row["supplier_id_type"] == "TVA"

    def test_identifier_types_are_spelled_one_way(self, layout: Layout) -> None:
        stage(
            layout,
            [
                decp_row(uid="A", titulaire_typeIdentifiant="Siret"),
                decp_row(uid="B", titulaire_typeIdentifiant="siret"),
                decp_row(uid="C", titulaire_typeIdentifiant="HORS-UE"),
                decp_row(uid="D", titulaire_typeIdentifiant="HORS UE"),
            ],
        )
        seen = {str(row["supplier_id_type"]) for row in staged(layout, "contracts")}
        assert seen == {"SIRET", "HORS_UE"}

    def test_a_type_this_project_has_no_name_for_passes_through(
        self, layout: Layout
    ) -> None:
        stage(layout, [decp_row(titulaire_typeIdentifiant="AUTRE")])
        row = staged(layout, "contracts")[0]
        assert row["supplier_id_type"] == "AUTRE"
        assert row["supplier_id_type_raw"] == "AUTRE"


class TestDates:
    def test_an_implausible_date_is_marked_and_carried(self, layout: Layout) -> None:
        # A platform's empty date lands on 0001-01-01. It is 0.028% of the real
        # file, which is the register being wrong rather than us misreading it.
        rows = [decp_row(uid=f"OK{n}") for n in range(200)]
        rows.append(decp_row(uid="BAD", dateNotification=date(1, 1, 1)))
        stage(layout, rows)
        marked = [
            row for row in staged(layout, "contracts") if not row["dates_plausible"]
        ]
        assert [row["uid"] for row in marked] == ["BAD"]

    def test_a_file_that_is_mostly_implausible_stops_the_stage(
        self, layout: Layout
    ) -> None:
        with pytest.raises(fr_decp.StageError, match="reading the file wrongly"):
            stage(
                layout,
                [
                    decp_row(uid=f"X{n}", dateNotification=date(1, 1, 1))
                    for n in range(10)
                ],
            )


class TestCommuneBuyers:
    def test_a_commune_buyer_is_mapped_to_its_commune(self, layout: Layout) -> None:
        stage(layout, [decp_row(acheteur_categorie="Commune")])
        mapped = staged(layout, "commune_buyers")
        assert len(mapped) == 1
        assert mapped[0]["commune_code"] == "93001"
        assert mapped[0]["commune_code_count"] == 1

    def test_a_buyer_that_is_not_a_commune_is_not_mapped(self, layout: Layout) -> None:
        stage(layout, [decp_row(acheteur_categorie="Groupement de communes")])
        assert staged(layout, "commune_buyers") == []

    def test_a_siren_carrying_two_communes_keeps_both_and_says_so(
        self, layout: Layout
    ) -> None:
        # Four SIRENs on the real file do this and one of them carries sixteen
        # commune codes. Picking one would invent a fact.
        stage(
            layout,
            [
                decp_row(uid="A", acheteur_commune_code="93001"),
                decp_row(uid="B", acheteur_commune_code="93002"),
            ],
        )
        mapped = staged(layout, "commune_buyers")
        assert len(mapped) == 2
        assert {row["commune_code_count"] for row in mapped} == {2}


class TestDeterminism:
    def test_staging_twice_gives_the_same_bytes(self, layout: Layout) -> None:
        rows = [decp_row(uid=f"U{n}", montant=float(n)) for n in range(50)]
        stage(layout, rows)
        first = {
            table: (
                layout.staged(fr_decp.SOURCE, SNAPSHOT) / f"{table}.parquet"
            ).read_bytes()
            for table in ("contracts", "contract_versions", "commune_buyers")
        }
        stage(layout, rows)
        for table, written in first.items():
            path = layout.staged(fr_decp.SOURCE, SNAPSHOT) / f"{table}.parquet"
            assert path.read_bytes() == written, table

    def test_the_row_order_of_the_input_does_not_change_the_output(
        self, layout: Layout
    ) -> None:
        rows = [decp_row(uid=f"U{n}", montant=float(n)) for n in range(50)]
        stage(layout, rows)
        forwards = (
            layout.staged(fr_decp.SOURCE, SNAPSHOT) / "contracts.parquet"
        ).read_bytes()
        stage(layout, list(reversed(rows)))
        assert (
            layout.staged(fr_decp.SOURCE, SNAPSHOT) / "contracts.parquet"
        ).read_bytes() == forwards


class TestReport:
    def test_it_writes_aggregates_and_no_row_content(self, layout: Layout) -> None:
        stage(layout, [decp_row(uid="A"), decp_row(uid="B", acheteur_categorie=None)])
        path = layout.reports() / f"{fr_decp.SOURCE}-{SNAPSHOT}.json"
        report = json.loads(path.read_text(encoding="utf-8"))

        assert report["rows_published"] == 2
        assert report["commune_supplier_pairs"] == 1
        # Names are the thing that must not be in it (constraint 13).
        assert "Fixtureville" not in path.read_text(encoding="utf-8")
        assert "Entreprise Fixture" not in path.read_text(encoding="utf-8")


class TestRefusals:
    def test_staging_without_fetching_says_so(self, layout: Layout) -> None:
        with pytest.raises(fr_decp.StageError, match="Fetch it first"):
            fr_decp.stage(layout, SNAPSHOT)


def client_for(
    handler: Callable[[httpx.Request], httpx.Response],
) -> SourceClient:
    """A client wired to a scripted data.gouv.fr. No socket is opened."""
    return SourceClient(
        source=fr_decp.SOURCE,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        limiter=RateLimiter(rate=1000.0, capacity=1000.0),
    )


def listing() -> httpx.Response:
    """What the dataset API returns when both resources are there."""
    return httpx.Response(
        200,
        json={
            "resources": [
                {"title": title, "url": f"https://files.invalid/{title}"}
                for title, _ in fr_decp.FILES
            ]
        },
    )


class TestFetch:
    def handler(self, calls: list[str]) -> Callable[[httpx.Request], httpx.Response]:
        def respond(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "/api/1/datasets/" in str(request.url):
                return listing()
            return httpx.Response(200, content=b"bytes")

        return respond

    def test_it_downloads_both_resources_and_records_them(self, layout: Layout) -> None:
        calls: list[str] = []
        entries = fr_decp.fetch(client_for(self.handler(calls)), layout, SNAPSHOT)

        assert [entry["path"] for entry in entries] == ["decp.parquet", "schema.json"]
        assert all(entry["licence"] == fr_decp.LICENCE for entry in entries)
        raw = layout.raw(fr_decp.SOURCE, SNAPSHOT)
        assert (raw / "decp.parquet").read_bytes() == b"bytes"

    def test_fetching_twice_downloads_nothing_the_second_time(
        self, layout: Layout
    ) -> None:
        # At 247MB this is not a nicety: it is what makes an interrupted run
        # resumable without asking data.gouv.fr for the whole file again.
        calls: list[str] = []
        handler = self.handler(calls)
        fr_decp.fetch(client_for(handler), layout, SNAPSHOT)
        before = len(calls)

        assert fr_decp.fetch(client_for(handler), layout, SNAPSHOT) == []
        assert len(calls) == before

    def test_a_renamed_resource_says_what_the_dataset_now_lists(
        self, layout: Layout
    ) -> None:
        def respond(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"resources": [{"title": "autre.parquet"}]})

        with pytest.raises(fr_decp.StageError, match=r"autre\.parquet"):
            fr_decp.fetch(client_for(respond), layout, SNAPSHOT)


class TestRowIdentity:
    def test_two_rows_this_project_cannot_tell_apart_stop_the_stage(
        self, layout: Layout
    ) -> None:
        # The id is a hash of every published field staged here, so a collision
        # means the publisher changed something and every count keyed on the id
        # is wrong until IDENTITY_COLUMNS catches up. On the real file this is
        # what `titulaire_typeIdentifiant` is in the key for.
        row = decp_row()
        with pytest.raises(fr_decp.StageError, match="share a decp_row_id"):
            stage(layout, [dict(row), dict(row)])


class TestAttributeLineage:
    """ADR-0007: a buyer's declaration and a consolidator's join are cited apart.

    The split is data rather than prose so that the export can read it, and this
    class is what stops a new column arriving without anyone deciding which kind
    of fact it is.
    """

    def test_every_staged_column_has_an_origin(self) -> None:
        assert set(fr_decp.ATTRIBUTE_ORIGIN) == set(fr_decp.CONTRACTS.names)

    def test_every_origin_is_one_of_the_three(self) -> None:
        assert set(fr_decp.ATTRIBUTE_ORIGIN.values()) == {
            fr_decp.DECLARED,
            fr_decp.DERIVED,
            fr_decp.IDENTITY,
        }

    def test_the_two_columns_the_adr_was_written_about_are_derived(self) -> None:
        assert fr_decp.ATTRIBUTE_ORIGIN["buyer_category"] == fr_decp.DERIVED
        assert fr_decp.ATTRIBUTE_ORIGIN["buyer_commune_code"] == fr_decp.DERIVED
        # And the buyer's own identifier is not.
        assert fr_decp.ATTRIBUTE_ORIGIN["buyer_siret"] == fr_decp.DECLARED

    def test_derived_columns_are_listed_for_the_export(self) -> None:
        listed = fr_decp.derived_columns()
        assert "buyer_commune_code" in listed
        assert "buyer_siret" not in listed
        assert listed == tuple(sorted(listed))


class TestProvenanceOnEveryRow:
    def test_a_row_carries_its_source_url_and_retrieval_time(
        self, layout: Layout
    ) -> None:
        # Constraint 2 wants a source, a URL and a retrieval time on anything
        # exported. Copying them on to the row means an export never has to go
        # back to a manifest to find out where an attribute came from.
        raw = layout.raw(fr_decp.SOURCE, SNAPSHOT)
        write_decp(raw / "decp.parquet", [decp_row()])
        append_manifest(
            layout.manifest(fr_decp.SOURCE, SNAPSHOT),
            {
                "source": fr_decp.SOURCE,
                "url": "https://files.invalid/decp.parquet",
                "path": "decp.parquet",
                "sha256": "0" * 64,
                "bytes": 1,
                "retrieved_at": "2026-09-19T10:43:32+00:00",
                "licence": fr_decp.LICENCE,
                "status": 200,
            },
        )
        fr_decp.stage(layout, SNAPSHOT)

        row = staged(layout, "contracts")[0]
        assert row["source_url"] == "https://files.invalid/decp.parquet"
        assert row["retrieved_at"] == "2026-09-19T10:43:32+00:00"


class TestBuyerAssertionBinding:
    """The handle a buyer verification attaches to.

    `decp_row_id` hashes only the published fields, so it does not move when the
    consolidator recomputes a commune code. That is right for a row id and wrong
    for binding a review to the values it examined, which is what the handoff
    means by "decp_row_id alone cannot bind a buyer check to its inputs".
    """

    def test_changing_the_enrichment_changes_the_binding(self, layout: Layout) -> None:
        stage(layout, [decp_row(acheteur_commune_code="93001")])
        first = staged(layout, "contracts")[0]

        stage(layout, [decp_row(acheteur_commune_code="93002")])
        second = staged(layout, "contracts")[0]

        assert first["decp_row_id"] == second["decp_row_id"]
        assert first["buyer_assertion_id"] != second["buyer_assertion_id"]

    def test_changing_the_category_changes_the_binding(self, layout: Layout) -> None:
        stage(layout, [decp_row(acheteur_categorie="Commune")])
        first = staged(layout, "contracts")[0]
        stage(layout, [decp_row(acheteur_categorie="Groupement de communes")])
        second = staged(layout, "contracts")[0]
        assert first["buyer_assertion_id"] != second["buyer_assertion_id"]

    def test_two_rows_asserting_the_same_buyer_share_a_binding(
        self, layout: Layout
    ) -> None:
        # One review can cover every contract that makes the same claim.
        stage(
            layout,
            [
                decp_row(uid="A", acheteur_commune_code="93001"),
                decp_row(uid="B", acheteur_commune_code="93001"),
            ],
        )
        ids = {str(row["buyer_assertion_id"]) for row in staged(layout, "contracts")}
        assert len(ids) == 1
