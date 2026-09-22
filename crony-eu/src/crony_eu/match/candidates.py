# SPDX-License-Identifier: AGPL-3.0-only
"""Every élu-officer pair whose `FR-NAME-BIRTHYM-v1` keys are equal, in one slice.

A candidate is a proposal and nothing more (constraint 3). This module finds them,
writes them to `$CRONY_DATA_DIR/matched/candidates/dep-<code>.parquet`, and enters
each new one into the judgments log as `pending` for a person to decide. It never
decides anything itself.

**Scope.** Élus of the communes in the département, both vintages of the register,
against the natural-person officers of the companies that supplied those
communes. The officers are restricted to the slice's suppliers even when the
company snapshot holds more, so a candidate always belongs to the slice it was
built for.

**`key_collision`.** Set when one key reaches more than one commune on the élu
side, or more than one company on the officer side. The second case includes one
person holding seats in two companies, which the key cannot tell from two people
who share a name and a birth month; the flag says so to the reviewer rather than
guessing which it is. Within one commune the same key across the two vintages is
treated as one councillor, because a person sits on one municipal council.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from typing import Any

import duckdb
import pyarrow as pa

from crony_eu.match import judgments
from crony_eu.match.keys import RULE_ID, elu_keys, officer_keys
from crony_eu.parquet import write
from crony_eu.paths import Layout

SCHEMA = pa.schema(
    [
        pa.field("judgment_id", pa.string()),
        pa.field("rule_id", pa.string()),
        pa.field("elu_person_id", pa.string()),
        pa.field("officer_row_id", pa.string()),
        pa.field("siren", pa.string()),
        pa.field("match_key", pa.string()),
        pa.field("surname_variant", pa.string()),
        pa.field("elu_commune_code", pa.string()),
        pa.field("elu_snapshot_kind", pa.string()),
        pa.field("elu_sex", pa.string()),
        pa.field("key_collision", pa.bool_()),
        pa.field("elu_communes_for_key", pa.int32()),
        pa.field("officer_companies_for_key", pa.int32()),
    ]
)


class CandidateError(Exception):
    """A staged input the builder needs is not there."""


@dataclass
class Report:
    """Aggregates only. What the slice gave the rule, and what the rule gave back."""

    elus: int = 0
    elus_with_key: int = 0
    officers: int = 0
    officers_with_key: int = 0
    candidates: int = 0
    collisions: int = 0
    entered_pending: int = 0
    by_variant_and_sex: dict[str, int] = field(default_factory=dict)


def _latest(layout: Layout, source: str, table: str) -> str:
    for snapshot in reversed(layout.snapshots(source)):
        if (layout.staged(source, snapshot) / f"{table}.parquet").is_file():
            return snapshot
    raise CandidateError(
        f"{source} has no staged {table}.parquet. Run `crony fetch {source}` and "
        f"`crony stage {source}` first."
    )


def _rows(sql: str) -> list[dict[str, Any]]:
    connection = duckdb.connect()
    try:
        values = connection.execute(sql).fetchall()
        names = [description[0] for description in connection.description or []]
    finally:
        connection.close()
    return [dict(zip(names, row, strict=True)) for row in values]


def build(layout: Layout, scope: str) -> tuple[list[dict[str, Any]], Report]:
    """Find the candidates for one département. Offline, and clock-free."""
    from crony_eu.sources import fr_entreprises_api, fr_rne_elus
    from crony_eu.survey import departement_of

    elus_snapshot = _latest(layout, fr_rne_elus.SOURCE, "elu_person")
    api_snapshot = _latest(layout, fr_entreprises_api.SOURCE, "officers")
    people = layout.staged(fr_rne_elus.SOURCE, elus_snapshot) / "elu_person.parquet"
    officers_path = layout.staged(fr_entreprises_api.SOURCE, api_snapshot) / (
        "officers.parquet"
    )
    suppliers = {
        ask.value
        for ask in fr_entreprises_api.asks_for_scope(layout, scope)
        if ask.kind == "siren"
    }

    elus = _rows(
        f"""
        SELECT elu_person_id, surname_raw, given_raw, birth_ym, commune_code,
               snapshot_kind, sex
        FROM '{people.as_posix()}'
        WHERE {departement_of("commune_code")} = '{scope}'
        ORDER BY elu_person_id
        """
    )
    officers = [
        row
        for row in _rows(
            f"""
            SELECT officer_row_id, siren, surname_birth_raw, surname_usage_raw,
                   given_names_raw, birth_ym
            FROM '{officers_path.as_posix()}'
            ORDER BY officer_row_id
            """
        )
        if row["siren"] in suppliers
    ]

    report = Report(elus=len(elus), officers=len(officers))

    elu_index: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for elu in elus:
        keys = elu_keys(elu["surname_raw"], elu["given_raw"], elu["birth_ym"])
        report.elus_with_key += bool(keys)
        for key in keys:
            elu_index[key.value].append((key.variant, elu))

    officer_index: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
    for officer in officers:
        keys = officer_keys(
            officer["surname_birth_raw"],
            officer["surname_usage_raw"],
            officer["given_names_raw"],
            officer["birth_ym"],
        )
        report.officers_with_key += bool(keys)
        for key in keys:
            officer_index[key.value].append((key.variant, officer))

    found: list[dict[str, Any]] = []
    tally: Counter[str] = Counter()
    for value in sorted(set(elu_index) & set(officer_index)):
        communes = {elu["commune_code"] for _, elu in elu_index[value]}
        companies = {officer["siren"] for _, officer in officer_index[value]}
        collision = len(communes) > 1 or len(companies) > 1
        for _, elu in elu_index[value]:
            for variant, officer in officer_index[value]:
                found.append(
                    {
                        "judgment_id": judgments.judgment_id(
                            RULE_ID, elu["elu_person_id"], officer["officer_row_id"]
                        ),
                        "rule_id": RULE_ID,
                        "elu_person_id": elu["elu_person_id"],
                        "officer_row_id": officer["officer_row_id"],
                        "siren": officer["siren"],
                        "match_key": value,
                        "surname_variant": variant,
                        "elu_commune_code": elu["commune_code"],
                        "elu_snapshot_kind": elu["snapshot_kind"],
                        "elu_sex": elu["sex"],
                        "key_collision": collision,
                        "elu_communes_for_key": len(communes),
                        "officer_companies_for_key": len(companies),
                    }
                )
                tally[f"{variant}/{elu['sex']}"] += 1

    report.candidates = len(found)
    report.collisions = sum(1 for row in found if row["key_collision"])
    report.by_variant_and_sex = dict(sorted(tally.items()))
    return found, report


def run(layout: Layout, scope: str) -> Report:
    """Build, write, and enter the new candidates as pending judgments."""
    from crony_eu.run import run_id
    from crony_eu.sources import fr_decp, fr_entreprises_api, fr_rne_elus

    found, report = build(layout, scope)
    write(found, SCHEMA, layout.candidates(scope), key=("judgment_id",))

    inputs = [
        (source, _latest(layout, source, table))
        for source, table in (
            (fr_rne_elus.SOURCE, "elu_person"),
            (fr_entreprises_api.SOURCE, "officers"),
            (fr_decp.SOURCE, "contracts"),
        )
    ]
    report.entered_pending = judgments.enter(layout, found, run_id(layout, inputs))

    # The counts go beside the staged data rather than into the repository. The
    # variant-by-sex cells are small in a single département, and constraint 12
    # says a small cell leaves the machine only after the maintainer has looked
    # at it, so the public documents carry the coarse answer and this file
    # carries the cells.
    destination = layout.reports() / f"candidates-dep-{scope}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(
            {"scope": f"dep:{scope}", "rule_id": RULE_ID, **asdict(report)},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return report
