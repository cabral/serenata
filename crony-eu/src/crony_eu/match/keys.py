# SPDX-License-Identifier: AGPL-3.0-only
"""`FR-NAME-BIRTHYM-v1`: the matching key, and nothing clever.

ADR-0003. A candidate exists when a surname variant, the first given name and the
birth year and month all match exactly, after the normalisation in
`crony_eu.normalize`. There is no fuzzy matching, no weighting, no threshold to
tune, because a wrong match between an elected official and a company officer is
a false accusation waiting to happen and the only defensible rule is one a person
can check by eye.

**Variants.** The élu side has one surname, `Nom de l'élu`. The officer side has
the birth name and, when the register holds one, the usage name; the company API
publishes them together as `BIRTH (USAGE)` and staging splits them. A key is
built per variant and duplicates are dropped, so an officer whose usage name
equals their birth name (931 of 1,366 in the `dep:74` slice) contributes one key,
not two.

**What is not a variant, on purpose.** 810 élu surnames nationally carry `EP`,
`NEE` or `VEUVE` inside them, and 139 carry a parenthesised name. The rule as
specified takes the élu surname whole, so those élus build a key that matches no
officer. That is 0.1% of élus, it is measured rather than assumed, and handling
it is a rule change with a new id, not an edit here.

**Missing parts build no key.** An officer without a birth month (2.69% of the
slice: 19 with a year only, 120 with nothing) cannot be matched by this rule and
is counted as such rather than matched on less.
"""

from __future__ import annotations

from dataclasses import dataclass

from crony_eu.normalize import given_key, norm_name

RULE_ID = "FR-NAME-BIRTHYM-v1"

#: Which surname a key was built from. Recorded on every candidate because
#: session 4 has to measure which variant élus match like, split by sex.
ELU = "elu"
BIRTH = "birth"
USAGE = "usage"


@dataclass(frozen=True)
class Key:
    """One matching key and the surname variant it came from."""

    variant: str
    value: str


def build(surname: str | None, given: str | None, birth_ym: str | None) -> str | None:
    """`SURNAME|GIVEN|YYYY-MM`, or `None` if any part is missing."""
    parts = (norm_name(surname), given_key(given), birth_ym)
    if not all(parts):
        return None
    return "|".join(str(part) for part in parts)


def elu_keys(surname: str | None, given: str | None, birth_ym: str | None) -> list[Key]:
    """The élu's one key, or none."""
    value = build(surname, given, birth_ym)
    return [] if value is None else [Key(ELU, value)]


def officer_keys(
    birth_surname: str | None,
    usage_surname: str | None,
    given: str | None,
    birth_ym: str | None,
) -> list[Key]:
    """One key per distinct surname variant, birth first."""
    found: list[Key] = []
    seen: set[str] = set()
    for variant, surname in ((BIRTH, birth_surname), (USAGE, usage_surname)):
        value = build(surname, given, birth_ym)
        if value is not None and value not in seen:
            seen.add(value)
            found.append(Key(variant, value))
    return found
