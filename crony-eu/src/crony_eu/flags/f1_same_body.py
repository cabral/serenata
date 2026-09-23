# SPDX-License-Identifier: AGPL-3.0-only
"""F1, same-body officer: `crony-eu/docs/flags/F1-same-body.md`, implemented.

An élu of commune C was in office when C notified a contract to company S, and a
judgment (pending or confirmed) links that élu to a natural-person officer of S.
That configuration is a **statistical anomaly with possible innocent
explanations**, never an accusation; the spec lists the explanations and what a
journalist has to verify before anything is said about anyone.

The six conditions are one function each, so each branch the work order lists
has a test of its own. Nothing here decides whether a hit may reach a case
packet by itself: every gate is a column, `packet_eligible` is their conjunction,
and the base rates count what each gate removed.

**Two things the data cannot say, written down rather than papered over.**

- `mandate_overlap` is `true` or `unknown`, never `false`. The spec sets it
  `unknown` "when neither can be established", and the register cannot establish
  that someone was *not* in office: it records the current mandate's start and
  nothing before it.
- The 432-12 tag's rule names `conseiller délégué`, and the register publishes no
  such function: a councillor holding a delegation looks exactly like one who
  does not. The tag therefore cannot fire for them, and it under-fires for that
  reason alone.

**Calibration.** `CALIBRATION` is `None` until the maintainer has approved the
measured base rates and they are in the spec (work order, session 5 STOP). While
it is `None` every row says `uncalibrated` and none is packet-eligible
(constraint 8). Setting it is a reviewed code change, so the git history records
when the flag was calibrated and by whom.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pyarrow as pa

from crony_eu import db
from crony_eu.match import buyer_verification as bv
from crony_eu.match import judgments
from crony_eu.parquet import write
from crony_eu.paths import Layout
from crony_eu.survey import ARTICLE_432_12_CEILING, band_of, departement_of

FLAG = "F1"

#: The date the maintainer approved F1's measured base rates, or `None`.
CALIBRATION: str | None = None

TRUE = "true"
FALSE = "false"
UNKNOWN = "unknown"

#: F1's exclusion list, pinned 2026-09-22 in the flag spec: économie mixte, and
#: the public-law families 4xxx and 7xxx. A société publique locale has no code of
#: its own and cannot be excluded by category; the spec says where this stops.
EXCLUDED_CODES = frozenset({"5415", "5515", "5615"})
EXCLUDED_FAMILIES = ("4", "7")

#: Art. 432-12, second paragraph, checked on Légifrance on 2026-09-22 (version in
#: force since 24 December 2025): "dans la limite d'un montant annuel fixé à
#: 16 000 euros".
ARTICLE_432_12_ANNUAL_CAP = Decimal("16000")

#: What `role_date_semantics` has to say before a role date can establish an
#: overlap. A filing date is not a role start date, and a packet claiming
#: otherwise would be wrong in the way that matters most.
ROLE_START_SEMANTICS = "role_start"

#: The only diffusion status that lets a company into an export (constraint 7).
#: `P`, partially diffusible, is treated like `N`: the rule is about what may be
#: redistributed, and "partially" is not a yes.
REDISTRIBUTABLE = "O"


def excluded(nature_juridique: str | None) -> bool:
    """Condition 3's list. A missing category cannot be excluded by it."""
    code = nature_juridique or ""
    return code in EXCLUDED_CODES or code[:1] in EXCLUDED_FAMILIES


def mandate_overlap(
    snapshot_kind: str,
    mandate_start: date | None,
    new_council_start: date | None,
    notified: date | None,
) -> str:
    """Condition 4: was this élu record in office on the notification date?

    - the current file: in office from its mandate start
    - the pre-election extract: in office from its mandate start until the
      commune's new council took office, which is the earliest mandate start
      among that commune's current records
    - anything else is `unknown`, because the register cannot show earlier
      terms, so it cannot show that someone was out of office
    """
    if notified is None or mandate_start is None or mandate_start > notified:
        return UNKNOWN
    if snapshot_kind == "current":
        return TRUE
    if new_council_start is not None and notified < new_council_start:
        return TRUE
    return UNKNOWN


