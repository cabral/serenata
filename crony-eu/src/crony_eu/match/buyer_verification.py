# SPDX-License-Identifier: AGPL-3.0-only
"""Was this contract's buyer the commune the data says it was?

[ADR-0007](../../../docs/adr/0007-consolidator-derived-attributes.md) Amendment 1
sets the standard: **snapshot corroboration**. Archived official evidence has to
return the exact buyer SIRET, link it to the expected legal unit, identify that
unit as a commune and agree with the commune code DECP asserts. All four, and
then the maintainer confirms. An establishment's location is not on its own
evidence of which public body awarded a contract, so the four mechanical checks
propose and a person decides.

**Two facts, recorded apart.** `identity_corroborated` is `true`, `false` or
`unknown`, and anything but `true` blocks a packet. `historical_geography` is
`established`, `contradicted` or `not_established`, and only `contradicted`
blocks. Nothing here rewrites `not_established` as `true`, and `assess` cannot
return `established` at all from this source, because there is nothing to return
it from: INSEE overwrites an establishment's commune code with the current one
whenever the Code officiel géographique changes, for closed establishments too,
so the historical code is not recorded anywhere in SIRENE at any access level
(`crony-eu/docs/sources/france.md`).

**Append-only, ordered by revision rather than by clock.** The handoff asks for a
stable reference and deterministic ordering without wall-clock timestamps, so a
revision is an integer that counts up per `verification_id` and the latest one
wins. `judgments` orders itself the same way: constraint 4 allows no timestamp
in data but `retrieved_at`, and the work order's `decided_at` for judgments was
removed on 2026-09-22 for that reason. Both logs share `crony_eu.match.log`.

**What a verification binds to.** `verification_id` hashes the DECP assertion
with the sha256 of the evidence that was examined. So a review cannot be reused
when the consolidator changes its claim, and cannot be reused when the registry
answers differently: either one is a new id with no decision against it yet.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa

from crony_eu.match.log import Log
from crony_eu.paths import Layout

#: `identity_corroborated`. Three values, because "no evidence came back" and
#: "evidence came back and disagreed" are different facts about a buyer and a
#: reviewer needs to tell them apart.
TRUE = "true"
FALSE = "false"
UNKNOWN = "unknown"

#: `historical_geography`.
ESTABLISHED = "established"
CONTRADICTED = "contradicted"
NOT_ESTABLISHED = "not_established"

#: The INSEE catégorie juridique of a commune. Pinned rather than inferred: the
#: check asks whether the legal unit **is a commune**, and a list of one is
#: honest about what has been verified. INSEE's own enumeration labels 7210
#: "Commune", amended in November 2011 to "Commune et commune nouvelle".
COMMUNE_CATEGORIES = ("7210",)

#: Why a mechanical check refused. Each is a condition from Amendment 1, named so
#: that a report can count them and a reviewer can see which one fired.
NO_EVIDENCE = "no_evidence"
NOT_RESOLVED = "evidence_did_not_resolve"
WRONG_LEGAL_UNIT = "siret_not_in_expected_legal_unit"
NOT_A_COMMUNE = "legal_unit_is_not_a_commune"
COMMUNE_DISAGREES = "commune_code_disagrees"


@dataclass(frozen=True)
class Assertion:
    """What DECP claims about one contract's buyer."""

    buyer_assertion_id: str
    decp_snapshot: str
    buyer_siret: str
    asserted_category: str | None
    asserted_commune_code: str | None

    @property
    def expected_siren(self) -> str:
        """The legal unit the SIRET belongs to, by construction."""
        return self.buyer_siret[:9]


@dataclass(frozen=True)
class Evidence:
    """What the registry said, as archived. Never a decision."""

    resolved: bool
    evidence_sha256: str
    source_url: str
    retrieved_at: str
    siren: str | None = None
    nature_juridique: str | None = None
    commune_code: str | None = None
    state: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Assessment:
    """The mechanical half. A proposal, and the reason behind it."""

    identity_corroborated: str
    historical_geography: str
    blocking_reason: str | None


