"""The documentation, checked for claims that have stopped being true.

The docs are part of the product here: funders, journalists and contributors
read them, and `CLAUDE.md` says so. A broken link or a reference to a file that
no longer exists costs a reader's trust in everything around it, and neither is
visible in a diff — you only see it when you follow the link, which a reviewer
does not do for forty of them.

Two things are checked, both mechanical:

- **Every relative link resolves**, including its anchor. A link to a heading
  that was renamed is the common failure, because renaming a heading is a
  one-line change nobody thinks of as breaking anything.
- **Every backticked path exists.** Documents and skills name files constantly —
  "the drop list is `serenata/parse/personal_data.py`" — and a document that
  names a file that is not there teaches the next reader something false. An
  illustrative path is written with a `<placeholder>` and is skipped, which is
  also how a reader tells an example from a claim.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

#: Everything a reader is expected to read. `.claude/skills/` is included
#: because those files are rules people follow, and a rule naming a file that
#: does not exist is a rule that cannot be followed.
DOCUMENT_ROOTS = ("docs", ".claude", "tests", "data")
TOP_LEVEL = ("README.md", "CONTRIBUTING.md", "CLAUDE.md")

#: A markdown link to something other than an absolute URL or a mail address.
_LINK = re.compile(r"\[[^\]]*\]\((?!https?:|mailto:)([^)]+)\)")

#: Anything in backticks; filtered down to path-shaped tokens below.
_BACKTICKED = re.compile(r"`([^`\n]+)`")

#: Suffixes that make a backticked token a claim about a file in this repository.
_FILE_SUFFIXES = (".py", ".md", ".toml", ".yml", ".yaml", ".lock", ".cfg")

#: A token carrying one of these is an illustration, not a claim: a placeholder
#: (`docs/hypotheses/<module>.md`), a glob, or a numbering convention.
_PLACEHOLDERS = ("<", ">", "*", "NNN", "…", " ", "|")

#: Prefixes that look path-shaped and are not repository paths: the gitignored
#: data workspace, and eForms element paths, which are full of slashes.
_NOT_REPOSITORY_PATHS = (
    "data/",
    "notice/",
    "urn:",
    "http",
    "efac:",
    "efbc:",
    "cac:",
    "cbc:",
    "ext:",
)


def documents() -> list[Path]:
    """Every markdown file a reader of this repository is offered."""
    found = [REPO / name for name in TOP_LEVEL]
    for root in DOCUMENT_ROOTS:
        found.extend(sorted((REPO / root).rglob("*.md")))
    return [path for path in found if path.is_file()]


def slug(heading: str) -> str:
    """The anchor GitHub gives a heading."""
    text = heading.lstrip("#").strip().lower()
    return re.sub(r"[^\w\s-]", "", text).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    return {
        slug(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.startswith("#")
    }


def links() -> list[tuple[Path, str]]:
    return [
        (path, target)
        for path in documents()
        for target in _LINK.findall(path.read_text(encoding="utf-8"))
    ]


def claimed_paths() -> list[tuple[Path, str]]:
    """Backticked tokens that claim a file exists in this repository."""
    found: list[tuple[Path, str]] = []
    for path in documents():
        for token in _BACKTICKED.findall(path.read_text(encoding="utf-8")):
            candidate = token.strip()
            if "/" not in candidate or any(mark in candidate for mark in _PLACEHOLDERS):
                continue
            if candidate.startswith(_NOT_REPOSITORY_PATHS):
                continue
            if not (candidate.endswith(_FILE_SUFFIXES) or candidate.endswith("/")):
                continue
            found.append((path, candidate))
    return found


class TestLinks:
    """A link a reader follows and a link a reviewer skims are different things."""

    def test_every_relative_link_resolves(self) -> None:
        broken = []
        for path, target in links():
            file_part = target.partition("#")[0]
            if not file_part:
                continue
            if not (path.parent / file_part).resolve().exists():
                broken.append(f"{path.relative_to(REPO)} -> {target}")
        assert not broken, f"links to files that do not exist: {broken}"

    def test_every_anchor_exists(self) -> None:
        broken = []
        for path, target in links():
            file_part, _, anchor = target.partition("#")
            destination = (path.parent / file_part).resolve() if file_part else path
            if not anchor or destination.suffix != ".md" or not destination.exists():
                continue
            if anchor not in anchors(destination):
                broken.append(f"{path.relative_to(REPO)} -> {target}")
        assert not broken, (
            f"links to headings that do not exist: {broken}. Renaming a heading "
            "is a one-line change that silently breaks every link to it."
        )

    def test_enough_links_were_checked(self) -> None:
        # The failure mode of a test that parses documents is passing because it
        # parsed nothing.
        assert len(links()) > 60, f"only found {len(links())} links to check"


class TestClaimsAboutFiles:
    """A document that names a file that is not there is worse than silent."""

    def test_every_backticked_path_exists(self) -> None:
        missing = sorted(
            {
                f"{path.relative_to(REPO)}: {candidate}"
                for path, candidate in claimed_paths()
                # Documents name paths both ways — from the repository root and
                # from their own directory — and both are legitimate.
                if not (REPO / candidate).exists()
                and not (path.parent / candidate).exists()
            }
        )
        assert not missing, (
            f"documents naming files that do not exist: {missing}. Write an "
            "illustration with a <placeholder> so a reader can tell it from a "
            "claim, or fix the path."
        )

    def test_enough_paths_were_checked(self) -> None:
        assert len(claimed_paths()) > 50, (
            f"only found {len(claimed_paths())} path claims to check"
        )

    @pytest.mark.parametrize(
        "example", ["docs/hypotheses/<module>.md", "docs/cases/NNN-slug.md"]
    )
    def test_placeholders_are_not_treated_as_claims(self, example: str) -> None:
        # Proves the skip above is doing what it says rather than swallowing
        # every path in the repository.
        assert any(mark in example for mark in _PLACEHOLDERS)
