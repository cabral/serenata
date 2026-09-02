"""The drop list, and the gate holding it identical to its documentation.

`docs/personal-data.md` is the authority for constraint 2 and carries the
reasoning; `serenata/parse/personal_data.py` is what the parse stage actually
consults. A list that says one thing and enforces another is worse than either
alone, so the tests below read the document and assert the code agrees with
every row of it.

That direction matters. The document is what a reviewer, a funder or a data
protection authority reads; the code is what runs. Deriving the test from the
document means the document cannot quietly become aspirational.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from serenata.parse.personal_data import (
    DROPPED_SEGMENTS,
    NATURAL_PERSON_INDICATOR,
    is_dropped,
    suppressed_for_natural_person,
)

DOC = Path(__file__).resolve().parent.parent / "docs" / "personal-data.md"

EXT = (
    "notice/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension"
)

#: Table rows in the document are ``| `path` | frequency | why |``.
_ROW = re.compile(r"^\| `([^`]+)` \|", re.M)


def expand(path: str) -> str:
    """Resolve the document's shorthands into a literal element path."""
    path = path.replace("<org>", "<orgs>/efac:Organization")
    path = path.replace("<orgs>", "<ext>/efac:Organizations")
    return path.replace("<ext>", EXT)


def section(title: str) -> str:
    """The body under a ``## title`` heading, up to the next ``## ``."""
    body = DOC.read_text(encoding="utf-8")
    marker = f"\n## {title}\n"
    assert marker in body, f"docs/personal-data.md has no section {title!r}"
    return body.split(marker, 1)[1].split("\n## ", 1)[0]


def documented_paths(title: str) -> list[str]:
    return [expand(path) for path in _ROW.findall(section(title))]


class TestDocumentAndCodeAgree:
    """The document is the authority; the code must implement all of it."""

    def test_every_documented_drop_is_dropped(self) -> None:
        documented = documented_paths("Dropped outright")
        # Guards against the regex silently matching nothing and the whole
        # gate passing vacuously.
        assert len(documented) >= 15, f"only found {len(documented)} documented drops"
        for path in documented:
            assert is_dropped(path), (
                f"docs/personal-data.md drops {path!r} but the code does not. "
                "The document is the authority for constraint 2."
            )

    def test_every_documented_keep_is_kept(self) -> None:
        documented = documented_paths("Kept, and why")
        assert len(documented) >= 5, f"only found {len(documented)} documented keeps"
        for path in documented:
            assert not is_dropped(path), (
                f"the code drops {path!r}, which docs/personal-data.md keeps. "
                "Over-dropping is safe legally and still a documentation bug."
            )

    def test_the_sole_trader_table_is_suppressed(self) -> None:
        rows = _ROW.findall(section("The sole-trader case: conditional suppression"))
        assert len(rows) >= 5, f"only found {len(rows)} sole-trader rows"
        for row in rows:
            # Rows are written from the notice root; the function takes a path
            # relative to the organisation, which is where the indicator lives.
            relative = row.replace("<org>/", "").removesuffix("/**")
            assert suppressed_for_natural_person(relative), (
                f"docs/personal-data.md suppresses {relative!r} for a natural "
                "person but the code does not."
            )


class TestDroppedOutright:
    """Constraint 2: these never reach an intermediate record."""

    @pytest.mark.parametrize(
        "path",
        [
            f"{EXT}/efac:Organizations/efac:Organization/efac:Company"
            "/cac:Contact/cbc:Name",
            "notice/cac:SenderParty/cac:Contact/cbc:ElectronicMail",
            f"{EXT}/efac:Organizations/efac:UltimateBeneficialOwner/cbc:FamilyName",
            f"{EXT}/efac:Organizations/efac:UltimateBeneficialOwner"
            "/cac:ResidenceAddress/cbc:StreetName",
            "notice/cac:ProcurementProjectLot/cac:TenderingTerms/cac:AwardingTerms"
            "/cac:TechnicalCommitteePerson/cbc:FamilyName",
            f"{EXT}/efac:NoticeResult/efac:FieldsPrivacy/efbc:ReasonDescription",
        ],
    )
    def test_known_person_carrying_paths(self, path: str) -> None:
        assert is_dropped(path)

    def test_a_leaf_added_inside_a_dropped_subtree_is_dropped_on_arrival(self) -> None:
        # The reason the rule matches segments rather than an enumerated list:
        # this path does not appear in any notice surveyed, and is dropped
        # anyway. Erring toward dropping, made structural.
        invented = (
            f"{EXT}/efac:Organizations/efac:Organization/efac:Company"
            "/cac:Contact/cbc:SomeFieldTedAddsLater"
        )
        assert is_dropped(invented)

    def test_the_coded_part_of_fieldsprivacy_survives(self) -> None:
        # Only the free-text explanation goes; the codes record that the
        # publisher withheld a field, which the project honours.
        kept = f"{EXT}/efac:NoticeResult/efac:FieldsPrivacy/efbc:FieldIdentifierCode"
        dropped = f"{EXT}/efac:NoticeResult/efac:FieldsPrivacy/efbc:ReasonDescription"
        assert not is_dropped(kept)
        assert is_dropped(dropped)

    def test_the_rule_is_not_vacuous(self) -> None:
        assert DROPPED_SEGMENTS
        assert not is_dropped("notice/cac:ProcurementProject/cbc:Name")


class TestNaturalPersonSuppression:
    """A sole trader's company data is a private individual's personal data."""

    @pytest.mark.parametrize(
        "relative",
        [
            "efac:Company/cac:PartyName/cbc:Name",
            "efac:Company/cac:PartyLegalEntity/cbc:CompanyID",
            "efac:Company/cac:PostalAddress/cbc:StreetName",
            "efac:TouchPoint/cac:PartyName/cbc:Name",
        ],
    )
    def test_identifying_values_are_suppressed(self, relative: str) -> None:
        assert suppressed_for_natural_person(relative)

    def test_the_registration_identifier_is_suppressed(self) -> None:
        # In Sweden a sole trader's organisationsnummer is the owner's
        # personnummer: a national identity number in a field that is an
        # innocuous company number for every other organisation.
        assert suppressed_for_natural_person(
            "efac:Company/cac:PartyLegalEntity/cbc:CompanyID"
        )

    def test_the_opaque_key_survives(self) -> None:
        # Suppression anonymises the record; it does not delete it. The
        # notice-scoped token names nobody and keeps the structure joinable.
        assert not suppressed_for_natural_person(
            "efac:Company/cac:PartyIdentification/cbc:ID"
        )

    def test_the_indicator_itself_is_kept(self) -> None:
        # Dropping it would remove the only in-band signal the rule depends on.
        path = f"{EXT}/efac:Organizations/efac:Organization/{NATURAL_PERSON_INDICATOR}"
        assert not is_dropped(path)
        assert not suppressed_for_natural_person(NATURAL_PERSON_INDICATOR)
