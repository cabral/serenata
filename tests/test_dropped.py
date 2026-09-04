"""The drop report: what it counts, what it refuses to print, and its one claim.

`docs/dropped-fields.md` exists to answer one question with evidence rather than
assertion: **what does constraint 2 actually cost the analysis?** It comes up
whenever someone proposes mirroring TED in full and filtering at publication,
and the honest answer needs a measurement, not a principle.

The claim it makes is that no dropped path is a column of the normalised model.
That is checkable, so it is checked here — including the case where it would be
false, because a claim whose negation nothing can express is not a claim.

It also reports counts and paths and **never a value**. The elements it counts
are the ones carrying names, e-mail addresses and telephone numbers.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from serenata.survey import __main__ as survey_cli
from serenata.survey.dropped import (
    BENEFICIAL_OWNER,
    Dropped,
    dropped_package,
    modelled_block_suffixes,
    modelled_paths,
    render,
)

from .support import make_notice_package, sample_notices, sample_package


@pytest.fixture(scope="module")
def measured(tmp_path_factory: pytest.TempPathFactory) -> Dropped:
    return dropped_package(sample_package(tmp_path_factory.mktemp("archive")))


class TestWhatItCounts:
    """Over the committed sample, whose person-carrying fields are known."""

    def test_it_counts_the_notices_it_could_measure(self, measured: Dropped) -> None:
        assert measured.notices == 4
        # The legacy notice: a format whose drop list has never been written,
        # so it is reported as unmeasured rather than as nothing-to-drop.
        # Counting it as clean would report the list as complete over data it
        # was never designed for.
        assert measured.unmeasured == 1
        assert measured.unreadable == 1

    def test_it_finds_the_contact_block_and_the_beneficial_owner(
        self, measured: Dropped
    ) -> None:
        rules = measured.by_subtree()
        assert rules["cac:Contact"] >= 1
        assert rules[BENEFICIAL_OWNER] >= 1

    def test_every_dropped_path_starts_at_the_notice_root(
        self, measured: Dropped
    ) -> None:
        # Paths are normalised onto `notice/...` rather than onto the document's
        # own root, so a contract notice and an award notice report one path for
        # one field instead of two that have to be added up by hand.
        assert measured.removed
        assert all(path.startswith("notice/") for path in measured.removed)

    def test_the_removals_are_a_minority_of_the_leaves(self, measured: Dropped) -> None:
        assert 0 < measured.total_removed < measured.leaves


class TestItsOneClaim:
    """No dropped path is a modelled column — and the check can say otherwise.

    [ADR-0010](../docs/adr/0010-raw-archive-retention.md) rests on this. Its
    argument for keeping the drop at ingestion is not that holding personal data
    downstream would be risky but that no purpose is served by it, which is what
    data minimisation actually asks — and that argument only stands while no
    dropped path is something a classifier reads. The ADR is a policy and cannot
    itself be tested; this is the measurement underneath it.
    """

    def test_no_dropped_path_is_a_modelled_column(self, measured: Dropped) -> None:
        assert measured.collisions_with_the_model() == []

    def test_the_document_states_it(self, measured: Dropped) -> None:
        assert "No dropped path is a column of the normalised model." in render(
            measured
        )

    def test_the_check_can_actually_fail(self) -> None:
        # Give it a removal at a path the model really does read. The report has
        # to call that a contradiction rather than print the reassuring sentence,
        # or the sentence means nothing.
        found = Dropped()
        modelled = sorted(modelled_paths())[0]
        found.removed[modelled] = 1
        found.leaves = 1
        assert found.collisions_with_the_model() == [modelled]
        document = render(found)
        assert "A dropped path is also a modelled column." in document
        assert "No dropped path is a column" not in document

    def test_the_model_actually_has_paths_to_collide_with(self) -> None:
        # Guards the guard: if `modelled_paths()` returned nothing, the claim
        # above would hold vacuously for every input.
        paths = modelled_paths()
        assert len(paths) > 50
        assert all(path.startswith("notice/") for path in paths)

    def test_it_covers_the_columns_that_carry_no_path_of_their_own(self) -> None:
        # The defect this exists to prevent: `modelled_paths()` once read only
        # columns declaring a `path`, which silently excluded every block-built
        # table — the bid count, the buyer reference, the place of performance.
        # The claim would then have been checked against a subset of the model,
        # which is weaker than the sentence the report prints.
        paths = modelled_paths()
        bid_count = (
            "notice/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent"
            "/efext:EformsExtension/efac:NoticeResult/efac:LotResult"
            "/efac:ReceivedSubmissionsStatistics/efbc:StatisticsNumeric"
        )
        buyer = "notice/cac:ContractingParty/cac:Party/cac:PartyIdentification/cbc:ID"
        assert bid_count in paths, "the single-bid input is not covered"
        assert buyer in paths, "the buyer reference is not covered"

    def test_a_variable_depth_block_is_matched_by_suffix(self) -> None:
        # A privacy block hangs off four different parents, so it has no one
        # absolute path. Its coded children are modelled; its free-text sibling
        # is dropped, and the two must not be confused.
        suffixes = modelled_block_suffixes()
        assert "efac:FieldsPrivacy/cbc:ReasonCode" in suffixes
        assert not any("ReasonDescription" in suffix for suffix in suffixes)

        found = Dropped()
        found.leaves = 1
        where = "notice/efac:NoticeResult/efac:FieldsPrivacy/cbc:ReasonCode"
        found.removed[where] = 1
        assert found.collisions_with_the_model() == [where]


class TestWhatItMustNeverPrint:
    def test_no_field_value_appears_in_the_document(self, measured: Dropped) -> None:
        document = render(measured)
        for value in ("MUST-NEVER-APPEAR", "DROPPED-CONTACT-VALUE"):
            assert value not in document, value

    def test_the_check_can_actually_fail(self) -> None:
        carried = b"".join(sample_notices().values()).decode()
        assert "DROPPED-CONTACT-VALUE" in carried


class TestItCanBeCited:
    def test_the_same_package_renders_the_same_document(self, tmp_path: Path) -> None:
        package = sample_package(tmp_path)
        assert render(dropped_package(package)) == render(dropped_package(package))

    def test_it_records_what_it_measured(self, measured: Dropped) -> None:
        document = render(measured)
        name, digest = measured.packages[0]
        assert name in document
        assert f"sha256:{digest}" in document

    def test_an_empty_measurement_still_renders(self) -> None:
        document = render(Dropped())
        assert "0 of 0 leaf elements" in document.replace("**", "")


class TestTheCommand:
    def test_it_writes_the_report(self, tmp_path: Path, capsys) -> None:
        package = sample_package(tmp_path)
        output = tmp_path / "dropped.md"

        code = survey_cli.main([str(package), "--report", "dropped", "-o", str(output)])

        assert code == 0
        text = output.read_text(encoding="utf-8")
        assert "# What the personal-data drop removes" in text
        assert "measured" in capsys.readouterr().err

    def test_a_package_with_no_eforms_notices_is_an_error(
        self, tmp_path: Path, capsys
    ) -> None:
        empty = tmp_path / "empty.tar.gz"
        empty.write_bytes(make_notice_package({"000001_2026.xml": b"<TED_EXPORT/>"}))

        assert survey_cli.main([str(empty), "--report", "dropped"]) == 1
        assert "no eForms notices" in capsys.readouterr().err
