# SPDX-License-Identifier: AGPL-3.0-only
"""F1's base rate: the query, Wilson intervals, per-gate losses and precision.

Constraint 8 wants the measured base rate with the query that measured it, so the
counting lives in `flags/sql/f1_base_rate.sql` and this module only runs it, adds
the intervals, and reads precision off the maintainer's reviews.

**Nothing here writes into the flag spec.** The work order's session 5 STOP: show
the maintainer the aggregate table, the coverage numbers and the precision
estimate first; only after approval are the spec's tables filled and the status
line changed. The table goes to `$CRONY_DATA_DIR/staged/_reports/` and to the
terminal, and constraint 12 applies to it before it goes anywhere else: its cells
are small in one département.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from crony_eu import db
from crony_eu.flags.f1_same_body import FLAG, current_run
from crony_eu.match import judgments
from crony_eu.paths import Layout
from crony_eu.survey import BANDS

QUERY = Path(__file__).parent / "sql" / "f1_base_rate.sql"

#: The two bands phase 1 reports, split at the 432-12 line (3,500 inhabitants,
#: inclusive). One département cannot support five: on `dep:74` the five-band
#: candidate counts were 0, 12, 4, 3 and 0, and every interval overlapped every
#: other. The five bands stay in the report for inspection and are not used for
#: any claim.
AT_OR_BELOW_432_12 = ("up to 500", "501 to 3,500")
ABOVE_432_12 = ("3,501 to 10,000", "10,001 to 50,000", "above 50,000")

#: DECP publishes a contract only from this amount, excluding VAT (Code de la
#: commande publique art. R2196-1; `crony-eu/docs/sources/france.md`). Every rate
#: here is a rate among contracts of at least this size, never among all of a
#: commune's purchasing.
DECP_THRESHOLD_EUR = 40_000

#: "Autre SA à conseil d'administration". A société publique locale has no
#: catégorie juridique of its own and is filed here, so F1's exclusion list cannot
#: remove it, and a pair whose supplier carries this code may be one.
SPL_INDISTINGUISHABLE = "5599"

#: z for a two-sided 95% interval.
Z95 = 1.959963984540054


def wilson(successes: int, trials: int, z: float = Z95) -> tuple[float, float] | None:
    """The Wilson score interval, or `None` when there were no trials.

    Wilson rather than the normal approximation because these proportions are
    small and so are the cells, which is exactly where the normal approximation
    produces intervals below zero.
    """
    if trials == 0:
        return None
    phat = successes / trials
    denominator = 1 + z * z / trials
    centre = (phat + z * z / (2 * trials)) / denominator
    margin = (
        z * math.sqrt(phat * (1 - phat) / trials + z * z / (4 * trials * trials))
    ) / denominator
    # At 0 successes the lower bound is exactly 0 and at `trials` successes the
    # upper bound is exactly 1; the arithmetic above reaches them only to within
    # a rounding error, and a published interval should not read 0.9999999999.
    low = 0.0 if successes == 0 else max(0.0, centre - margin)
    high = 1.0 if successes == trials else min(1.0, centre + margin)
    return (low, high)


@dataclass(frozen=True)
class Precision:
    """Confirmed over reviewed, across every candidate in the slice.

    A census rather than a sample. ADR-0003 reviews a seeded sample of 100 by
    default; `dep:74` has 107 candidates, so a sample would be 93% of them and a
    census costs seven more decisions for a figure with no sampling error. A slice
    with thousands of candidates goes back to `crony review --sample`.
    """

    population: int
    reviewed: int
    confirmed: int
    rejected: int
    ambiguous: int

    @property
    def estimate(self) -> float | None:
        return self.confirmed / self.reviewed if self.reviewed else None

    @property
    def interval(self) -> tuple[float, float] | None:
        return wilson(self.confirmed, self.reviewed)


def current_run_directory(layout: Layout, scope: str) -> Path:
    """The F1 run the current inputs correspond to, which must already exist."""
    _, run = current_run(layout, scope)
    if not (run / "hits.parquet").is_file():
        raise FileNotFoundError(
            f"no F1 run for the current inputs of dep:{scope}. "
            f"Run `crony flag F1 --scope dep:{scope}`."
        )
    return run


def table(layout: Layout, run: Path) -> list[dict[str, Any]]:
    """The per-band counts from the cited query, with intervals added."""
    connection = db.connect(layout)
    try:
        cursor = connection.execute(
            QUERY.read_text(encoding="utf-8"),
            {
                "hits": (run / "hits.parquet").as_posix(),
                "pairs": (run / "pairs.parquet").as_posix(),
            },
        )
        values = cursor.fetchall()
        names = [description[0] for description in cursor.description or []]
    finally:
        connection.close()

    # In band order rather than the query's alphabetical one, so "10,001 to
    # 50,000" does not sort before "up to 500".
    order = {label: index for index, (_, label) in enumerate(BANDS)}
    rows = sorted(
        (dict(zip(names, row, strict=True)) for row in values),
        key=lambda row: order.get(str(row["band"]), len(order)),
    )
    for row in rows:
        for cut in ("candidate", "confirmed", "eligible"):
            row[f"{cut}_rate_ci95"] = wilson(
                int(row[f"{cut}_pairs"]), int(row["pairs"])
            )
    return rows


def precision(layout: Layout, scope: str) -> Precision:
    """Confirmed over reviewed, across every candidate judgment in the slice."""
    connection = db.connect(layout)
    try:
        candidates = connection.execute(
            f"SELECT judgment_id FROM '{layout.candidates(scope).as_posix()}'"
        ).fetchall()
    finally:
        connection.close()
    status = {
        str(row["judgment_id"]): row["status"] for row in judgments.latest(layout)
    }
    counted = {
        s: 0 for s in (judgments.CONFIRMED, judgments.REJECTED, judgments.AMBIGUOUS)
    }
    for (identifier,) in candidates:
        decided = status.get(str(identifier))
        if decided in counted:
            counted[decided] += 1
    return Precision(
        population=len(candidates),
        reviewed=sum(counted.values()),
        confirmed=counted[judgments.CONFIRMED],
        rejected=counted[judgments.REJECTED],
        ambiguous=counted[judgments.AMBIGUOUS],
    )


def summary(bands: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One overall row and two bands split at the 432-12 line, with intervals.

    Sums of the query's per-band rows, and exact: a pair belongs to one commune
    and a commune to one band, so no pair is counted in two rows. A commune with no
    population row (band `unknown`) counts in the overall row and in neither band.
    """
    groups = {
        "all pairs": [row["band"] for row in bands],
        "3,500 or fewer": list(AT_OR_BELOW_432_12),
        "over 3,500": list(ABOVE_432_12),
    }
    rows = []
    for label, members in groups.items():
        chosen = [row for row in bands if row["band"] in members]
        pairs = sum(int(row["pairs"]) for row in chosen)
        candidates = sum(int(row["candidate_pairs"]) for row in chosen)
        rows.append(
            {
                "group": label,
                "pairs": pairs,
                "candidate_pairs": candidates,
                "confirmed_pairs": sum(int(row["confirmed_pairs"]) for row in chosen),
                "eligible_pairs": sum(int(row["eligible_pairs"]) for row in chosen),
                "role_resolved_pairs": sum(
                    int(row["role_resolved_pairs"]) for row in chosen
                ),
                "candidate_rate": candidates / pairs if pairs else None,
                "candidate_rate_ci95": wilson(candidates, pairs),
            }
        )
    return rows


