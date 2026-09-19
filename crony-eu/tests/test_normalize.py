# SPDX-License-Identifier: AGPL-3.0-only
"""Date parsing, and the two ways it is allowed to be wrong.

Staging does this in SQL, over the same closed format list. This is the Python
statement of the same rule, used where an error has to be raised with an
explanation, and tested here because the property that matters is not "it parses
dates" but "it refuses everything else".

`03/04/1971` is the case the closed list exists for. It is 3 April in French
order and 3 March in American order, and a parser that accepted both would read
one file each way and nothing downstream could tell which.
"""

from __future__ import annotations

from datetime import date

import pytest
from crony_eu.normalize import (
    DATE_SHAPES,
    EARLIEST_PLAUSIBLE_YEAR,
    LA_POSTE_SIREN,
    DateFormatError,
    birth_ym,
    digits,
    luhn_ok,
    parse_date,
    plausible,
    siren_of,
    siren_valid,
    siret_valid,
)

#: Any snapshot date does; it is what places a two-digit year in a century.
SNAPSHOT = date(2026, 9, 16)


class TestParseDate:
    def test_it_reads_iso_8601(self) -> None:
        assert parse_date("1971-04-03") == date(1971, 4, 3)

    def test_it_reads_the_older_french_order(self) -> None:
        # The register published DD/MM/YYYY before its August 2026 update.
        assert parse_date("03/04/1971") == date(1971, 4, 3)

    def test_both_formats_agree_on_the_same_day(self) -> None:
        assert parse_date("03/04/1971") == parse_date("1971-04-03")

    @pytest.mark.parametrize("empty", ["", "   ", None])
    def test_empty_is_an_answer_not_an_error(self, empty: str | None) -> None:
        # "Not provided" is a fact about the record. A malformed value is a
        # fact about our reading of the file, and only the second is a bug.
        assert parse_date(empty) is None

    @pytest.mark.parametrize(
        "rejected",
        [
            "03 avril 1971",
            "1971/04/03",
            "04-03-1971",
            "1971-04",
            "19710403",
            "not a date",
        ],
    )
    def test_anything_else_is_refused(self, rejected: str) -> None:
        with pytest.raises(DateFormatError):
            parse_date(rejected)

    def test_a_trailing_comment_is_refused(self) -> None:
        # `datetime.strptime` accepts this by reading the prefix, which is the
        # silent acceptance the module exists to prevent.
        with pytest.raises(DateFormatError):
            parse_date("1971-04-03 (approximate)")

    def test_an_impossible_day_is_refused(self) -> None:
        with pytest.raises(DateFormatError):
            parse_date("1971-02-30")

    def test_the_message_does_not_carry_the_value(self) -> None:
        # Constraint 13: it may be a birth date.
        with pytest.raises(DateFormatError) as raised:
            parse_date("03 avril 1971")

        assert "avril" not in str(raised.value)
        assert "constraint 13" in str(raised.value)

    def test_surrounding_space_is_ignored(self) -> None:
        assert parse_date("  1971-04-03  ") == date(1971, 4, 3)


class TestBirthKey:
    def test_it_is_year_and_month(self) -> None:
        # The precision the officer side carries (ADR-0003), measured on the
        # open company API: `date_de_naissance` is YYYY-MM.
        assert birth_ym(date(1971, 4, 3)) == "1971-04"

    def test_it_pads_a_single_digit_month(self) -> None:
        assert birth_ym(date(1971, 1, 3)) == "1971-01"

    def test_a_missing_date_has_no_key(self) -> None:
        # No key means no candidate. An élu with no birth date cannot be
        # matched by this rule, which is the honest outcome rather than a
        # match on name alone.
        assert birth_ym(None) is None


class TestTheTwoDigitYear:
    """The shape that made the first staging of the real register wrong."""

    def test_it_is_read_at_all(self) -> None:
        # The pre-election extracts publish DD/MM/YY, which the specification
        # did not mention and the first parser silently mangled.
        assert parse_date("03/04/71", not_after=SNAPSHOT) == date(1971, 4, 3)

    def test_a_year_that_would_be_in_the_future_goes_back_a_century(self) -> None:
        # `30` in a file published in 2026 is 1930, because a register cannot
        # publish a date that has not happened.
        assert parse_date("18/05/30", not_after=SNAPSHOT) == date(1930, 5, 18)

    def test_a_year_that_is_already_past_stays_where_it_is(self) -> None:
        assert parse_date("22/03/20", not_after=SNAPSHOT) == date(2020, 3, 22)

    def test_without_a_reference_date_it_is_refused_not_guessed(self) -> None:
        with pytest.raises(DateFormatError, match="two-digit year"):
            parse_date("03/04/71")

    def test_the_four_digit_rule_cannot_claim_it(self) -> None:
        # The actual bug: `%d/%m/%Y` accepts `03/04/71` and returns year 71.
        # Matching the whole shape is what stops that.
        assert parse_date("03/04/71", not_after=SNAPSHOT).year != 71  # type: ignore[union-attr]


