"""The frame every page shares: the status strip, the header, the footer.

Pages are self-contained. The stylesheet and the script are written into each
file, so a page opens from an email attachment, from a USB stick or from a
folder on disk exactly as it does from a server, and makes no request to
anyone. That matters for the reader this site is mostly for: counsel, who will
save a page, print it and mark it up.
"""

from __future__ import annotations

from importlib import resources

from serenata.site.markup import Html, fill, join

#: File name, then the label in the navigation. The order is the navigation's.
PAGES: tuple[tuple[str, str], ...] = (
    ("index.html", "Overview"),
    ("how-it-works.html", "How it works"),
    ("flag.html", "A flag, explained"),
    ("status.html", "Status"),
    ("counsel.html", "For counsel"),
)

#: On every page, sticky, because nothing on this site is meant to be seen
#: without it: no flag has been published, and the records shown are invented.
STRIP = (
    "No flag has been published. Every flag record on this site is "
    "<strong>synthetic</strong>, invented to show how one is read. "
    '<a href="status.html">Why</a>'
)

#: Three dots on a line and one lifted out of it. The point of the project is a
#: value that sits away from the rest, drawn without borrowing anyone's mark.
MARK = (
    '<svg width="34" height="22" viewBox="0 0 34 22" aria-hidden="true" '
    'focusable="false">'
    '<g fill="#fff"><circle cx="3.5" cy="16" r="3.5"/><circle cx="13.5" cy="16" '
    'r="3.5"/>'
    '<circle cx="23.5" cy="16" r="3.5"/></g><circle cx="30" cy="4.5" r="4" '
    'fill="#bc68d1"/></svg>'
)


def static(name: str) -> str:
    """A file from this package's ``static/`` directory."""
    return (resources.files("serenata.site") / "static" / name).read_text(
        encoding="utf-8"
    )


def _navigation(current: str) -> Html:
    items = join(
        fill(
            '<li><a href="{href}"{current}>{label}</a></li>',
            href=href,
            label=label,
            current=Html(' aria-current="page"') if href == current else "",
        )
        for href, label in PAGES
    )
    return fill('<nav aria-label="Main"><ul>{items}</ul></nav>', items=items)


def page(
    *,
    filename: str,
    title: str,
    description: str,
    bands: Html,
    footer: Html,
    script: bool,
) -> str:
    """One complete HTML document."""
    head = fill(
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        # Not indexable until the release gates clear: ADR-0014 says why, and
        # says what removing this line requires.
        '<meta name="robots" content="noindex">\n'
        '<meta name="description" content="{description}">\n'
        "<title>{title} | Serenata Europa</title>\n<style>\n",
        description=description,
        title=title,
    )
    body = fill(
        "\n</style>\n</head>\n<body>\n"
        '<a class="skip" href="#main">Skip to the content</a>\n'
        '<div class="strip" role="note">{strip}</div>\n'
        '<header class="site"><div class="wrap">'
        '<a class="wordmark" href="index.html">{mark}<span>Serenata Europa</span></a>'
        "{navigation}</div></header>\n"
        '<main id="main">\n{bands}\n</main>\n'
        '<footer class="site band band--deep">{footer}</footer>\n',
        strip=Html(STRIP),
        mark=Html(MARK),
        navigation=_navigation(filename),
        bands=bands,
        footer=footer,
    )
    tail = Html("</body>\n</html>\n")
    if script:
        tail = Html(f"<script>\n{static('site.js')}\n</script>\n</body>\n</html>\n")
    return str(head) + static("site.css") + str(body) + str(tail)