def assess(assertion: Assertion, evidence: Evidence | None) -> Assessment:
    """The four conditions of Amendment 1, checked in order.

    This proposes and never decides: `crony review buyers` puts the proposal in
    front of the maintainer, who confirms it or overrides it, and only the
    written record counts. A function that decided would be the thing the ADR
    says an establishment's location must not be.
    """
    if evidence is None:
        return Assessment(UNKNOWN, NOT_ESTABLISHED, NO_EVIDENCE)
    if not evidence.resolved:
        return Assessment(UNKNOWN, NOT_ESTABLISHED, NOT_RESOLVED)

    if (evidence.siren or "") != assertion.expected_siren:
        return Assessment(FALSE, NOT_ESTABLISHED, WRONG_LEGAL_UNIT)
    if (evidence.nature_juridique or "") not in COMMUNE_CATEGORIES:
        return Assessment(FALSE, NOT_ESTABLISHED, NOT_A_COMMUNE)
    if (evidence.commune_code or "") != (assertion.asserted_commune_code or ""):
        return Assessment(FALSE, NOT_ESTABLISHED, COMMUNE_DISAGREES)

    # All four hold. `historical_geography` stays `not_established` because this
    # source cannot establish it and no approved source can: the commune code is
    # normalised forward by INSEE, so there is no historical value to compare
    # against. `established` is reachable only from evidence this project does
    # not have, and is never produced here.
    return Assessment(TRUE, NOT_ESTABLISHED, None)


def verification_id(buyer_assertion_id: str, evidence_sha256: str) -> str:
    """The handle a decision hangs on, bound to both of its inputs."""
    return hashlib.sha256(
        f"{buyer_assertion_id}|{evidence_sha256}".encode()
    ).hexdigest()


SCHEMA = pa.schema(
    [
        pa.field("verification_id", pa.string()),
        pa.field("revision", pa.int32()),
        pa.field("buyer_assertion_id", pa.string()),
        pa.field("decp_snapshot", pa.string()),
        pa.field("buyer_siret", pa.string()),
        pa.field("asserted_category", pa.string()),
        pa.field("asserted_commune_code", pa.string()),
        pa.field("observed_siren", pa.string()),
        pa.field("observed_nature_juridique", pa.string()),
        pa.field("observed_commune_code", pa.string()),
        pa.field("observed_state", pa.string()),
        pa.field("identity_corroborated", pa.string()),
        pa.field("historical_geography", pa.string()),
        pa.field("blocking_reason", pa.string()),
        pa.field("evidence_source", pa.string()),
        pa.field("evidence_url", pa.string()),
        pa.field("evidence_retrieved_at", pa.string()),
        pa.field("evidence_sha256", pa.string()),
        pa.field("decided_by", pa.string()),
        pa.field("note", pa.string()),
    ]
)


def path(layout: Layout) -> Path:
    return layout.root / "matched" / "buyer_verification.parquet"


def _log(layout: Layout) -> Log:
    return Log(path(layout), SCHEMA, "verification_id")


def read(layout: Layout) -> list[dict[str, Any]]:
    """Every revision ever written, oldest first. Empty when none."""
    return _log(layout).read()


def append(layout: Layout, decisions: Sequence[dict[str, Any]]) -> int:
    """Add revisions without rewriting any. See `crony_eu.match.log`."""
    return _log(layout).append(decisions)


def latest(layout: Layout) -> list[dict[str, Any]]:
    """The current answer for each verification."""
    return _log(layout).latest()


def history(layout: Layout, identifier: str) -> list[dict[str, Any]]:
    """Every revision of one verification, oldest first."""
    return _log(layout).history(identifier)


def pending(layout: Layout, evidence: Sequence[dict[str, Any]]) -> list[str]:
    """Verification ids that evidence exists for and nobody has decided.

    The review queue. A verification whose evidence has changed gets a new id, so
    it reappears here rather than inheriting the old decision, which is the point
    of binding the id to the evidence hash.
    """
    decided = _log(layout).decided()
    return sorted(
        {
            str(row["verification_id"])
            for row in evidence
            if str(row["verification_id"]) not in decided
        }
    )


