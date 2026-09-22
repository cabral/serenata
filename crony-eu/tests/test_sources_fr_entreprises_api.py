# SPDX-License-Identifier: AGPL-3.0-only
"""The company API adapter, and the refusals that are the point of it.

A search endpoint is being used to answer an identity question. That is fine as
long as the code never treats "the closest thing the search returned" as "the
thing I asked for", and ADR-0007 Amendment 1 says so in as many words because a
best match here would attach a wrong buyer to correct-looking provenance.

So most of this file is the four ways resolution fails. There is deliberately no
test for a best-match path, because there is deliberately no best-match path.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pyarrow.parquet as pq
import pytest
from crony_eu.http import RateLimiter, SourceClient
from crony_eu.paths import Layout
from crony_eu.sources import fr_entreprises_api as api
from fakes import (
    api_establishment,
    api_officer,
    api_response,
    api_unit,
    siren,
    siret,
)

SNAPSHOT = "2026-09-22"
SUPPLIER = siren("81230001")
BUYER = siret("21740010")


@pytest.fixture
def layout(outside_repo: Path) -> Layout:
    made = Layout(outside_repo)
    made.create()
    return made


def client_for(
    handler: Callable[[httpx.Request], httpx.Response],
) -> SourceClient:
    return SourceClient(
        source=api.SOURCE,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        limiter=RateLimiter(rate=1000.0, capacity=1000.0),
    )


class TestResolveSiren:
    def test_one_result_with_the_asked_siren_resolves(self) -> None:
        ask = api.Ask("siren", SUPPLIER)
        payload = api_response([api_unit(unit_siren=SUPPLIER)])
        outcome = api.resolve(payload, ask)
        assert isinstance(outcome, api.Resolved)
        assert outcome.unit["siren"] == SUPPLIER

    def test_nothing_found_is_a_reason_not_an_empty_result(self) -> None:
        outcome = api.resolve(api_response([]), api.Ask("siren", SUPPLIER))
        assert isinstance(outcome, api.Unresolved)
        assert outcome.reason == api.NOT_FOUND

    def test_several_results_refuse_rather_than_pick_the_first(self) -> None:
        payload = api_response(
            [api_unit(unit_siren=SUPPLIER), api_unit(unit_siren=siren("81230002"))]
        )
        outcome = api.resolve(payload, api.Ask("siren", SUPPLIER))
        assert isinstance(outcome, api.Unresolved)
        assert outcome.reason == api.SEVERAL_RESULTS
        assert outcome.results == 2

    def test_one_result_for_a_different_siren_is_not_a_match(self) -> None:
        payload = api_response([api_unit(unit_siren=siren("81230002"))])
        outcome = api.resolve(payload, api.Ask("siren", SUPPLIER))
        assert isinstance(outcome, api.Unresolved)
        assert outcome.reason == api.NO_EXACT_MATCH


class TestResolveSiret:
    """The buyer side, which is what ADR-0007 Amendment 1 governs."""

    def test_the_exact_establishment_resolves(self) -> None:
        payload = api_response(
            [
                api_unit(
                    unit_siren=BUYER[:9],
                    nature_juridique="7210",
                    establishments=[api_establishment(establishment_siret=BUYER)],
                )
            ]
        )
        outcome = api.resolve(payload, api.Ask("siret", BUYER))
        assert isinstance(outcome, api.Resolved)
        assert outcome.establishment is not None
        assert outcome.establishment["siret"] == BUYER
        assert outcome.unit["nature_juridique"] == "7210"

    def test_a_result_with_no_establishments_refuses(self) -> None:
        # What a SIREN query actually returns: the legal unit and its head
        # office, with nothing saying which establishment was matched. The head
        # office is not a substitute and the code must not accept it as one.
        payload = api_response([api_unit(unit_siren=BUYER[:9], establishments=[])])
        outcome = api.resolve(payload, api.Ask("siret", BUYER))
        assert isinstance(outcome, api.Unresolved)
        assert outcome.reason == api.NO_EXACT_MATCH

    def test_establishments_that_are_not_the_one_asked_for_refuse(self) -> None:
        other = siret("21740011")
        payload = api_response(
            [
                api_unit(
                    unit_siren=BUYER[:9],
                    establishments=[api_establishment(establishment_siret=other)],
                )
            ]
        )
        outcome = api.resolve(payload, api.Ask("siret", BUYER))
        assert isinstance(outcome, api.Unresolved)
        assert outcome.reason == api.NO_ESTABLISHMENT

    def test_the_same_siret_twice_refuses_rather_than_choosing(self) -> None:
        payload = api_response(
            [
                api_unit(
                    unit_siren=BUYER[:9],
                    establishments=[
                        api_establishment(establishment_siret=BUYER, commune="74010"),
                        api_establishment(establishment_siret=BUYER, commune="74011"),
                    ],
                )
            ]
        )
        outcome = api.resolve(payload, api.Ask("siret", BUYER))
        assert isinstance(outcome, api.Unresolved)
        assert outcome.reason == api.SEVERAL_RESULTS


def staged(layout: Layout, table: str) -> list[dict[str, object]]:
    path = layout.staged(api.SOURCE, SNAPSHOT) / f"{table}.parquet"
    return [dict(row) for row in pq.read_table(path).to_pylist()]


def archive(
    layout: Layout, asks: list[api.Ask], bodies: list[dict[str, object]]
) -> None:
    """Write responses into a raw snapshot as `fetch` would have."""
    import hashlib
    import json

    from crony_eu.http import append_manifest

    raw = layout.raw(api.SOURCE, SNAPSHOT)
    raw.mkdir(parents=True, exist_ok=True)
    for ask, body in zip(asks, bodies, strict=True):
        text = json.dumps(body)
        (raw / ask.filename).write_text(text, encoding="utf-8")
        append_manifest(
            layout.manifest(api.SOURCE, SNAPSHOT),
            {
                "source": api.SOURCE,
                "url": f"{api.ENDPOINT}?q={ask.value}",
                "path": ask.filename,
                "sha256": hashlib.sha256(text.encode()).hexdigest(),
                "bytes": len(text),
                "retrieved_at": "2026-09-22T09:00:00+00:00",
                "licence": api.LICENCE,
                "status": 200,
            },
        )


class TestStageSuppliers:
    def test_a_company_and_its_natural_person_officers_are_staged(
        self, layout: Layout
    ) -> None:
        archive(
            layout,
            [api.Ask("siren", SUPPLIER)],
            [
                api_response(
                    [
                        api_unit(
                            unit_siren=SUPPLIER,
                            nature_juridique="5515",
                            officers=[
                                api_officer(surname="UNDEUX", birth="1971-04"),
                                api_officer(surname="TROISQUATRE", birth="1960-11"),
                                api_officer(kind="personne morale"),
                            ],
                        )
                    ]
                )
            ],
        )
        written = api.stage(layout, SNAPSHOT)

        assert written["companies"] == 1
        assert written["officers"] == 2
        assert written["officer_companies"] == 1

        company = staged(layout, "companies")[0]
        # What F1's exclusion list needs and DECP could not give.
        assert company["nature_juridique"] == "5515"
        assert company["officer_count"] == 3

    def test_an_officer_carries_no_role_dates_and_says_so(self, layout: Layout) -> None:
        # Measured, not assumed: this source publishes a current-officer list.
        # `absent` is a value so that a later reader can tell it from a date this
        # project failed to read.
        archive(
            layout,
            [api.Ask("siren", SUPPLIER)],
            [api_response([api_unit(unit_siren=SUPPLIER, officers=[api_officer()])])],
        )
        api.stage(layout, SNAPSHOT)
        officer = staged(layout, "officers")[0]
        assert officer["role_start"] is None
        assert officer["role_end"] is None
        assert officer["role_date_source"] == "none"
        assert officer["role_date_semantics"] == "absent"

    def test_a_birth_month_is_kept_and_a_year_only_value_is_not(
        self, layout: Layout
    ) -> None:
        # ADR-0003 needs YYYY-MM. A four-character value is a year, and putting it
        # in `birth_ym` would make a key that matches the wrong people.
        archive(
            layout,
            [api.Ask("siren", SUPPLIER)],
            [
                api_response(
                    [
                        api_unit(
                            unit_siren=SUPPLIER,
                            officers=[
                                api_officer(surname="UNDEUX", birth="1971-04"),
                                api_officer(surname="CINQSIX", birth="1971"),
                                api_officer(surname="SEPTHUIT", birth=None),
                            ],
                        )
                    ]
                )
            ],
        )
        api.stage(layout, SNAPSHOT)
        keys = sorted(
            (str(row["surname_birth_raw"]), row["birth_ym"])
            for row in staged(layout, "officers")
        )
        assert keys == [("CINQSIX", None), ("SEPTHUIT", None), ("UNDEUX", "1971-04")]

    def test_officer_ids_are_stable_and_distinct(self, layout: Layout) -> None:
        # One person can hold two roles in one company, and two rows that differ
        # in nothing visible still have to be two rows.
        archive(
            layout,
            [api.Ask("siren", SUPPLIER)],
            [
                api_response(
                    [
                        api_unit(
                            unit_siren=SUPPLIER,
                            officers=[
                                api_officer(role="président"),
                                api_officer(role="directeur général"),
                            ],
                        )
                    ]
                )
            ],
        )
        api.stage(layout, SNAPSHOT)
        ids = [str(row["officer_row_id"]) for row in staged(layout, "officers")]
        assert len(set(ids)) == 2

    def test_staging_twice_gives_the_same_bytes(self, layout: Layout) -> None:
        archive(
            layout,
            [api.Ask("siren", SUPPLIER)],
            [api_response([api_unit(unit_siren=SUPPLIER, officers=[api_officer()])])],
        )
        api.stage(layout, SNAPSHOT)
        path = layout.staged(api.SOURCE, SNAPSHOT) / "officers.parquet"
        first = path.read_bytes()
        api.stage(layout, SNAPSHOT)
        assert path.read_bytes() == first


class TestStageBuyerEvidence:
    def test_a_resolved_buyer_records_what_the_registry_said(
        self, layout: Layout
    ) -> None:
        archive(
            layout,
            [api.Ask("siret", BUYER)],
            [
                api_response(
                    [
                        api_unit(
                            unit_siren=BUYER[:9],
                            nature_juridique="7210",
                            establishments=[
                                api_establishment(
                                    establishment_siret=BUYER, commune="74010"
                                )
                            ],
                        )
                    ]
                )
            ],
        )
        api.stage(layout, SNAPSHOT)
        row = staged(layout, "buyer_evidence")[0]

        assert row["resolved"] is True
        assert row["nature_juridique"] == "7210"
        assert row["establishment_commune_code"] == "74010"
        assert row["establishment_state"] == "A"
        assert row["evidence_sha256"]
        # The stage records and decides nothing: there is no column here that
        # says the mapping is corroborated. That is the maintainer's, under
        # ADR-0007 Amendment 1.
        assert "buyer_identity_corroborated" not in row

    def test_an_unresolved_buyer_is_recorded_with_its_reason(
        self, layout: Layout
    ) -> None:
        archive(layout, [api.Ask("siret", BUYER)], [api_response([])])
        api.stage(layout, SNAPSHOT)

        row = staged(layout, "buyer_evidence")[0]
        assert row["resolved"] is False
        assert row["reason"] == api.NOT_FOUND
        assert row["establishment_commune_code"] is None

        missing = staged(layout, "officers_missing")[0]
        assert (missing["kind"], missing["value"]) == ("siret", BUYER)

    def test_a_closed_establishment_is_staged_with_its_dates(
        self, layout: Layout
    ) -> None:
        # Amendment 1: a closure today does not disqualify a contract that
        # predates it, so the dates are staged and no rule is applied here.
        archive(
            layout,
            [api.Ask("siret", BUYER)],
            [
                api_response(
                    [
                        api_unit(
                            unit_siren=BUYER[:9],
                            nature_juridique="7210",
                            establishments=[
                                api_establishment(
                                    establishment_siret=BUYER,
                                    state="F",
                                    created="2015-12-15",
                                    closed="2025-01-01",
                                )
                            ],
                        )
                    ]
                )
            ],
        )
        api.stage(layout, SNAPSHOT)
        row = staged(layout, "buyer_evidence")[0]
        assert row["establishment_state"] == "F"
        assert row["establishment_created"] == "2015-12-15"
        assert row["establishment_closed"] == "2025-01-01"
        assert row["resolved"] is True


class TestFetch:
    def test_it_asks_once_per_identifier_and_is_resumable(
        self, layout: Layout, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        asks = [api.Ask("siren", SUPPLIER), api.Ask("siret", BUYER)]
        monkeypatch.setattr(api, "asks_for_scope", lambda layout, scope: asks)

        calls: list[str] = []

        def respond(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, json=api_response([api_unit()]))

        entries = api.fetch(client_for(respond), layout, SNAPSHOT, "74")
        assert len(entries) == 2
        assert len(calls) == 2

        # A second run asks nothing: at one request per supplier and per buyer,
        # resuming is the difference between a minute and an apology.
        assert api.fetch(client_for(respond), layout, SNAPSHOT, "74") == []
        assert len(calls) == 2

    def test_a_refusal_is_archived_rather_than_re_asked(
        self, layout: Layout, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            api, "asks_for_scope", lambda layout, scope: [api.Ask("siret", BUYER)]
        )
        calls: list[str] = []

        def respond(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            return httpx.Response(200, json=api_response([]))

        api.fetch(client_for(respond), layout, SNAPSHOT, "74")
        api.stage(layout, SNAPSHOT)
        assert staged(layout, "buyer_evidence")[0]["resolved"] is False
        assert len(calls) == 1


class TestRefusals:
    def test_staging_without_fetching_says_so(self, layout: Layout) -> None:
        with pytest.raises(api.SourceError, match="Fetch it first"):
            api.stage(layout, SNAPSHOT)

    def test_a_manifest_entry_with_no_file_stops_the_stage(
        self, layout: Layout
    ) -> None:
        from crony_eu.http import append_manifest

        append_manifest(
            layout.manifest(api.SOURCE, SNAPSHOT),
            {
                "source": api.SOURCE,
                "url": api.ENDPOINT,
                "path": "siren-000000000.json",
                "sha256": "0" * 64,
                "bytes": 0,
                "retrieved_at": "2026-09-22T09:00:00+00:00",
                "licence": api.LICENCE,
                "status": 200,
            },
        )
        with pytest.raises(api.SourceError, match="not on disk"):
            api.stage(layout, SNAPSHOT)


class TestAsksForScope:
    """Which identifiers the slice needs, read from staged DECP rather than asked.

    Both sides come out of one staged snapshot, so the set of questions is a
    function of data on disk and not of what the API happens to hold today. That
    is what makes a run repeatable.
    """

    def stage_decp(self, layout: Layout, rows: list[dict[str, object]]) -> None:
        from crony_eu.sources import fr_decp
        from fakes import write_decp

        write_decp(layout.raw(fr_decp.SOURCE, "2026-09-19") / "decp.parquet", rows)
        fr_decp.stage(layout, "2026-09-19")

    def test_it_asks_for_suppliers_by_siren_and_buyers_by_siret(
        self, layout: Layout
    ) -> None:
        from fakes import decp_row

        supplier = siret("81230001")
        buyer = siret("21740010")
        self.stage_decp(
            layout,
            [
                decp_row(
                    acheteur_id=buyer,
                    acheteur_commune_code="74010",
                    titulaire_id=supplier,
                )
            ],
        )
        asks = api.asks_for_scope(layout, "74")
        assert sorted((a.kind, a.value) for a in asks) == [
            ("siren", supplier[:9]),
            ("siret", buyer),
        ]

    def test_a_commune_outside_the_scope_is_not_asked_about(
        self, layout: Layout
    ) -> None:
        from fakes import decp_row

        self.stage_decp(
            layout,
            [
                decp_row(uid="IN", acheteur_commune_code="74010"),
                decp_row(
                    uid="OUT",
                    acheteur_commune_code="93001",
                    titulaire_id=siret("81230002"),
                ),
            ],
        )
        values = {a.value for a in api.asks_for_scope(layout, "74")}
        assert siret("81230002")[:9] not in values

    def test_a_buyer_that_is_not_a_commune_is_not_asked_about(
        self, layout: Layout
    ) -> None:
        from fakes import decp_row

        self.stage_decp(
            layout,
            [
                decp_row(
                    acheteur_categorie="Groupement de communes",
                    acheteur_commune_code="74010",
                )
            ],
        )
        assert api.asks_for_scope(layout, "74") == []

    def test_each_identifier_is_asked_about_once(self, layout: Layout) -> None:
        from fakes import decp_row

        self.stage_decp(
            layout,
            [decp_row(uid=f"U{n}", acheteur_commune_code="74010") for n in range(5)],
        )
        asks = api.asks_for_scope(layout, "74")
        assert len(asks) == len({(a.kind, a.value) for a in asks}) == 2

    def test_it_says_which_command_to_run_when_decp_is_not_staged(
        self, layout: Layout
    ) -> None:
        with pytest.raises(api.SourceError, match="crony stage fr-decp"):
            api.asks_for_scope(layout, "74")
