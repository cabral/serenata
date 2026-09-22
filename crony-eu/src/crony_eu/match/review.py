# SPDX-License-Identifier: AGPL-3.0-only
"""`crony review`: the maintainer's screen, for both logs.

This is the one part of the pipeline that shows real names, birth dates and
roles, and it is meant to. Constraint 13 says looking at real records is the
maintainer's job, in this command, outside any agent session; so the command
exists, it is tested on generated records, and it is run by a person.

**Two queues, because two questions.** People (`crony review --scope dep:<code>`):
is this élu that officer? Buyers (`crony review buyers --scope dep:<code>`): is
this contract's buyer SIRET the commune DECP says? ADR-0007 keeps them apart and
so does this screen: confirming one never touches the other.

Plain `print` and `input`, per ADR-0006. The two are passed in rather than
called directly, so a test can script the keypresses and read the screen, which
is how the work order asks for the loop to be tested.

**What a keypress can and cannot do on the buyer queue.** Amendment 1 to
ADR-0007: the four mechanical conditions have to hold, and the maintainer
confirms on top. So `c` is refused when the mechanical check failed; a person
cannot corroborate what the evidence does not. The reverse is allowed: a person
may record `false` or `unknown`, or mark the geography `contradicted`, because
erring toward a block is the safe direction. There is no key for `established`,
because no approved source can establish historical geography and a person's
recollection is not an official source.
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from crony_eu import db
from crony_eu.match import buyer_verification as bv
from crony_eu.match import judgments
from crony_eu.paths import Layout

Ask = Callable[[str], str]
Say = Callable[[str], None]

#: A link the reader may click. Printed, never fetched: constraint 6 forbids
#: scraping the annuaire, and a person following a link is not scraping.
ANNUAIRE = "https://annuaire-entreprises.data.gouv.fr/entreprise/{siren}"

PEOPLE_KEYS = {
    "c": judgments.CONFIRMED,
    "r": judgments.REJECTED,
    "a": judgments.AMBIGUOUS,
}
BUYER_KEYS = {"c": bv.TRUE, "r": bv.FALSE, "u": bv.UNKNOWN}


class ReviewError(Exception):
    """Nothing to review yet, and the command that would make something."""


@dataclass
class Tally:
    """What happened in one sitting. Counts only."""

    shown: int = 0
    skipped: int = 0
    stopped: bool = False
    decided: Counter[str] = field(default_factory=Counter)


def sample_ids(ids: Sequence[str], size: int, seed: int) -> list[str]:
    """A reproducible random sample, for the precision estimate.

    ADR-0003: precision is measured on a seeded random sample of candidates. The
    population is sorted before sampling, so the same candidates and the same seed
    give the same sample on any machine, and the flag's precision figure can be
    recomputed from the same draw rather than trusted.
    """
    ordered = sorted(ids)
    return random.Random(seed).sample(ordered, min(size, len(ordered)))


def _rows(layout: Layout, sql: str) -> list[dict[str, Any]]:
    connection = db.connect(layout)
    try:
        values = connection.execute(sql).fetchall()
        names = [description[0] for description in connection.description or []]
    finally:
        connection.close()
    return [dict(zip(names, row, strict=True)) for row in values]


def _by(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(row[key]): row for row in rows}


def people_queue(
    layout: Layout,
    scope: str,
    sample: int | None = None,
    seed: int | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Pending candidates for the slice, with everything the screen shows.

    Returns the cards and how many of the sample (or of all candidates) were
    already decided, so the screen can say how far through a sample a person is.
    """
    from crony_eu.sources import fr_entreprises_api, fr_rne_elus

    path = layout.candidates(scope)
    if not path.is_file():
        raise ReviewError(
            f"no candidates for dep:{scope}. Run `crony match fr --scope dep:{scope}`."
        )
    candidates = _rows(
        layout, f"SELECT * FROM '{path.as_posix()}' ORDER BY judgment_id"
    )
    status = {
        str(row["judgment_id"]): row["status"] for row in judgments.latest(layout)
    }

    chosen = [str(row["judgment_id"]) for row in candidates]
    if sample is not None:
        chosen = sample_ids(chosen, sample, seed if seed is not None else 0)
    already = sum(
        1 for identifier in chosen if status.get(identifier) != judgments.PENDING
    )
    wanted = [i for i in chosen if status.get(i) == judgments.PENDING]
    if not wanted:
        return [], already

    elus_snapshot = layout.latest_staged(fr_rne_elus.SOURCE, "elu_person")
    api_snapshot = layout.latest_staged(fr_entreprises_api.SOURCE, "officers")
    if (
        elus_snapshot is None or api_snapshot is None
    ):  # pragma: no cover - match needs both
        raise ReviewError(
            "the staged élus or officers have gone missing since matching"
        )
    staged_elus = layout.staged(fr_rne_elus.SOURCE, elus_snapshot)
    staged_api = layout.staged(fr_entreprises_api.SOURCE, api_snapshot)

    elus = _by(
        _rows(
            layout, f"SELECT * FROM '{(staged_elus / 'elu_person.parquet').as_posix()}'"
        ),
        "elu_person_id",
    )
    officers = _by(
        _rows(
            layout, f"SELECT * FROM '{(staged_api / 'officers.parquet').as_posix()}'"
        ),
        "officer_row_id",
    )
    companies = _by(
        _rows(
            layout, f"SELECT * FROM '{(staged_api / 'companies.parquet').as_posix()}'"
        ),
        "siren",
    )

    index = {str(row["judgment_id"]): row for row in candidates}
    cards = []
    for identifier in wanted:
        candidate = index[identifier]
        cards.append(
            {
                "candidate": candidate,
                "elu": elus.get(str(candidate["elu_person_id"]), {}),
                "officer": officers.get(str(candidate["officer_row_id"]), {}),
                "company": companies.get(str(candidate["siren"]), {}),
            }
        )
    return cards, already


