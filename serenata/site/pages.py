"""The four pages for everyone: overview, how it works, a flag explained, status.

The page for counsel is `serenata.site.counsel`. Copy here is written to the
project's communication rules: mechanical, source-linked, numbers next to the
claim, flags described as anomalies with ordinary explanations. Figures come
from `Facts`; a sentence that states one is built from it, never typed.
"""

from __future__ import annotations

import dataclasses

from serenata.classify import RULES
from serenata.classify import single_bid_in_segment as rule
from serenata.classify.records import Flag
from serenata.site import demo
from serenata.site.charts import Bar, bar_chart, heat_table, share
from serenata.site.components import (
    Context,
    actions,
    band,
    bullets,
    data_table,
    hero,
    tiles,
)
from serenata.site.docs import plain
from serenata.site.facts import Gate
from serenata.site.figures import percent, thousands
from serenata.site.markup import Html, fill, join

#: Fields the explorer rewrites when the reader moves a number.
LIVE_FIELDS = frozenset({"bids", "segment_size", "segment_single_bids"})


def overview(ctx: Context) -> Html:
    facts = ctx.facts
    m = facts.hypothesis.measurement
    days = len(m.package_ids)

    top = hero(
        "Open data infrastructure for EU public procurement",
        "EU procurement notices, read by a pipeline anyone can rerun",
        "Serenata Europa turns the notices published on TED into a documented "
        "dataset and flags statistical anomalies in it. Every flag links to the "
        "notice it came from and carries the numbers it was measured against.",
        actions(
            ("counsel.html", "For counsel", True),
            ("flag.html", "How a flag is checked", False),
        ),
    )

    funnel = bar_chart(
        [
            Bar("Lot outcomes the rule can consider", m.population, note="100%"),
            Bar(
                f"In a market of at least {rule.SEGMENT_FLOOR} comparable lots",
                m.covered,
                note=share(m.covered, m.population),
            ),
            Bar("Flagged", m.flagged, note=share(m.flagged, m.population)),
        ],
        value_header="Lot outcomes",
    )
    numbers = band(
        "light",
        fill(
            '<h2 class="statement">{notices} notices from {days} publication days of '
            "{year} have been parsed. One rule flags {flagged} lot outcomes in them. "
            "None of it is published.</h2>"
            "<figure>{funnel}<figcaption>Single-bid rule, version {version}, measured "
            "on {date}. The rule flags {rate}% of the outcomes it can speak about. "
            "{silent}% of all outcomes sit in markets below that size, and for those "
            "the rule stays silent.</figcaption></figure>"
            "{tiles}"
            '<div class="prose"><p>The {flagged} are what the rule produced on this '
            "archive. They are measurements, not findings. No empirical false-positive "
            "rate has been measured, and no flag has completed the verification "
            'protocol. <a href="status.html">What blocks release</a>, and '
            '<a href="flag.html">how a flag is checked</a>.</p></div>',
            notices=thousands(m.notices),
            days=days,
            year=m.period_start.year,
            flagged=m.flagged,
            funnel=funnel,
            version=m.rule_version,
            date=m.measured_on.isoformat(),
            rate=percent(m.flagged, m.covered, 2),
            silent=percent(m.uncovered, m.population),
            tiles=tiles(
                [
                    (thousands(facts.corpus.notices), "notices parsed"),
                    (
                        thousands(facts.corpus.rows),
                        f"rows in {len(facts.corpus.tables)} tables",
                    ),
                    (
                        str(len(RULES)),
                        "classifier built" if len(RULES) == 1 else "classifiers built",
                    ),
                    ("0", "flags published"),
                ]
            ),
        ),
    )

    audiences = band(
        "dark",
        fill(
            '<h2>Where to start</h2><ul class="cards">{cards}</ul>',
            cards=join(
                fill(
                    '<li class="card"><a '
                    'href="{href}"><h3>{who}</h3><p>{what}</p></a></li>',
                    href=href,
                    who=who,
                    what=what,
                )
                for href, who, what in [
                    (
                        "counsel.html",
                        "Counsel",
                        "What the project holds, what it drops on the way in, and the "
                        "questions waiting for an answer.",
                    ),
                    (
                        "flag.html",
                        "Journalists and reviewers",
                        "What a flag says, what it does not say, and how to check one "
                        "against TED.",
                    ),
                    (
                        "how-it-works.html",
                        "Contributors",
                        "Five stages, six constraints and the tests that hold them.",
                    ),
                    (
                        "status.html",
                        "Funders",
                        "Milestones, open gates and what each one needs.",
                    ),
                ]
            ),
        ),
    )

    lineage = band(
        "light",
        fill(
            '<h2>Where it comes from</h2><div class="prose">{lineage}</div>'
            '<div class="callout"><p>{independence}</p></div>',
            lineage=join(fill("<p>{p}</p>", p=p) for p in facts.lineage),
            independence=facts.independence,
        ),
    )
    return join([top, numbers, audiences, lineage])


