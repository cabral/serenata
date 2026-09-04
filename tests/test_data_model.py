"""The data model contract, checked against what was actually measured.

`docs/data-model.md` is the contract the normalise stage is written against. It
cites a source element path for every column, and two things must hold for those
citations to be worth anything.

They must be **real**: a path that no notice carries is a column nobody can
trace back to a source, and a typo in a 400-line document is invisible to
review. Every path is checked against the set `serenata.survey` actually
measured, in `docs/field-usage.md`.

They must be **permitted**: constraint 2 says a field that can name a natural
person gets no column at all. `docs/personal-data.md` says which those are and
`serenata/parse/personal_data.py` enforces it, so the model is checked against
the same function the parse stage will call. A column that mapped to a dropped
path would be a constraint 2 violation introduced in a document, where no code
review would catch it.
"""

from __future__ import annotations

import re
from pathlib import Path

from serenata.parse.personal_data import is_dropped

DOCS = Path(__file__).resolve().parent.parent / "docs"
MODEL = DOCS / "data-model.md"
USAGE = DOCS / "field-usage.md"

EXT = (
    "notice/ext:UBLExtensions/ext:UBLExtension/ext:ExtensionContent/"
    "efext:EformsExtension"
)

#: Any backticked token shaped like a source path, in prose or in a table.
_CITED = re.compile(r"`((?:notice/|<ext>/|<org>/)[^`]+)`")

#: The section that defines the shorthands necessarily spells out a path prefix
#: that is not itself a complete field path.
_DEFINITIONS = "What this is written against"


def expand(path: str) -> str:
    """Resolve the document's shorthands into a literal element path."""
    path = path.replace("<org>", f"{EXT}/efac:Organizations/efac:Organization")
    return path.replace("<ext>", EXT)


def without_section(text: str, title: str) -> str:
    before, _, rest = text.partition(f"\n## {title}\n")
    return before + rest.partition("\n## ")[2]


def cited_paths() -> list[str]:
    body = without_section(MODEL.read_text(encoding="utf-8"), _DEFINITIONS)
    return sorted({expand(path) for path in _CITED.findall(body)})


def measured_paths() -> set[str]:
    """Every path `serenata.survey` reported, valued or empty."""
    return set(re.findall(r"`(notice/[^`]+)`", USAGE.read_text(encoding="utf-8")))


class TestEveryColumnTracesToAMeasuredField:
    """A column whose source path no notice carries is untraceable.

    This is what holds [ADR-0005](../docs/adr/0005-element-paths-as-provenance.md)
    true. Provenance there is the *element path* rather than the eForms BT code,
    which is only worth anything if every path a column claims was observed in a
    real notice — otherwise the model cites a field that may not exist.
    """

    def test_every_cited_path_was_actually_measured(self) -> None:
        measured = measured_paths()
        # Guards the whole gate against passing vacuously if the regex or the
        # document's shape changes.
        assert len(measured) > 700, f"only parsed {len(measured)} measured paths"
        cited = cited_paths()
        assert len(cited) > 60, f"only parsed {len(cited)} cited paths"

        unknown = [path for path in cited if path not in measured]
        assert not unknown, (
            "docs/data-model.md cites source paths that docs/field-usage.md "
            f"never measured: {unknown}. The model is written against measured "
            "usage; a path no notice carries is a column nobody can trace."
        )


class TestTheModelObeysTheDropList:
    """Constraint 2: person-carrying fields get no column, not a nullable one."""

    def test_no_column_maps_to_a_dropped_path(self) -> None:
        offending = [path for path in cited_paths() if is_dropped(path)]
        assert not offending, (
            f"docs/data-model.md gives a column to dropped paths: {offending}. "
            "Fields that can name a natural person get no column at all "
            "(CLAUDE.md constraint 2, docs/personal-data.md)."
        )

    def test_the_check_can_actually_fail(self) -> None:
        # The test above passes trivially if is_dropped never returns True for
        # anything path-shaped. Prove the cross-check is live.
        contact = f"{EXT}/efac:Organizations/efac:Organization/efac:Company"
        assert is_dropped(f"{contact}/cac:Contact/cbc:Name")
        assert not is_dropped(f"{contact}/cac:PartyName/cbc:Name")


class TestTheContractIsComplete:
    """open-work #1's own done-when conditions, as far as a test can hold them."""

    def test_every_entity_has_a_section(self) -> None:
        body = MODEL.read_text(encoding="utf-8")
        for table in (
            "notice",
            "procedure",
            "lot",
            "organisation",
            "organisation_role",
            "tendering_party",
            "lot_tender",
            "lot_result",
            "settled_contract",
            "field_privacy",
        ):
            assert f"### `{table}`" in body, f"data-model.md has no {table} section"

    def test_the_absence_states_are_all_defined(self) -> None:
        body = MODEL.read_text(encoding="utf-8")
        for status in ("present", "empty", "absent", "withheld", "not_applicable"):
            assert f"`{status}`" in body, f"data-model.md never defines {status!r}"

    def test_it_says_legacy_ted_is_unmapped(self) -> None:
        # The model claims to span both formats. It may not quietly imply the
        # legacy mappings exist when no legacy notice has been measured.
        body = MODEL.read_text(encoding="utf-8")
        assert "Legacy TED" in body
        assert "zero" in body.split("## Legacy TED")[1].split("## ")[0]
