"""Reading the project's own documents, and refusing when they change shape.

The site states numbers and quotes questions that already live in this
repository's documents: a hypothesis file, a generated report, a counsel
instruction. Copying them into templates would give each fact two homes, and the
second would be wrong within a month. So the site reads them where they are.

That makes each document an interface. Renaming a heading or reordering a table
changes what the site can find, and the honest response is a build that stops
and says which document and which part, not a page that quietly loses a section
or, worse, keeps the old number. Every reader here raises `SourceError` naming
the document and what it expected.

Nothing in this module reads data. It reads Markdown that a person can open.
"""

from __future__ import annotations

import posixpath
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

from serenata.site.markup import Html, esc, join

#: Where a reader lands when a page links to a document. The default branch,
#: because a page cannot know which commit a reader will look at.
REPOSITORY = "https://github.com/cabral/serenata"
BRANCH = "main"

_HEADING = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
_FENCE = re.compile(r"^[ \t]*(```|~~~)")

_INLINE = re.compile(
    r"(?P<code>`[^`\n]+`)"
    r"|(?P<link>\[(?P<label>[^\]\n]+)\]\((?P<href>[^)\s]+)\))"
    r"|(?P<bold>\*\*(?P<strong>.+?)\*\*)"
    r"|(?P<em>(?<![\w*])\*(?P<emph>[^*\s][^*]*?)\*(?![\w*]))",
    re.S,
)


class SourceError(Exception):
    """A document no longer has the shape the site reads it in."""


@dataclass(frozen=True)
class Table:
    """A Markdown table: its header cells and its rows, as written."""

    header: tuple[str, ...]
    rows: tuple[tuple[str, ...], ...]


def slug(heading: str) -> str:
    """The anchor GitHub gives a heading."""
    text = heading.lstrip("#").strip().lower()
    return re.sub(r"[^\w\s-]", "", text).replace(" ", "-")


def plain(text: str) -> str:
    """``text`` with its inline Markdown marks removed, for a label or a match."""
    text = re.sub(r"\[([^\]\n]+)\]\([^)\s]+\)", r"\1", text)
    text = text.replace("`", "").replace("**", "")
    return re.sub(r"(?<![\w*])\*([^*\s][^*]*?)\*(?![\w*])", r"\1", text)