def queue(
    layout: Layout, decp_snapshot: str, api_snapshot: str
) -> list[dict[str, Any]]:
    """Join the DECP assertions to the archived evidence, one row per buyer.

    Offline, and it decides nothing: every row carries the mechanical assessment
    as a proposal for the maintainer to accept or override.
    """
    from crony_eu.sources import fr_decp, fr_entreprises_api

    contracts = (
        layout.staged(fr_decp.SOURCE, decp_snapshot) / "contracts.parquet"
    ).as_posix()
    buyers = (
        layout.staged(fr_entreprises_api.SOURCE, api_snapshot)
        / "buyer_evidence.parquet"
    ).as_posix()

    connection = duckdb.connect()
    try:
        rows = connection.execute(
            f"""
            SELECT DISTINCT
                c.buyer_assertion_id, c.buyer_siret,
                c.buyer_category      AS asserted_category,
                c.buyer_commune_code  AS asserted_commune_code,
                e.resolved, e.reason, e.siren, e.nature_juridique,
                e.establishment_commune_code, e.establishment_state,
                e.evidence_sha256, e.source_url, e.retrieved_at
            FROM '{contracts}' c
            LEFT JOIN '{buyers}' e ON e.buyer_siret = c.buyer_siret
            WHERE c.buyer_category = '{fr_decp.COMMUNE_CATEGORY}'
              AND c.buyer_siret IS NOT NULL
            ORDER BY c.buyer_assertion_id
            """
        ).fetchall()
        names = [description[0] for description in connection.description or []]
    finally:
        connection.close()

    queued = []
    for values in rows:
        row = dict(zip(names, values, strict=True))
        assertion = Assertion(
            buyer_assertion_id=str(row["buyer_assertion_id"]),
            decp_snapshot=decp_snapshot,
            buyer_siret=str(row["buyer_siret"]),
            asserted_category=row["asserted_category"],
            asserted_commune_code=row["asserted_commune_code"],
        )
        evidence = (
            None
            if row["evidence_sha256"] is None
            else Evidence(
                resolved=bool(row["resolved"]),
                evidence_sha256=str(row["evidence_sha256"]),
                source_url=str(row["source_url"]),
                retrieved_at=str(row["retrieved_at"]),
                siren=row["siren"],
                nature_juridique=row["nature_juridique"],
                commune_code=row["establishment_commune_code"],
                state=row["establishment_state"],
                reason=row["reason"],
            )
        )
        assessment = assess(assertion, evidence)
        queued.append(
            {
                "verification_id": verification_id(
                    assertion.buyer_assertion_id,
                    evidence.evidence_sha256 if evidence else "",
                ),
                "assertion": assertion,
                "evidence": evidence,
                "assessment": assessment,
            }
        )
    return queued


def record(
    queued: dict[str, Any],
    *,
    identity_corroborated: str,
    historical_geography: str,
    decided_by: str,
    note: str | None = None,
) -> dict[str, Any]:
    """One decision, ready to append. The revision is filled in by `append`.

    The two fields are arguments rather than one, because they are two facts and
    the caller has to say both. A signature that took a single verdict would be
    the collapse Amendment 1 forbids.
    """
    if identity_corroborated not in (TRUE, FALSE, UNKNOWN):
        raise ValueError(
            f"identity_corroborated is {identity_corroborated!r}; it is one of "
            f"{TRUE!r}, {FALSE!r}, {UNKNOWN!r}."
        )
    if historical_geography not in (ESTABLISHED, CONTRADICTED, NOT_ESTABLISHED):
        raise ValueError(
            f"historical_geography is {historical_geography!r}; it is one of "
            f"{ESTABLISHED!r}, {CONTRADICTED!r}, {NOT_ESTABLISHED!r}."
        )

    assertion: Assertion = queued["assertion"]
    evidence: Evidence | None = queued["evidence"]
    assessment: Assessment = queued["assessment"]

    return {
        "verification_id": queued["verification_id"],
        "revision": 0,
        "buyer_assertion_id": assertion.buyer_assertion_id,
        "decp_snapshot": assertion.decp_snapshot,
        "buyer_siret": assertion.buyer_siret,
        "asserted_category": assertion.asserted_category,
        "asserted_commune_code": assertion.asserted_commune_code,
        "observed_siren": evidence.siren if evidence else None,
        "observed_nature_juridique": evidence.nature_juridique if evidence else None,
        "observed_commune_code": evidence.commune_code if evidence else None,
        "observed_state": evidence.state if evidence else None,
        "identity_corroborated": identity_corroborated,
        "historical_geography": historical_geography,
        "blocking_reason": assessment.blocking_reason,
        "evidence_source": "fr-entreprises-api",
        "evidence_url": evidence.source_url if evidence else None,
        "evidence_retrieved_at": evidence.retrieved_at if evidence else None,
        "evidence_sha256": evidence.evidence_sha256 if evidence else None,
        "decided_by": decided_by,
        "note": note,
    }


def blocks_a_packet(decision: dict[str, Any]) -> str | None:
    """Why this verification stops a packet, or `None` if it does not.

    Amendment 1, stated once so that the flag's eligibility count and the
    export's refusal cannot drift apart: anything but a corroborated identity
    blocks, and of the three geography values only `contradicted` does.
    `not_established` is expected on nearly every row and removes none of them.
    """
    identity = str(decision.get("identity_corroborated") or "")
    if identity != TRUE:
        return f"buyer identity is {identity or UNKNOWN!r}, not corroborated"
    if str(decision.get("historical_geography") or "") == CONTRADICTED:
        return "historical geography is contradicted by the evidence"
    return None