class TestPlausibility:
    """Parsed is not the same as right, which is what 520,240 rows taught us."""

    def test_a_believable_date_passes(self) -> None:
        assert plausible(date(1971, 4, 3), SNAPSHOT)

    def test_the_year_20_does_not(self) -> None:
        assert not plausible(date(20, 5, 18), SNAPSHOT)

    def test_a_future_date_does_not(self) -> None:
        assert not plausible(date(2030, 1, 1), SNAPSHOT)

    def test_the_window_edge_is_included(self) -> None:
        assert plausible(date(EARLIEST_PLAUSIBLE_YEAR, 1, 1), SNAPSHOT)
        assert plausible(SNAPSHOT, SNAPSHOT)

    def test_a_missing_date_is_not_implausible(self) -> None:
        # Absent and wrong are different facts.
        assert plausible(None, SNAPSHOT)


class TestTheShapeListIsClosed:
    def test_there_are_exactly_three(self) -> None:
        # Widening this is a decision about how a date is read, and it belongs
        # in a record rather than in a commit that adds a fourth pattern.
        assert [fmt for _, fmt in DATE_SHAPES] == ["%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"]

    def test_staging_reads_the_same_list(self) -> None:
        # The SQL in the source module builds its CASE from this exact tuple.
        # Two readers of one file must not disagree about what a date is.
        from crony_eu.sources import fr_rne_elus

        assert fr_rne_elus.DATE_SHAPES is DATE_SHAPES


# --- identifiers -------------------------------------------------------------


def with_luhn(body: str) -> str:
    """`body` plus the check digit that makes it pass, for generated cases.

    Written out rather than imported from the module under test: a fixture that
    borrowed the implementation would agree with a wrong implementation.
    """
    total = 0
    for offset, character in enumerate(reversed(body + "0")):
        digit = int(character)
        if offset % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return body + str((10 - total % 10) % 10)


class TestDigits:
    def test_it_keeps_only_digits(self) -> None:
        assert digits("732 829 320") == "732829320"

    def test_it_survives_the_non_breaking_space_a_paste_brings(self) -> None:
        # Written as an escape rather than the character: a NO-BREAK SPACE
        # in a source file is invisible to the next reader, which is the
        # same property that puts it in a pasted identifier.
        assert digits("732\u00a0829\u00a0320") == "732829320"

    def test_nothing_to_keep_is_none_rather_than_an_empty_string(self) -> None:
        assert digits("n/a") is None
        assert digits("") is None
        assert digits(None) is None


class TestSiren:
    def test_a_valid_siren_passes(self) -> None:
        assert siren_valid(with_luhn("73282932")) is True

    def test_a_wrong_check_digit_fails(self) -> None:
        valid = with_luhn("73282932")
        wrong = valid[:8] + str((int(valid[8]) + 1) % 10)
        assert siren_valid(wrong) is False

    def test_the_right_digits_at_the_wrong_length_fail(self) -> None:
        assert siren_valid(with_luhn("7328293")) is False
        assert siren_valid(with_luhn("732829321")) is False

    def test_la_poste_needs_no_exception_at_siren_level(self) -> None:
        # The documented exception is about La Poste's establishments, not its
        # legal unit. This test is here because the module special-cased the
        # SIREN too until this assertion said it did not have to.
        assert luhn_ok(LA_POSTE_SIREN) is True
        assert siren_valid(LA_POSTE_SIREN) is True


class TestSiret:
    def test_a_valid_siret_passes(self) -> None:
        assert siret_valid(with_luhn("7328293200007")) is True

    def test_a_transposition_is_caught(self) -> None:
        # Luhn's reason for existing: two adjacent digits swapped.
        valid = with_luhn("7328293200007")
        swapped = valid[:2] + valid[3] + valid[2] + valid[4:]
        assert valid != swapped
        assert siret_valid(swapped) is False

    def test_la_poste_follows_the_digit_sum_rule_instead(self) -> None:
        # INSEE documents this: the sum of the fourteen digits is a multiple of
        # five, because La Poste's establishment numbers were allocated outside
        # the Luhn series.
        establishment = LA_POSTE_SIREN + "00001"
        assert sum(int(c) for c in establishment) % 5 == 0
        assert luhn_ok(establishment) is False
        assert siret_valid(establishment) is True

    def test_a_la_poste_number_failing_that_rule_is_still_invalid(self) -> None:
        # The exception is another rule, not an exemption from checking.
        establishment = LA_POSTE_SIREN + "00002"
        assert sum(int(c) for c in establishment) % 5 != 0
        assert siret_valid(establishment) is False


class TestSirenOf:
    def test_a_siret_starts_with_its_siren(self) -> None:
        siren = with_luhn("73282932")
        siret = with_luhn(siren + "0000")
        assert siret.startswith(siren)
        assert siren_of(siret) == siren

    def test_a_siren_passes_through(self) -> None:
        siren = with_luhn("73282932")
        assert siren_of(siren) == siren

    def test_any_other_length_has_no_siren_in_it(self) -> None:
        assert siren_of("1234") is None
        assert siren_of(None) is None

    def test_it_reports_shape_and_not_validity(self) -> None:
        # Deliberate: the staged tables carry the digits and the verdict in
        # separate columns, so a failed checksum is a fact about a contract
        # rather than a reason to lose it.
        # Nine zeros are not a company, and they pass Luhn, which is the whole
        # reason a checksum is a shape check and not an existence check.
        assert siren_of("000000001") == "000000001"
        assert siren_valid("000000001") is False
