"""Every fact a page states, and the document it was read from.

`read_facts` is the only place the site learns anything about the project. Each
reader below names its source document, extracts a small number of things from
it, and raises `SourceError` when the document has changed shape. Pages receive
the result and never open a file themselves, so "where did this number come
from" always has the same answer: one function in this module.

Numbers come from three kinds of source, in decreasing order of trust:

- **Executable**: constants imported from the code that enforces them (the
  personal-data drop list, the rule's thresholds).
- **Generated**: reports produced from the archive and reproducible byte for
  byte (`docs/dataset-shape.md`, `docs/dropped-fields.md`), and the structured
  measurement block in a hypothesis file.
- **Written**: prose and tables a person maintains (the milestone table, the
  counsel instructions). These are quoted, never paraphrased into a second copy.

Where a written figure can be cross-checked against a computed one, `read_facts`
does so and refuses to continue if they disagree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from serenata.parse import personal_data
from serenata.site.docs import BRANCH, REPOSITORY, Doc, SourceError, plain, slug
from serenata.site.figures import percent
from serenata.site.markup import Html

HYPOTHESIS = "docs/hypotheses/single_bid_in_segment.md"
COUNSEL_README = "docs/counsel/README.md"
ADR_RETENTION = "docs/adr/0010-raw-archive-retention.md"

#: Characters the documents use that this source spells out, so that no file in
#: the package carries a look-alike a reviewer could not tell from a hyphen.
CHECK_MARK = "\u2705"
EM_DASH = "\u2014"


@dataclass(frozen=True)
class Measurement:
    """The structured block in a hypothesis file: one rule version, one corpus."""

    rule_version: int
    measured_on: date
    period_start: date
    period_end: date
    package_ids: tuple[str, ...]
    notices: int
    population: int
    population_notices: int
    covered: int
    uncovered: int
    flagged: int
    flagged_notices: int


@dataclass(frozen=True)
class BaseRate:
    """Figures the hypothesis states in prose, read where it states them."""

    single_bids: int
    single_bid_percent: str
    segments: int
    segment_low_percent: str
    segment_high_percent: str
    segment_median_percent: str


@dataclass(frozen=True)
class SensitivityRow:
    floor: int
    segments: int
    covered: int
    flags: tuple[int, ...]


@dataclass(frozen=True)
class Sensitivity:
    """Flags produced at each pair of parameters, on the measured corpus."""

    percents: tuple[int, ...]
    rows: tuple[SensitivityRow, ...]


@dataclass(frozen=True)
class Hypothesis:
    path: str
    status: str
    claim: Html
    wrong_if: tuple[Html, ...]
    anticipated: tuple[Html, ...]
    measurement: Measurement
    base_rate: BaseRate
    sensitivity: Sensitivity


@dataclass(frozen=True)
class Package:
    identifier: str
    sha256: str


@dataclass(frozen=True)
class Corpus:
    """What the reports measured: which archive, how large."""

    notices: int
    packages: tuple[Package, ...]
    tables: tuple[tuple[str, int], ...]

    @property
    def rows(self) -> int:
        return sum(count for _, count in self.tables)


@dataclass(frozen=True)
class Leak:
    """One retained column, and how many of its values are shaped like an address."""

    column: str
    address_shaped: int
    person_shaped: int


@dataclass(frozen=True)
class Dropped:
    leaves_dropped: int
    leaves_total: int
    percent: str
    by_rule: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class DropRules:
    """The personal-data drop list, imported from the code that enforces it."""

    segments: tuple[str, ...]
    suffixes: tuple[str, ...]
    natural_person_indicator: str
    natural_person_prefixes: tuple[str, ...]


@dataclass(frozen=True)
class Stage:
    name: str
    reads: Html
    writes: Html
    networked: Html
    built: bool
    note: str


@dataclass(frozen=True)
class Milestone:
    number: str
    title: Html
    status: Html


@dataclass(frozen=True)
class Gate:
    """One line of "open right now": what is unresolved and what it needs."""

    number: str
    title: Html
    needs: Html
    url: str


@dataclass(frozen=True)
class Issue:
    title: str
    url: str


@dataclass(frozen=True)
class Question:
    label: str
    text: str


@dataclass(frozen=True)
class Row:
    """A table row of inline HTML, for tables the site quotes rather than reads."""

    cells: tuple[Html, ...]


@dataclass(frozen=True)
class Grid:
    header: tuple[str, ...]
    rows: tuple[Row, ...]


@dataclass(frozen=True)
class Instruction:
    """One counsel instruction: the question, its status, and what it would change."""

    path: str
    url: str
    number: str
    title: str
    status: str
    summary: Html
    parts: tuple[tuple[str, str], ...]
    questions: tuple[Question, ...]
    holds: tuple[tuple[Html, Html], ...]
    limits: tuple[Html, ...]
    options: tuple[Html, ...]
    consequences: Grid
    fields: int
    unresolved: int


@dataclass(frozen=True)
class CounselGate:
    """One row of the counsel index: a gate, its instruction and where it stands."""

    number: str
    title: str
    status: str
    drafted: bool


@dataclass(frozen=True)
class Facts:
    hypothesis: Hypothesis
    corpus: Corpus
    leaks: tuple[Leak, ...]
    dropped: Dropped
    drop_rules: DropRules
    stages: tuple[Stage, ...]
    milestones: tuple[Milestone, ...]
    gates: tuple[Gate, ...]
    issues: tuple[Issue, ...]
    instructions: tuple[Instruction, ...]
    counsel_gates: tuple[CounselGate, ...]
    retention_status: str
    natural_person_present: str
    natural_person_absent: str
    lineage: tuple[Html, ...]
    independence: Html
    attribution: Html
    release: Html
    counsel_notice: Html


def _int(text: str, doc: Doc, what: str) -> int:
    try:
        return int(text.replace(",", "").strip())
    except ValueError:
        raise doc.fail(f"expected a whole number for {what}, found {text!r}") from None


def read_hypothesis(repo: Path) -> Hypothesis:
    doc = Doc.read(repo, HYPOTHESIS)
    status = doc.find(r"(?m)^Status:[ \t]*(\S+)").group(1)

    metadata = doc.toml(doc.section("Measurement metadata"))
    raw = metadata.get("measurement")
    if not isinstance(raw, dict):
        raise doc.fail("has no [measurement] table")
    try:
        measurement = Measurement(
            rule_version=int(raw["rule_version"]),
            measured_on=raw["measured_on"],
            period_start=raw["period_start"],
            period_end=raw["period_end"],
            package_ids=tuple(raw["package_ids"]),
            notices=int(raw["notice_count"]),
            population=int(raw["population_count"]),
            population_notices=int(raw["population_notice_count"]),
            covered=int(raw["covered_count"]),
            uncovered=int(raw["uncovered_count"]),
            flagged=int(raw["flagged_count"]),
            flagged_notices=int(raw["flagged_notice_count"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise doc.fail(f"has an unusable measurement block: {error!r}") from error
    if measurement.covered + measurement.uncovered != measurement.population:
        raise doc.fail("covered and uncovered do not add up to the population")

    base = doc.section("Base rate")
    rate_section, _, profile = base.partition("**Anticipated false-positive profile.**")
    if not profile:
        raise doc.fail("has no 'Anticipated false-positive profile' in its base rate")

    single = doc.find(
        r"\*\*Single bid anywhere in it\*\*:\s*([\d,]+),\s*or\s*([\d.]+)%", rate_section
    )
    segments = doc.find(
        r"\*\*Segments with at least 50 lot results\*\*:\s*(\d+),\s*covering\s*"
        r"[\d,]+\s*of\s*the\s*population\.\s*Their\s*single-bid\s*rates\s*run\s*from\s*"
        r"([\d.]+)%\s*to\s*([\d.]+)%,\s*median\s*([\d.]+)%",
        rate_section,
    )
    base_rate = BaseRate(
        single_bids=_int(single.group(1), doc, "single bids"),
        single_bid_percent=single.group(2),
        segments=_int(segments.group(1), doc, "segments"),
        segment_low_percent=segments.group(2),
        segment_high_percent=segments.group(3),
        segment_median_percent=segments.group(4),
    )

    table = doc.table(rate_section, after="Sensitivity, same dataset")
    percents = tuple(
        _int(match.group(1), doc, "a threshold")
        for cell in table.header[3:]
        if (match := re.search(r"(\d+)%", cell))
    )
    if len(percents) != len(table.header) - 3:
        raise doc.fail("has a sensitivity table whose thresholds are not percentages")
    rows = tuple(
        SensitivityRow(
            floor=_int(row[0], doc, "a floor"),
            segments=_int(row[1], doc, "a segment count"),
            covered=_int(row[2], doc, "a coverage count"),
            flags=tuple(_int(cell, doc, "a flag count") for cell in row[3:]),
        )
        for row in table.rows
    )

    # The written percentages must agree with the counts the block carries. A
    # hypothesis edited in one place and not the other would otherwise put two
    # different coverage figures on two different pages.
    written = doc.find(r"\(([\d.]+)%\)\s*are in eligible segments", rate_section)
    computed = percent(measurement.covered, measurement.population)
    if written.group(1) != computed:
        raise doc.fail(
            f"states coverage of {written.group(1)}% but its counts give {computed}%"
        )

    return Hypothesis(
        path=HYPOTHESIS,
        status=status,
        claim=doc.inline(doc.paragraph(doc.section("Claim"))),
        wrong_if=tuple(
            doc.inline(item) for item in doc.items(doc.section("This flag is wrong if"))
        ),
        anticipated=tuple(doc.inline(item) for item in doc.items(profile)),
        measurement=measurement,
        base_rate=base_rate,
        sensitivity=Sensitivity(percents=percents, rows=rows),
    )


def read_corpus(repo: Path) -> tuple[Corpus, tuple[Leak, ...]]:
    doc = Doc.read(repo, "docs/dataset-shape.md")
    measured = doc.section("What was measured")
    notices = _int(
        doc.find(r"\*\*([\d,]+) notices\*\*", measured).group(1), doc, "notices"
    )
    packages = tuple(
        Package(match.group(1), match.group(2))
        for match in re.finditer(
            r"`(\d{9})\.tar\.gz`\s*.\s*`sha256:([0-9a-f]{64})`", measured
        )
    )
    if not packages:
        raise doc.fail("lists no packages under 'What was measured'")

    rows = doc.table(doc.section("Rows"))
    tables = tuple(
        (plain(row[0]), _int(row[1], doc, "a row count")) for row in rows.rows
    )

    leaks = doc.table(doc.section("Address-shaped values"))
    return (
        Corpus(notices=notices, packages=packages, tables=tables),
        tuple(
            Leak(
                plain(row[0]),
                _int(row[1], doc, "a count"),
                _int(row[2], doc, "a count"),
            )
            for row in leaks.rows
        ),
    )


def read_dropped(repo: Path) -> Dropped:
    doc = Doc.read(repo, "docs/dropped-fields.md")
    total = doc.find(
        r"\*\*([\d,]+) of ([\d,]+) leaf elements \(([\d.]+)%\) are dropped"
    )
    by_rule = doc.table(doc.section("By the rule that rejected them"))
    return Dropped(
        leaves_dropped=_int(total.group(1), doc, "dropped leaves"),
        leaves_total=_int(total.group(2), doc, "total leaves"),
        percent=total.group(3),
        by_rule=tuple(
            (plain(row[0]), _int(row[1], doc, "a count")) for row in by_rule.rows
        ),
    )


def read_drop_rules() -> DropRules:
    return DropRules(
        segments=tuple(sorted(personal_data.DROPPED_SEGMENTS)),
        suffixes=tuple(personal_data.DROPPED_SUFFIXES),
        natural_person_indicator=personal_data.NATURAL_PERSON_INDICATOR,
        natural_person_prefixes=tuple(personal_data.IDENTIFYING_ORGANISATION_PREFIXES),
    )


def read_stages(repo: Path) -> tuple[Stage, ...]:
    doc = Doc.read(repo, "docs/architecture.md")
    table = doc.table(doc.section("The shape"))
    stages = []
    for row in table.rows:
        mark = row[4].split(" ", 1)
        stages.append(
            Stage(
                name=plain(row[0]),
                reads=doc.inline(row[1]),
                writes=doc.inline(row[2]),
                networked=doc.inline(row[3]),
                built=mark[0] == CHECK_MARK,
                note=mark[1] if len(mark) > 1 else "",
            )
        )
    return tuple(stages)


def read_milestones(repo: Path) -> tuple[Milestone, ...]:
    doc = Doc.read(repo, "README.md")
    table = doc.table(doc.section("Status"))
    return tuple(
        Milestone(plain(row[0]), doc.inline(row[1]), doc.inline(row[2]))
        for row in table.rows
    )


def read_gates(repo: Path) -> tuple[Gate, ...]:
    doc = Doc.read(repo, "docs/open-work.md")
    table = doc.table(doc.section("Open right now"))
    gates = []
    for row in table.rows:
        anchor = doc.find(r"\((#[^)]+)\)", row[0]).group(1)
        gates.append(
            Gate(
                number=plain(row[0]),
                title=doc.inline(row[1]),
                needs=doc.inline(row[2]),
                url=doc.href(anchor),
            )
        )
    return tuple(gates)


def read_issues(repo: Path) -> tuple[Issue, ...]:
    doc = Doc.read(repo, "docs/known-issues.md")
    return tuple(
        Issue(plain(title), doc.href(f"#{slug(title)}")) for title in doc.headings(2)
    )


def _first_sentence(text: str) -> str:
    """Up to and including the first question mark, else the first full stop."""
    text = plain(text)
    for mark in ("?", "."):
        cut = text.find(mark)
        if cut != -1:
            return text[: cut + 1].strip()
    return text.strip()


def _questions(doc: Doc) -> tuple[Question, ...]:
    found: dict[str, Question] = {}
    for item in doc.items(doc.text):
        match = re.match(r"\*\*([AB]\d+)\.\s*(.*?)\*\*\s*(.*)$", item)
        if not match:
            continue
        label, bold, rest = match.groups()
        text = bold.rstrip(".") if bold else _first_sentence(rest)
        found[label] = Question(label, text)
    for _, level, heading in doc.outline():
        match = re.match(r"([AB]\d+)\.\s*(.+)$", heading)
        if level == 3 and match:
            found[match.group(1)] = Question(match.group(1), plain(match.group(2)))
    if not found:
        raise doc.fail("has no questions labelled A1, B1 and so on")
    return tuple(
        found[label]
        for label in sorted(found, key=lambda label: (label[0], int(label[1:])))
    )


def _parts(doc: Doc) -> tuple[tuple[str, str], ...]:
    parts = {}
    for _, _, heading in doc.outline():
        match = re.match(r"Part ([AB])\s*(?:\u2014|:|-)\s*(.+)$", heading)
        if match:
            parts[match.group(1)] = plain(match.group(2))
    if set(parts) != {"A", "B"}:
        raise doc.fail("expected headings for Part A and Part B")
    return tuple(sorted(parts.items()))


def _holds(doc: Doc) -> tuple[tuple[Html, Html], ...]:
    """The facts an instruction says the project holds, as (label, statement)."""
    try:
        body = doc.section("What the project holds and does")
    except SourceError:
        return ()
    held = []
    for item in doc.items(body):
        match = re.match(r"\*\*(.+?)\*\*\s*(.*)$", item)
        if match:
            held.append(
                (doc.inline(match.group(1).rstrip(".")), doc.inline(match.group(2)))
            )
    return tuple(held)


def _limits(doc: Doc) -> tuple[Html, ...]:
    try:
        body = doc.section("What the project holds")
    except SourceError:
        return ()
    if "Limits of these numbers" not in body:
        return ()
    _, _, tail = body.partition("Limits of these numbers")
    return tuple(doc.inline(item) for item in doc.items(tail))


def _options(doc: Doc) -> tuple[Html, ...]:
    try:
        body = doc.section("Options")
    except SourceError:
        return ()
    return tuple(doc.inline(item) for item in doc.items(body, marker=r"\d+\."))


def read_instruction(repo: Path, path: str) -> Instruction:
    doc = Doc.read(repo, path)
    title = re.sub(r"^Counsel instruction\s*(?:\u2014|:|-)\s*", "", doc.title())
    title = title[:1].upper() + title[1:]
    number = doc.find(r"open-work #(\d+)").group(1)

    summary = None
    for name in ("The one-paragraph version", "The short version"):
        try:
            summary = doc.paragraph(doc.section(name))
            break
        except SourceError:
            continue
    if summary is None:
        raise doc.fail(
            "has neither 'The one-paragraph version' nor 'The short version'"
        )

    consequences = doc.table(doc.section("What each answer changes in the code"))
    record = doc.table(doc.section("Decision record"))
    return Instruction(
        path=path,
        url=doc.url,
        number=number,
        title=title,
        status=doc.find(r"\*\*(Status: [^*]+)\*\*").group(1),
        summary=doc.inline(summary),
        parts=_parts(doc),
        questions=_questions(doc),
        holds=_holds(doc),
        limits=_limits(doc),
        options=_options(doc),
        consequences=Grid(
            header=consequences.header,
            rows=tuple(
                Row(tuple(doc.inline(cell) for cell in row))
                for row in consequences.rows
            ),
        ),
        fields=len(record.rows),
        unresolved=sum(1 for row in record.rows if "UNRESOLVED" in row[1]),
    )


def read_counsel(repo: Path) -> tuple[tuple[Instruction, ...], tuple[CounselGate, ...]]:
    index = Doc.read(repo, COUNSEL_README)
    table = index.table(index.text)
    instructions = []
    gates = []
    for row in table.rows:
        link = re.search(r"\]\(([0-9]+-[a-z0-9-]+\.md)\)", row[1])
        if link:
            instructions.append(read_instruction(repo, f"docs/counsel/{link.group(1)}"))
        gates.append(
            CounselGate(
                number=plain(row[0]),
                title=plain(row[1]),
                status=plain(row[2]),
                drafted=link is not None,
            )
        )
    if not instructions:
        raise index.fail("links to no counsel instruction")
    return tuple(instructions), tuple(gates)


def _indicator_split(
    repo: Path, instructions: tuple[Instruction, ...]
) -> re.Match[str]:
    """Where an instruction says how often the natural-person indicator is present."""
    pattern = re.compile(
        r"\*\*present on ([\d.]+)%\*\*\s*and\s*\*\*absent on ([\d.]+)%\*\*"
    )
    for instruction in instructions:
        found = pattern.search(Doc.read(repo, instruction.path).text)
        if found:
            return found
    raise SourceError(
        "no counsel instruction states how often the natural-person indicator "
        "is present and absent"
    )


def read_statements(repo: Path) -> tuple[tuple[Html, ...], Html, Html]:
    """The lineage, the independence statement and the source attribution.

    Read from the README because the README is where they were approved, and a
    disclaimer with two copies is one that gets updated in one place.
    """
    doc = Doc.read(repo, "README.md")
    paragraphs = doc.paragraphs(doc.section("Lineage"))
    independence = next(
        (p for p in paragraphs if p.startswith("**This is an independent project.**")),
        None,
    )
    if independence is None:
        raise doc.fail(
            "has no 'This is an independent project.' statement under Lineage"
        )
    # The last sentence points at "the lineage above", which is a README layout
    # and means nothing on another page.
    independence = independence.split(" The lineage above")[0]
    lineage = tuple(
        doc.inline(p)
        for p in paragraphs
        if not p.startswith("**This is an independent")
    )
    attribution = doc.paragraph(doc.section("Data source and attribution"))
    return lineage, doc.inline(independence), doc.inline(attribution)


def _paragraph_starting(doc: Doc, body: str, start: str) -> str:
    for paragraph in doc.paragraphs(body):
        if paragraph.startswith(start):
            return paragraph
    raise doc.fail(f"has no paragraph starting {start!r}")


def read_notices(repo: Path) -> tuple[Html, Html]:
    """The two paragraphs the site repeats word for word: release and caveat.

    The README says no flag has been published and why. The counsel index says
    its instructions are questionnaires and authorize nothing. Both are the
    statements a reader must not meet a paraphrase of.
    """
    readme = Doc.read(repo, "README.md")
    release = _paragraph_starting(
        readme, readme.section("Status"), "**No flag has been published"
    )
    index = Doc.read(repo, COUNSEL_README)
    caveat = _paragraph_starting(index, index.text, "**These are questionnaires")
    return readme.inline(release), index.inline(caveat)


def read_facts(repo: Path) -> Facts:
    """Everything the pages state, or `SourceError` naming what changed shape."""
    corpus, leaks = read_corpus(repo)
    hypothesis = read_hypothesis(repo)
    if hypothesis.measurement.notices != corpus.notices:
        raise SourceError(
            f"{HYPOTHESIS} measured {hypothesis.measurement.notices} notices but "
            f"docs/dataset-shape.md reports {corpus.notices}; they describe "
            "different corpora"
        )
    if (
        tuple(p.identifier for p in corpus.packages)
        != hypothesis.measurement.package_ids
    ):
        raise SourceError(
            f"{HYPOTHESIS} and docs/dataset-shape.md list different packages"
        )

    instructions, counsel_gates = read_counsel(repo)
    retention = Doc.read(repo, ADR_RETENTION)
    indicator = _indicator_split(repo, instructions)
    lineage, independence, attribution = read_statements(repo)
    release, counsel_notice = read_notices(repo)
    return Facts(
        hypothesis=hypothesis,
        corpus=corpus,
        leaks=leaks,
        dropped=read_dropped(repo),
        drop_rules=read_drop_rules(),
        stages=read_stages(repo),
        milestones=read_milestones(repo),
        gates=read_gates(repo),
        issues=read_issues(repo),
        instructions=instructions,
        counsel_gates=counsel_gates,
        retention_status=retention.find(r"(?m)^- Status: ([^\n]+)$")
        .group(1)
        .replace(f" {EM_DASH} ", ": "),
        natural_person_present=indicator.group(1),
        natural_person_absent=indicator.group(2),
        lineage=lineage,
        independence=independence,
        attribution=attribution,
        release=release,
        counsel_notice=counsel_notice,
    )


__all__ = ["BRANCH", "REPOSITORY", "Facts", "read_facts"]
