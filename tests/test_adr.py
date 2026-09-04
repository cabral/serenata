"""Architecture decision records, and whether they still describe this code.

An ADR is prose, and prose about code rots. Most of these decisions *are*
enforced — the byte-stability of ADR-0001 is a rerun in CI, the DTD refusal of
ADR-0003 raises with the ADR's own number in the message — but nothing said so
in the direction a reader travels. Someone reading a decision wants to know
whether it is still true, and "there is a test" is only useful if they can find
it.

So each record names what enforces it, and this checks that the name resolves.
A record pointing at a test class that was renamed or deleted is worse than one
pointing at nothing: it claims a guarantee that has quietly stopped existing.

Two records name no test, and say so rather than inventing one. ADR-0009 is
enforced by a CI workflow rather than by pytest, and ADR-0010 is a policy about
retention and lawful basis — the kind of thing no test can hold true.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
ADR_ROOT = REPO / "docs" / "adr"

#: `- Enforced by: …` in the header block of a record.
ENFORCED = re.compile(r"^- Enforced by: (.+?)(?=^\n|^## )", re.M | re.S)

#: A backticked `tests/test_x.py::TestY` or `.github/workflows/x.yml`.
REFERENCE = re.compile(r"`([^`\n]+)`")

#: What a record says when nothing mechanical holds it true.
NOT_MECHANICAL = "nothing mechanical"


def records() -> list[Path]:
    """Every numbered decision record."""
    return sorted(ADR_ROOT.glob("[0-9]*.md"))


def enforcement(path: Path) -> str:
    found = ENFORCED.search(path.read_text(encoding="utf-8"))
    assert found, (
        f"{path.name} has no `- Enforced by:` line. Every record says what holds "
        "it true, including the ones where the answer is that nothing does."
    )
    return found.group(1).strip()


def classes_in(module: Path) -> set[str]:
    """Every class defined in a test module, by name."""
    tree = ast.parse(module.read_text(encoding="utf-8"))
    return {node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)}


def ids(path: Path) -> list[str]:
    return [
        token
        for token in REFERENCE.findall(enforcement(path))
        if "/" in token or "::" in token
    ]


class TestEveryRecordSaysWhatHoldsItTrue:
    def test_the_directory_is_not_empty(self) -> None:
        # Guards every parametrised test below: with no records they would all
        # pass by having nothing to check.
        assert len(records()) >= 10

    @pytest.mark.parametrize("path", records(), ids=lambda p: p.name[:4])
    def test_it_has_an_enforcement_line(self, path: Path) -> None:
        assert enforcement(path)

    @pytest.mark.parametrize("path", records(), ids=lambda p: p.name[:4])
    def test_it_names_something_or_says_it_names_nothing(self, path: Path) -> None:
        text = enforcement(path)
        assert ids(path) or NOT_MECHANICAL in text, (
            f"{path.name} names no test and does not say that nothing enforces "
            f"it. One or the other, so a reader is never left guessing: {text!r}"
        )


class TestEveryReferenceResolves:
    """A record naming a test that no longer exists claims a guarantee it lost."""

    @pytest.mark.parametrize("path", records(), ids=lambda p: p.name[:4])
    def test_every_named_file_exists(self, path: Path) -> None:
        for reference in ids(path):
            target = REPO / reference.split("::")[0]
            assert target.is_file(), f"{path.name} names {reference}, which is gone"

    @pytest.mark.parametrize("path", records(), ids=lambda p: p.name[:4])
    def test_every_named_test_class_exists(self, path: Path) -> None:
        for reference in ids(path):
            module, _, name = reference.partition("::")
            if not name:
                continue
            available = classes_in(REPO / module)
            assert name in available, (
                f"{path.name} names {reference}, but {module} defines no such "
                f"class. It was renamed or removed, and the record now claims a "
                f"guarantee nothing provides. Classes there: {sorted(available)}"
            )

    def test_the_check_can_actually_fail(self, tmp_path: Path) -> None:
        # A resolver that cannot report a miss would pass over any reference at
        # all, which is the failure mode this whole file exists to prevent.
        module = tmp_path / "test_nothing.py"
        module.write_text("class TestSomethingElse:\n    pass\n", encoding="utf-8")
        assert "TestRenamed" not in classes_in(module)
        assert "TestSomethingElse" in classes_in(module)


class TestTheRecordsAreWiredBothWays:
    def test_most_records_name_a_test(self) -> None:
        # Not all of them can, and pretending otherwise would be the dishonest
        # version of this. But if the majority stopped naming one, these
        # decisions would have drifted back to being prose about code.
        naming = [p.name[:4] for p in records() if ids(p) and "::" in enforcement(p)]
        assert len(naming) >= len(records()) - 2, (
            f"only {len(naming)} of {len(records())} records name a test class"
        )

    def test_the_tests_named_cite_the_record_back(self) -> None:
        # The reverse direction, which existed before this file did: a test
        # enforcing a decision says which decision, so a reader arriving from
        # the code finds the reasoning.
        silent = []
        for path in records():
            number = path.name[:4]
            for reference in ids(path):
                module = REPO / reference.split("::")[0]
                if module.suffix != ".py":
                    continue
                if f"ADR-{number}" not in module.read_text(encoding="utf-8"):
                    silent.append(f"{module.name} does not mention ADR-{number}")
        assert not silent, (
            "these tests enforce a decision without naming it, so a reader of "
            f"the code cannot find the reasoning: {silent}"
        )