def render_person(card: dict[str, Any]) -> list[str]:
    """One candidate, the élu beside the officer, and what the dates mean."""
    candidate, elu = card["candidate"], card["elu"]
    officer, company = card["officer"], card["company"]
    head_office = str(company.get("head_office_commune_code") or "")
    commune = str(candidate["elu_commune_code"] or "")
    same = (
        "same departement"
        if head_office[:2] == commune[:2] and head_office
        else ("different departement" if head_office else "head office unknown")
    )
    lines = [
        "",
        f"  candidate {candidate['judgment_id'][:12]}  rule {candidate['rule_id']}"
        f"  matched on the {candidate['surname_variant']} surname",
    ]
    if candidate["key_collision"]:
        lines.append(
            f"  ! key collision: {candidate['elu_communes_for_key']} commune(s), "
            f"{candidate['officer_companies_for_key']} company(ies) share this key"
        )
    lines += [
        "",
        "  ELU                                 OFFICER",
        f"  surname  {elu.get('surname_raw')!s:<26} "
        f"birth {officer.get('surname_birth_raw')}  "
        f"usage {officer.get('surname_usage_raw')}",
        f"  given    {elu.get('given_raw')!s:<26} {officer.get('given_names_raw')}",
        f"  born     {elu.get('birth_date')!s:<26} {officer.get('birth_ym')}",
        f"  sex      {elu.get('sex')!s:<26}",
        f"  commune  {commune} {elu.get('commune_label')} ({elu.get('snapshot_kind')})",
        f"  mandate  from {elu.get('mandate_start')}  "
        f"functions: {elu.get('function_labels') or 'none'}",
        "",
        f"  company  {company.get('name')}  SIREN {candidate['siren']}",
        f"           legal category {company.get('nature_juridique')}, "
        f"diffusion {company.get('statut_diffusion')}, {same}",
        f"  role     {officer.get('role_label')}",
        f"  dates    start {officer.get('role_start')}  end {officer.get('role_end')}  "
        f"({officer.get('role_date_semantics')}: "
        + (
            "this source publishes no role dates, so no overlap can be shown"
            if officer.get("role_date_semantics") == "absent"
            else "see the source"
        )
        + ")",
        f"  source   {ANNUAIRE.format(siren=candidate['siren'])}",
        "",
        "  A territory hint never confirms a match on its own (ADR-0003).",
    ]
    return lines


def _read(ask: Ask, prompt: str) -> str:
    try:
        return ask(prompt).strip().lower()
    except EOFError:
        return "q"


def review_people(
    layout: Layout,
    scope: str,
    reviewer: str,
    *,
    ask: Ask | None = None,
    say: Say | None = None,
    sample: int | None = None,
    seed: int | None = None,
) -> Tally:
    """Walk the pending candidates and record what the reviewer decides.

    `ask` and `say` default to `input` and `print` looked up when called, not
    when this module was imported; a default bound at import would ignore
    anything that replaced them afterwards, which is how the first version of
    this command's own test was fooled.
    """
    ask = ask if ask is not None else input
    say = say if say is not None else print
    cards, already = people_queue(layout, scope, sample, seed)
    tally = Tally()
    if sample is not None:
        say(
            f"sample of {sample} with seed {seed}: {already} already decided, "
            f"{len(cards)} to go"
        )
    else:
        say(f"{len(cards)} pending candidates in dep:{scope}")

    for card in cards:
        tally.shown += 1
        for line in render_person(card):
            say(line)
        note: str | None = None
        while True:
            key = _read(ask, "[c]onfirm [r]eject [a]mbiguous [n]ote [s]kip [q]uit > ")
            if key == "n":
                note = _read_note(ask)
                continue
            if key in PEOPLE_KEYS:
                judgments.decide(
                    layout,
                    str(card["candidate"]["judgment_id"]),
                    PEOPLE_KEYS[key],
                    reviewer,
                    note,
                )
                tally.decided[PEOPLE_KEYS[key]] += 1
                break
            if key == "s":
                tally.skipped += 1
                break
            if key == "q":
                tally.stopped = True
                return tally
            say("  keys: c r a n s q")
    return tally


