"""ADR-0013: which notices a correction takes out of the population.

The other classify tests build a market and check the rule; these build
corrections and check the population underneath it. Every notice identifier is
a synthetic UUID per tests/fixtures/README.md, because the `eforms` namespace is
defined by that shape — a link to `notice-0001` is not an eForms link, and a
fixture that pretended otherwise would test nothing the pipeline does.

No withdrawal is exercised. Nothing measured distinguishes one from a
correction, so there is no behaviour to assert and a test claiming otherwise
would be inventing the feature it checks.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from serenata.classify import classify_dataset
from serenata.classify.dataset import read_outcomes
from serenata.normalise import normalise_package

from .support import make_notice_package, notice_xml
from .test_classify_dataset import ORGANISATIONS, body, result


#: Synthetic notice identifiers, shaped like the eForms ones they stand in for.
def uuid_for(index: int) -> str:
    return f"00000000-0000-0000-0000-{index:012d}"


def changes(link: str | None = None, reason: str | None = None) -> str:
    """An `efac:Changes` block, with either part or both — TED publishes each."""
    inner = ""
    if link is not None:
        inner += f"<efbc:ChangedNoticeIdentifier>{link}</efbc:ChangedNoticeIdentifier>"
    if reason is not None:
        inner += (
            "<efac:ChangeReason>"
            f'<cbc:ReasonCode listName="change-corrig-justification">{reason}'
            "</cbc:ReasonCode></efac:ChangeReason>"
        )
    return f"<efac:Changes>{inner}</efac:Changes>"


def award(
    index: int,
    *,
    bids: str = "1",
    corrects: str | None = None,
    version: str | None = None,
    reason: str | None = None,
    date: str = "2026-08-17+02:00",
) -> bytes:
    """An award notice that may correct another, and may say why."""
    notice_body = body(procedure="open", cpv="45000000", system="none")
    if version is not None:
        notice_body = f"<cbc:VersionID>{version}</cbc:VersionID>" + notice_body
    extension = ORGANISATIONS.format(country="SWE") + result(bids)
    if corrects is not None or reason is not None:
        extension += changes(corrects, reason)
    return notice_xml(
        root="ContractAwardNotice",
        notice_id=uuid_for(index),
        publication_id=f"{index:08d}-2026",
        publication_date=date,
        body=notice_body,
        extension=extension,
    )


def build(notices: dict[int, bytes], tmp_path: Path) -> Path:
    """Normalise a handful of notices into a dataset to read outcomes from."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    package = tmp_path / "202600157.tar.gz"
    package.write_bytes(
        make_notice_package(
            {f"{index:08d}_2026.xml": body for index, body in notices.items()}
        )
    )
    root = tmp_path / "dataset"
    normalise_package(package, root)
    return root