def how_it_works(ctx: Context) -> Html:
    facts = ctx.facts
    d = facts.dropped
    days = len(facts.corpus.packages)

    top = hero(
        "How it works",
        "Five stages, and only the first touches the network",
        "Every later stage runs from the archive alone and produces the same bytes "
        "when it is run again. That property is what lets a stranger rerun the code "
        "and get the same rows.",
    )

    stages = band(
        "light",
        fill(
            "<h2>The pipeline</h2>"
            '<ol class="stages">{stages}</ol>'
            '<p class="muted">A summary of <a '
            'href="{architecture}">docs/architecture.md</a>. '
            "The last stage is not built: it is where flags would reach a reader, and "
            "nothing may reach a reader yet.</p>",
            architecture=ctx.link("docs/architecture.md"),
            stages=join(
                fill(
                    '<li class="stage{unbuilt}"><h3>{name}</h3>'
                    "<p>Reads {reads}. Writes {writes}.{networked}</p>"
                    '<span class="pill {pill}">{state}{note}</span></li>',
                    unbuilt="" if stage.built else " stage--unbuilt",
                    name=stage.name,
                    reads=stage.reads,
                    writes=stage.writes,
                    networked=fill(" Network: {n}.", n=stage.networked)
                    if plain(stage.networked).strip("-\u2014 ")
                    else "",
                    pill="pill--done" if stage.built else "pill--open",
                    state="built" if stage.built else "not built",
                    note=f", {stage.note}" if stage.note else "",
                )
                for stage in facts.stages
            ),
        ),
    )

    boundaries = [
        (
            "TED to the raw archive",
            "The only place the network exists. Whole publication days are downloaded "
            "and stored byte for byte, addressed by checksum, and not fetched again. "
            "That is what makes a flag checkable years later: the exact bytes it came "
            "from are still on disk.",
            "docs/adr/0002-fetch-daily-bulk-packages.md",
            "ADR-0002",
        ),
        (
            "The archive to records",
            f"Parse drops the documented personal-data paths before a value becomes a "
            f"record. On the {days} publication days measured, "
            f"{thousands(d.leaves_dropped)} of {thousands(d.leaves_total)} leaf "
            f"elements ({d.percent}%) were dropped this way. That limits what is kept. "
            "It does not make what is kept anonymous, and the page for counsel lists "
            "what is still held.",
            "docs/personal-data.md",
            "the drop list",
        ),
        (
            "Records to the model",
            "Each value keeps the element path it came from. Every value column has a "
            "status beside it: present, empty, absent, withheld or not applicable. A "
            "withheld bid count is published as the code unpublished and the number "
            "-1, and the status is what stops it being read as a quantity.",
            "docs/adr/0006-absence-is-recorded-not-collapsed.md",
            "ADR-0006",
        ),
        (
            "The model to Parquet",
            "Identical bytes are something this stage produces, not something Parquet "
            "has. Rows are sorted by key before every write, the schema comes from the "
            "model, writer options are pinned and the partition is the notice's own "
            "publication year, never the run's clock. On the measured archive "
            f"{thousands(facts.corpus.notices)} notices become "
            f"{thousands(facts.corpus.rows)} rows in "
            f"{len(facts.corpus.tables)} tables, "
            "and CI runs the pipeline twice and compares checksums.",
            "docs/adr/0001-parquet-duckdb-storage.md",
            "ADR-0001",
        ),
    ]
    boundary_band = band(
        "dark",
        fill(
            "<h2>Four boundaries, and what each one guarantees</h2>"
            '<dl class="facts">{items}</dl>',
            items=join(
                fill(
                    '<dt>{title}</dt><dd>{text} <a href="{href}">{label}</a>.</dd>',
                    title=title,
                    text=text,
                    href=ctx.link(path),
                    label=label,
                )
                for title, text, path, label in boundaries
            ),
        ),
    )

    constraints = band(
        "light",
        fill(
            "<h2>Six constraints</h2>"
            '<ol class="plain">{items}</ol>'
            '<p class="muted">Stated in full, with the reasons, in '
            '<a href="{claude}">CLAUDE.md</a>. Tests check specified patterns, '
            "fixtures "
            "and metadata. They do not certify privacy, legal compliance or every "
            "possible source of nondeterminism.</p>",
            claude=ctx.link("CLAUDE.md"),
            items=join(
                fill("<li>{item}</li>", item=item)
                for item in [
                    "The code is AGPL-3.0, and every dependency must be compatible "
                    "with it.",
                    "No personal data in the derived model. Fields that can name a "
                    "natural "
                    "person are dropped at ingestion, not stored and filtered later. "
                    "The "
                    "current implementation does not fully meet this; the gaps are on "
                    "the "
                    "status page.",
                    "Flags are statistical anomalies with possible innocent "
                    "explanations, "
                    "linked to their source notice. They are never accusations.",
                    "The same input and the same classifier version give the same "
                    "flags, "
                    "byte for byte. No clock, no unseeded randomness, no network "
                    "inside "
                    "transform or classify.",
                    "Core classifiers read structured fields only: no free text, no "
                    "NLP, "
                    "no language models.",
                    "A classifier needs a written hypothesis, tests, and a base rate "
                    "measured on real data before it merges.",
                ]
            ),
        ),
    )
    return join([top, stages, boundary_band, constraints])


