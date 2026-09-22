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
from crony_eu.match.review import sample_ids
from crony_eu.paths import Layout
from crony_eu.survey import BANDS

QUERY = Path(__file__).parent / "sql" / "f1_base_rate.sql"

#: The flag spec: "a seeded random sample of 100 candidate judgments reviewed by
#: the maintainer". The seed is the one the work order's acceptance run uses, so
#: the sample the maintainer reviews with `crony review --sample 100 --seed 1` is
#: the sample this reads.
PRECISION_SAMPLE = 100
PRECISION_SEED = 1

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
    sample_size: int
    seed: int
    reviewed: int
    confirmed: int
    rejected: int
    ambiguous: int

    @property
    def estimate(self) -> float | None:
        return self.confirmed / self.reviewed if self.reviewed else None


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
    """Confirmed over reviewed, on the seeded sample of candidate judgments."""
    connection = db.connect(layout)
    try:
        candidates = connection.execute(
            f"SELECT judgment_id FROM '{layout.candidates(scope).as_posix()}'"
        ).fetchall()
    finally:
        connection.close()
    drawn = sample_ids(
        [str(row[0]) for row in candidates], PRECISION_SAMPLE, PRECISION_SEED
    )
    status = {
        str(row["judgment_id"]): row["status"] for row in judgments.latest(layout)
    }
    counted = {
        s: 0 for s in (judgments.CONFIRMED, judgments.REJECTED, judgments.AMBIGUOUS)
    }
    for identifier in drawn:
        decided = status.get(identifier)
        if decided in counted:
            counted[decided] += 1
    return Precision(
        sample_size=len(drawn),
        seed=PRECISION_SEED,
        reviewed=sum(counted.values()),
        confirmed=counted[judgments.CONFIRMED],
        rejected=counted[judgments.REJECTED],
        ambiguous=counted[judgments.AMBIGUOUS],
    )


def report(layout: Layout, scope: str) -> dict[str, Any]:
    """Everything the STOP shows the maintainer, written beside the staged data."""
    run = current_run_directory(layout, scope)
    measured = precision(layout, scope)
    body = {
        "flag": FLAG,
        "scope": f"dep:{scope}",
        "run": run.name,
        "query": "crony-eu/src/crony_eu/flags/sql/f1_base_rate.sql",
        "bands": table(layout, run),
        "precision": {
            "sample_size": measured.sample_size,
            "seed": measured.seed,
            "reviewed": measured.reviewed,
            "confirmed": measured.confirmed,
            "rejected": measured.rejected,
            "ambiguous": measured.ambiguous,
            "estimate": measured.estimate,
        },
        "status": "uncalibrated: awaiting the maintainer's review of this table",
    }
    destination = layout.reports() / f"f1-base-rate-dep-{scope}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(body, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8"
    )
    return body