def measure(bands: list[dict[str, Any]]) -> str:
    """What the candidate rate actually measures, read off the data.

    F1 is about an officer role held **on the notification date**. While no
    candidate pair has a role date that resolves, the rate cannot be that: it is
    a name and birth-month match between a councillor and someone who is an
    officer of the supplier now. The label says so, and changes by itself the
    first time a role date resolves, so it cannot outlive the reason for it.
    """
    if any(int(row["role_resolved_pairs"]) for row in bands):
        return "dated overlap: officer role checked against the notification date"
    return (
        "co-occurrence with a current officer, counts only: no candidate pair has "
        "a role date, so nothing here says the role was held when the contract was "
        "notified"
    )


def limits(layout: Layout, run: Path, scope: str) -> list[str]:
    """The limits that travel with the rate, with their numbers where they have one."""
    connection = db.connect(layout)
    try:
        counted = connection.execute(
            f"""
            SELECT count(*),
                   count(*) FILTER (
                       supplier_legal_category = '{SPL_INDISTINGUISHABLE}'),
                   count(*) FILTER (population_band = 'unknown')
            FROM '{(run / "pairs.parquet").as_posix()}'
            """
        ).fetchone()
    finally:
        connection.close()
    assert counted is not None, "an aggregate query always returns one row"
    pairs, spl_code, unknown = (int(value) for value in counted)
    return [
        f"DECP publishes contracts of {DECP_THRESHOLD_EUR:,} EUR excluding VAT or "
        "more (art. R2196-1), so every rate is among contracts of that size and says "
        "nothing about smaller purchasing.",
        f"One département, dep:{scope}, chosen as a pilot and not as representative; "
        "no rate here generalises to France.",
        f"{spl_code:,} of {pairs:,} pairs have a supplier filed as "
        f"{SPL_INDISTINGUISHABLE} ('Autre SA à conseil d'administration'), where a "
        "société publique locale also sits and cannot be excluded by category.",
        f"{unknown:,} of {pairs:,} pairs are in a commune with no population row, "
        "and are counted overall but in neither band.",
        "Candidates are matched on name and birth month and are unreviewed until the "
        "maintainer decides them, so the candidate rate includes homonyms at a rate "
        "the precision figure below measures once reviewed.",
    ]


def report(layout: Layout, scope: str) -> dict[str, Any]:
    """Everything the STOP shows the maintainer, written beside the staged data."""
    run = current_run_directory(layout, scope)
    measured = precision(layout, scope)
    bands = table(layout, run)
    body = {
        "flag": FLAG,
        "scope": f"dep:{scope}",
        "run": run.name,
        "query": "crony-eu/src/crony_eu/flags/sql/f1_base_rate.sql",
        "measure": measure(bands),
        "summary": summary(bands),
        "limits": limits(layout, run, scope),
        "bands_for_inspection_only": bands,
        "precision": {
            "population": measured.population,
            "reviewed": measured.reviewed,
            "confirmed": measured.confirmed,
            "rejected": measured.rejected,
            "ambiguous": measured.ambiguous,
            "estimate": measured.estimate,
            "estimate_ci95": measured.interval,
        },
        "status": "uncalibrated: awaiting the maintainer's review of this table",
    }
    destination = layout.reports() / f"f1-base-rate-dep-{scope}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(body, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return body
