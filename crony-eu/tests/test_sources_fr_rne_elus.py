# SPDX-License-Identifier: AGPL-3.0-only
"""Reading the Répertoire national des élus, against invented councillors.

Every fixture row is obviously synthetic: `NOMDEXEMPLE` is not a surname and
commune `99001` is not a commune. Constraint 1 says no real person's record
reaches this repository, not even with the name changed, and a plausible
fabrication would be worse than a real one because it could be mistaken for a
finding.

Three things here are doing real work rather than exercising plumbing.

- **The maires files have no function column.** The published header proves it,
  and the module supplies `Maire` rather than leaving a null that would make a
  mayor indistinguishable from a councillor with no delegated function. F1's
  Code pénal 432-12 tag reads that field, so a null there would silently stop
  the tag firing.
- **A mayor appears in two files and is one person.** `elu_person` has to group
  them, or every mayor would be counted twice in the base rate's denominator.
- **A malformed date stops the stage and does not print itself.** It may be a
  birth date (constraint 13).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import duckdb
import httpx
import pytest
from crony_eu.http import RateLimiter, SourceClient
from crony_eu.paths import Layout
from crony_eu.sources import fr_rne_elus
from crony_eu.sources.fr_rne_elus import SOURCE, StageError, stage
from fakes import Elu, write_rne_snapshot

SNAPSHOT = "2026-09-16"


def staged(root: Path, table: str) -> duckdb.DuckDBPyRelation:
    path = Layout(root).staged(SOURCE, SNAPSHOT) / f"{table}.parquet"
    return duckdb.sql(f"SELECT * FROM read_parquet('{path.as_posix()}')")


def client_for(handler: Callable[[httpx.Request], httpx.Response]) -> SourceClient:
    """A client wired to a scripted data.gouv.fr. No socket is opened."""
    return SourceClient(
        source=SOURCE,
        client=httpx.Client(transport=httpx.MockTransport(handler)),
        limiter=RateLimiter(rate=1000.0, capacity=1000.0),
    )


def listing() -> httpx.Response:
    """What the dataset API returns when every expected resource is there."""
    return httpx.Response(
        200,
        json={
            "resources": [
                {
                    "title": published.title,
                    "url": f"https://files.invalid/{published.title}",
                }
                for published in fr_rne_elus.FILES
            ]
        },
    )


class TestStaging:
    def test_a_council_round_trips(self, tmp_path: Path) -> None:
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[Elu(surname=f"NOMDEXEMPLE{n}") for n in range(3)],
        )

        written = stage(Layout(tmp_path), SNAPSHOT)

        assert written["elus"] == 3
        assert written["elu_person"] == 3

    def test_every_declared_column_is_written(self, tmp_path: Path) -> None:
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu()])
        stage(Layout(tmp_path), SNAPSHOT)

        assert staged(tmp_path, "elus").columns == list(fr_rne_elus.ELUS.names)
        assert staged(tmp_path, "elu_person").columns == list(
            fr_rne_elus.ELU_PERSON.names
        )

    def test_an_empty_file_is_not_an_error(self, tmp_path: Path) -> None:
        # A département with no councillors in one of the four files is a fact
        # about the file, not a failure to read it.
        write_rne_snapshot(tmp_path, SNAPSHOT)

        assert stage(Layout(tmp_path), SNAPSHOT) == {"elus": 0, "elu_person": 0}

    def test_a_missing_snapshot_says_to_fetch_it(self, tmp_path: Path) -> None:
        Layout(tmp_path).create()

        with pytest.raises(StageError, match="Fetch it first"):
            stage(Layout(tmp_path), SNAPSHOT)

    def test_the_commune_code_keeps_its_leading_zero(self, tmp_path: Path) -> None:
        # The bug this prevents: type sniffing reads `01001` as the integer
        # 1001, and the commune no longer joins to anything.
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu(commune_code="01001")])
        stage(Layout(tmp_path), SNAPSHOT)

        assert staged(tmp_path, "elus").fetchall()[0][6] == "01001"


class TestDates:
    @pytest.mark.parametrize("published", ["1971-04-03", "03/04/1971"])
    def test_both_published_formats_read_as_the_same_date(
        self, tmp_path: Path, published: str
    ) -> None:
        # The register switched to ISO 8601 in August 2026 and files of both
        # vintages are in circulation.
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu(birth_date=published)])
        stage(Layout(tmp_path), SNAPSHOT)

        rows = staged(tmp_path, "elus").project("birth_date, birth_ym").fetchall()
        assert str(rows[0][0]) == "1971-04-03"
        assert rows[0][1] == "1971-04"

    def test_an_empty_date_is_null_not_an_error(self, tmp_path: Path) -> None:
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu(birth_date="")])
        stage(Layout(tmp_path), SNAPSHOT)

        assert staged(tmp_path, "elus").project("birth_date, birth_ym").fetchall()[
            0
        ] == (
            None,
            None,
        )

    def test_a_malformed_date_stops_the_stage(self, tmp_path: Path) -> None:
        write_rne_snapshot(
            tmp_path, SNAPSHOT, cm_current=[Elu(birth_date="03 avril 1971")]
        )

        with pytest.raises(
            StageError, match="matches none of the published date shapes"
        ):
            stage(Layout(tmp_path), SNAPSHOT)

    def test_the_error_names_the_row_and_not_the_value(self, tmp_path: Path) -> None:
        # Constraint 13. The row number is enough to find it; the value is a
        # birth date and an agent session does not print one.
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[Elu(), Elu(birth_date="pas une date")],
        )

        with pytest.raises(StageError) as raised:
            stage(Layout(tmp_path), SNAPSHOT)

        message = str(raised.value)
        assert "row 2" in message
        assert "pas une date" not in message
        assert "constraint 13" in message

    def test_an_ambiguous_looking_date_is_read_one_way_only(
        self, tmp_path: Path
    ) -> None:
        # 03/04/1971 is April in French order and March in American order. The
        # accepted format list is closed so that it cannot be both.
        write_rne_snapshot(
            tmp_path, SNAPSHOT, cm_current=[Elu(birth_date="03/04/1971")]
        )
        stage(Layout(tmp_path), SNAPSHOT)

        assert (
            staged(tmp_path, "elus").project("birth_ym").fetchall()[0][0] == "1971-04"
        )


class TestTheTwoDigitYear:
    """The bug real data found: the pre-election extracts publish DD/MM/YY."""

    def test_it_is_read_with_the_right_century(self, tmp_path: Path) -> None:
        # `%d/%m/%Y` accepts `03/04/71` and returns the year 71. Staging the
        # real register that way put 520,240 rows in the first century.
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_pre_election=[Elu(birth_date="03/04/71", mandate_start="22/03/20")],
        )
        stage(Layout(tmp_path), SNAPSHOT)

        rows = staged(tmp_path, "elus").project("birth_ym, mandate_start").fetchall()
        assert rows[0][0] == "1971-04"
        assert str(rows[0][1]) == "2020-03-22"

    def test_a_year_that_would_be_in_the_future_goes_back_a_century(
        self, tmp_path: Path
    ) -> None:
        # A councillor born in `30` was born in 1930, because the register
        # cannot publish a birth in 2030.
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_pre_election=[Elu(birth_date="18/05/30", mandate_start="22/03/20")],
        )
        stage(Layout(tmp_path), SNAPSHOT)

        assert (
            staged(tmp_path, "elus").project("birth_ym").fetchall()[0][0] == "1930-05"
        )

    def test_the_two_vintages_can_be_staged_together(self, tmp_path: Path) -> None:
        # Which is the real arrangement: the current files are ISO 8601 and the
        # pre-election files are DD/MM/YY, in one snapshot.
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[Elu(birth_date="1971-04-03")],
            cm_pre_election=[Elu(birth_date="03/04/71", mandate_start="22/03/20")],
        )
        stage(Layout(tmp_path), SNAPSHOT)

        keys = staged(tmp_path, "elus").project("birth_ym").fetchall()
        assert {key for (key,) in keys} == {"1971-04"}


class TestPlausibilityGate:
    """Parsed is not right, which is the lesson of those 520,240 rows."""

    def test_a_mandate_starting_in_the_year_20_stops_the_stage(
        self, tmp_path: Path
    ) -> None:
        # The failure that would have mattered most: a mandate beginning in the
        # year 20 precedes every contract ever notified, so F1's mandate
        # overlap would have been true for everyone.
        write_rne_snapshot(
            tmp_path, SNAPSHOT, cm_current=[Elu(mandate_start="0020-05-18")]
        )

        with pytest.raises(StageError, match="outside 1900"):
            stage(Layout(tmp_path), SNAPSHOT)

    def test_a_birth_before_1900_stops_the_stage(self, tmp_path: Path) -> None:
        write_rne_snapshot(
            tmp_path, SNAPSHOT, cm_current=[Elu(birth_date="0071-04-03")]
        )

        with pytest.raises(StageError, match="outside 1900"):
            stage(Layout(tmp_path), SNAPSHOT)

    def test_a_date_after_the_snapshot_stops_the_stage(self, tmp_path: Path) -> None:
        # A register cannot publish a mandate that has not started.
        write_rne_snapshot(
            tmp_path, SNAPSHOT, cm_current=[Elu(mandate_start="2030-01-01")]
        )

        with pytest.raises(StageError, match="outside 1900"):
            stage(Layout(tmp_path), SNAPSHOT)

    def test_the_message_names_the_row_and_not_the_value(self, tmp_path: Path) -> None:
        write_rne_snapshot(
            tmp_path, SNAPSHOT, cm_current=[Elu(), Elu(mandate_start="0020-05-18")]
        )

        with pytest.raises(StageError) as raised:
            stage(Layout(tmp_path), SNAPSHOT)

        assert "row 2" in str(raised.value)
        assert "0020-05-18" not in str(raised.value)

    def test_a_believable_snapshot_passes(self, tmp_path: Path) -> None:
        # The gate has to let the real register through, or it is just a way of
        # never staging anything.
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu()])

        assert stage(Layout(tmp_path), SNAPSHOT)["elus"] == 1

    def test_a_rare_typo_is_carried_rather_than_fatal(self, tmp_path: Path) -> None:
        # The real register has exactly one councillor with a birth year in the
        # 1000s, out of 511,225. Stopping for that would mean never staging
        # France until a prefecture fixes a typo.
        good = [Elu(surname=f"NOMDEXEMPLE{n}") for n in range(200)]
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[*good, Elu(surname="NOMDEXEMPLE999", birth_date="1071-04-03")],
        )

        assert stage(Layout(tmp_path), SNAPSHOT)["elus"] == 201

    def test_the_carried_row_is_marked_rather_than_trusted(
        self, tmp_path: Path
    ) -> None:
        # Constraint 9 does the rest: an implausible date cannot establish an
        # overlap, and an unknown overlap cannot reach a case packet.
        good = [Elu(surname=f"NOMDEXEMPLE{n}") for n in range(200)]
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[*good, Elu(surname="NOMDEXEMPLE999", birth_date="1071-04-03")],
        )
        stage(Layout(tmp_path), SNAPSHOT)

        counts = (
            staged(tmp_path, "elus")
            .aggregate("dates_plausible, count(*) AS rows")
            .fetchall()
        )
        assert sorted(counts) == [(False, 1), (True, 200)]

    def test_a_whole_file_of_them_still_stops_the_stage(self, tmp_path: Path) -> None:
        # The difference that matters: one typo is the register, every row is
        # this project reading the file wrongly.
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[
                Elu(surname=f"NOMDEXEMPLE{n}", birth_date="1071-04-03")
                for n in range(20)
            ],
        )

        with pytest.raises(StageError, match="reading the file wrongly"):
            stage(Layout(tmp_path), SNAPSHOT)


class TestTheMairesFilesHaveNoFunctionColumn:
    def test_a_maire_row_gets_its_function_supplied(self, tmp_path: Path) -> None:
        write_rne_snapshot(tmp_path, SNAPSHOT, maires_current=[Elu()])
        stage(Layout(tmp_path), SNAPSHOT)

        rows = (
            staged(tmp_path, "elus").project("source_file, function_label").fetchall()
        )
        assert rows == [("maires_current", "Maire")]

    def test_a_conseiller_row_keeps_the_published_function(
        self, tmp_path: Path
    ) -> None:
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[Elu(function_label="1er adjoint au Maire")],
        )
        stage(Layout(tmp_path), SNAPSHOT)

        assert staged(tmp_path, "elus").project("function_label").fetchall() == [
            ("1er adjoint au Maire",)
        ]

    def test_a_conseiller_with_no_function_is_null(self, tmp_path: Path) -> None:
        # Most councillors hold no delegated function, and that is not the same
        # fact as being the mayor.
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu(function_label="")])
        stage(Layout(tmp_path), SNAPSHOT)

        assert staged(tmp_path, "elus").project("function_label").fetchall() == [
            (None,)
        ]


class TestGroupingIntoPeople:
    def mayor_in_both_files(self) -> dict[str, list[Elu]]:
        one = Elu(
            surname="NOMDEXEMPLE1", function_label="Maire", function_start="2026-03-25"
        )
        return {"cm_current": [one], "maires_current": [Elu(surname="NOMDEXEMPLE1")]}

    def test_a_mayor_in_two_files_is_one_person(self, tmp_path: Path) -> None:
        # Without this every mayor would be two people, and the base rate's
        # denominator would be wrong by the number of communes.
        write_rne_snapshot(tmp_path, SNAPSHOT, **self.mayor_in_both_files())  # type: ignore[arg-type]
        written = stage(Layout(tmp_path), SNAPSHOT)

        assert written["elus"] == 2
        assert written["elu_person"] == 1

    def test_the_person_carries_both_functions(self, tmp_path: Path) -> None:
        write_rne_snapshot(tmp_path, SNAPSHOT, **self.mayor_in_both_files())  # type: ignore[arg-type]
        stage(Layout(tmp_path), SNAPSHOT)

        rows = (
            staged(tmp_path, "elu_person")
            .project("function_labels, function_count, is_maire")
            .fetchall()
        )
        assert rows == [("Maire", 1, True)]

    def test_two_functions_are_carried_not_picked(self, tmp_path: Path) -> None:
        # ADR-0007's rule in the other project, and the right one here: an élu
        # who is both a deputy mayor and a delegated councillor holds two
        # functions, and choosing one would lose the fact.
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[
                Elu(function_label="1er adjoint au Maire"),
                Elu(function_label="Conseiller délégué"),
            ],
        )
        stage(Layout(tmp_path), SNAPSHOT)

        rows = (
            staged(tmp_path, "elu_person")
            .project("function_labels, function_count")
            .fetchall()
        )
        assert rows == [("1er adjoint au Maire;Conseiller délégué", 2)]

    def test_the_same_name_in_two_communes_is_two_people(self, tmp_path: Path) -> None:
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[Elu(commune_code="99001"), Elu(commune_code="99002")],
        )

        assert stage(Layout(tmp_path), SNAPSHOT)["elu_person"] == 2

    def test_the_two_snapshot_kinds_stay_apart(self, tmp_path: Path) -> None:
        # The same councillor before and after the election is two rows, and
        # F1 reads the pre-election one to establish office at an older date.
        write_rne_snapshot(
            tmp_path, SNAPSHOT, cm_current=[Elu()], cm_pre_election=[Elu()]
        )
        stage(Layout(tmp_path), SNAPSHOT)

        kinds = staged(tmp_path, "elu_person").project("snapshot_kind").fetchall()
        assert sorted(kind for (kind,) in kinds) == ["current", "pre_election"]


class TestIdentifiersAreStable:
    def test_the_row_id_does_not_change_between_runs(self, tmp_path: Path) -> None:
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu()])

        stage(Layout(tmp_path), SNAPSHOT)
        first = staged(tmp_path, "elus").project("elu_row_id").fetchall()
        stage(Layout(tmp_path), SNAPSHOT)
        second = staged(tmp_path, "elus").project("elu_row_id").fetchall()

        assert first == second

    def test_the_row_id_is_unique(self, tmp_path: Path) -> None:
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[Elu(surname=f"NOMDEXEMPLE{n}") for n in range(50)],
        )
        stage(Layout(tmp_path), SNAPSHOT)

        rows = staged(tmp_path, "elus").project("elu_row_id").fetchall()
        assert len({row[0] for row in rows}) == 50

    def test_a_changed_field_changes_the_id(self, tmp_path: Path) -> None:
        # A hash that ignored a field would silently merge two councillors.
        ids = []
        for commune in ("99001", "99002"):
            write_rne_snapshot(
                tmp_path, SNAPSHOT, cm_current=[Elu(commune_code=commune)]
            )
            stage(Layout(tmp_path), SNAPSHOT)
            ids.append(staged(tmp_path, "elus").project("elu_row_id").fetchall()[0][0])

        assert ids[0] != ids[1]


class TestDeterminism:
    def test_a_rerun_is_byte_identical(self, tmp_path: Path) -> None:
        # Constraint 4, over the path that actually matters: DuckDB orders the
        # rows and pyarrow writes them, and neither may vary between runs.
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[Elu(surname=f"NOMDEXEMPLE{n}") for n in range(40)],
            maires_current=[Elu(surname="NOMDEXEMPLE7")],
        )
        path = Layout(tmp_path).staged(SOURCE, SNAPSHOT) / "elus.parquet"

        stage(Layout(tmp_path), SNAPSHOT)
        first = path.read_bytes()
        stage(Layout(tmp_path), SNAPSHOT)

        assert path.read_bytes() == first

    def test_the_comparison_can_actually_fail(self, tmp_path: Path) -> None:
        path = Layout(tmp_path).staged(SOURCE, SNAPSHOT) / "elus.parquet"
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu()])
        stage(Layout(tmp_path), SNAPSHOT)
        first = path.read_bytes()

        write_rne_snapshot(
            tmp_path, SNAPSHOT, cm_current=[Elu(), Elu(commune_code="99002")]
        )
        stage(Layout(tmp_path), SNAPSHOT)

        assert path.read_bytes() != first

    def test_the_retrieved_timestamp_is_the_only_clock_reading(
        self, tmp_path: Path
    ) -> None:
        # It comes from the manifest, written at fetch, not from staging. Two
        # stagings a week apart produce the same value.
        write_rne_snapshot(
            tmp_path,
            SNAPSHOT,
            cm_current=[Elu()],
            retrieved_at="2026-09-16T08:00:00+00:00",
        )
        stage(Layout(tmp_path), SNAPSHOT)

        rows = staged(tmp_path, "elus").project("retrieved_at").fetchall()
        assert rows == [("2026-09-16T08:00:00+00:00",)]


class TestFetchResolvesUrls:
    def prepared(self, tmp_path: Path) -> Layout:
        layout = Layout(tmp_path)
        layout.create()
        return layout

    def test_it_asks_the_api_rather_than_hardcoding(self, tmp_path: Path) -> None:
        # data.gouv.fr resources move: some SIRENE files changed storage in
        # February 2026 and the old links return 404.
        calls: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(str(request.url))
            if "/api/1/datasets/" in str(request.url):
                return listing()
            return httpx.Response(200, content=b"Code du departement\n")

        entries = fr_rne_elus.fetch(
            client_for(handler), self.prepared(tmp_path), SNAPSHOT
        )

        assert len(entries) == 4
        assert any("/api/1/datasets/" in call for call in calls)
        assert all(entry["licence"] == "Licence Ouverte 2.0" for entry in entries)

    def test_a_second_run_downloads_nothing(self, tmp_path: Path) -> None:
        # Resumability, and the reason a 130MB fetch is safe to rerun.
        def handler(request: httpx.Request) -> httpx.Response:
            if "/api/1/datasets/" in str(request.url):
                return listing()
            return httpx.Response(200, content=b"Code du departement\n")

        layout = self.prepared(tmp_path)
        fr_rne_elus.fetch(client_for(handler), layout, SNAPSHOT)

        assert fr_rne_elus.fetch(client_for(handler), layout, SNAPSHOT) == []

    def test_a_renamed_resource_is_reported_not_guessed(self, tmp_path: Path) -> None:
        # Downloading "something that looks close" is how a pipeline silently
        # stages the wrong file.
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                200, json={"resources": [{"title": "something-else.csv"}]}
            )

        with pytest.raises(StageError, match="no longer publishes a resource"):
            fr_rne_elus.fetch(client_for(handler), self.prepared(tmp_path), SNAPSHOT)


class TestTheFixtureIsHonest:
    def test_the_headers_match_what_the_module_expects(self, tmp_path: Path) -> None:
        # If the fixture's header drifted from the module's mapping, every test
        # above would still pass while reading the wrong columns.
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu()])
        header = (
            (tmp_path / "raw" / SOURCE / SNAPSHOT / "cm_current.csv")
            .read_text(encoding="utf-8")
            .splitlines()[0]
            .split(";")
        )

        for published in fr_rne_elus.COLUMNS:
            assert published in header, f"the fixture no longer publishes {published!r}"

    def test_no_fixture_name_could_be_mistaken_for_a_person(
        self, tmp_path: Path
    ) -> None:
        write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu()])
        text = (tmp_path / "raw" / SOURCE / SNAPSHOT / "cm_current.csv").read_text(
            "utf-8"
        )

        assert "EXEMPLE" in text

    def test_the_manifest_is_readable(self, tmp_path: Path) -> None:
        directory = write_rne_snapshot(tmp_path, SNAPSHOT, cm_current=[Elu()])
        recorded = json.loads((directory / "manifest.json").read_text("utf-8"))["files"]

        assert {entry["path"] for entry in recorded} == {
            published.filename for published in fr_rne_elus.FILES
        }
