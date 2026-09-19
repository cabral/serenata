# SPDX-License-Identifier: AGPL-3.0-only
"""The SQL fragments, and the one property that keeps two rules in step.

`normalize.py` states the identifier rules in Python and `sql.py` states them
again in SQL, because one of them runs in a test and the other runs over three
million rows in DuckDB. Two statements of one rule drift. The last class here is
the thing that notices when they do.
"""

from __future__ import annotations

import duckdb
import pyarrow as pa
import pytest
from crony_eu import normalize
from crony_eu.sql import digits_only, identity, luhn_ok, plausible_date, siret_valid
from fakes import siren, siret


@pytest.fixture(scope="module")
def connection() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def one(connection: duckdb.DuckDBPyConnection, sql: str) -> object:
    row = connection.execute(f"SELECT {sql}").fetchone()
    assert row is not None
    return row[0]


class TestIdentity:
    def test_a_null_keeps_its_slot(self, connection: duckdb.DuckDBPyConnection) -> None:
        # The bug this function exists for. `concat_ws` drops a NULL argument
        # rather than leaving its separator, so without the coalesce these two
        # build the same string and get the same id.
        first = one(connection, identity(["'A'", "NULL", "'B'"]))
        second = one(connection, identity(["'A'", "'B'", "NULL"]))
        assert first != second

    def test_the_same_values_give_the_same_id(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        assert one(connection, identity(["'A'", "'B'"])) == one(
            connection, identity(["'A'", "'B'"])
        )

    def test_a_number_and_its_text_are_one_value(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        # Everything is cast to VARCHAR, so this is deliberate rather than a
        # surprise: an id is built from what a field says, not from its type.
        assert one(connection, identity(["1"])) == one(connection, identity(["'1'"]))


class TestDigitsOnly:
    def test_it_strips_what_a_paste_brings(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        assert one(connection, digits_only("'732 829 320'", 9)) == "732829320"

    def test_the_wrong_length_is_null(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        assert one(connection, digits_only("'7328293'", 9)) is None

    def test_null_in_null_out(self, connection: duckdb.DuckDBPyConnection) -> None:
        assert one(connection, digits_only("NULL", 9)) is None


class TestPlausibleDate:
    def test_a_null_date_is_plausible(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        # "Not provided" is a fact about the source, not a bad value.
        assert one(connection, plausible_date("NULL::DATE", 1900, "2026-09-19")) is True

    def test_a_date_before_the_window_is_not(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        sql = plausible_date("DATE '0001-01-01'", 1900, "2026-09-19")
        assert one(connection, sql) is False

    def test_a_date_after_the_snapshot_is_not(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        sql = plausible_date("DATE '2030-01-01'", 1900, "2026-09-19")
        assert one(connection, sql) is False


class TestTheTwoRulesAgree:
    """The SQL and the Python have to say the same thing about the same string.

    This is the test that earns the right to have the rule written twice.

    Every candidate is put through both in **one** query rather than sampled one
    at a time. That makes the check exhaustive over the range instead of
    probabilistic, and it makes it deterministic, which a project whose fourth
    constraint is byte-identical reruns should prefer on principle.
    """

    def compare(
        self,
        connection: duckdb.DuckDBPyConnection,
        candidates: list[str],
        sql: str,
        python: object,
    ) -> None:
        # Registered as one Arrow table rather than a hundred thousand inserts,
        # which is the difference between half a minute and no time at all.
        table = pa.table({"value": pa.array(candidates, pa.string())})
        connection.register("candidate", table)
        verdicts = connection.execute(f"SELECT value, {sql} FROM candidate").fetchall()
        assert len(verdicts) == len(candidates)
        disagreed = [
            value
            for value, in_sql in verdicts
            if bool(in_sql) != python(value)  # type: ignore[operator]
        ]
        assert not disagreed, f"{len(disagreed)} disagreements, first {disagreed[0]}"

    def test_siren_validity_agrees(self, connection: duckdb.DuckDBPyConnection) -> None:
        stems = [f"{n:08d}" for n in range(10_000_000, 10_002_000)]
        candidates = [siren(stem) for stem in stems] + [stem + "0" for stem in stems]
        self.compare(connection, candidates, luhn_ok("value", 9), normalize.siren_valid)

    def test_siret_validity_agrees(self, connection: duckdb.DuckDBPyConnection) -> None:
        stems = [f"{n:08d}" for n in range(10_000_000, 10_002_000)]
        candidates = [siret(stem) for stem in stems]
        candidates += [stem + "000000" for stem in stems]
        self.compare(
            connection,
            candidates,
            siret_valid("value", normalize.LA_POSTE_SIREN),
            normalize.siret_valid,
        )

    def test_they_agree_about_every_la_poste_establishment(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        # The exception is the part most likely to be implemented twice and
        # differently, and there are only a hundred thousand of them, so this
        # checks all of them rather than a sample.
        candidates = [normalize.LA_POSTE_SIREN + f"{nic:05d}" for nic in range(100_000)]
        self.compare(
            connection,
            candidates,
            siret_valid("value", normalize.LA_POSTE_SIREN),
            normalize.siret_valid,
        )

    def test_a_null_identifier_is_neither_valid_nor_invalid_in_sql(
        self, connection: duckdb.DuckDBPyConnection
    ) -> None:
        # The two differ here on purpose: SQL returns NULL so that a report can
        # count "no identifier published" apart from "an identifier that
        # failed", and the Python returns False because it answers a yes or no
        # question. The difference is stated here so it stays deliberate.
        assert one(connection, siret_valid("NULL", normalize.LA_POSTE_SIREN)) is None
        assert normalize.siret_valid(None) is False