def role_overlap(
    semantics: str | None,
    role_start: date | None,
    role_end: date | None,
    notified: date | None,
) -> str:
    """Condition 6: did the officer role cover the notification date?

    Start on or before it and end absent or on or after it. A missing start, or a
    date whose recorded meaning is not a role start, is `unknown`; a start after
    the date or an end before it is `false`.
    """
    if notified is None or semantics != ROLE_START_SEMANTICS or role_start is None:
        return UNKNOWN
    if role_start > notified:
        return FALSE
    if role_end is not None and role_end < notified:
        return FALSE
    return TRUE


def holds_a_432_12_function(function_labels: str | None) -> bool:
    """Maire, maire délégué or adjoint. See the module note on délégués."""
    labels = [label.strip() for label in (function_labels or "").split(";")]
    return any(
        label in ("Maire", "Maire délégué") or label.endswith("adjoint au Maire")
        for label in labels
    )


def possible_432_12_exception(
    population: int | None, function_labels: str | None, yearly_total: Decimal | None
) -> bool:
    """The spec's tag: a possible innocent explanation, set only when computable.

    `yearly_total` is `None` when any contract in that year has no amount, and
    then the tag is not set; the hit row carries the null so a reader sees why.
    """
    return (
        population is not None
        and population <= ARTICLE_432_12_CEILING
        and holds_a_432_12_function(function_labels)
        and yearly_total is not None
        and yearly_total <= ARTICLE_432_12_ANNUAL_CAP
    )


HITS = pa.schema(
    [
        pa.field("hit_id", pa.string()),
        pa.field("decp_row_id", pa.string()),
        pa.field("contract_uid", pa.string()),
        pa.field("buyer_siren", pa.string()),
        pa.field("buyer_siret", pa.string()),
        pa.field("buyer_assertion_id", pa.string()),
        pa.field("commune_code", pa.string()),
        pa.field("supplier_siren", pa.string()),
        pa.field("amount_eur", pa.decimal128(18, 2)),
        pa.field("date_notification", pa.date32()),
        pa.field("procedure", pa.string()),
        pa.field("elu_person_id", pa.string()),
        pa.field("elu_snapshot_kind", pa.string()),
        pa.field("elu_function", pa.string()),
        pa.field("officer_row_id", pa.string()),
        pa.field("judgment_id", pa.string()),
        pa.field("judgment_status", pa.string()),
        pa.field("match_status", pa.string()),
        pa.field("rule_id", pa.string()),
        pa.field("mandate_overlap", pa.string()),
        pa.field("role_overlap", pa.string()),
        pa.field("population", pa.int32()),
        pa.field("population_band", pa.string()),
        pa.field("supplier_legal_category", pa.string()),
        pa.field("supplier_size_category", pa.string()),
        pa.field("supplier_diffusion", pa.string()),
        pa.field("yearly_total_eur", pa.decimal128(18, 2)),
        pa.field("key_collision", pa.bool_()),
        pa.field("possible_432_12_exception", pa.bool_()),
        pa.field("buyer_identity_corroborated", pa.string()),
        pa.field("historical_geography", pa.string()),
        pa.field("gate_judgment_confirmed", pa.bool_()),
        pa.field("gate_mandate_overlap", pa.bool_()),
        pa.field("gate_role_overlap", pa.bool_()),
        pa.field("gate_redistributable", pa.bool_()),
        pa.field("gate_buyer_verified", pa.bool_()),
        pa.field("gate_calibrated", pa.bool_()),
        pa.field("packet_eligible", pa.bool_()),
        pa.field("calibration", pa.string()),
        pa.field("source_url", pa.string()),
        pa.field("retrieved_at", pa.string()),
    ]
)

#: The denominator: every (commune, supplier) pair a hit could have come from,
#: which is a pair with at least one contract meeting conditions 1 to 3.
PAIRS = pa.schema(
    [
        pa.field("commune_code", pa.string()),
        pa.field("supplier_siren", pa.string()),
        pa.field("population", pa.int32()),
        pa.field("population_band", pa.string()),
        pa.field("supplier_legal_category", pa.string()),
        pa.field("contracts", pa.int32()),
    ]
)

#: Hits whose supplier the exclusion list removed. "Reported separately, never
#: flagged": they are the flag's most confident wrong answers, kept for a person
#: to see rather than dropped.
EXCLUDED = pa.schema(
    [
        pa.field("decp_row_id", pa.string()),
        pa.field("judgment_id", pa.string()),
        pa.field("commune_code", pa.string()),
        pa.field("supplier_siren", pa.string()),
        pa.field("supplier_legal_category", pa.string()),
    ]
)