def _explorer(ctx: Context) -> Html:
    """The rule, with its numbers movable, and the record it would write."""
    example = demo.example_flag()
    first = demo.cases()[0]
    code = demo.verdict(1, first.size, first.singles)
    record = join(
        fill(
            "<dt>{name}</dt><dd{marker}>{value}</dd>",
            name=field.name,
            marker=fill(' data-field="{n}"', n=field.name)
            if field.name in LIVE_FIELDS
            else "",
            value=getattr(example, field.name),
        )
        for field in dataclasses.fields(Flag)
    )
    return fill(
        '<div class="explorer" data-explorer data-floor="{floor}" data-rate="{rate}">'
        '<form aria-label="Rule explorer">'
        '<label>Bids this lot received<input name="bids" type="number" min="0" '
        'inputmode="numeric" value="1"></label>'
        '<label>Lot results in its market<input name="size" type="number" min="0" '
        'inputmode="numeric" value="{size}"></label>'
        '<label>Of those, lots that drew one bid<input name="singles" type="number" '
        'min="0" inputmode="numeric" value="{singles}"></label>'
        "</form>"
        '<div class="out" aria-live="polite">'
        "<p data-rate-line>{singles} of {size} lot results in this market drew one "
        "bid: {pct}%.</p>"
        '<p class="verdict" data-verdict data-code="{code}">Flagged</p>'
        "<p data-why>This lot drew one bid, its market has at least {floor} comparable "
        "lot "
        "results, and fewer than {rate}% of them drew one bid.</p>"
        '<p class="muted" data-note hidden></p>'
        "<div data-record><h4>The record the rule writes</h4><dl "
        'class="record">{record}</dl>'
        '<p class="muted">The source_url above points at a notice that does not exist. '
        "A real flag links to the notice on TED.</p></div>"
        "<p data-none hidden>No flag record is written.</p>"
        "</div></div>",
        floor=rule.SEGMENT_FLOOR,
        rate=rule.SINGLE_BID_RATE_PERCENT,
        size=first.size,
        singles=first.singles,
        pct=percent(first.singles, first.size),
        code=code,
        record=record,
    )


