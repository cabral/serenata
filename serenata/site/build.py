"""Build the site: read the facts once, render each page, write the files.

Deterministic by construction. Pages are functions of `Facts`; nothing consults
a clock, the environment or the order the file system lists things in, and files
are written in a fixed order with fixed line endings. Building twice from the
same working tree gives the same bytes, which `tests/test_site.py` checks, for
the reason every stage of this project is held to it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from serenata.site import counsel, layout, pages
from serenata.site.components import Context, footer
from serenata.site.docs import Doc
from serenata.site.facts import read_facts
from serenata.site.markup import Html


@dataclass(frozen=True)
class PageSpec:
    filename: str
    title: str
    description: str
    render: Callable[[Context], Html]
    script: bool = False


SPECS: tuple[PageSpec, ...] = (
    PageSpec(
        "index.html",
        "Overview",
        "An open pipeline that flags statistical anomalies in EU procurement notices, "
        "each checkable against its source.",
        pages.overview,
    ),
    PageSpec(
        "how-it-works.html",
        "How it works",
        "The five stages of the pipeline, the four boundaries between them and the "
        "six constraints they keep.",
        pages.how_it_works,
    ),
    PageSpec(
        "flag.html",
        "A flag, explained",
        "What one flag says, how the rule decides, and how a reader checks it. "
        "Every record shown is synthetic.",
        pages.flag,
        script=True,
    ),
    PageSpec(
        "status.html",
        "Status",
        "Milestones, the gates that block release, and the archive every figure was "
        "measured on.",
        pages.status,
    ),
    PageSpec(
        "counsel.html",
        "For counsel",
        "What the project holds, what it removes on the way in, what it keeps, and "
        "the questions waiting for an answer.",
        counsel.counsel,
        script=True,
    ),
)


def default_repo() -> Path:
    """The repository this package is installed from."""
    return Path(__file__).resolve().parents[2]


def render_site(repo: Path) -> dict[str, str]:
    """Every page, by file name. Raises `SourceError` if a document changed shape."""
    context = Context(facts=read_facts(repo), root=Doc.read(repo, "README.md"))
    footer_html = footer(context)
    names = {filename for filename, _ in layout.PAGES}
    if names != {spec.filename for spec in SPECS}:
        raise AssertionError("the navigation and the page specifications disagree")
    return {
        spec.filename: layout.page(
            filename=spec.filename,
            title=spec.title,
            description=spec.description,
            bands=spec.render(context),
            footer=footer_html,
            script=spec.script,
        )
        for spec in SPECS
    }


def build_site(repo: Path, out: Path) -> tuple[Path, ...]:
    """Write the pages under ``out`` and return the paths written, in order."""
    rendered = render_site(repo)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for filename in sorted(rendered):
        target = out / filename
        target.write_bytes(rendered[filename].encode("utf-8"))
        written.append(target)
    return tuple(written)
