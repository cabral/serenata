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

from serenata.classify import classify_dataset
from serenata.classify.dataset import read_outcomes
from serenata.normalise import normalise_package

from .support import make_notice_package, notice_xml
from .test_classify_dataset import ORGANISATIONS, body, result


#: Synthetic notice identifiers, shaped like the eForms ones they stand in for.
def uuid_for(index: int) -> str:
    return f"00000000-0000-0000-0000-{index:012d}"


def changes(link: str) -> str:
    return (
        "<efac:Changes>"
        f"<efbc:ChangedNoticeIdentifier>{link}</efbc:ChangedNoticeIdentifier>"
        "</efac:Changes>"
    )


def award(
    index: int,
    *,
    bids: str = "1",
    corrects: str | None = None,
    version: str | None = None,
) -> bytes:
    """An award notice that may correct another, and may name its own version."""
    notice_body = body(procedure="open", cpv="45000000", system="none")
    if version is not None:
        notice_body = f"<cbc:VersionID>{version}</cbc:VersionID>" + notice_body
    extension = ORGANISATIONS.format(country="SWE") + result(bids)
    if corrects is not None:
        extension += changes(corrects)
    return notice_xml(
        root="ContractAwardNotice",
        notice_id=uuid_for(index),
        publication_id=f"{index:08d}-2026",
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
