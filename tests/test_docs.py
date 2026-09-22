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

Since [ADR-0014](../docs/adr/0014-replace-serenata-with-crony.md) this also
reads `crony-eu/`, where the failure mode is the opposite of a rotted claim: a
specification written before the code, naming modules that were never built. A
planned path is a `<placeholder>` here too, so the same rule separates what
exists from what is intended.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

#: Everything a reader is expected to read. `.claude/skills/` is included
#: because those files are rules people follow, and a rule naming a file that
#: does not exist is a rule that cannot be followed. `crony-eu/` is included
#: because ADR-0014 makes it this repository's future, and a specification for
#: a tool nobody has built yet is the document most likely to name a file that
#: is not there.
DOCUMENT_ROOTS = ("docs", ".claude", "tests", "data", "tools", ".github", "crony-eu")

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
#: data workspace, eForms element paths, which are full of slashes, and anything
#: starting with a shell variable, which is by definition somewhere else.
#: Crony's data directory is written `$CRONY_DATA_DIR/raw/` rather than `raw/`
#: for that reason — a bare `raw/` reads like a directory here, and the one rule
#: that project has above all others is that its data never is.
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
    "$",
)

#: The tree phase 1 is specified to build and has not built yet. These are not
#: illustrations — they are the real intended paths, named by a work order
#: written before the code, and a `<placeholder>` would be a lie about that.
#: `TestPathsNotYetBuilt` below makes the exemption expire on its own: the day
#: the tree exists, this constant has to shrink or the tests fail.
#:
#: It has shrunk three times. `crony-eu/src/` and `crony-eu/tests/` went when
#: session 0 built them, `sources/` went when session 1 built the first adapter,
#: and `fr_entreprises_api.py` went when tier A of the ADR-0007 plan built it.
#: Every path the Crony documents claim inside those trees is now checked like
#: any other. What is left is the code the later sessions are ordered to write.
#:
#: `match/` stopped being exempt module by module as session 4 built it, and is
#: now checked in full like `sources/`.
#: That is the exemption doing its job: it gets narrower every time code lands,
#: and it cannot go on covering a directory that now holds real modules whose
#: documented paths deserve checking like any other.
_NOT_YET_BUILT = (
    "crony-eu/src/crony_eu/flags/",
    "crony-eu/src/crony_eu/export/",
    "crony-eu/src/crony_eu/sources/fr_inpi_rne.py",
)


def documents() -> list[Path]:
    """Every markdown file a reader of this repository is offered.

    Top-level documents are *discovered* rather than listed. They were listed
    once, and adding `SECURITY.md` proved the cost of that: it linked to a file
    that did not exist and every check here passed, because the new document was
    not among the three the tuple named. A gate that has to be told about a
    document is a gate that silently stops covering the repository.
    """
    found = sorted((REPO).glob("*.md"))
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
            if candidate.startswith(_NOT_REPOSITORY_PATHS + _NOT_YET_BUILT):
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


class TestPathsNotYetBuilt:
    """An exemption for unwritten code has to stop applying once it is written.

    `_NOT_YET_BUILT` lets a work order name the modules it is ordering. The
    danger is the ordinary one: the code arrives at a slightly different path,
    the exemption keeps swallowing the old name, and the document goes on
    describing a module nobody built. So the exemption checks its own premise.
    """

    @pytest.mark.parametrize("prefix", _NOT_YET_BUILT)
    def test_it_really_is_absent(self, prefix: str) -> None:
        assert not (REPO / prefix).exists(), (
            f"{prefix} exists now, so it is no longer unbuilt. Remove it from "
            "_NOT_YET_BUILT and let the paths inside it be checked like every "
            "other claim in this repository."
        )

    def test_the_exemption_is_narrow(self) -> None:
        # `crony-eu/` as a whole would exempt the specifications themselves,
        # which is the opposite of why ADR-0014 brought them in here.
        assert "crony-eu/" not in _NOT_YET_BUILT