class FlagError(Exception):
    """A staged input or a decision log the flag needs is not there."""


@dataclass(frozen=True)
class Result:
    run_id: str
    hits: int
    pairs: int
    excluded: int
    packet_eligible: int


def _rows(layout: Layout, sql: str) -> list[dict[str, Any]]:
    connection = db.connect(layout)
    try:
        values = connection.execute(sql).fetchall()
        names = [description[0] for description in connection.description or []]
    finally:
        connection.close()
    return [dict(zip(names, row, strict=True)) for row in values]


def _staged(layout: Layout, source: str, table: str) -> tuple[str, str]:
    snapshot = layout.latest_staged(source, table)
    if snapshot is None:
        raise FlagError(
            f"{source} has no staged {table}.parquet. Run `crony fetch {source}` "
            f"and `crony stage {source}` first."
        )
    return snapshot, (layout.staged(source, snapshot) / f"{table}.parquet").as_posix()


def _buyer_decisions(layout: Layout, evidence_path: str) -> dict[str, dict[str, Any]]:
    """buyer_assertion_id -> the decision bound to the *current* evidence.

    A decision made on older evidence does not carry over: its verification id
    hashes the evidence it examined, so it simply is not found here, and the
    buyer reads as unverified until a person looks at what the registry says now.
    """
    current = {
        str(row["buyer_siret"]): str(row["evidence_sha256"])
        for row in _rows(
            layout, f"SELECT buyer_siret, evidence_sha256 FROM '{evidence_path}'"
        )
    }
    decided = {str(row["verification_id"]): row for row in bv.latest(layout)}
    by_assertion: dict[str, dict[str, Any]] = {}
    for row in decided.values():
        siret = str(row["buyer_siret"])
        if siret in current and row["verification_id"] == bv.verification_id(
            str(row["buyer_assertion_id"]), current[siret]
        ):
            by_assertion[str(row["buyer_assertion_id"])] = row
    return by_assertion


def current_run(layout: Layout, scope: str) -> tuple[str, Path]:
    """The run id the current inputs and decisions give, and its directory.

    Which run a base rate reads is decided by the inputs, not by which directory
    was written last: picking by modification time would make the rate depend on
    when things ran, which constraint 4 does not allow.
    """
    from crony_eu.run import run_id
    from crony_eu.sources import fr_decp, fr_entreprises_api, fr_insee_pop, fr_rne_elus

    inputs = [
        (fr_decp.SOURCE, _staged(layout, fr_decp.SOURCE, "contracts")[0]),
        (fr_rne_elus.SOURCE, _staged(layout, fr_rne_elus.SOURCE, "elu_person")[0]),
        (
            fr_entreprises_api.SOURCE,
            _staged(layout, fr_entreprises_api.SOURCE, "officers")[0],
        ),
        (fr_insee_pop.SOURCE, _staged(layout, fr_insee_pop.SOURCE, "populations")[0]),
    ]
    identifier = run_id(layout, inputs, decisions=[layout.judgments(), bv.path(layout)])
    return identifier, layout.flags(FLAG, f"dep-{scope}-{identifier[:12]}")


