"""The page for counsel.

Counsel is the reader who can stop the project, so this page is written to be
useful to someone who will read it once, carefully, probably on paper. It states
what the project holds, what it removes on the way in, what it keeps that it
should not have to, and the questions waiting for an answer, in that order,
with counts and no values.

Nearly everything here is quoted from the counsel instructions themselves
(`docs/counsel/`), which are the documents counsel would receive. The page is a
designed view over them. It adds no fact, and where the instructions and a
generated report disagree the build stops.
"""

from __future__ import annotations

from serenata.site.charts import Bar, bar_chart
from serenata.site.components import Context, band, bullets, data_table, tiles
from serenata.site.facts import Instruction
from serenata.site.figures import percent, thousands
from serenata.site.markup import Html, fill, join

SECTIONS = (
    ("holds", "What is held"),
    ("removed", "What is removed"),
    ("kept", "What is kept"),
    ("asks", "What is asked"),
    ("changes", "What each answer changes"),
    ("record", "Decision record"),
)


def _grouped(instruction: Instruction) -> Html:
    """An instruction's questions, under the headings the instruction gave them."""
    parts = dict(instruction.parts)
    columns = []
    for letter in ("A", "B"):
        rows = [q for q in instruction.questions if q.label.startswith(letter)]
        columns.append(
            fill(
                "<div><h4>Part {letter}: {title}</h4><ol "
                'class="questions">{items}</ol></div>',
                letter=letter,
                title=parts[letter],
                items=join(
                    fill(
                        "<li><span "
                        'class="label">{label}</span><span>{text}</span></li>',
                        label=q.label,
                        text=q.text,
                    )
                    for q in rows
                ),
            )
        )
    return fill('<div class="parts">{columns}</div>', columns=join(columns))


