# SPDX-License-Identifier: AGPL-3.0-only
"""Is this élu that officer? A person's answer, never the program's.

Constraint 3: candidate matches are not facts. A candidate enters here as
`pending`, and only a `confirmed` judgment set by a person in `crony review` can
put a person-to-company edge into an export.

Append-only, through `crony_eu.match.log`. A judgment is never overwritten, only
superseded by a newer revision, because a packet names the judgments it was built
on and constraint 11 says a packet whose judgment is later reversed has to be
found and withdrawn. `history` is how.

**A judgment records the rule it was made under.** ADR-0003: a rule change gets a
new rule id and does not revalue old decisions. `judgment_id` hashes the rule id
with the two records, so the same pair under a new rule is a new judgment with no
decision against it.

**A confirmed identity is not a dated link.** ADR-0003's amendment: `confirmed`
says two records describe one person. Whether that person held the office when
the contract was signed is `role_overlap`, which F1 computes and which this
module knows nothing about.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from typing import Any

import pyarrow as pa

from crony_eu.match.log import Log
from crony_eu.paths import Layout

PENDING = "pending"
CONFIRMED = "confirmed"
REJECTED = "rejected"
AMBIGUOUS = "ambiguous"
STATUSES = (PENDING, CONFIRMED, REJECTED, AMBIGUOUS)

#: Who wrote a `pending` row. Not a person: the candidate builder, entering a
#: candidate into the log so a person can decide it.
MACHINE = "crony match"

SCHEMA = pa.schema(
    [
        pa.field("judgment_id", pa.string()),
        pa.field("revision", pa.int32()),
        pa.field("rule_id", pa.string()),
        pa.field("elu_person_id", pa.string()),
        pa.field("officer_row_id", pa.string()),
        pa.field("siren", pa.string()),
        pa.field("status", pa.string()),
        pa.field("decided_by", pa.string()),
        pa.field("note", pa.string()),
        pa.field("run_id", pa.string()),
    ]
)


def judgment_id(rule_id: str, elu_person_id: str, officer_row_id: str) -> str:
    return hashlib.sha256(
        f"{rule_id}|{elu_person_id}|{officer_row_id}".encode()
    ).hexdigest()


def _log(layout: Layout) -> Log:
    return Log(layout.judgments(), SCHEMA, "judgment_id")


def enter(layout: Layout, candidates: Sequence[dict[str, Any]], run_id: str) -> int:
    """Add a `pending` row for every candidate not already in the log.

    Safe to run twice. A candidate that already has any judgment, pending or
    decided, is left alone: re-entering it as pending would supersede a person's
    decision with the program's, which is the one thing this log exists to
    prevent. Returns how many were entered.
    """
    known = _log(layout).decided()
    fresh = [
        {
            "judgment_id": candidate["judgment_id"],
            "rule_id": candidate["rule_id"],
            "elu_person_id": candidate["elu_person_id"],
            "officer_row_id": candidate["officer_row_id"],
            "siren": candidate["siren"],
            "status": PENDING,
            "decided_by": MACHINE,
            "note": None,
            "run_id": run_id,
        }
        for candidate in candidates
        if str(candidate["judgment_id"]) not in known
    ]
    unique = list({row["judgment_id"]: row for row in fresh}.values())
    if unique:
        _log(layout).append(unique)
    return len(unique)


def decide(
    layout: Layout,
    identifier: str,
    status: str,
    decided_by: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Record a person's decision as a new revision. Returns the row written.

    Only an existing judgment can be decided, so a decision always carries the
    rule id and the two records it is about, copied from the log rather than
    supplied again by a caller who might supply them wrongly.
    """
    if status not in (CONFIRMED, REJECTED, AMBIGUOUS):
        raise ValueError(
            f"a person decides {CONFIRMED!r}, {REJECTED!r} or {AMBIGUOUS!r}, "
            f"not {status!r}; {PENDING!r} is only ever the program's entry."
        )
    told = _log(layout).history(identifier)
    if not told:
        raise KeyError(f"no judgment {identifier} to decide")
    base = told[-1]
    row = {
        **{name: base[name] for name in SCHEMA.names if name != "revision"},
        "status": status,
        "decided_by": decided_by,
        "note": note,
    }
    _log(layout).append([row])
    return _log(layout).history(identifier)[-1]


def latest(layout: Layout) -> list[dict[str, Any]]:
    """`judgments_latest`: the current status of every judgment."""
    return _log(layout).latest()


def history(layout: Layout, identifier: str) -> list[dict[str, Any]]:
    """Every revision of one judgment, oldest first."""
    return _log(layout).history(identifier)
