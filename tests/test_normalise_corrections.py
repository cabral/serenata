"""ADR-0013: the corrigendum link is split into parts, never resolved here.

Every identifier below is synthetic, per tests/fixtures/README.md. The shapes
they exercise are the ones `docs/correction-links.md` measured; the values are
not, and none of them could be mistaken for a notice TED published.
"""

from __future__ import annotations

import io

import pytest

from serenata.normalise import notice_rows
from serenata.normalise.corrections import Namespace, parse_link
from serenata.normalise.model import NOTICE_TABLE, Kind, Status
from serenata.parse import read_notice

from .support import SYNTHETIC_NOTICE_ID, notice_xml

#: An eForms link: a notice identifier and the version being corrected.
EFORMS_LINK = f"{SYNTHETIC_NOTICE_ID}-02"

#: A legacy TED link: publication number and year, carrying no version.
LEGACY_LINK = "00000001-2026"


class TestTheLinkIsSplitNotResolved:
    @pytest.mark.parametrize(
        ("link", "namespace", "target", "version"),
        [
            (EFORMS_LINK, Namespace.EFORMS, SYNTHETIC_NOTICE_ID, "02"),
            # Every suffix is two digits, including the first version.
            (f"{SYNTHETIC_NOTICE_ID}-01", Namespace.EFORMS, SYNTHETIC_NOTICE_ID, "01"),
            (LEGACY_LINK, Namespace.TED_LEGACY, LEGACY_LINK, None),
            # Measured legacy numbers run four to six digits.
            ("0001-2026", Namespace.TED_LEGACY, "0001-2026", None),
            ("000001-1999", Namespace.TED_LEGACY, "000001-1999", None),
        ],
    )
    def test_a_measured_shape_keeps_its_parts(
        self, link: str, namespace: Namespace, target: str, version: str | None
    ) -> None:
        assert parse_link(link) == (namespace, target, version)

    @pytest.mark.parametrize(
        "link",
        [
            # A bare identifier with no version is not the eForms link shape.
            SYNTHETIC_NOTICE_ID,
            # Neither is one whose suffix is not two digits.
            f"{SYNTHETIC_NOTICE_ID}-2",
            f"{SYNTHETIC_NOTICE_ID}-002",
            # A year outside 19xx/20xx is not the legacy shape.
            "000001-3026",
            # Nor is a number with no year at all.
            "000001",
            "not-an-identifier",
        ],
    )
    def test_an_unrecognised_shape_is_kept_whole(self, link: str) -> None:
        """The one wrong answer is reporting no link where TED published one."""
        assert parse_link(link) == (Namespace.UNKNOWN, link, None)

    @pytest.mark.parametrize("link", [None, "", "   "])
    def test_nothing_to_split_is_nothing(self, link: str | None) -> None:
        assert parse_link(link) is None

    def test_surrounding_whitespace_is_not_a_different_link(self) -> None:
        assert parse_link(f"  {EFORMS_LINK}  ") == parse_link(EFORMS_LINK)

    def test_the_version_suffix_is_not_part_of_the_target(self) -> None:
        """With it attached a link resolves against nothing: 0 of 2,840."""
        namespace, target, version = parse_link(EFORMS_LINK)
        assert namespace is Namespace.EFORMS
        assert target == SYNTHETIC_NOTICE_ID
        assert version == "02"
        assert target != EFORMS_LINK


def changes(link: str) -> str:
    return f"<efac:Changes><efbc:ChangedNoticeIdentifier>{link}"


CHANGES_CLOSE = "</efbc:ChangedNoticeIdentifier></efac:Changes>"


def notice_row(extension: str = "") -> dict[str, object]:
    notice = read_notice(io.BytesIO(notice_xml(extension=extension)))
    return notice_rows(notice)["notice"][0]


class TestTheColumnsTheModelBuilds:
    def test_the_parts_are_computed_columns(self) -> None:
        """Not element paths: nothing in the notice carries them separately."""
        parts = {
            column.name: column.kind
            for column in NOTICE_TABLE.columns
            if column.name.startswith("changed_notice_")
            and column.name != ("changed_notice_id")
        }
        assert parts == {
            "changed_notice_namespace": Kind.COMPUTED,
            "changed_notice_target": Kind.COMPUTED,
            "changed_notice_version": Kind.COMPUTED,
        }

    def test_an_eforms_link_carries_every_part(self) -> None:
        row = notice_row(changes(EFORMS_LINK) + CHANGES_CLOSE)
        assert row["changed_notice_id"] == EFORMS_LINK
        assert row["changed_notice_namespace"] == Namespace.EFORMS.value
        assert row["changed_notice_target"] == SYNTHETIC_NOTICE_ID
        assert row["changed_notice_version"] == "02"
        for part in ("namespace", "target", "version"):
            assert row[f"changed_notice_{part}_status"] == Status.PRESENT.value

    def test_a_legacy_link_records_an_absent_version(self) -> None:
        """Not `not_applicable`: that status is reserved for subtype rules."""
        row = notice_row(changes(LEGACY_LINK) + CHANGES_CLOSE)
        assert row["changed_notice_namespace"] == Namespace.TED_LEGACY.value
        assert row["changed_notice_target"] == LEGACY_LINK
        assert row["changed_notice_version"] is None
        assert row["changed_notice_version_status"] == Status.ABSENT.value
        assert row["changed_notice_namespace_status"] == Status.PRESENT.value

    def test_no_link_means_no_parts(self) -> None:
        row = notice_row()
        assert row["changed_notice_id_status"] == Status.ABSENT.value
        for part in ("namespace", "target", "version"):
            assert row[f"changed_notice_{part}"] is None
            assert row[f"changed_notice_{part}_status"] == Status.ABSENT.value

    def test_the_parts_mirror_an_empty_link(self) -> None:
        row = notice_row(changes("") + CHANGES_CLOSE)
        assert row["changed_notice_id_status"] == Status.EMPTY.value
        for part in ("namespace", "target", "version"):
            assert row[f"changed_notice_{part}"] is None
            assert row[f"changed_notice_{part}_status"] == Status.EMPTY.value

    def test_an_unknown_shape_stays_visible(self) -> None:
        """An unrecognised link is not quietly an absent one."""
        row = notice_row(changes("not-an-identifier") + CHANGES_CLOSE)
        assert row["changed_notice_namespace"] == Namespace.UNKNOWN.value
        assert row["changed_notice_target"] == "not-an-identifier"
        assert row["changed_notice_namespace_status"] == Status.PRESENT.value
