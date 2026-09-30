"""Small pieces the pages share: a band, a row of tiles, a table, the footer."""

from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from serenata.site.docs import Doc
from serenata.site.facts import Facts
from serenata.site.markup import Html, fill, join


@dataclass(frozen=True)
class Context:
    """What a page is built from: the facts, and a way to link to the repository."""

    facts: Facts
    root: Doc

    def link(self, path: str) -> str:
        """The address of a file or directory in the repository, which must exist."""
        return self.root.href(path)


def band(tone: str, inner: Html, ident: str | None = None) -> Html:
    """A full-width band. ``tone`` is ``dark`` or ``light``; bands alternate."""
    return fill(
        '<section class="band band--{tone}"{ident}><div '
        'class="wrap">{inner}</div></section>',
        tone=tone,
        ident=fill(' id="{ident}"', ident=ident) if ident else "",
        inner=inner,
    )


def hero(
    kicker: str, title: str, lede: Html | str, actions: Html | None = None
) -> Html:
    return band(
        "dark",
        fill(
            '<p class="kicker">{kicker}</p><h1>{title}</h1><p '
            'class="lede">{lede}</p>{actions}',
            kicker=kicker,
            title=title,
            lede=lede,
            actions=actions or "",
        ),
    )


def actions(*links: tuple[str, str, bool]) -> Html:
    """A row of buttons: ``(href, label, solid)``."""
    return fill(
        '<div class="actions">{items}</div>',
        items=join(
            fill(
                '<a class="button{solid}" href="{href}">{label}</a>',
                solid=" button--solid" if solid else "",
                href=href,
                label=label,
            )
            for href, label, solid in links
        ),
    )


def tiles(items: Sequence[tuple[str, str]]) -> Html:
    """A row of figures: ``(value, label)``."""
    return fill(
        '<ul class="tiles">{items}</ul>',
        items=join(
            fill(
                '<li class="tile"><span class="value">{value}</span>'
                '<span class="label">{label}</span></li>',
                value=value,
                label=label,
            )
            for value, label in items
        ),
    )


def data_table(
    header: Sequence[object],
    rows: Sequence[Sequence[object]],
    numeric: Collection[int] = (),
) -> Html:
    """A table. Cells that are `Html` pass through; anything else is escaped."""
    head = join(
        fill('<th scope="col"{cls}>{cell}</th>', cls=_cls(i, numeric), cell=cell)
        for i, cell in enumerate(header)
    )
    body = join(
        fill(
            "<tr>{cells}</tr>",
            cells=join(
                fill("<td{cls}>{cell}</td>", cls=_cls(i, numeric), cell=cell)
                for i, cell in enumerate(row)
            ),
        )
        for row in rows
    )
    return fill(
        '<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        "<tbody>{body}</tbody></table></div>",
        head=head,
        body=body,
    )


def _cls(index: int, numeric: Collection[int]) -> Html:
    return Html(' class="num"') if index in numeric else Html("")


def bullets(items: Sequence[Html | str], css: str = "plain") -> Html:
    return fill(
        '<ul class="{css}">{items}</ul>',
        css=css,
        items=join(fill("<li>{item}</li>", item=item) for item in items),
    )


def footer(ctx: Context) -> Html:
    """The independence statement, the source attribution and the way out."""
    facts = ctx.facts
    links = [
        ("Repository", "https://github.com/cabral/serenata"),
        ("Corrections policy", ctx.link("docs/corrections-policy.md")),
        ("Data reuse", ctx.link("docs/data-reuse.md")),
        ("Security", ctx.link("SECURITY.md")),
        ("Licence", ctx.link("LICENSE")),
    ]
    return fill(
        '<div class="wrap"><p>{independence}</p><p>{attribution}</p>'
        "<p>Code is AGPL-3.0. Figures on this site are measurements from the "
        "project's generated reports, licensed CC BY 4.0 "
        '(<a href="{adr4}">ADR-0004</a>). Source notices keep the terms above.</p>'
        "<ul>{links}</ul></div>",
        independence=facts.independence,
        attribution=facts.attribution,
        adr4=ctx.link("docs/adr/0004-dataset-licence.md"),
        links=join(
            fill('<li><a href="{href}">{label}</a></li>', href=h, label=n)
            for n, h in links
        ),
    )
