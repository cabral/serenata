"""The replacement decision, checked against the repository it describes.

[ADR-0014](../docs/adr/0014-replace-serenata-with-crony.md) makes Crony this
repository's purpose and puts Serenata Europa's TED pipeline on a path to
retirement. A decision like that is mostly prose, and prose about a repository
in the middle of being replaced rots faster than usual: the whole point of the
period this covers is that files move, get marked, and get deleted in groups.

Three things here are mechanical, so they are checked rather than asserted:

- **Every earlier decision record says what became of it.** Thirteen records
  predate ADR-0014 and each carries a `- Transition:` line reading `carried`,
  `retired` or `continuing obligation`. The third is the category that matters,
  because an obligation is not discharged by deleting the code that triggered
  it — ADR-0010's archive is still on disk.
- **The scope exists once.** `scope.md` arrived in two byte-identical copies,
  and two files that must agree eventually will not. The root copy is canonical
  and the other is a pointer.
- **Crony's documentation is inside the documentation checks.** Until it was,
  `crony-eu/` could describe a tool that does not exist and nothing would say
  so.

What no test here can hold true is the part that matters most: the legal
obligations in ADR-0010, which survive the transition untouched and unresolved.
The record says so itself.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests import test_docs

REPO = Path(__file__).resolve().parent.parent
ADR_ROOT = REPO / "docs" / "adr"

#: The record that introduced the disposition line, and so the first one that
#: does not carry it.
TRANSITION_RECORD = "0014"

#: The three answers a record may give. Anything else is a record that has not
#: been thought about, dressed as one that has.
DISPOSITIONS = ("carried", "retired", "continuing obligation")

#: `- Transition: <disposition> — …`, to the end of the line.
_TRANSITION = re.compile(r"^- Transition: (.+)$", re.M)


def earlier_records() -> list[Path]:
    """Every decision record taken before the replacement was decided."""
    return sorted(
        path for path in ADR_ROOT.glob("[0-9]*.md") if path.name[:4] < TRANSITION_RECORD
    )


def disposition(path: Path) -> str:
    found = _TRANSITION.search(path.read_text(encoding="utf-8"))
    assert found, (
        f"{path.name} does not say what became of it. Every record taken before "
        f"ADR-{TRANSITION_RECORD} carries a `- Transition:` line, so a reader "
        "arriving at an old decision learns whether it still binds anything."
    )
    return found.group(1).strip()


class TestTheReplacementIsRecorded:
    """ADR-0014, and whether the repository matches what it claims."""

    def test_the_record_exists(self) -> None:
        assert list(ADR_ROOT.glob(f"{TRANSITION_RECORD}-*.md")), (
            "the transition ADR is gone, and every disposition line below now "
            "cites a decision nobody can read"
        )

    def test_there_are_records_to_check(self) -> None:
        # Guards the parametrised tests below: with no earlier records they
        # would all pass by having nothing to check.
        assert len(earlier_records()) >= 13

    @pytest.mark.parametrize("path", earlier_records(), ids=lambda p: p.name[:4])
    def test_it_says_what_became_of_it(self, path: Path) -> None:
        assert disposition(path)

    @pytest.mark.parametrize("path", earlier_records(), ids=lambda p: p.name[:4])
    def test_it_uses_one_of_the_three_answers(self, path: Path) -> None:
        text = disposition(path)
        assert text.startswith(DISPOSITIONS), (
            f"{path.name} answers {text[:40]!r}, which is not one of "
            f"{DISPOSITIONS}. A fourth word is a reader having to work out "
            "whether the decision still binds them."
        )

    def test_the_record_defines_every_answer_it_asks_for(self) -> None:
        # A vocabulary checked here and explained nowhere is a rule with no
        # reasoning behind it.
        found = next(ADR_ROOT.glob(f"{TRANSITION_RECORD}-*.md"))
        record = found.read_text(encoding="utf-8")
        undefined = [word for word in DISPOSITIONS if f"**{word}**" not in record]
        assert not undefined, f"ADR-{TRANSITION_RECORD} never defines: {undefined}"

    def test_something_is_a_continuing_obligation(self) -> None:
        # The category exists because ADR-0010's archive outlives the code that
        # reads it. A transition where every record turned out to be retired or
        # carried would mean that reasoning had been quietly dropped.
        binding = [
            path.name[:4]
            for path in earlier_records()
            if disposition(path).startswith("continuing")
        ]
        assert binding, (
            "no earlier record is marked a continuing obligation. Retiring the "
            "pipeline does not dispose of the archive it fetched, and the "
            "records that say so are the ones a reader needs most."
        )

    def test_the_check_can_actually_fail(self, tmp_path: Path) -> None:
        # A reader of the parametrised results sees thirteen passes and has no
        # way to tell a real check from one matching nothing.
        empty = tmp_path / "0001-undecided.md"
        empty.write_text("# ADR-0001\n\n- Status: accepted\n", encoding="utf-8")
        with pytest.raises(AssertionError):
            disposition(empty)


class TestTheScopeExistsOnce:
    """Two copies of one document is a disagreement waiting for a deadline."""

    def test_the_canonical_scope_is_at_the_root(self) -> None:
        assert (REPO / "scope.md").is_file()

    def test_the_nested_copy_is_a_pointer(self) -> None:
        nested = REPO / "crony-eu" / "docs" / "scope.md"
        if not nested.exists():
            pytest.skip("the nested copy has been removed outright, which also works")
        canonical = (REPO / "scope.md").read_text(encoding="utf-8")
        assert nested.read_text(encoding="utf-8") != canonical, (
            "crony-eu/docs/scope.md is still a byte-identical copy of scope.md. "
            "Edit either one and the repository starts stating two scopes."
        )

    def test_the_pointer_points_somewhere(self) -> None:
        nested = REPO / "crony-eu" / "docs" / "scope.md"
        if not nested.exists():
            pytest.skip("the nested copy has been removed outright, which also works")
        assert "../../scope.md" in nested.read_text(encoding="utf-8")


class TestCronyIsUnderTheDocumentationChecks:
    """The docs described a tool that does not exist, and nothing said so."""

    def test_crony_is_a_document_root(self) -> None:
        assert "crony-eu" in test_docs.DOCUMENT_ROOTS, (
            "crony-eu/ left the roots test_docs.py reads, so its documents can "
            "again name files that were never built"
        )

    def test_crony_documents_are_actually_reached(self) -> None:
        reached = [p for p in test_docs.documents() if "crony-eu" in p.parts]
        assert len(reached) >= 8, f"only {len(reached)} Crony documents are checked"