def flag(ctx: Context) -> Html:
    facts = ctx.facts
    hypothesis = facts.hypothesis

    top = band(
        "dark",
        fill(
            '<p class="kicker">A flag, explained</p>'
            "<h1>What one flag says, and how to check it</h1>"
            '<p class="lede">A flag is a statistical anomaly matched against a '
            "documented "
            "indicator. It has ordinary explanations, and the record carries the "
            "numbers "
            "needed to disagree with it.</p>"
            '<p><span class="synthetic">Synthetic</span> Every record on this page was '
            "produced by running the real rule over an invented market. No notice "
            "named "
            "here exists.</p>",
        ),
    )

    the_rule = band(
        "light",
        fill(
            "<h2>The rule</h2>"
            '<div class="prose"><p>{claim}</p>'
            '<p class="muted">From <a href="{hypothesis}">the hypothesis file</a>. In '
            "code, a lot is flagged when all three hold:</p></div>"
            '<ol class="plain">'
            "<li>it drew exactly {single} bid;</li>"
            "<li>its market, the buyer's country and the lot's CPV division, holds at "
            "least {floor} lot results in the dataset;</li>"
            "<li>fewer than {rate}% of the lots in that market drew one bid.</li></ol>"
            '<p class="muted">Thresholds are read from <code>{module}</code>, '
            "version {version}.</p>",
            claim=hypothesis.claim,
            hypothesis=ctx.link(hypothesis.path),
            single=rule.SINGLE_BID,
            floor=rule.SEGMENT_FLOOR,
            rate=rule.SINGLE_BID_RATE_PERCENT,
            module="serenata/classify/single_bid_in_segment.py",
            version=rule.RULE_VERSION,
        ),
    )

    cases = demo.cases()
    case_rows = [
        (
            case.label,
            case.size,
            case.singles,
            f"{percent(case.singles, case.size)}%",
            len(case.flags),
        )
        for case in cases
    ]
    playground = band(
        "dark",
        fill(
            "<h2>Move the numbers</h2>"
            '<p class="muted">Change a value and the verdict follows. This mirrors the '
            "rule for reading; a test holds it to the Python.</p>"
            "{explorer}"
            "<h3>The same rule on five invented markets</h3>"
            "{table}"
            '<p class="muted">Each row is the actual output of '
            "<code>single_bid_in_segment.flags</code> on that market. Where a market "
            "has a flag, every lot in it that drew one bid gets one.</p>",
            explorer=_explorer(ctx),
            table=data_table(
                ["Market", "Lot results", "One-bid lots", "Rate", "Flags returned"],
                case_rows,
                numeric={1, 2, 3, 4},
            ),
        ),
    )

    steps = [
        "Open the source link. It points at the notice's XML on TED, the document the "
        "pipeline read.",
        "Find the lot result and its bid count in that XML, and confirm the count is "
        "the one on the row.",
        "Recompute the market rate from the two counts on the row: lots that drew one "
        "bid, divided by lot results. The row also names the last publication day the "
        "dataset covered, which bounds the corrections it could have known about.",
        "Check TED for a corrigendum or a withdrawal of that notice. A flag on a "
        "notice "
        "that no longer stands is void.",
        "Walk the ordinary explanations below and note each as checked or not.",
    ]
    checking = band(
        "light",
        fill(
            "<h2>How a flag is checked</h2>"
            '<ol class="plain">{steps}</ol>'
            '<div class="parts">'
            "<div><h3>This flag is wrong if</h3>{wrong}</div>"
            "<div><h3>What the design predicts will go wrong</h3>{anticipated}"
            '<p class="muted">Predicted, not observed. No flag has completed '
            "verification.</p></div></div>",
            steps=join(fill("<li>{s}</li>", s=step) for step in steps),
            wrong=bullets(hypothesis.wrong_if),
            anticipated=bullets(hypothesis.anticipated),
        ),
    )

    sens = hypothesis.sensitivity
    rate_index = sens.percents.index(rule.SINGLE_BID_RATE_PERCENT)
    floor_row = next(row for row in sens.rows if row.floor == rule.SEGMENT_FLOOR)
    later = next((p for p in sens.percents if p > rule.SINGLE_BID_RATE_PERCENT), None)
    same = (
        later is not None
        and floor_row.flags[rate_index] == floor_row.flags[sens.percents.index(later)]
    )
    thresholds = band(
        "dark",
        fill(
            "<h2>How the two thresholds were chosen</h2>"
            '<div class="prose"><p>Both were set after measuring, on the archive '
            "above. "
            "The table shows how many flags each pair would have produced. The "
            "outlined "
            "cell is the pair the rule uses.</p>{same}</div>"
            "{table}"
            '<p class="muted">Measured on {days} publication days, so a different or '
            "larger archive will move these counts.</p>",
            same=fill(
                "<p>At a floor of {floor}, a limit of {a}% and a limit of {b}% give "
                "the "
                "same number of flags, so this measurement cannot tell them apart. The "
                "lower, more conservative limit is used.</p>",
                floor=rule.SEGMENT_FLOOR,
                a=rule.SINGLE_BID_RATE_PERCENT,
                b=later,
            )
            if same
            else "",
            table=heat_table(
                sens, floor=rule.SEGMENT_FLOOR, rate=rule.SINGLE_BID_RATE_PERCENT
            ),
            days=len(hypothesis.measurement.package_ids),
        ),
    )

    disclaimer = band(
        "light",
        fill(
            '<div class="callout"><h3>Read this before reading any flag</h3>'
            "<p>A flag is a statistical anomaly with possible innocent explanations. "
            "It is not an allegation about anyone. A single bid is lawful and common, "
            "and usually means one supplier wanted the work.</p>"
            "<p>When a flag is wrong, or the notice behind it is corrected or "
            "withdrawn, "
            "the project corrects it in place with a dated note. "
            '<a href="{policy}">The corrections policy</a> says how.</p></div>',
            policy=ctx.link("docs/corrections-policy.md"),
        ),
    )
    return join([top, the_rule, playground, checking, thresholds, disclaimer])


