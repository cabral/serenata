# SPDX-License-Identifier: AGPL-3.0-only
"""SQL fragments the source modules build their staging queries from.

Staging happens in DuckDB rather than in Python, because the files are large
enough that reading them into dicts costs more memory than the machine has. That
leaves a handful of expressions that more than one source needs to get exactly
right, and getting one of them subtly different in two places is the kind of
difference nobody notices until two tables disagree about the same row.

Fragments, not queries. Each function returns a string that a source module
drops into a `SELECT`, and the module decides what it means.
"""

from __future__ import annotations

from collections.abc import Sequence


def identity(parts: Sequence[str]) -> str:
    """sha256 over `parts`, with an explicit empty slot where a value is NULL.

    This is how every stable row and person id in the project is built, so the
    NULL handling matters more than it looks. `concat_ws` **drops** a NULL
    argument rather than leaving its separator behind, so `('A', NULL, 'B')` and
    `('A', 'B', NULL)` build the same string and get the same id. Casting each
    part and coalescing it to an empty string keeps the slot.

    Nothing in the élus register collides on it either way, and 691,606 of its
    1,066,291 rows carry a NULL in a hashed field. That is more rows than anyone
    should be relying on luck for.
    """
    slots = ", ".join(f"coalesce(CAST({part} AS VARCHAR), '')" for part in parts)
    return f"sha256(concat_ws('|', {slots}))"


def plausible_date(expression: str, earliest_year: int, pivot: str) -> str:
    """Whether a parsed date falls in the window this project believes.

    NULL is plausible: "not provided" is a fact about the source, and a stage
    that treated an absent date as a bad one would refuse every file with an
    optional column in it.
    """
    return (
        f"({expression} IS NULL OR (year({expression}) >= {earliest_year} "
        f"AND {expression} <= DATE '{pivot}'))"
    )


def luhn_ok(column: str, length: int) -> str:
    """Whether a fixed-length digit string passes the Luhn check.

    Unrolled rather than looped, because the lengths are fixed (9 for a SIREN,
    14 for a SIRET) and an unrolled sum is both obvious to read and fast over
    three million rows. Every second digit counting from the right is doubled,
    and a doubled value over nine has nine subtracted.

    The caller checks the length and the character class; this assumes both.
    """
    terms = []
    for position in range(1, length + 1):
        digit = f"CAST(substr({column}, {position}, 1) AS INTEGER)"
        if (length - position) % 2 == 1:
            terms.append(
                f"CASE WHEN {digit} > 4 THEN {digit} * 2 - 9 ELSE {digit} * 2 END"
            )
        else:
            terms.append(digit)
    return f"(({' + '.join(terms)}) % 10 = 0)"


def digits_only(column: str, length: int) -> str:
    """The column's digits, when there are exactly `length` of them, else NULL.

    Published identifiers arrive with spaces in them because that is how they
    are displayed. Stripping non-digits is safe here only because the length and
    the checksum are both checked afterwards.
    """
    stripped = f"regexp_replace(coalesce({column}, ''), '[^0-9]', '', 'g')"
    return f"nullif(CASE WHEN length({stripped}) = {length} THEN {stripped} END, '')"


def siret_valid(column: str, la_poste_siren: str) -> str:
    """Whether a fourteen-digit SIRET checks out, La Poste included.

    The SQL twin of `normalize.siret_valid`. Two implementations of one rule is
    a drift risk, and the reason there are two is that one runs over three
    million rows in DuckDB and the other runs in a test; the mitigation is a
    test that puts generated identifiers through both and compares.

    NULL in, NULL out: "no identifier published" is not "an identifier that
    failed", and F1's denominator needs to tell them apart.
    """
    digit_sum = " + ".join(
        f"CAST(substr({column}, {position}, 1) AS INTEGER)" for position in range(1, 15)
    )
    return (
        f"CASE WHEN {column} IS NULL THEN NULL "
        f"WHEN starts_with({column}, '{la_poste_siren}') THEN (({digit_sum}) % 5 = 0) "
        f"ELSE {luhn_ok(column, 14)} END"
    )