def _read_note(ask: Ask) -> str | None:
    try:
        return ask("note > ").strip() or None
    except EOFError:
        return None


def buyers_queue(layout: Layout, scope: str) -> list[dict[str, Any]]:
    """The slice's buyer assertions that nobody has decided."""
    from crony_eu.sources import fr_decp, fr_entreprises_api

    decp_snapshot = layout.latest_staged(fr_decp.SOURCE, "contracts")
    api_snapshot = layout.latest_staged(fr_entreprises_api.SOURCE, "buyer_evidence")
    if decp_snapshot is None or api_snapshot is None:
        raise ReviewError(
            "buyer review needs staged DECP contracts and staged buyer evidence. "
            f"Run `crony fetch fr-entreprises-api --scope dep:{scope}` and "
            "`crony stage fr-entreprises-api`."
        )
    queued = bv.queue(layout, decp_snapshot, api_snapshot, scope)
    waiting = set(bv.pending(layout, queued))
    return [row for row in queued if row["verification_id"] in waiting]


def render_buyer(row: dict[str, Any], geography: str) -> list[str]:
    """What DECP asserts, what the registry answered, and the proposal."""
    assertion: bv.Assertion = row["assertion"]
    evidence: bv.Evidence | None = row["evidence"]
    assessment: bv.Assessment = row["assessment"]
    lines = [
        "",
        f"  buyer SIRET {assertion.buyer_siret}   "
        f"DECP snapshot {assertion.decp_snapshot}",
        "",
        "  DECP ASSERTS (consolidator's join)     REGISTRY ANSWERED",
        f"  category {assertion.asserted_category!s:<29} "
        f"legal category {evidence.nature_juridique if evidence else '-'}",
        f"  commune  {assertion.asserted_commune_code!s:<29} "
        f"commune {evidence.commune_code if evidence else '-'}",
        f"  legal unit {assertion.expected_siren:<27} "
        f"legal unit {evidence.siren if evidence else '-'}",
    ]
    if evidence is not None:
        lines += [
            f"  establishment state {evidence.state}   "
            f"retrieved {evidence.retrieved_at}",
            f"  evidence {evidence.source_url}",
        ]
    lines += [
        "",
        f"  proposal: identity {assessment.identity_corroborated}"
        + (f" ({assessment.blocking_reason})" if assessment.blocking_reason else ""),
        f"  historical geography: {geography}",
        "  Snapshot corroboration: the four checks establish identity as of the",
        "  snapshot. Historical commune-code continuity is not established by any",
        "  approved source, and is recorded as such, never as true.",
    ]
    return lines


def review_buyers(
    layout: Layout,
    scope: str,
    reviewer: str,
    *,
    ask: Ask | None = None,
    say: Say | None = None,
) -> Tally:
    """Walk the undecided buyer assertions and record the two facts apart."""
    ask = ask if ask is not None else input
    say = say if say is not None else print
    queue = buyers_queue(layout, scope)
    tally = Tally()
    say(f"{len(queue)} buyer assertions to review in dep:{scope}")

    for row in queue:
        tally.shown += 1
        geography = bv.NOT_ESTABLISHED
        note: str | None = None
        for line in render_buyer(row, geography):
            say(line)
        while True:
            key = _read(
                ask,
                "[c]orroborated [r]efuted [u]nknown  "
                "[x] geography contradicted  [n]ote [s]kip [q]uit > ",
            )
            if key == "n":
                note = _read_note(ask)
                continue
            if key == "x":
                geography = bv.CONTRADICTED
                say("  historical geography marked contradicted; a note is required")
                note = _read_note(ask) or note
                continue
            if key == "c" and row["assessment"].identity_corroborated != bv.TRUE:
                say(
                    "  refused: a mechanical condition failed "
                    f"({row['assessment'].blocking_reason}), and a person cannot "
                    "corroborate what the evidence does not (ADR-0007, Amendment 1)"
                )
                continue
            if key in BUYER_KEYS:
                if geography == bv.CONTRADICTED and not note:
                    say(
                        "  a contradicted geography needs a note saying what "
                        "contradicts it"
                    )
                    continue
                bv.append(
                    layout,
                    [
                        bv.record(
                            row,
                            identity_corroborated=BUYER_KEYS[key],
                            historical_geography=geography,
                            decided_by=reviewer,
                            note=note,
                        )
                    ],
                )
                tally.decided[BUYER_KEYS[key]] += 1
                break
            if key == "s":
                tally.skipped += 1
                break
            if key == "q":
                tally.stopped = True
                return tally
            say("  keys: c r u x n s q")
    return tally