@dataclass(frozen=True)
class Doc:
    """One Markdown file in the repository, read for what the site needs."""

    repo: Path
    path: str
    text: str

    @classmethod
    def read(cls, repo: Path, path: str) -> Doc:
        target = repo / path
        if not target.is_file():
            raise SourceError(f"{path}: the site reads this document and it is gone")
        return cls(repo, path, target.read_text(encoding="utf-8"))

    def fail(self, message: str) -> SourceError:
        return SourceError(f"{self.path}: {message}")

    # -- structure ---------------------------------------------------------

    def outline(self) -> list[tuple[int, int, str]]:
        """``(line index, level, title)`` for every heading outside a code fence."""
        found = []
        fenced = False
        for index, line in enumerate(self.text.splitlines()):
            if _FENCE.match(line):
                fenced = not fenced
                continue
            match = None if fenced else _HEADING.match(line)
            if match:
                found.append((index, len(match.group(1)), match.group(2)))
        return found

    @property
    def url(self) -> str:
        """This document's own address on the web."""
        return f"{REPOSITORY}/blob/{BRANCH}/{self.path}"

    def headings(self, level: int = 2) -> list[str]:
        """The titles of every heading at ``level``, in document order."""
        return [title for _, at, title in self.outline() if at == level]

    def title(self) -> str:
        """The document's own title, its first level-one heading."""
        titles = self.headings(1)
        if not titles:
            raise self.fail("has no level-one heading")
        return titles[0]

    def section(self, title: str, *, level: int = 2) -> str:
        """The body under the first ``level`` heading starting with ``title``.

        A prefix match, because a heading such as "Part A - processing (answer
        this first)" is allowed to be reworded after the dash without breaking
        the reader; the part a person searched for is the part that matters.
        """
        headings = self.outline()
        lines = self.text.splitlines()
        for position, (index, at, heading) in enumerate(headings):
            if at != level or not heading.startswith(title):
                continue
            end = len(lines)
            for later_index, later_level, _ in headings[position + 1 :]:
                if later_level <= level:
                    end = later_index
                    break
            return "\n".join(lines[index + 1 : end]).strip("\n")
        raise self.fail(f"has no level-{level} heading starting {title!r}")

    # -- blocks inside a section -------------------------------------------

    def paragraph(self, body: str) -> str:
        """The first paragraph of ``body``, unwrapped onto one line."""
        block: list[str] = []
        for line in body.splitlines():
            if line.strip():
                block.append(line.strip())
            elif block:
                break
        if not block:
            raise self.fail("expected a paragraph and found none")
        return " ".join(block)

    def paragraphs(self, body: str) -> list[str]:
        """Every paragraph of ``body``, each unwrapped onto one line."""
        blocks: list[list[str]] = [[]]
        for line in body.splitlines():
            if line.strip():
                blocks[-1].append(line.strip())
            elif blocks[-1]:
                blocks.append([])
        return [" ".join(block) for block in blocks if block]

    def items(self, body: str, marker: str = r"-") -> list[str]:
        """Top-level list items of ``body``, each unwrapped onto one line.

        ``marker`` is a regular expression for the bullet: ``-`` for bullets,
        ``\\d+\\.`` for a numbered list. A wrapped item continues until a blank
        line or the next item.
        """
        start = re.compile(rf"^{marker}[ \t]+(.*)$")
        items: list[list[str]] = []
        current: list[str] | None = None
        for line in body.splitlines():
            found = start.match(line)
            if found:
                current = [found.group(1).strip()]
                items.append(current)
            elif not line.strip() or _HEADING.match(line):
                # A blank line ends the item it follows: text after one is a
                # new paragraph, not a continuation of the bullet.
                current = None
            elif current is not None:
                current.append(line.strip())
        return [" ".join(parts) for parts in items]

    def table(self, body: str, *, after: str | None = None) -> Table:
        """The first Markdown table in ``body`` (after the text ``after`` if given)."""
        text = body
        if after is not None:
            if after not in body:
                raise self.fail(f"expected the text {after!r} before a table")
            text = body.split(after, 1)[1]
        rows: list[tuple[str, ...]] = []
        started = False
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("|"):
                started = True
                cells = re.split(r"(?<!\\)\|", stripped.strip("|"))
                rows.append(tuple(cell.strip().replace("\\|", "|") for cell in cells))
            elif started:
                break
        if len(rows) < 3 or not all(set(c) <= set(":- ") for c in rows[1]):
            raise self.fail("expected a Markdown table with a header and rows")
        width = len(rows[0])
        if any(len(row) != width for row in rows):
            raise self.fail("has a table whose rows differ in width")
        return Table(header=rows[0], rows=tuple(rows[2:]))

    def toml(self, body: str) -> dict[str, object]:
        """The single fenced TOML block in ``body``."""
        blocks = re.findall(r"^```toml\n(.*?)^```[ \t]*$", body, re.M | re.S)
        if len(blocks) != 1:
            raise self.fail(f"expected one fenced TOML block, found {len(blocks)}")
        try:
            return tomllib.loads(blocks[0])
        except tomllib.TOMLDecodeError as error:
            raise self.fail(f"has TOML that does not parse: {error}") from error

    def find(self, pattern: str, body: str | None = None) -> re.Match[str]:
        """The first match of ``pattern`` in ``body`` (default: the whole document)."""
        match = re.search(pattern, self.text if body is None else body, re.S)
        if not match:
            raise self.fail(f"expected text matching {pattern!r}")
        return match

    # -- rendering ---------------------------------------------------------

    def href(self, target: str) -> str:
        """Where a link in this document points, as an address on the web.

        A relative link is resolved against this document's directory and must
        name something that exists: a page that links to a file the repository
        no longer has teaches a reader that the rest is stale too.
        """
        if target.startswith(("http://", "https://", "mailto:")):
            return target
        path, _, anchor = target.partition("#")
        if path:
            resolved = posixpath.normpath(
                posixpath.join(posixpath.dirname(self.path), path)
            )
        else:
            resolved = self.path
        if resolved.startswith("..") or not (self.repo / resolved).exists():
            raise self.fail(f"links to {target!r}, which does not exist")
        kind = "tree" if (self.repo / resolved).is_dir() else "blob"
        suffix = f"#{anchor}" if anchor else ""
        return f"{REPOSITORY}/{kind}/{BRANCH}/{resolved}{suffix}"

    def inline(self, text: str) -> Html:
        """``text`` as HTML: code, bold, emphasis and links; everything else escaped."""
        parts: list[Html] = []
        cursor = 0
        for match in _INLINE.finditer(text):
            parts.append(esc(text[cursor : match.start()]))
            cursor = match.end()
            if match.group("code"):
                parts.append(Html(f"<code>{esc(match.group('code')[1:-1])}</code>"))
            elif match.group("link"):
                label = self.inline(match.group("label"))
                address = esc(self.href(match.group("href")))
                parts.append(Html(f'<a href="{address}">{label}</a>'))
            elif match.group("bold"):
                parts.append(
                    Html(f"<strong>{self.inline(match.group('strong'))}</strong>")
                )
            else:
                parts.append(Html(f"<em>{self.inline(match.group('emph'))}</em>"))
        parts.append(esc(text[cursor:]))
        return join(parts)