def build_days(days: dict[str, dict[int, bytes]], tmp_path: Path) -> Path:
    """Normalise several publication days into one dataset, one package each.

    Package names are the OJS issue numbers TED uses; only their being distinct
    matters here, since each package writes its own part files.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    root = tmp_path / "dataset"
    for name, notices in days.items():
        package = tmp_path / f"{name}.tar.gz"
        package.write_bytes(
            make_notice_package(
                {f"{index:08d}_2026.xml": body for index, body in notices.items()}
            )
        )
        normalise_package(package, root)
    return root


def population(notices: dict[int, bytes], tmp_path: Path) -> set[str]:
    """The publication identifiers that survive into the population."""
    return {
        outcome.source_publication_id
        for outcome in read_outcomes(build(notices, tmp_path))
    }


def published(index: int) -> str:
    return f"{index:08d}-2026"


class TestACorrectedNoticeLeavesThePopulation:
    def test_the_target_goes_and_the_corrector_stays(self, tmp_path: Path) -> None:
        surviving = population(
            {1: award(1), 2: award(2, corrects=f"{uuid_for(1)}-01")}, tmp_path
        )
        assert surviving == {published(2)}

    def test_a_link_naming_another_version_still_excludes(self, tmp_path: Path) -> None:
        """The 28-of-46 case: a version 02 exists, so the copy held is behind."""
        surviving = population(
            {
                1: award(1, version="01"),
                2: award(2, corrects=f"{uuid_for(1)}-07"),
            },
            tmp_path,
        )
        assert surviving == {published(2)}

    def test_a_link_naming_the_held_version_excludes(self, tmp_path: Path) -> None:
        surviving = population(
            {
                1: award(1, version="03"),
                2: award(2, corrects=f"{uuid_for(1)}-03"),
            },
            tmp_path,
        )
        assert surviving == {published(2)}

    def test_two_correctors_exclude_the_target_once(self, tmp_path: Path) -> None:
        """Ambiguity refuses rather than picks, and refusing is not counted twice."""
        outcomes = read_outcomes(
            build(
                {
                    1: award(1),
                    2: award(2, corrects=f"{uuid_for(1)}-01"),
                    3: award(3, corrects=f"{uuid_for(1)}-01"),
                },
                tmp_path,
            )
        )
        assert [outcome.source_publication_id for outcome in outcomes] == [
            published(2),
            published(3),
        ]

    def test_a_chain_excludes_every_corrected_link_in_it(self, tmp_path: Path) -> None:
        surviving = population(
            {
                1: award(1),
                2: award(2, corrects=f"{uuid_for(1)}-01"),
                3: award(3, corrects=f"{uuid_for(2)}-01"),
            },
            tmp_path,
        )
        assert surviving == {published(3)}

    def test_a_notice_correcting_itself_excludes_only_itself(
        self, tmp_path: Path
    ) -> None:
        """A cycle terminates: this is a set membership test, not a traversal."""
        surviving = population(
            {1: award(1, corrects=f"{uuid_for(1)}-01"), 2: award(2)}, tmp_path
        )
        assert surviving == {published(2)}


class TestWhatDoesNotExclude:
    def test_a_link_to_a_notice_outside_the_corpus_excludes_nothing(
        self, tmp_path: Path
    ) -> None:
        """Unresolved is not corrected: 1.6% of links resolve, and the rest
        cannot be acted on without inventing what they point at."""
        surviving = population(
            {1: award(1), 2: award(2, corrects=f"{uuid_for(999)}-01")}, tmp_path
        )
        assert surviving == {published(1), published(2)}

    def test_a_legacy_ted_link_excludes_nothing(self, tmp_path: Path) -> None:
        """38.3% of links, in a namespace no eForms notice carries."""
        surviving = population(
            {1: award(1), 2: award(2, corrects="000001-2026")}, tmp_path
        )
        assert surviving == {published(1), published(2)}

    def test_an_unknown_link_shape_excludes_nothing(self, tmp_path: Path) -> None:
        surviving = population(
            {1: award(1), 2: award(2, corrects="not-an-identifier")}, tmp_path
        )
        assert surviving == {published(1), published(2)}

    def test_no_link_excludes_nothing(self, tmp_path: Path) -> None:
        surviving = population({1: award(1), 2: award(2)}, tmp_path)
        assert surviving == {published(1), published(2)}


class TestAWithdrawingNoticeLeavesToo:
    """ADR-0013: the announcement goes, not only the notice it corrects."""

    @pytest.mark.parametrize("reason", ["cancel", "cancel-intent", "susp-review"])
    def test_a_cancel_like_reason_excludes_its_own_notice(
        self, tmp_path: Path, reason: str
    ) -> None:
        surviving = population(
            {1: award(1), 2: award(2, reason=reason)}, tmp_path / reason
        )
        assert surviving == {published(1)}

    @pytest.mark.parametrize(
        "reason", ["update-add", "cor-buy", "cor-pub", "info-release"]
    )
    def test_an_ordinary_correction_reason_excludes_nothing(
        self, tmp_path: Path, reason: str
    ) -> None:
        """Most reasons are corrections; only the unsettled ones silence a lot."""
        surviving = population(
            {1: award(1), 2: award(2, reason=reason)}, tmp_path / reason
        )
        assert surviving == {published(1), published(2)}

    def test_both_exclusions_apply_together(self, tmp_path: Path) -> None:
        """The cancelling notice goes, and so does the notice it cancels."""
        surviving = population(
            {
                1: award(1),
                2: award(2, corrects=f"{uuid_for(1)}-01", reason="cancel"),
                3: award(3),
            },
            tmp_path,
        )
        assert surviving == {published(3)}

    def test_a_reason_without_a_link_still_excludes(self, tmp_path: Path) -> None:
        """117 links carry no reason; a reason with no link is the mirror case."""
        surviving = population({1: award(1), 2: award(2, reason="cancel")}, tmp_path)
        assert surviving == {published(1)}

    def test_a_link_without_a_reason_excludes_only_its_target(
        self, tmp_path: Path
    ) -> None:
        surviving = population(
            {1: award(1), 2: award(2, corrects=f"{uuid_for(1)}-01")}, tmp_path
        )
        assert surviving == {published(2)}


class TestTheCutoffTravels:
    def test_every_outcome_carries_the_corpus_latest_publication_day(
        self, tmp_path: Path
    ) -> None:
        outcomes = read_outcomes(build({1: award(1), 2: award(2)}, tmp_path))

        assert {outcome.correction_cutoff for outcome in outcomes} == {"2026-08-17"}

    def test_a_flag_carries_it_too(self, tmp_path: Path) -> None:
        # Sixty lots so the market is large enough for the rule to speak.
        notices = {
            index: award(index, bids="1" if index <= 3 else "4")
            for index in range(1, 61)
        }
        root = build(notices, tmp_path)

        results = classify_dataset(root, tmp_path / "flags")

        assert results[0].flags > 0
        outcomes = read_outcomes(root)
        assert all(outcome.correction_cutoff == "2026-08-17" for outcome in outcomes)


class TestCorrectionsDoNotBreakDeterminism:
    def test_the_same_corrected_dataset_gives_the_same_outcomes(
        self, tmp_path: Path
    ) -> None:
        notices = {
            1: award(1),
            2: award(2, corrects=f"{uuid_for(1)}-01"),
            3: award(3, corrects="000001-2026"),
        }
        root = build(notices, tmp_path)

        first = read_outcomes(root)
        second = read_outcomes(root)

        assert first == second

    def test_a_correction_arriving_changes_the_population(self, tmp_path: Path) -> None:
        """Non-vacuous: materially different input, materially different output."""
        without = population({1: award(1), 2: award(2)}, tmp_path / "a")
        with_correction = population(
            {1: award(1), 2: award(2, corrects=f"{uuid_for(1)}-01")}, tmp_path / "b"
        )

        assert without != with_correction
        assert without - with_correction == {published(1)}


class TestCorrectionsAcrossPackages:
    """#18: the archive that would exercise this is continuous, so the join
    must already work when target and corrector arrive in different packages.
    Synthetic days here; the real resolution rate stays unmeasured."""

    def test_a_corrector_in_a_later_package_excludes_the_earlier_target(
        self, tmp_path: Path
    ) -> None:
        root = build_days(
            {
                "202600157": {1: award(1, date="2026-08-17+02:00")},
                "202600158": {
                    2: award(2, corrects=f"{uuid_for(1)}-01", date="2026-08-18+02:00")
                },
            },
            tmp_path,
        )

        assert {o.source_publication_id for o in read_outcomes(root)} == {published(2)}

    def test_a_corrector_in_an_earlier_package_excludes_a_later_target(
        self, tmp_path: Path
    ) -> None:
        """Order of arrival is not part of the rule: identifiers are."""
        root = build_days(
            {
                "202600157": {
                    2: award(2, corrects=f"{uuid_for(1)}-01", date="2026-08-17+02:00")
                },
                "202600158": {1: award(1, date="2026-08-18+02:00")},
            },
            tmp_path,
        )

        assert {o.source_publication_id for o in read_outcomes(root)} == {published(2)}

    def test_a_chain_spanning_three_packages_leaves_only_its_head(
        self, tmp_path: Path
    ) -> None:
        root = build_days(
            {
                "202600157": {1: award(1, date="2026-08-17+02:00")},
                "202600158": {
                    2: award(2, corrects=f"{uuid_for(1)}-01", date="2026-08-18+02:00")
                },
                "202600159": {
                    3: award(3, corrects=f"{uuid_for(2)}-01", date="2026-08-19+02:00")
                },
            },
            tmp_path,
        )

        assert {o.source_publication_id for o in read_outcomes(root)} == {published(3)}

    def test_two_correctors_in_different_packages_exclude_the_target_once(
        self, tmp_path: Path
    ) -> None:
        root = build_days(
            {
                "202600157": {1: award(1, date="2026-08-17+02:00")},
                "202600158": {
                    2: award(2, corrects=f"{uuid_for(1)}-01", date="2026-08-18+02:00")
                },
                "202600159": {
                    3: award(3, corrects=f"{uuid_for(1)}-01", date="2026-08-19+02:00")
                },
            },
            tmp_path,
        )

        assert [o.source_publication_id for o in read_outcomes(root)] == [
            published(2),
            published(3),
        ]

    def test_the_cutoff_is_the_latest_day_across_every_package(
        self, tmp_path: Path
    ) -> None:
        root = build_days(
            {
                "202600158": {1: award(1, date="2026-08-18+02:00")},
                "202600157": {2: award(2, date="2026-08-17+02:00")},
            },
            tmp_path,
        )

        assert {o.correction_cutoff for o in read_outcomes(root)} == {"2026-08-18"}

    def test_a_correction_across_a_year_boundary_still_resolves(
        self, tmp_path: Path
    ) -> None:
        """Parquet is partitioned by year; the join must not be."""
        root = build_days(
            {
                "202500250": {1: award(1, date="2025-12-31+01:00")},
                "202600001": {
                    2: award(2, corrects=f"{uuid_for(1)}-01", date="2026-01-02+01:00")
                },
            },
            tmp_path,
        )

        outcomes = read_outcomes(root)
        assert [o.source_publication_id for o in outcomes] == [published(2)]
        assert outcomes[0].correction_cutoff == "2026-01-02"

    def test_the_order_packages_are_added_does_not_change_the_outcomes(
        self, tmp_path: Path
    ) -> None:
        one = {"202600157": {1: award(1, date="2026-08-17+02:00")}}
        two = {
            "202600158": {
                2: award(2, corrects=f"{uuid_for(1)}-01", date="2026-08-18+02:00")
            }
        }

        forward = read_outcomes(build_days({**one, **two}, tmp_path / "forward"))
        backward = read_outcomes(build_days({**two, **one}, tmp_path / "backward"))

        assert forward == backward
