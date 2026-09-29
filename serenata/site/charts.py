"""The few charts the site draws, as plain HTML.

A bar is a ``<span>`` with a width, not an SVG or a script: it prints, it needs
no library, and its value is real text beside it. Every chart has a table twin
in a ``<details>`` so no number is reachable only by looking at a length.

Marks follow the project's reading of the data-visualisation rules it borrowed:
thin bars with a rounded data end, a 2px gap between touching fills instead of
a stroke, one hue for magnitude and grey for context, and a value at the tip of
each bar. A value is never carried by colour alone; the legend names both fills
and the table twin states them.
"""

from __future__ import annotations

from dataclasses import dataclass

from serenata.site.facts import Sensitivity
from serenata.site.figures import percent, ratio, thousands
from serenata.site.markup import Html, fill, join


@dataclass(frozen=True)
class Bar:
    """One bar. ``part`` is the emphasised share of ``value``, drawn first."""

    label: str
    value: int
    part: int | None = None
    note: str = ""


def _table(header: tuple[str, ...], rows: list[tuple[object, ...]]) -> Html:
    head = join(
        (fill('<th class="num">{h}</th>', h=h) if i else fill("<th>{h}</th>", h=h))
        for i, h in enumerate(header)
    )
    body = join(
        fill(
            "<tr>{cells}</tr>",
            cells=join(
                fill('<td class="num">{c}</td>', c=c)
                if i
                else fill("<td>{c}</td>", c=c)
                for i, c in enumerate(row)
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


def bar_chart(
    bars: list[Bar],
    *,
    value_header: str,
    part_header: str | None = None,
    part_label: str = "",
    rest_label: str = "",
) -> Html:
    """Horizontal bars, longest-first as given, with a legend if any bar has a part."""
    top = max(bar.value for bar in bars)
    rows = []
    for bar in bars:
        if bar.part is None:
            fills = Html("<span></span>")
        else:
            rest = bar.value - bar.part
            fills = join(
                [
                    fill('<span style="flex:{n} 1 0"></span>', n=bar.part)
                    if bar.part
                    else "",
                    fill('<span class="rest" style="flex:{n} 1 0"></span>', n=rest)
                    if rest
                    else "",
                ]
            )
        rows.append(
            fill(
                '<li class="bar-row"><span class="bar-label">{label}</span>'
                '<span class="bar-track"><span class="bar" '
                'style="--r:{r}">{fills}</span>'
                '<span class="bar-value">{value}{note}</span></span></li>',
                label=bar.label,
                r=ratio(bar.value, top),
                fills=fills,
                value=thousands(bar.value),
                note=f" ({bar.note})" if bar.note else "",
            )
        )
    legend = Html("")
    if any(bar.part is not None for bar in bars):
        legend = fill(
            '<ul class="legend"><li><i></i>{part}</li><li><i '
            'class="rest"></i>{rest}</li></ul>',
            part=part_label,
            rest=rest_label,
        )
    header = (
        ("", value_header) if part_header is None else ("", value_header, part_header)
    )
    table_rows: list[tuple[object, ...]] = [
        (bar.label, thousands(bar.value))
        if bar.part is None
        else (bar.label, thousands(bar.value), thousands(bar.part))
        for bar in bars
    ]
    return fill(
        '<ul class="bars">{rows}</ul>{legend}'
        '<details class="twin"><summary>Table view</summary>{table}</details>',
        rows=join(rows),
        legend=legend,
        table=_table(header, table_rows),
    )


def heat_table(sensitivity: Sensitivity, *, floor: int, rate: int) -> Html:
    """Flags at each pair of parameters; the pair the rule uses is outlined.

    Shade is a step on one hue by count. The count is written in every cell, so
    the shade is a convenience for finding the edge, not the only way to read it.
    """
    top = max(max(row.flags) for row in sensitivity.rows)
    head = join(
        [
            Html('<th scope="col">Segment floor</th>'),
            Html('<th scope="col" class="num">Segments</th>'),
            Html('<th scope="col" class="num">Lot results covered</th>'),
            *(
                fill('<th scope="col" class="num">Flags if below {p}%</th>', p=p)
                for p in sensitivity.percents
            ),
        ]
    )
    body = []
    for row in sensitivity.rows:
        cells = []
        for percent_limit, count in zip(sensitivity.percents, row.flags, strict=True):
            chosen = row.floor == floor and percent_limit == rate
            cells.append(
                fill(
                    '<td class="heat heat-{level}{chosen}">{count}</td>',
                    level=count * 4 // top,
                    chosen=" chosen" if chosen else "",
                    count=count,
                )
            )
        body.append(
            fill(
                '<tr><th scope="row">{floor}</th><td class="num">{segments}</td>'
                '<td class="num">{covered}</td>{cells}</tr>',
                floor=row.floor,
                segments=row.segments,
                covered=thousands(row.covered),
                cells=join(cells),
            )
        )
    return fill(
        '<div class="scroll"><table><thead><tr>{head}</tr></thead>'
        "<tbody>{body}</tbody></table></div>",
        head=head,
        body=join(body),
    )


def share(part: int, whole: int) -> str:
    """``part`` of ``whole`` as a percentage with its unit, for a bar's note."""
    return f"{percent(part, whole)}%"