def counsel(ctx: Context) -> Html:
    facts = ctx.facts
    instructions = facts.instructions
    total_questions = sum(len(i.questions) for i in instructions)
    fields = sum(i.fields for i in instructions)
    unresolved = sum(i.unresolved for i in instructions)
    drafted = sum(1 for gate in facts.counsel_gates if gate.drafted)

    top = band(
        "dark",
        fill(
            '<p class="kicker">For counsel</p>'
            "<h1>What the project holds, and what it is asking</h1>"
            '<p class="lede">What is held today, what is removed on the way in, what '
            "is "
            "kept that should not be, and the questions waiting for an answer. Counts "
            "only: no field value appears on this page.</p>"
            '<div class="callout"><p>{notice}</p></div>'
            "{tiles}"
            '<ul class="toc no-print">{toc}</ul>'
            '<div class="actions no-print"><button class="button" type="button" '
            "data-print>Print this page</button></div>",
            notice=facts.counsel_notice,
            tiles=tiles(
                [
                    (
                        f"{drafted} of {len(facts.counsel_gates)}",
                        "instructions drafted",
                    ),
                    (str(total_questions), "questions in them"),
                    (f"{unresolved} of {fields}", "decision-record fields unresolved"),
                ]
            ),
            toc=join(
                fill(
                    '<li><a href="#{ident}">{label}</a></li>', ident=ident, label=label
                )
                for ident, label in SECTIONS
            ),
        ),
    )

    holder = next((i for i in instructions if i.holds), None)
    organisation_rows = dict(facts.corpus.tables).get("organisation", 0)
    holds_body = fill(
        "<h2>The project holds {notices} notices as raw XML, and as {rows} rows in "
        "{n} tables.</h2>"
        '<div class="prose"><p>Organisation records are the population that matters '
        "most. The indicator that says an organisation is a natural person is a field "
        "publishers may leave out, and absent means not provided, never false. Across "
        "the {org} organisation rows in this corpus:</p></div>"
        "{indicator_tiles}"
        "{facts_list}"
        "<h3>Rows per table</h3>{tables}",
        notices=thousands(facts.corpus.notices),
        rows=thousands(facts.corpus.rows),
        n=len(facts.corpus.tables),
        indicator_tiles=tiles(
            [
                (
                    f"{facts.natural_person_absent}%",
                    "carry no natural-person indicator",
                ),
                (f"{facts.natural_person_present}%", "carry one, true or false"),
            ]
        ),
        org=thousands(organisation_rows),
        facts_list=(
            fill(
                '<p class="muted">Quoted from <a href="{url}">the instruction on '
                "{title}</a>.</p>"
                '<dl class="facts">{items}</dl>',
                url=holder.url,
                title=holder.title.lower(),
                items=join(
                    fill("<dt>{label}</dt><dd>{text}</dd>", label=label, text=text)
                    for label, text in holder.holds
                ),
            )
            if holder
            else ""
        ),
        tables=data_table(
            ["Table", "Rows"],
            [(name, thousands(count)) for name, count in facts.corpus.tables],
            numeric={1},
        ),
    )
    holds = band("light", holds_body, "holds")

    d = facts.dropped
    rules = facts.drop_rules
    removed = band(
        "dark",
        fill(
            "<h2>{dropped} of {total} leaf elements ({pct}%) are dropped before a "
            "record exists.</h2>"
            '<div class="prose"><p>Measured on the same {n} packages. Each is dropped '
            "by "
            "the path it sits on, so a field TED adds next year inside a contact block "
            "is dropped on arrival.</p></div>"
            "<figure>{chart}<figcaption>Leaf elements dropped, by the rule that "
            "dropped "
            "them.</figcaption></figure>"
            "<h3>The rules, as code</h3>"
            '<ul class="plain"><li>Any path through: {segments}.</li>'
            "<li>Any path ending: {suffixes}, which is free text a publisher wrote to "
            "explain a withheld field.</li>"
            "<li>Where <code>{indicator}</code> is true, the organisation's name, "
            "registration identifier, postal address and website are suppressed and "
            "only an opaque key is kept: {prefixes}.</li></ul>"
            '<div class="callout"><p><strong>Structural suppression is not '
            "anonymisation.</strong> The source notice stays public and linkable, and "
            "an opaque key that joins back to it does not make a person anonymous. "
            'The rule list is <a href="{personal_data}">docs/personal-data.md</a>, '
            "executable as <code>serenata/parse/personal_data.py</code>.</p></div>",
            dropped=thousands(d.leaves_dropped),
            total=thousands(d.leaves_total),
            pct=d.percent,
            n=len(facts.corpus.packages),
            chart=bar_chart(
                [Bar(name, count) for name, count in d.by_rule],
                value_header="Leaves dropped",
            ),
            segments=join(
                (fill("<code>{s}</code>", s=s) for s in rules.segments), ", "
            ),
            suffixes=join(
                (fill("<code>{s}</code>", s=s) for s in rules.suffixes), ", "
            ),
            indicator=rules.natural_person_indicator,
            prefixes=join(
                (fill("<code>{s}</code>", s=s) for s in rules.natural_person_prefixes),
                ", ",
            ),
            personal_data=ctx.link("docs/personal-data.md"),
        ),
        "removed",
    )

    leaks = sorted(facts.leaks, key=lambda leak: (-leak.address_shaped, leak.column))
    address = sum(leak.address_shaped for leak in leaks)
    person = sum(leak.person_shaped for leak in leaks)
    described = sum(
        leak.address_shaped for leak in leaks if leak.column.endswith(".description")
    )
    retained = next((i for i in instructions if i.limits), None)
    kept_parts = [
        fill(
            "<h2>{address} values in retained columns are shaped like an email "
            "address.</h2>"
            '<div class="prose"><p>{person} of them are shaped like a person\'s own '
            "address. {described} ({share}%) sit in the two description columns, which "
            "no classifier reads and the dataset still carries. The path rules cannot "
            "catch a publisher who types a contact address into a field that is not a "
            "contact field, and publishers do.</p></div>"
            "<figure>{chart}<figcaption>Email-shaped values by retained column, with "
            "the subset shaped like a person's own address. A pattern count, not an "
            "inventory and not a legal classification.</figcaption></figure>",
            address=address,
            person=person,
            described=described,
            share=percent(described, address),
            chart=bar_chart(
                [
                    Bar(leak.column, leak.address_shaped, part=leak.person_shaped)
                    for leak in leaks
                ],
                value_header="Email-shaped values",
                part_header="Shaped like a person's",
                part_label="Shaped like a person's own address",
                rest_label="Other email-shaped",
            ),
        )
    ]
    if retained:
        kept_parts.append(
            fill(
                '<h3>Limits of these numbers</h3><p class="muted">From <a '
                'href="{url}">the '
                "instruction on {title}</a>.</p>{items}",
                url=retained.url,
                title=retained.title.lower(),
                items=bullets(retained.limits),
            )
        )
        if retained.options:
            kept_parts.append(
                fill(
                    '<h3>The options put to counsel</h3><ol class="plain">{items}</ol>',
                    items=join(
                        fill("<li>{o}</li>", o=option) for option in retained.options
                    ),
                )
            )
    kept = band("light", join(kept_parts), "kept")

    asks_parts = [
        fill(
            "<h2>{n} questions in {k} instructions. {done} of {k} decision records "
            "completed.</h2>"
            '<div class="prose"><p>In both instructions Part A concerns what the '
            "project "
            "holds today. Part B concerns the rule from here on, including what may be "
            "published.</p></div>",
            n=total_questions,
            k=len(instructions),
            done=sum(1 for i in instructions if i.unresolved == 0),
        )
    ]
    for instruction in instructions:
        asks_parts.append(
            fill(
                '<section><h3>#{number}: {title} <span class="pill '
                'pill--open">{status}</span></h3>'
                '<div class="prose"><p>{summary}</p>'
                '<p><a href="{url}">Read the full '
                "instruction</a></p></div>{questions}</section>",
                number=instruction.number,
                title=instruction.title,
                status=instruction.status.removeprefix("Status: ").split(".")[0],
                summary=instruction.summary,
                url=instruction.url,
                questions=_grouped(instruction),
            )
        )
    asks = band("dark", join(asks_parts), "asks")

    changes_parts = [
        Html(
            "<h2>What each answer changes in the code</h2>"
            '<p class="muted">So the questions are not abstract. Quoted from the '
            "instructions.</p>"
        )
    ]
    for instruction in instructions:
        changes_parts.append(
            fill(
                "<h3>#{number}: {title}</h3>{table}",
                number=instruction.number,
                title=instruction.title,
                table=data_table(
                    list(instruction.consequences.header),
                    [row.cells for row in instruction.consequences.rows],
                ),
            )
        )
    changes = band("light", join(changes_parts), "changes")

    record_parts = [
        fill(
            "<h2>Decision record: {unresolved} of {fields} fields unresolved</h2>"
            '<div class="prose"><p>Each instruction ends with the same record: '
            "decision status, bounded scope, permitted and prohibited actions, expiry, "
            "implementation conditions, existing holdings and completion evidence. "
            "Until "
            "counsel has answered and an authorized human has recorded the decision, "
            "the "
            "affected work stays on hold.</p>"
            "<p>The retention decision the whole page rests on is "
            '<a href="{adr}">ADR-0010</a>, whose status reads: '
            "<strong>{status}</strong>. "
            "It records that lawful basis, retention, transparency and the need for a "
            "data protection impact assessment are unresolved for the raw archive and "
            "for the derived data.</p></div>",
            unresolved=unresolved,
            fields=fields,
            adr=ctx.link("docs/adr/0010-raw-archive-retention.md"),
            status=facts.retention_status,
        ),
        data_table(
            ["Instruction", "Status", "Fields unresolved"],
            [
                (
                    fill('<a href="{u}">#{n}: {t}</a>', u=i.url, n=i.number, t=i.title),
                    i.status.removeprefix("Status: "),
                    f"{i.unresolved} of {i.fields}",
                )
                for i in instructions
            ],
        ),
        fill(
            '<p class="muted">Not drafted yet: {pending}.</p>',
            pending=", ".join(
                f"{g.number} {g.title.lower()}"
                for g in facts.counsel_gates
                if not g.drafted
            )
            or "nothing",
        ),
    ]
    record = band("dark", join(record_parts), "record")
    return join([top, holds, removed, kept, asks, changes, record])