def run(layout: Layout, scope: str) -> Result:
    """Evaluate F1 over one département and write hits, pairs and exclusions."""
    from crony_eu.sources import fr_decp, fr_entreprises_api, fr_insee_pop, fr_rne_elus

    identifier, destination = current_run(layout, scope)
    _, contracts_path = _staged(layout, fr_decp.SOURCE, "contracts")
    _, elus_path = _staged(layout, fr_rne_elus.SOURCE, "elu_person")
    api_snapshot, officers_path = _staged(layout, fr_entreprises_api.SOURCE, "officers")
    companies_path = (
        layout.staged(fr_entreprises_api.SOURCE, api_snapshot) / "companies.parquet"
    ).as_posix()
    evidence_path = (
        layout.staged(fr_entreprises_api.SOURCE, api_snapshot)
        / "buyer_evidence.parquet"
    ).as_posix()
    _, populations_path = _staged(layout, fr_insee_pop.SOURCE, "populations")
    if not layout.candidates(scope).is_file():
        raise FlagError(
            f"no candidates for dep:{scope}. Run `crony match fr --scope dep:{scope}`."
        )

    # Conditions 1 and 2: the latest version (contracts.parquet holds only that)
    # and a supplier with a SIREN, for commune buyers in the slice.
    contracts = _rows(
        layout,
        f"""
        SELECT decp_row_id, uid, buyer_siren, buyer_siret, buyer_assertion_id,
               buyer_commune_code AS commune_code, supplier_siren, amount_eur,
               CASE WHEN dates_plausible THEN date_notification END AS notified,
               procedure, source_url, retrieved_at
        FROM '{contracts_path}'
        WHERE buyer_category = '{fr_decp.COMMUNE_CATEGORY}'
          AND buyer_commune_code IS NOT NULL
          AND {departement_of("buyer_commune_code")} = '{scope}'
          AND supplier_has_siren
        ORDER BY decp_row_id
        """,
    )
    companies = {
        str(row["siren"]): row
        for row in _rows(layout, f"SELECT * FROM '{companies_path}'")
    }
    populations = {
        str(row["geo_code"]): int(row["population"])
        for row in _rows(
            layout,
            f"""SELECT geo_code, population FROM '{populations_path}'
                WHERE geo_object = 'COM'
                  AND measure = '{fr_insee_pop.LEGAL_MEASURE}'""",
        )
    }
    elus = {
        str(row["elu_person_id"]): row
        for row in _rows(
            layout,
            f"""SELECT elu_person_id, snapshot_kind, commune_code, mandate_start,
                       function_labels
                FROM '{elus_path}'
                WHERE {departement_of("commune_code")} = '{scope}'""",
        )
    }
    new_council: dict[str, date] = {}
    for row in elus.values():
        if row["snapshot_kind"] == "current" and row["mandate_start"] is not None:
            code = str(row["commune_code"])
            start = row["mandate_start"]
            new_council[code] = min(start, new_council.get(code, start))
    officers = {
        str(row["officer_row_id"]): row
        for row in _rows(
            layout,
            f"""SELECT officer_row_id, role_start, role_end, role_date_semantics
                FROM '{officers_path}'""",
        )
    }
    status = {str(row["judgment_id"]): row for row in judgments.latest(layout)}
    candidates_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for candidate in _rows(
        layout,
        f"SELECT * FROM '{layout.candidates(scope).as_posix()}' ORDER BY judgment_id",
    ):
        # Condition 5: pending or confirmed. Rejected and ambiguous are not hits.
        decided = status.get(str(candidate["judgment_id"]), {}).get("status")
        if decided in (judgments.PENDING, judgments.CONFIRMED):
            key = (str(candidate["elu_commune_code"]), str(candidate["siren"]))
            candidates_by_pair[key].append({**candidate, "status": decided})

    buyers = _buyer_decisions(layout, evidence_path)

    # The 432-12 tag reads a yearly total per (commune, supplier), over every
    # contract in scope that year, so it is computed before any hit is.
    yearly: dict[tuple[str, str, int], Decimal | None] = {}
    for contract in contracts:
        if contract["notified"] is None:
            continue
        year_key = (
            str(contract["commune_code"]),
            str(contract["supplier_siren"]),
            int(contract["notified"].year),
        )
        amount = contract["amount_eur"]
        held = yearly.get(year_key, Decimal(0))
        yearly[year_key] = None if held is None or amount is None else held + amount

    hits: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    pairs: dict[tuple[str, str], int] = defaultdict(int)
    for contract in contracts:
        commune = str(contract["commune_code"])
        supplier = str(contract["supplier_siren"])
        company = companies.get(supplier, {})
        category = company.get("nature_juridique")
        population = populations.get(commune)

        if excluded(category):
            for candidate in candidates_by_pair.get((commune, supplier), []):
                excluded_rows.append(
                    {
                        "decp_row_id": contract["decp_row_id"],
                        "judgment_id": candidate["judgment_id"],
                        "commune_code": commune,
                        "supplier_siren": supplier,
                        "supplier_legal_category": category,
                    }
                )
            continue
        pairs[(commune, supplier)] += 1

        notified = contract["notified"]
        buyer = buyers.get(str(contract["buyer_assertion_id"]), {})
        for candidate in candidates_by_pair.get((commune, supplier), []):
            elu = elus.get(str(candidate["elu_person_id"]), {})
            officer = officers.get(str(candidate["officer_row_id"]), {})
            mandate = mandate_overlap(
                str(elu.get("snapshot_kind")),
                elu.get("mandate_start"),
                new_council.get(commune),
                notified,
            )
            role = role_overlap(
                officer.get("role_date_semantics"),
                officer.get("role_start"),
                officer.get("role_end"),
                notified,
            )
            total = yearly.get((commune, supplier, notified.year)) if notified else None
            identity = str(buyer.get("identity_corroborated") or bv.UNKNOWN)
            geography = str(buyer.get("historical_geography") or bv.NOT_ESTABLISHED)
            gates = {
                "gate_judgment_confirmed": candidate["status"] == judgments.CONFIRMED,
                "gate_mandate_overlap": mandate == TRUE,
                "gate_role_overlap": role == TRUE,
                "gate_redistributable": company.get("statut_diffusion")
                == REDISTRIBUTABLE,
                "gate_buyer_verified": bv.blocks_a_packet(
                    {
                        "identity_corroborated": identity,
                        "historical_geography": geography,
                    }
                )
                is None,
                "gate_calibrated": CALIBRATION is not None,
            }
            hits.append(
                {
                    "hit_id": judgments.judgment_id(
                        FLAG,
                        str(contract["decp_row_id"]),
                        str(candidate["judgment_id"]),
                    ),
                    "decp_row_id": contract["decp_row_id"],
                    "contract_uid": contract["uid"],
                    "buyer_siren": contract["buyer_siren"],
                    "buyer_siret": contract["buyer_siret"],
                    "buyer_assertion_id": contract["buyer_assertion_id"],
                    "commune_code": commune,
                    "supplier_siren": supplier,
                    "amount_eur": contract["amount_eur"],
                    "date_notification": notified,
                    "procedure": contract["procedure"],
                    "elu_person_id": candidate["elu_person_id"],
                    "elu_snapshot_kind": elu.get("snapshot_kind"),
                    "elu_function": elu.get("function_labels"),
                    "officer_row_id": candidate["officer_row_id"],
                    "judgment_id": candidate["judgment_id"],
                    "judgment_status": candidate["status"],
                    # Constraint 3: flags run on candidates for triage, and every
                    # such row says it is unconfirmed.
                    "match_status": "confirmed"
                    if candidate["status"] == judgments.CONFIRMED
                    else "unconfirmed",
                    "rule_id": candidate["rule_id"],
                    "mandate_overlap": mandate,
                    "role_overlap": role,
                    "population": population,
                    "population_band": band_of(population),
                    "supplier_legal_category": category,
                    "supplier_size_category": company.get("size_category"),
                    "supplier_diffusion": company.get("statut_diffusion"),
                    "yearly_total_eur": total,
                    "key_collision": candidate["key_collision"],
                    "possible_432_12_exception": possible_432_12_exception(
                        population, elu.get("function_labels"), total
                    ),
                    "buyer_identity_corroborated": identity,
                    "historical_geography": geography,
                    **gates,
                    "packet_eligible": all(gates.values()),
                    "calibration": CALIBRATION or "uncalibrated",
                    "source_url": contract["source_url"],
                    "retrieved_at": contract["retrieved_at"],
                }
            )

    write(hits, HITS, destination / "hits.parquet", key=("hit_id",))
    write(
        [
            {
                "commune_code": commune,
                "supplier_siren": supplier,
                "population": populations.get(commune),
                "population_band": band_of(populations.get(commune)),
                "supplier_legal_category": companies.get(supplier, {}).get(
                    "nature_juridique"
                ),
                "contracts": count,
            }
            for (commune, supplier), count in pairs.items()
        ],
        PAIRS,
        destination / "pairs.parquet",
        key=("commune_code", "supplier_siren"),
    )
    write(
        excluded_rows,
        EXCLUDED,
        destination / "excluded.parquet",
        key=("decp_row_id", "judgment_id"),
    )
    return Result(
        run_id=identifier,
        hits=len(hits),
        pairs=len(pairs),
        excluded=len(excluded_rows),
        packet_eligible=sum(1 for hit in hits if hit["packet_eligible"]),
    )
