# SPDX-License-Identifier: AGPL-3.0-only
"""API Recherche d'entreprises: who a company is, and who its officers are.

Two questions, one endpoint, and they are not the same request.

**Suppliers, by SIREN.** F1 needs each supplier's officers (to match against
élus) and its catégorie juridique (to apply the exclusion list, which
`crony-eu/docs/flags/F1-same-body.md` could not pin from DECP because DECP
publishes only the INSEE size band).

**Buyers, by SIRET.** [ADR-0007](../../docs/adr/0007-consolidator-derived-attributes.md)
and its Amendment 1 require archived official evidence that the contract's exact
buyer SIRET is the commune DECP asserts. A SIREN answers a different question:
asked for a legal unit, this service returns no establishment at all, and one
commune in the September 2026 probes ran 109 of them.

**The resolution is exact or it is a refusal.** A search endpoint is not a lookup
endpoint: there is no `/siret/<siret>` path, the identifier goes in the free-text
`q`, and a search can return nothing, several things, or something that merely
resembles what was asked for. So `resolve` below requires exactly one result
carrying the exact identifier, and returns a reason rather than a best match
otherwise. Amendment 1 says this in as many words, because a best match here
would be a wrong buyer with correct-looking provenance.

**This source carries no officer role dates.** `dirigeants` is a current-officer
list taken from INPI, and a snapshot is not a history. Measured on 2026-09-22:
`qualite` holds the role, `date_de_naissance` is `YYYY-MM`, and no start or end
date exists under any name. So `role_start` and `role_end` stage as NULL with
`role_date_semantics = 'absent'`, which is a value rather than a footnote, and
constraint 9 then keeps every hit built on them out of a case packet. Whether
INPI's own register carries the history is the session 3 gate and needs an
account.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

import pyarrow as pa

from crony_eu.http import SourceClient, append_manifest, now, read_manifest
from crony_eu.parquet import write
from crony_eu.paths import Layout

SOURCE = "fr-entreprises-api"

#: The data is SIRENE and RNE republished by DINUM. Its backing dataset on
#: data.gouv.fr ("Données des entreprises utilisées dans l'Annuaire des
#: Entreprises") is Licence Ouverte 2.0. The `license` field in the service's own
#: OpenAPI document says MIT, which is the specification's licence and not the
#: data's; recording that here so nobody has to rediscover the difference.
LICENCE = "Licence Ouverte 2.0"

ENDPOINT = "https://recherche-entreprises.api.gouv.fr/search"

#: The publisher allows 7 requests per second per IP and asks for a descriptive
#: User-Agent. The client's default is 5, and it stays there: the documented
#: ceiling is "une limite maximale" and not a promise, and the publisher says
#: public services get priority when it is busy.
RATE_PER_SECOND = 5.0

#: What `type_dirigeant` says, and what this project calls it.
OFFICER_TYPES = {"personne physique": "natural", "personne morale": "legal"}


class SourceError(Exception):
    """A response this module will not read as an answer."""


@dataclass(frozen=True)
class Ask:
    """One identifier to resolve, and which question it answers."""

    kind: str  # "siren" for a supplier legal unit, "siret" for a buyer establishment
    value: str

    @property
    def filename(self) -> str:
        return f"{self.kind}-{self.value}.json"


@dataclass(frozen=True)
class Resolved:
    """A response that carried exactly what was asked for."""

    ask: Ask
    unit: dict[str, Any]
    establishment: dict[str, Any] | None


@dataclass(frozen=True)
class Unresolved:
    """A response that did not, and the reason, which is recorded not retried."""

    ask: Ask
    reason: str
    results: int


#: Reason codes. Written out so a report can count them and a reader can tell
#: "the registry does not have this" from "the search was ambiguous".
NOT_FOUND = "not_found"
SEVERAL_RESULTS = "several_results"
NO_EXACT_MATCH = "no_exact_match"
NO_ESTABLISHMENT = "no_establishment_for_siret"


#: `nom` as the service publishes it: the birth name, then the usage name in
#: parentheses when the register holds one. Measured over the `dep:74` slice on
#: 2026-09-22: 1,366 of 5,164 natural-person officers (26%) carry exactly this
#: shape and no other parenthesised shape occurs; in 931 of them the two names
#: are equal. The whole field must never reach a matching key: `DUPONT (DUPONT)`
#: normalises to `DUPONT DUPONT`, which matches no élu, and nothing raises.
_BIRTH_AND_USAGE = re.compile(r"^\s*([^()]+?)\s*\(\s*([^()]+?)\s*\)\s*$")


def split_surname(published: str | None) -> tuple[str | None, str | None]:
    """The birth name and the usage name, from one published field.

    ADR-0003 names both as surname variants and the source packs them into one
    string, so the split happens here, once, and the matching key reads two
    clean columns. A field with no parenthesised part is a birth name with no
    usage name recorded; anything that does not fit the one observed shape is
    kept whole as the birth name rather than guessed at.
    """
    if published is None:
        return None, None
    found = _BIRTH_AND_USAGE.match(published)
    if found is None:
        return published.strip() or None, None
    return found.group(1), found.group(2)


def resolve(payload: dict[str, Any], ask: Ask) -> Resolved | Unresolved:
    """Exactly one result carrying exactly this identifier, or a reason.

    Amendment 1 to ADR-0007: "a query returning zero results, several results, or
    no result carrying the exact SIRET is a refusal, not a best match". This is
    that rule, and it is written here rather than at the call site so that the
    buyer check and the supplier fetch cannot disagree about it.

    For a SIRET the establishment has to be in `matching_etablissements`, because
    that is the only place the service says which establishment it matched. The
    head office is not a substitute: asked for a legal unit it returns the siege
    and no match, which would answer a question nobody asked.
    """
    results = payload.get("results") or []
    if not results:
        return Unresolved(ask, NOT_FOUND, 0)
    if len(results) > 1:
        return Unresolved(ask, SEVERAL_RESULTS, len(results))

    unit = results[0]
    if ask.kind == "siren":
        if str(unit.get("siren") or "") != ask.value:
            return Unresolved(ask, NO_EXACT_MATCH, 1)
        return Resolved(ask, unit, None)

    matching = unit.get("matching_etablissements") or []
    exact = [e for e in matching if str(e.get("siret") or "") == ask.value]
    if not exact:
        return Unresolved(ask, NO_ESTABLISHMENT if matching else NO_EXACT_MATCH, 1)
    if len(exact) > 1:
        return Unresolved(ask, SEVERAL_RESULTS, len(exact))
    return Resolved(ask, unit, exact[0])


COMPANIES = pa.schema(
    [
        pa.field("siren", pa.string()),
        pa.field("nature_juridique", pa.string()),
        pa.field("statut_diffusion", pa.string()),
        pa.field("etat_administratif", pa.string()),
        pa.field("size_category", pa.string()),
        pa.field("activity_code", pa.string()),
        pa.field("date_creation", pa.string()),
        pa.field("head_office_siret", pa.string()),
        pa.field("head_office_commune_code", pa.string()),
        pa.field("establishment_count", pa.int32()),
        pa.field("officer_count", pa.int32()),
        pa.field("retrieved_at", pa.string()),
        pa.field("source_url", pa.string()),
    ]
)

OFFICERS = pa.schema(
    [
        pa.field("officer_row_id", pa.string()),
        pa.field("siren", pa.string()),
        pa.field("officer_type", pa.string()),
        pa.field("surname_birth_raw", pa.string()),
        pa.field("surname_usage_raw", pa.string()),
        pa.field("given_names_raw", pa.string()),
        pa.field("birth_ym", pa.string()),
        pa.field("birth_year_only", pa.string()),
        pa.field("role_label", pa.string()),
        pa.field("role_start", pa.date32()),
        pa.field("role_end", pa.date32()),
        pa.field("role_date_source", pa.string()),
        pa.field("role_date_semantics", pa.string()),
        pa.field("retrieved_at", pa.string()),
        pa.field("source_url", pa.string()),
    ]
)

#: Legal-person officers, kept for phase 2 (a company on a board is a hop, not a
#: person-to-company edge) and staged apart so nothing joins them to an élu.
OFFICER_COMPANIES = pa.schema(
    [
        pa.field("officer_row_id", pa.string()),
        pa.field("siren", pa.string()),
        pa.field("officer_siren", pa.string()),
        pa.field("denomination_raw", pa.string()),
        pa.field("role_label", pa.string()),
        pa.field("retrieved_at", pa.string()),
        pa.field("source_url", pa.string()),
    ]
)

#: The buyer-side evidence ADR-0007 Amendment 1 checks. One row per buyer SIRET
#: asked about. It records what the registry said; it decides nothing, because
#: the decision is the maintainer's and lives in the verification log.
BUYER_EVIDENCE = pa.schema(
    [
        pa.field("buyer_siret", pa.string()),
        pa.field("resolved", pa.bool_()),
        pa.field("reason", pa.string()),
        pa.field("siren", pa.string()),
        pa.field("nature_juridique", pa.string()),
        pa.field("establishment_commune_code", pa.string()),
        pa.field("establishment_state", pa.string()),
        pa.field("establishment_created", pa.string()),
        pa.field("establishment_closed", pa.string()),
        pa.field("statut_diffusion_etablissement", pa.string()),
        pa.field("is_head_office", pa.bool_()),
        pa.field("retrieved_at", pa.string()),
        pa.field("source_url", pa.string()),
        pa.field("evidence_sha256", pa.string()),
    ]
)

#: Identifiers the source would not resolve. Recorded with a reason and not
#: retried in a loop: a SIREN the registry does not have is an answer.
MISSING = pa.schema(
    [
        pa.field("kind", pa.string()),
        pa.field("value", pa.string()),
        pa.field("reason", pa.string()),
        pa.field("results", pa.int32()),
        pa.field("retrieved_at", pa.string()),
        pa.field("source_url", pa.string()),
    ]
)


SCOPED = True


def asks_for_scope(layout: Layout, scope: str) -> list[Ask]:
    """Every identifier the slice needs, read from staged DECP. Offline.

    Supplier SIRENs for the officers and the legal category; buyer SIRETs for the
    ADR-0007 check. Both come from `contracts.parquet`, so the set is a function
    of a staged snapshot rather than of whatever the API happens to hold today.
    """
    import duckdb

    from crony_eu.sources import fr_decp
    from crony_eu.survey import departement_of

    snapshot = None
    for candidate in reversed(layout.snapshots(fr_decp.SOURCE)):
        if (layout.staged(fr_decp.SOURCE, candidate) / "contracts.parquet").is_file():
            snapshot = candidate
            break
    if snapshot is None:
        raise SourceError(
            "fr-decp has no staged contracts.parquet. Run `crony fetch fr-decp` "
            "and `crony stage fr-decp` first."
        )

    path = (layout.staged(fr_decp.SOURCE, snapshot) / "contracts.parquet").as_posix()
    connection = duckdb.connect()
    try:
        rows = connection.execute(
            f"""
            WITH slice AS (
                SELECT * FROM '{path}'
                WHERE buyer_category = '{fr_decp.COMMUNE_CATEGORY}'
                  AND buyer_commune_code IS NOT NULL
                  AND {departement_of("buyer_commune_code")} = '{scope}'
            )
            SELECT 'siren' AS kind, supplier_siren AS value FROM slice
            WHERE supplier_siren IS NOT NULL
            UNION
            SELECT 'siret' AS kind, buyer_siret AS value FROM slice
            WHERE buyer_siret IS NOT NULL
            ORDER BY kind, value
            """
        ).fetchall()
    finally:
        connection.close()
    return [Ask(kind, value) for kind, value in rows]


def fetch(
    client: SourceClient, layout: Layout, snapshot: str, scope: str
) -> list[dict[str, Any]]:
    """One request per identifier in the slice, archived as it arrives.

    Resumable: an identifier already in the snapshot's manifest is skipped, so an
    interrupted run continues rather than starting the whole slice again. That is
    the difference between a minute and an apology to a public service.

    The response is archived whether or not it resolved. A refusal is evidence
    too, and re-asking to find out why would be the loop the work order forbids.
    """
    destination = layout.raw(SOURCE, snapshot)
    manifest = layout.manifest(SOURCE, snapshot)
    already = {entry["path"] for entry in read_manifest(manifest)}

    entries: list[dict[str, Any]] = []
    for ask in asks_for_scope(layout, scope):
        if ask.filename in already:
            continue
        response = client.get(ENDPOINT, params={"q": ask.value, "per_page": 5})
        body = response.content
        path = destination / ask.filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

        entry = {
            "source": SOURCE,
            "url": str(response.request.url),
            "path": ask.filename,
            "sha256": hashlib.sha256(body).hexdigest(),
            "bytes": len(body),
            "retrieved_at": now(),
            "licence": LICENCE,
            "status": response.status_code,
        }
        append_manifest(manifest, entry)
        entries.append(entry)
    return entries


def _officer_id(siren: str, index: int, officer: dict[str, Any]) -> str:
    """A stable id for one officer row within one company's response.

    The response carries no officer identifier, so the id is built from what
    distinguishes the row: the company, the role, and the officer's own fields.
    The position is included because a company can list the same person twice
    under two roles, and two rows that differ in nothing a reader can see still
    have to be two rows.
    """
    parts = [
        siren,
        str(index),
        str(officer.get("type_dirigeant") or ""),
        str(officer.get("qualite") or ""),
        str(officer.get("nom") or ""),
        str(officer.get("prenoms") or ""),
        str(officer.get("date_de_naissance") or ""),
        str(officer.get("denomination") or ""),
        str(officer.get("siren") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def stage(layout: Layout, snapshot: str) -> dict[str, int]:
    """Read the archived responses into four tables. Offline, and clock-free.

    Nothing here decides anything. `buyer_evidence` records what the registry
    said about a buyer SIRET; whether that corroborates the contract's buyer is a
    maintainer decision under ADR-0007 Amendment 1, and it lives in the
    verification log rather than in a column this stage could quietly set.
    """
    raw = layout.raw(SOURCE, snapshot)
    entries = read_manifest(layout.manifest(SOURCE, snapshot))
    if not entries:
        raise SourceError(
            f"{SOURCE}: snapshot {snapshot} has no manifest entries. Fetch it first."
        )

    companies: list[dict[str, Any]] = []
    officers: list[dict[str, Any]] = []
    officer_companies: list[dict[str, Any]] = []
    buyers: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []

    for entry in entries:
        path = raw / entry["path"]
        if not path.is_file():
            raise SourceError(
                f"{SOURCE}: {entry['path']} is in the manifest and not on disk."
            )
        kind, _, value = entry["path"].removesuffix(".json").partition("-")
        ask = Ask(kind, value)
        payload = json.loads(path.read_text(encoding="utf-8"))
        outcome = resolve(payload, ask)
        common = {"retrieved_at": entry["retrieved_at"], "source_url": entry["url"]}

        if isinstance(outcome, Unresolved):
            missing.append(
                {
                    "kind": ask.kind,
                    "value": ask.value,
                    "reason": outcome.reason,
                    "results": outcome.results,
                    **common,
                }
            )
            if ask.kind == "siret":
                buyers.append(
                    {
                        "buyer_siret": ask.value,
                        "resolved": False,
                        "reason": outcome.reason,
                        "evidence_sha256": entry["sha256"],
                        **common,
                    }
                )
            continue

        unit = outcome.unit
        if ask.kind == "siret":
            establishment = outcome.establishment or {}
            buyers.append(
                {
                    "buyer_siret": ask.value,
                    "resolved": True,
                    "reason": None,
                    "siren": unit.get("siren"),
                    "nature_juridique": unit.get("nature_juridique"),
                    "establishment_commune_code": establishment.get("commune"),
                    "establishment_state": establishment.get("etat_administratif"),
                    "establishment_created": establishment.get("date_creation"),
                    "establishment_closed": establishment.get("date_fermeture"),
                    "statut_diffusion_etablissement": establishment.get(
                        "statut_diffusion_etablissement"
                    ),
                    "is_head_office": establishment.get("est_siege"),
                    "evidence_sha256": entry["sha256"],
                    **common,
                }
            )
            continue

        siege = unit.get("siege") or {}
        officer_list = unit.get("dirigeants") or []
        companies.append(
            {
                "siren": unit.get("siren"),
                "nature_juridique": unit.get("nature_juridique"),
                "statut_diffusion": unit.get("statut_diffusion"),
                "etat_administratif": unit.get("etat_administratif"),
                "size_category": unit.get("categorie_entreprise"),
                "activity_code": unit.get("activite_principale"),
                "date_creation": unit.get("date_creation"),
                "head_office_siret": siege.get("siret"),
                "head_office_commune_code": siege.get("commune"),
                "establishment_count": unit.get("nombre_etablissements"),
                "officer_count": len(officer_list),
                **common,
            }
        )

        for index, officer in enumerate(officer_list):
            kind_of = OFFICER_TYPES.get(str(officer.get("type_dirigeant") or ""))
            row_id = _officer_id(str(unit.get("siren") or ""), index, officer)
            if kind_of == "legal":
                officer_companies.append(
                    {
                        "officer_row_id": row_id,
                        "siren": unit.get("siren"),
                        "officer_siren": officer.get("siren"),
                        "denomination_raw": officer.get("denomination"),
                        "role_label": officer.get("qualite"),
                        **common,
                    }
                )
                continue
            birth = officer.get("date_de_naissance")
            surname_birth, surname_usage = split_surname(officer.get("nom"))
            officers.append(
                {
                    "officer_row_id": row_id,
                    "siren": unit.get("siren"),
                    "officer_type": kind_of or "unknown",
                    # One published field, two names: see `split_surname`.
                    "surname_birth_raw": surname_birth,
                    "surname_usage_raw": surname_usage,
                    "given_names_raw": officer.get("prenoms"),
                    "birth_ym": birth if birth and len(str(birth)) == 7 else None,
                    "birth_year_only": officer.get("annee_de_naissance"),
                    "role_label": officer.get("qualite"),
                    # No role history in this source, measured rather than
                    # assumed. `absent` is a value, so a later reader can tell it
                    # from a date this project failed to parse.
                    "role_start": None,
                    "role_end": None,
                    "role_date_source": "none",
                    "role_date_semantics": "absent",
                    **common,
                }
            )

    staged = layout.staged(SOURCE, snapshot)
    return {
        "companies": write(
            companies, COMPANIES, staged / "companies.parquet", key=("siren",)
        ),
        "officers": write(
            officers, OFFICERS, staged / "officers.parquet", key=("officer_row_id",)
        ),
        "officer_companies": write(
            officer_companies,
            OFFICER_COMPANIES,
            staged / "officer_companies.parquet",
            key=("officer_row_id",),
        ),
        "buyer_evidence": write(
            buyers,
            BUYER_EVIDENCE,
            staged / "buyer_evidence.parquet",
            key=("buyer_siret",),
        ),
        "missing": write(
            missing,
            MISSING,
            staged / "officers_missing.parquet",
            key=("kind", "value"),
        ),
    }
