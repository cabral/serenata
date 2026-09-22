# SPDX-License-Identifier: AGPL-3.0-only
"""Turning what a source published into what the pipeline compares.

Dates, French company identifiers, and the name keys `FR-NAME-BIRTHYM-v1` is
built on. The name rules are specified in `crony-eu/CLAUDE.md` and ADR-0003, and
they are written here once so that the élu side and the officer side of a match
cannot be normalised by two slightly different rules.

**Three published shapes, chosen by the shape and not by trying in order.**

    1971-04-03   ISO 8601, the current register since its August 2026 update
    03/04/1971   day first, four-digit year, older files
    03/04/71     day first, TWO-digit year, the pre-election extracts

The third one is why this module is written the way it is. Trying formats in
order looks reasonable and is not: `%d/%m/%Y` **accepts** `03/04/71` and returns
the year 71. Staging the real register that way produced 520,240 rows, every row
of both pre-election files, with a birth year under 100 and a mandate starting
in the year 20. Nothing raised. A mandate beginning in the year 20 precedes
every contract ever notified, so F1's `mandate_overlap` would have been true for
half the population and the flag would have looked like it worked.

So the format is decided by matching the whole string against a pattern, and
anything that matches none of them is an error rather than a best effort.

**The two-digit year needs a century, and guessing is not allowed.** The rule
is that a published register cannot record a date in the future: `30` read as
2030 in a file published in 2026 must be 1930. That resolves every value except
one born more than a century before the file, and `plausible` below is how many
of those there are rather than a claim there are none.

**An error message never carries the value.** A malformed birth date is still a
birth date, and constraint 13 says an agent session prints schemas and counts,
never values.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date

#: Shape -> format, in the order they are tested. The pattern is matched against
#: the whole string, so `03/04/71` cannot be read by the four-digit rule.
DATE_SHAPES: tuple[tuple[str, str], ...] = (
    (r"\d{4}-\d{2}-\d{2}", "%Y-%m-%d"),
    (r"\d{2}/\d{2}/\d{4}", "%d/%m/%Y"),
    (r"\d{2}/\d{2}/\d{2}", "%d/%m/%y"),
)

#: The shape whose year is two digits and therefore needs a century.
TWO_DIGIT_YEAR = r"\d{2}/\d{2}/\d{2}"

#: The earliest year this project believes. A councillor born before this is
#: over a century old at the time of writing; a mandate starting before it is a
#: typo. Values outside the window are counted and reported, never corrected.
EARLIEST_PLAUSIBLE_YEAR = 1900

#: Above this share of implausible dates in one column of one file, staging
#: stops: that is this project reading the file wrongly, not the register being
#: surprising. Reading the pre-election extracts with the four-digit rule put
#: 100% of their rows outside the window; the real register's own typos are one
#: row in 511,225. Anything between those two is worth a look rather than a
#: silent pass, and 1% is where that line is drawn.
IMPLAUSIBLE_RATE_LIMIT = 0.01


class DateFormatError(ValueError):
    """A date in none of the three published shapes."""


def parse_date(value: str | None, *, not_after: date | None = None) -> date | None:
    """A published date, or `None` when the source left it empty.

    `not_after` supplies the century for a two-digit year: anything landing
    after it belongs to the previous century, because a register cannot publish
    a date that has not happened. Without it, a two-digit year is refused rather
    than guessed.
    """
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None

    for pattern, fmt in DATE_SHAPES:
        if not re.fullmatch(pattern, text):
            continue
        parsed = _strict(text, fmt)
        if pattern == TWO_DIGIT_YEAR:
            return _century(parsed, not_after)
        return parsed

    raise DateFormatError(
        f"not one of the published date shapes {[p for p, _ in DATE_SHAPES]}. "
        "The value is deliberately not shown: it may be a person's birth date "
        "(CLAUDE.md, constraint 13)."
    )


def _strict(text: str, fmt: str) -> date:
    """`strptime`, refusing the trailing text it would otherwise accept."""
    from datetime import datetime

    try:
        parsed = datetime.strptime(text, fmt)
    except ValueError as error:
        raise DateFormatError(
            f"matched the shape for {fmt} and is not a real date (the value is "
            "not shown; constraint 13)."
        ) from error
    return date(parsed.year, parsed.month, parsed.day)


def _century(parsed: date, not_after: date | None) -> date:
    if not_after is None:
        raise DateFormatError(
            "has a two-digit year and no reference date to place it in a "
            "century. Pass `not_after` (the snapshot's own date): a register "
            "cannot publish a date in the future, which is what decides the "
            "century without guessing."
        )
    if parsed <= not_after:
        return parsed
    return parsed.replace(year=parsed.year - 100)


def plausible(value: date | None, not_after: date) -> bool:
    """Whether a date falls in the window this project believes.

    Not a correction and not a filter: staging counts what fails and refuses to
    continue if anything does, because a date outside this window means the file
    was read wrongly rather than that someone was born in the year 20.
    """
    if value is None:
        return True
    return value.year >= EARLIEST_PLAUSIBLE_YEAR and value <= not_after


def birth_ym(value: date | None) -> str | None:
    """`YYYY-MM`, the birth key the matching rule compares on (ADR-0003).

    Year and month rather than the full date, because that is the precision the
    officer side of the match carries. Measured on the open company API in
    September 2026: `date_de_naissance` is `YYYY-MM` on every officer record
    that has one.
    """
    return None if value is None else f"{value.year:04d}-{value.month:02d}"


# --- French company identifiers ---------------------------------------------
#
# A SIREN identifies a legal unit (9 digits); a SIRET identifies one of its
# establishments (the same 9 digits, then a 5-digit NIC). Both carry a Luhn
# check digit, and checking it is worth the lines: DECP's supplier identifier is
# keyed in by the buyer, and a mistyped SIRET that still matches `\d{14}` would
# join a contract to whichever company happens to own that number.
#
# Validity is recorded, never used to drop a row. A contract whose supplier
# identifier fails the check is still a contract, and F1 needs it in the
# denominator; what it must not do is claim that identifier means a company.

#: La Poste's SIREN. Its *establishments* are the documented exception to the
#: checksum: the SIRET series was allocated outside the Luhn rule, and the
#: published rule for them is instead that the sum of the fourteen digits is a
#: multiple of five. Without it, every one of them reads as a typo.
#:
#: The SIREN itself needs no exception; it passes Luhn like any other. The first
#: version of this module special-cased it too, and the test that asserted the
#: exception was needed is what showed it was not.
LA_POSTE_SIREN = "356000000"


def digits(value: str | None) -> str | None:
    """The digits in a published identifier, or `None` when there are none.

    Published SIRETs arrive with spaces and non-breaking spaces in them, because
    that is how they are displayed and how they get pasted. Stripping anything
    that is not a digit is safe here precisely because the length and the
    checksum are both checked afterwards.
    """
    if value is None:
        return None
    kept = "".join(character for character in value if character.isdigit())
    return kept or None


def luhn_ok(number: str) -> bool:
    """The Luhn check, over a string that is already all digits.

    Every second digit counting from the right is doubled, a doubled value over
    nine has nine subtracted, and the total is a multiple of ten.
    """
    total = 0
    for offset, character in enumerate(reversed(number)):
        digit = int(character)
        if offset % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


def siren_valid(value: str | None) -> bool:
    """Whether `value` is nine digits with a correct check digit."""
    cleaned = digits(value)
    if cleaned is None or len(cleaned) != 9:
        return False
    return luhn_ok(cleaned)


def siret_valid(value: str | None) -> bool:
    """Whether `value` is fourteen digits with a correct check digit.

    La Poste takes the documented alternative rule rather than an exemption: its
    establishments are still checked, against the rule that applies to them.
    """
    cleaned = digits(value)
    if cleaned is None or len(cleaned) != 14:
        return False
    if cleaned.startswith(LA_POSTE_SIREN):
        return sum(int(character) for character in cleaned) % 5 == 0
    return luhn_ok(cleaned)


def siren_of(value: str | None) -> str | None:
    """The SIREN inside a SIRET, or a SIREN passed through.

    Shape only: a nine-digit prefix is what a SIREN is, and whether it checks
    out is a separate question this does not answer. Callers that need the
    answer ask `siren_valid`, and the staged tables carry both.
    """
    cleaned = digits(value)
    if cleaned is None or len(cleaned) not in (9, 14):
        return None
    return cleaned[:9]


# --- Names ------------------------------------------------------------------
#
# The rule, from `crony-eu/CLAUDE.md`: NFKD, drop combining marks, uppercase,
# turn apostrophes and hyphens into spaces, keep A-Z and spaces, collapse
# spaces. The standard library's `unicodedata` does it, rather than `unidecode`,
# for its licence and because its tables are pinned by the Python version.
#
# The élu register publishes given names in mixed case with accents on 19% of
# them; the company register publishes upper case. Both reach the same key here
# or neither does.

#: Characters the rule turns into a space. The typographic apostrophes (U+2019
#: and U+2018) are here because French text uses them, and a key that treated
#: them differently from the ASCII one would split one surname into two.
_SEPARATORS = str.maketrans({"'": " ", "\u2019": " ", "\u2018": " ", "-": " "})

_NOT_KEPT = re.compile(r"[^A-Z ]")
_SPACES = re.compile(r" +")


def _fold(value: str) -> str:
    """NFKD, combining marks dropped, upper case."""
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def norm_name(value: str | None) -> str | None:
    """A surname as the matching key compares it, or `None` if nothing is left.

    Idempotent, which the tests check: a key that changed when normalised twice
    would make a candidate depend on how many times a value had passed through.
    """
    if value is None:
        return None
    kept = _NOT_KEPT.sub("", _fold(value).translate(_SEPARATORS))
    collapsed = _SPACES.sub(" ", kept).strip()
    return collapsed or None


def given_key(value: str | None) -> str | None:
    """The first given name, with a hyphenated compound kept as one word.

    `JEAN-PIERRE` and `Jean-Pierre Marie` both give `JEANPIERRE`. `JEAN PIERRE`,
    with a space, gives `JEAN`: a space separates given names and a hyphen joins
    one, so the two spellings are two different claims about a person and the
    rule does not guess which one was meant. That costs recall wherever one
    register hyphenates a compound the other spaces, and ADR-0003 accepts it for
    precision.
    """
    if value is None:
        return None
    first = value.strip().split()
    if not first:
        return None
    joined = _NOT_KEPT.sub("", _fold(first[0]))
    return joined or None