def _needs_counsel(gates: tuple[Gate, ...]) -> Html:
    """Which open items wait on counsel, worked out from what each one says it needs."""
    numbers = [g.number for g in gates if "counsel" in plain(g.needs).lower()]
    if not numbers:
        return Html("")
    listed = (
        ", ".join(numbers[:-1]) + (" and " if len(numbers) > 1 else "") + numbers[-1]
    )
    return fill(
        'Items {listed} need counsel; <a href="counsel.html">the page for counsel</a> '
        "shows their questions.",
        listed=listed,
    )


def status(ctx: Context) -> Html:
    facts = ctx.facts
    m = facts.hypothesis.measurement

    top = band(
        "dark",
        fill(
            '<p class="kicker">Status</p>'
            "<h1>Where it stands, and what blocks release</h1>"
            '<div class="callout"><p>{release}</p></div>',
            release=facts.release,
        ),
    )

    milestones = band(
        "light",
        fill(
            "<h2>Milestones</h2>{table}"
            '<p class="muted">From the <a href="{readme}">README</a>, which is kept '
            "current before this page is.</p>",
            table=data_table(
                ["#", "Milestone", "Status"],
                [(ms.number, ms.title, ms.status) for ms in facts.milestones],
            ),
            readme=ctx.link("README.md"),
        ),
    )

    gates = band(
        "dark",
        fill(
            "<h2>Open right now</h2>{table}"
            '<p class="muted">From <a href="{open_work}">open-work.md</a>. {counsel}'
            "</p>",
            table=data_table(
                ["#", "Item", "What it needs"],
                [
                    (
                        fill('<a href="{u}">{n}</a>', u=g.url, n=g.number),
                        g.title,
                        g.needs,
                    )
                    for g in facts.gates
                ],
            ),
            open_work=ctx.link("docs/open-work.md"),
            counsel=_needs_counsel(facts.gates),
        ),
    )

    provenance = band(
        "light",
        fill(
            "<h2>What every number here was measured on</h2>"
            '<div class="prose"><p>{notices} notices from {n} TED daily packages, '
            "measured {date}. Each figure on this site is read from a document "
            "generated "
            "from these packages, or from the hypothesis file that names them, and the "
            "site refuses to build when a document stops agreeing with "
            "another.</p></div>"
            "{table}",
            notices=thousands(m.notices),
            n=len(facts.corpus.packages),
            date=m.measured_on.isoformat(),
            table=data_table(
                ["Package", "SHA-256"],
                [
                    (p.identifier, Html(f"<code>{p.sha256}</code>"))
                    for p in facts.corpus.packages
                ],
            ),
        ),
    )

    issues = band(
        "dark",
        fill(
            "<h2>Known issues</h2>"
            '<p class="muted">What the pipeline does not do, or does incompletely, '
            "from "
            '<a href="{known}">known-issues.md</a>.</p>{items}',
            known=ctx.link("docs/known-issues.md"),
            items=bullets(
                [
                    fill('<a href="{u}">{t}</a>', u=issue.url, t=issue.title)
                    for issue in facts.issues
                ]
            ),
        ),
    )
    return join([top, milestones, gates, provenance, issues])
