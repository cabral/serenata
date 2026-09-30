"""The site, and the promises it makes about itself.

[ADR-0014](../docs/adr/0014-a-site-that-cannot-show-a-flag.md) decided that the
site shows the project and cannot show a flag. Nothing about a page's look can
be tested here, and nothing about it needs to be: what has to hold is that the
page cannot say something the documents do not, cannot be handed a dataset,
cannot reach a third party, and cannot describe a rule the code has stopped
implementing. Each class below holds one of those.

The last of them matters most for a project whose whole argument is that a
stranger can check its work. A page that explains the rule with a sentence the
code no longer matches would be the one place the project is unverifiable.
"""

from __future__ import annotations

import ast
import html
import inspect
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar
from urllib.parse import urlparse

import pytest

from serenata.classify import single_bid_in_segment as rule
from serenata.site import __main__ as cli
from serenata.site import demo, layout
from serenata.site.build import SPECS, build_site, render_site
from serenata.site.charts import Bar, bar_chart, heat_table
from serenata.site.docs import Doc, SourceError, slug
from serenata.site.facts import Gate, read_facts
from serenata.site.figures import percent, ratio, thousands
from serenata.site.markup import Html, esc, fill, join
from serenata.site.pages import _needs_counsel

from .test_constraints import TestFlagsAreNotAccusations, module_name, python_files
from .test_docs import slug as reference_slug

REPO = Path(__file__).resolve().parent.parent
SITE_PACKAGE = REPO / "serenata" / "site"
STATIC = SITE_PACKAGE / "static"


# -- helpers ---------------------------------------------------------------


def copy_repo(destination: Path) -> Path:
    """A copy of the working tree small enough to break on purpose.

    Everything the site reads, and nothing it does not: no history, no
    environment, and only the committed sample of ``data/``, so a laptop with
    gigabytes of fetched archive does not copy them for a test.
    """
    skipped = {".git", ".venv", "site", "__pycache__", "htmlcov"}

    def ignore(directory: str, names: list[str]) -> set[str]:
        found = {n for n in names if n in skipped or n.endswith("_cache")}
        found |= {n for n in names if n.startswith(".coverage")}
        if Path(directory) == REPO / "data":
            found |= {n for n in names if n != "sample"}
        return found

    shutil.copytree(REPO, destination, ignore=ignore)
    return destination


def edit(repo: Path, path: str, old: str, new: str) -> None:
    """Change a document, insisting the text being changed was there.

    Without the assertion a reworded source would turn every mutation test into
    a test that changes nothing and passes.
    """
    target = repo / path
    text = target.read_text(encoding="utf-8")
    assert old in text, f"{path} no longer contains {old!r}; update this test"
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


VOID = frozenset(
    {"meta", "link", "br", "hr", "img", "input", "area", "base", "col", "source"}
)


class Audit(HTMLParser):
    """Everything a check needs to know about a page, gathered in one pass."""

    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.problems: list[str] = []
        self.ids: list[str] = []
        self.links: list[str] = []
        self.resources: list[str] = []
        self.text: list[str] = []
        self.title = ""
        self.h1 = 0
        self.current = 0
        self.language = ""
        self.inputs_outside_label: list[str] = []
        self.scripts_with_source = 0
        self._label_depth = 0
        self._silent = 0
        self._in_title = False
        self.feed(source)
        self.close()
        if self.stack:
            self.problems.append(f"unclosed at end: {self.stack}")

    def _record(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        found = {name: value or "" for name, value in attrs}
        if "id" in found:
            self.ids.append(found["id"])
        if tag == "a" and "href" in found:
            self.links.append(found["href"])
        if tag in {"script", "img", "iframe"} and "src" in found:
            self.resources.append(found["src"])
            self.scripts_with_source += tag == "script"
        if tag == "link" and "href" in found:
            self.resources.append(found["href"])
        if tag == "html":
            self.language = found.get("lang", "")
        if tag == "h1":
            self.h1 += 1
        if found.get("aria-current") == "page":
            self.current += 1
        if tag == "input" and not self._label_depth:
            self.inputs_outside_label.append(found.get("name", "?"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record(tag, attrs)
        if tag in VOID:
            return
        self.stack.append(tag)
        self._label_depth += tag == "label"
        self._silent += tag in {"style", "script"}
        self._in_title = tag == "title"

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self._record(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"</{tag}> closes {self.stack[-1:]}")
            return
        self.stack.pop()
        self._label_depth -= tag == "label"
        self._silent -= tag in {"style", "script"}
        self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif not self._silent:
            self.text.append(data)

    @property
    def visible(self) -> str:
        return " ".join(" ".join(self.text).split())


@pytest.fixture(scope="module")
def pages() -> dict[str, str]:
    return render_site(REPO)


@pytest.fixture(scope="module")
def audits(pages: dict[str, str]) -> dict[str, Audit]:
    return {name: Audit(source) for name, source in pages.items()}


@pytest.fixture(scope="module")
def facts():  # type: ignore[no-untyped-def]
    return read_facts(REPO)


# -- the small pieces --------------------------------------------------------


class TestMarkupEscapesByDefault:
    """The failure to prevent is a document injecting markup into a page."""

    def test_plain_text_is_escaped(self) -> None:
        assert esc('<script>alert(1)</script> & "x"') == (
            "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;x&quot;"
        )

    def test_html_passes_through_untouched(self) -> None:
        assert esc(Html("<b>kept</b>")) == "<b>kept</b>"

    def test_a_template_is_trusted_and_its_values_are_not(self) -> None:
        out = fill("<p>{a}</p>{b}", a="<i>", b=Html("<hr>"))
        assert out == "<p>&lt;i&gt;</p><hr>"

    def test_join_escapes_each_part(self) -> None:
        assert join(["<", Html("<br>")], sep="|") == "&lt;|<br>"


class TestFiguresAreIntegerArithmetic:
    def test_percentages_round_half_up(self) -> None:
        assert percent(4283, 8132) == "52.7"
        assert percent(96, 4283, 2) == "2.24"
        assert percent(1, 8, 0) == "13"
        assert percent(1, 8, 1) == "12.5"
        assert percent(0, 5) == "0.0"

    def test_a_zero_whole_has_no_percentage(self) -> None:
        with pytest.raises(ValueError, match="positive whole"):
            percent(1, 0)

    def test_ratios_are_truncated_decimals_between_zero_and_one(self) -> None:
        assert ratio(1, 3) == "0.333"
        assert ratio(0, 5) == "0.000"
        assert ratio(2, 2) == "1"
        assert ratio(3, 2) == "1"

    def test_thousands(self) -> None:
        assert thousands(632068) == "632,068"


# -- reading documents ---------------------------------------------------------

DOCUMENT = """\
# Title

Intro paragraph
wrapped over two lines.

## Alpha

Alpha body.

```
## not a heading
```

### Alpha child

Child body.

## Beta

- first item
  continues here
- second item

Text after a blank line.

1. one
2. two

| A | B |
|---|--:|
| x | 1 |
| y | 2 |

```toml
[t]
n = 3
```

## Gamma
"""


@pytest.fixture
def doc(tmp_path: Path) -> Doc:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "sibling.md").write_text("sibling", encoding="utf-8")
    (tmp_path / "docs" / "d.md").write_text(DOCUMENT, encoding="utf-8")
    return Doc.read(tmp_path, "docs/d.md")


class TestReadingADocument:
    def test_a_section_runs_to_the_next_heading_of_its_level(self, doc: Doc) -> None:
        body = doc.section("Alpha")
        assert "Alpha body." in body
        assert "Child body." in body
        assert "first item" not in body

    def test_a_heading_inside_a_code_fence_is_not_a_heading(self, doc: Doc) -> None:
        assert doc.headings(2) == ["Alpha", "Beta", "Gamma"]

    def test_a_heading_is_found_by_its_prefix(self, doc: Doc) -> None:
        assert doc.section("Be").startswith("- first item")

    def test_a_missing_heading_names_the_document(self, doc: Doc) -> None:
        with pytest.raises(SourceError, match=r"docs/d\.md.*Delta"):
            doc.section("Delta")

    def test_a_missing_document_says_it_is_gone(self, tmp_path: Path) -> None:
        with pytest.raises(SourceError, match="is gone"):
            Doc.read(tmp_path, "docs/none.md")

    def test_title_and_paragraphs(self, doc: Doc) -> None:
        assert doc.title() == "Title"
        assert doc.paragraph(doc.text.split("\n\n", 1)[1]) == (
            "Intro paragraph wrapped over two lines."
        )
        assert doc.paragraphs("a\nb\n\nc")[1] == "c"

    def test_a_document_without_a_paragraph_is_refused(self, doc: Doc) -> None:
        with pytest.raises(SourceError, match="paragraph"):
            doc.paragraph("\n\n")

    def test_bullets_unwrap_and_stop_at_a_blank_line(self, doc: Doc) -> None:
        assert doc.items(doc.section("Beta")) == [
            "first item continues here",
            "second item",
        ]

    def test_numbered_items(self, doc: Doc) -> None:
        assert doc.items(doc.section("Beta"), marker=r"\d+\.") == ["one", "two"]

    def test_a_table(self, doc: Doc) -> None:
        table = doc.table(doc.section("Beta"))
        assert table.header == ("A", "B")
        assert table.rows == (("x", "1"), ("y", "2"))

    def test_a_table_can_be_read_after_a_marker(self, doc: Doc) -> None:
        assert doc.table(doc.text, after="1. one").rows[0] == ("x", "1")
        with pytest.raises(SourceError, match="before a table"):
            doc.table(doc.text, after="absent marker")

    def test_no_table_is_refused(self, doc: Doc) -> None:
        with pytest.raises(SourceError, match="table"):
            doc.table(doc.section("Gamma"))

    def test_a_ragged_table_is_refused(self, doc: Doc) -> None:
        with pytest.raises(SourceError, match="differ in width"):
            doc.table("| a | b |\n|---|---|\n| 1 |\n| 2 | 3 |")

    def test_one_toml_block(self, doc: Doc) -> None:
        assert doc.toml(doc.section("Beta")) == {"t": {"n": 3}}
        with pytest.raises(SourceError, match="found 0"):
            doc.toml("nothing")
        with pytest.raises(SourceError, match="does not parse"):
            doc.toml("```toml\nnot = = toml\n```\n")

    def test_find_refuses_a_pattern_that_is_gone(self, doc: Doc) -> None:
        assert doc.find(r"n = (\d)").group(1) == "3"
        with pytest.raises(SourceError, match="expected text matching"):
            doc.find(r"no such text")

    def test_a_document_with_no_title_is_refused(self, tmp_path: Path) -> None:
        (tmp_path / "x.md").write_text("no heading", encoding="utf-8")
        with pytest.raises(SourceError, match="level-one"):
            Doc.read(tmp_path, "x.md").title()


class TestInlineMarkdown:
    def test_marks_become_elements(self, doc: Doc) -> None:
        out = doc.inline("a `code` and **bold** and *em* here")
        assert (
            out == "a <code>code</code> and <strong>bold</strong> and <em>em</em> here"
        )

    def test_text_is_escaped_including_inside_marks(self, doc: Doc) -> None:
        out = doc.inline("<b>x</b> **<i>y</i>** `<z>`")
        assert "<b>" not in out and "<i>" not in out and "<z>" not in out
        assert "&lt;b&gt;" in out

    def test_marks_nest(self, doc: Doc) -> None:
        assert doc.inline("**a `b` c**") == "<strong>a <code>b</code> c</strong>"

    def test_a_relative_link_points_at_the_repository(self, doc: Doc) -> None:
        out = doc.inline("[s](sibling.md#part)")
        assert out == (
            '<a href="https://github.com/cabral/serenata/blob/main/docs/sibling.md#part">s</a>'
        )

    def test_a_link_to_a_directory_uses_tree(self, doc: Doc) -> None:
        assert "/tree/main/docs" in doc.inline("[d](.)")

    def test_an_anchor_alone_stays_in_the_same_document(self, doc: Doc) -> None:
        assert "docs/d.md#alpha" in doc.inline("[a](#alpha)")

    def test_an_absolute_link_is_left_alone(self, doc: Doc) -> None:
        assert 'href="https://ted.europa.eu"' in doc.inline(
            "[t](https://ted.europa.eu)"
        )

    def test_a_link_to_nothing_is_refused(self, doc: Doc) -> None:
        with pytest.raises(SourceError, match="does not exist"):
            doc.inline("[x](missing.md)")

    def test_a_link_out_of_the_repository_is_refused(self, doc: Doc) -> None:
        with pytest.raises(SourceError, match="does not exist"):
            doc.inline("[x](../../etc/passwd)")

    def test_a_reader_and_github_agree_on_anchors(self) -> None:
        for heading in (
            "Part A — processing (answer this first)",
            "`not_applicable` is never derived",
        ):
            assert slug(heading) == reference_slug(heading)


# -- the facts agree with their sources ------------------------------------------


class TestFactsAreReadFromTheirSources:
    def test_the_real_documents_read_cleanly(self, facts) -> None:  # type: ignore[no-untyped-def]
        hypothesis = facts.hypothesis
        assert hypothesis.status == "building"
        assert hypothesis.measurement.rule_version == rule.RULE_VERSION
        assert len(facts.stages) == 5 and len(facts.milestones) == 6
        assert facts.instructions and facts.gates and facts.issues

    def test_the_measurement_is_the_rules_current_version(self, facts) -> None:  # type: ignore[no-untyped-def]
        # A site quoting last version's numbers as this version's would be the
        # quiet kind of wrong the hypothesis metadata exists to prevent.
        assert facts.hypothesis.measurement.rule_version == rule.RULE_VERSION

    def test_the_sums_are_the_documents_own(self, facts) -> None:  # type: ignore[no-untyped-def]
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        assert str(sum(leak.address_shaped for leak in facts.leaks)) in readme
        assert str(sum(leak.person_shaped for leak in facts.leaks)) in readme
        assert thousands(facts.corpus.rows) in readme

    def test_the_thresholds_the_pages_use_are_in_the_sensitivity_table(
        self, facts
    ) -> None:  # type: ignore[no-untyped-def]
        sensitivity = facts.hypothesis.sensitivity
        assert rule.SINGLE_BID_RATE_PERCENT in sensitivity.percents
        assert rule.SEGMENT_FLOOR in {row.floor for row in sensitivity.rows}

    def test_the_drop_rules_are_the_codes(self, facts) -> None:  # type: ignore[no-untyped-def]
        from serenata.parse import personal_data

        assert set(facts.drop_rules.segments) == set(personal_data.DROPPED_SEGMENTS)
        assert facts.drop_rules.suffixes == personal_data.DROPPED_SUFFIXES

    def test_every_counsel_instruction_is_found_from_the_index(self, facts) -> None:  # type: ignore[no-untyped-def]
        drafted = [gate for gate in facts.counsel_gates if gate.drafted]
        assert len(drafted) == len(facts.instructions)
        for instruction in facts.instructions:
            assert instruction.questions and instruction.parts
            assert (
                instruction.fields == instruction.unresolved
                or instruction.unresolved <= instruction.fields
            )


class TestABrokenDocumentStopsTheBuild:
    """The site refuses rather than keeping an old number or dropping a section."""

    @pytest.fixture
    def repo(self, tmp_path: Path) -> Path:
        return copy_repo(tmp_path / "repo")

    def test_a_copy_of_the_repository_builds(self, repo: Path) -> None:
        # The control for every test below: if the copy alone failed, each of
        # them would pass for the wrong reason.
        assert set(render_site(repo)) == {spec.filename for spec in SPECS}

    def test_written_coverage_that_disagrees_with_the_counts(self, repo: Path) -> None:
        edit(
            repo,
            "docs/hypotheses/single_bid_in_segment.md",
            "(52.7%) are in eligible",
            "(53.0%) are in eligible",
        )
        with pytest.raises(SourceError, match=r"states coverage of 53\.0%"):
            render_site(repo)

    def test_two_documents_measuring_different_corpora(self, repo: Path) -> None:
        edit(
            repo,
            "docs/hypotheses/single_bid_in_segment.md",
            "notice_count = 19180",
            "notice_count = 19181",
        )
        with pytest.raises(SourceError, match="different corpora"):
            render_site(repo)

    def test_two_documents_naming_different_packages(self, repo: Path) -> None:
        edit(repo, "docs/dataset-shape.md", "`202600052.tar.gz`", "`202600053.tar.gz`")
        with pytest.raises(SourceError, match="different packages"):
            render_site(repo)

    def test_a_renamed_heading(self, repo: Path) -> None:
        edit(repo, "docs/dataset-shape.md", "## Rows", "## How many rows")
        with pytest.raises(SourceError, match=r"dataset-shape\.md.*Rows"):
            render_site(repo)

    def test_a_reworded_counsel_section(self, repo: Path) -> None:
        edit(
            repo,
            "docs/counsel/11-natural-person-status.md",
            "## Decision record",
            "## Outcome",
        )
        with pytest.raises(SourceError, match="Decision record"):
            render_site(repo)

    def test_a_link_to_a_file_that_is_gone(self, repo: Path) -> None:
        edit(
            repo,
            "docs/counsel/11-natural-person-status.md",
            "(../adr/0006-absence-is-recorded-not-collapsed.md)",
            "(../adr/0006-gone.md)",
        )
        with pytest.raises(SourceError, match="does not exist"):
            render_site(repo)

    def test_a_missing_indicator_split(self, repo: Path) -> None:
        edit(
            repo,
            "docs/counsel/11-natural-person-status.md",
            "**present on 3.4%** and **absent on 96.6%**",
            "present on 3.4% and absent on 96.6%",
        )
        with pytest.raises(SourceError, match="natural-person indicator"):
            render_site(repo)

    def test_a_missing_independence_statement(self, repo: Path) -> None:
        edit(
            repo, "README.md", "**This is an independent project.**", "**Independent.**"
        )
        with pytest.raises(SourceError, match="independent project"):
            render_site(repo)

    def test_the_command_reports_it_and_exits_nonzero(
        self,
        repo: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        edit(repo, "docs/dataset-shape.md", "## Rows", "## Elsewhere")
        monkeypatch.setattr(cli, "default_repo", lambda: repo)
        assert cli.main(["--out", str(repo / "out")]) == 1
        assert "cannot be built" in capsys.readouterr().err
        assert not (repo / "out").exists()


# -- the guarantees ----------------------------------------------------------------


class TestTheSiteCannotPublishFlags:
    """ADR-0014: it reads documents, never data, and shows only invented flags."""

    #: Names the package may import from the rest of `serenata`. Constants and
    #: record types only: nothing that reads a file, a dataset or the network.
    ALLOWED_FROM: ClassVar[dict[str, set[str]]] = {
        "serenata.classify": {"RULES", "single_bid_in_segment"},
        "serenata.classify.records": {"Flag", "LotOutcome"},
        "serenata.parse": {"personal_data"},
    }
    NEVER: ClassVar[set[str]] = {
        "pyarrow",
        "duckdb",
        "httpx",
        "socket",
        "requests",
        "urllib.request",
        "http",
    }

    def imports(self, path: Path) -> list[tuple[str, str]]:
        found = []
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                found.extend((alias.name, "") for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                found.extend((node.module, alias.name) for alias in node.names)
        return found

    @pytest.mark.parametrize(
        "path", python_files("site"), ids=lambda p: module_name(Path(p))
    )
    def test_it_imports_no_reader_of_data(self, path: Path) -> None:
        stdlib = sys.stdlib_module_names
        for module, name in self.imports(path):
            top = module.split(".")[0]
            assert module not in self.NEVER and top not in self.NEVER, (
                f"{path.name} imports {module}: the site must not read data "
                "or reach a network"
            )
            if top == "serenata":
                if module.startswith("serenata.site"):
                    continue
                assert name in self.ALLOWED_FROM.get(module, set()), (
                    f"{path.name} imports {name} from {module}, which is outside "
                    "what ADR-0014 lets the site read"
                )
            else:
                assert top in stdlib, (
                    f"{path.name} imports {top}, which is not the standard library"
                )

    def test_the_allowance_does_not_include_anything_that_reads_data(self) -> None:
        # The guard above is only as good as its list.
        allowed = {name for names in self.ALLOWED_FROM.values() for name in names}
        assert not allowed & {
            "read_outcomes",
            "write_flags",
            "classify_dataset",
            "default_flag_root",
        }

    def test_the_builder_takes_no_dataset(self) -> None:
        assert list(inspect.signature(build_site).parameters) == ["repo", "out"]
        assert list(inspect.signature(render_site).parameters) == ["repo"]

    def test_the_command_takes_only_an_output_directory(self) -> None:
        source = (SITE_PACKAGE / "__main__.py").read_text(encoding="utf-8")
        assert re.findall(r'add_argument\(\s*"(--?[a-z-]+)"', source) == ["--out"]

    def test_a_build_reads_markdown_and_its_own_assets_and_nothing_else(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        read: list[Path] = []
        original = Path.read_text

        def spy(self: Path, *args: object, **kwargs: object) -> str:
            read.append(self)
            return original(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(Path, "read_text", spy)
        render_site(REPO)
        assert len(read) > 10, (
            "the spy saw almost nothing; it is not watching the build"
        )
        strangers = [p for p in read if p.suffix != ".md" and STATIC not in p.parents]
        assert not strangers, f"the build read {strangers}"
        assert not [p for p in read if REPO / "data" in p.parents]

    def test_every_ted_address_on_a_page_is_synthetic(
        self, pages: dict[str, str]
    ) -> None:
        addresses = [
            address
            for source in pages.values()
            for address in re.findall(r"ted\.europa\.eu/en/notice/([^\s\"<]+)", source)
        ]
        assert addresses, "the flag page should show the shape of a source address"
        assert all(demo.SYNTHETIC in address for address in addresses), addresses

    def test_the_invented_market_cannot_be_mistaken_for_a_real_one(self) -> None:
        for flag in demo.cases()[0].flags:
            for value in (
                flag.source_publication_id,
                flag.source_notice_id,
                flag.lot_ref,
            ):
                assert value.startswith(demo.SYNTHETIC)
            assert (flag.segment_country, flag.segment_cpv_division) == ("XX", "00")

    def test_every_page_says_no_flag_has_been_published(
        self, audits: dict[str, Audit]
    ) -> None:
        for name, audit in audits.items():
            assert "No flag has been published" in audit.visible, name

    def test_every_page_asks_not_to_be_indexed(self, pages: dict[str, str]) -> None:
        for name, source in pages.items():
            assert '<meta name="robots" content="noindex">' in source, name

    def test_the_synthetic_label_is_on_the_page_that_shows_a_record(
        self, audits: dict[str, Audit]
    ) -> None:
        assert "Synthetic" in audits["flag.html"].visible


class TestTheBuildIsReproducible:
    """Constraint 4 for the one output a stranger will actually open."""

    def test_two_builds_are_byte_identical(self, tmp_path: Path) -> None:
        first = build_site(REPO, tmp_path / "a")
        second = build_site(REPO, tmp_path / "b")
        assert [p.name for p in first] == [p.name for p in second]
        for a, b in zip(first, second, strict=True):
            assert a.read_bytes() == b.read_bytes(), a.name

    def test_it_writes_exactly_the_pages_in_the_navigation(
        self, tmp_path: Path
    ) -> None:
        written = build_site(REPO, tmp_path)
        assert [p.name for p in written] == sorted(name for name, _ in layout.PAGES)

    def test_line_endings_and_encoding_are_fixed(self, tmp_path: Path) -> None:
        for path in build_site(REPO, tmp_path):
            data = path.read_bytes()
            assert b"\r" not in data
            data.decode("utf-8")

    def test_the_command_writes_where_asked_and_lists_the_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        assert cli.main(["--out", str(tmp_path / "pages")]) == 0
        out = capsys.readouterr().out
        assert all(name in out for name, _ in layout.PAGES)
        assert (tmp_path / "pages" / "index.html").is_file()


class TestNoPageReachesAThirdParty:
    """A project arguing about lawful basis cannot load a font from a stranger."""

    HOSTS: ClassVar[set[str]] = {
        "github.com",
        "ted.europa.eu",
        "eur-lex.europa.eu",
        "creativecommons.org",
    }

    def test_nothing_is_fetched_when_a_page_opens(
        self, audits: dict[str, Audit], pages: dict[str, str]
    ) -> None:
        for name, audit in audits.items():
            assert audit.resources == [], f"{name} loads {audit.resources}"
            assert audit.scripts_with_source == 0
            assert "@import" not in pages[name]
            assert not re.search(r"url\(\s*['\"]?(https?:)?//", pages[name]), name

    def test_links_leave_only_for_places_the_pages_name(
        self, audits: dict[str, Audit]
    ) -> None:
        hosts = {
            urlparse(link).hostname
            for audit in audits.values()
            for link in audit.links
            if link.startswith(("http://", "https://"))
        }
        assert hosts, "no page links out; the check is looking at nothing"
        assert hosts <= self.HOSTS, hosts - self.HOSTS

    def test_no_link_uses_plain_http(self, audits: dict[str, Audit]) -> None:
        assert not [
            link
            for audit in audits.values()
            for link in audit.links
            if link.startswith("http://")
        ]

    def test_the_font_stack_names_no_download(self) -> None:
        css = (STATIC / "site.css").read_text(encoding="utf-8")
        assert "@font-face" not in css and "fonts.googleapis" not in css


class TestPagesAreWellFormed:
    def test_tags_open_and_close_in_order(self, audits: dict[str, Audit]) -> None:
        for name, audit in audits.items():
            assert audit.problems == [], f"{name}: {audit.problems}"

    def test_each_page_has_a_language_a_title_and_one_main_heading(
        self, audits: dict[str, Audit]
    ) -> None:
        for name, audit in audits.items():
            assert audit.language == "en", name
            assert audit.title.strip().endswith("| Serenata Europa"), name
            assert audit.h1 == 1, name

    def test_navigation_marks_the_current_page_once(
        self, audits: dict[str, Audit]
    ) -> None:
        assert {audit.current for audit in audits.values()} == {1}

    def test_ids_are_unique_and_anchors_resolve(self, audits: dict[str, Audit]) -> None:
        for name, audit in audits.items():
            assert len(audit.ids) == len(set(audit.ids)), name
            for link in audit.links:
                if link.startswith("#"):
                    assert link[1:] in audit.ids, f"{name}: {link}"

    def test_links_between_pages_resolve(self, audits: dict[str, Audit]) -> None:
        names = set(audits)
        for name, audit in audits.items():
            for link in audit.links:
                if "://" in link or link.startswith(("#", "mailto:")):
                    continue
                assert link.split("#")[0] in names, f"{name}: {link}"

    def test_links_work_under_a_subpath(self, pages: dict[str, str]) -> None:
        # GitHub Pages serves a repository at /<name>/ (ADR-0015), so a link that
        # starts with a slash would leave the site. Every internal one is relative.
        for name, source in pages.items():
            assert not re.search(r"""(?:href|src|action)=["']/(?!/)""", source), name

    def test_every_field_has_a_label(self, audits: dict[str, Audit]) -> None:
        for name, audit in audits.items():
            assert audit.inputs_outside_label == [], name

    def test_no_markdown_reaches_a_reader(self, audits: dict[str, Audit]) -> None:
        for name, audit in audits.items():
            assert "**" not in audit.visible, name
            assert "](" not in audit.visible, name
            assert "`" not in audit.visible, name

    def test_repository_links_target_the_default_branch(
        self, audits: dict[str, Audit]
    ) -> None:
        repo_links = [
            link
            for audit in audits.values()
            for link in audit.links
            if link.startswith("https://github.com/cabral/serenata/")
        ]
        assert repo_links
        for link in repo_links:
            match = re.match(
                r"https://github\.com/cabral/serenata/(blob|tree)/main/([^#]*)", link
            )
            if match:
                assert (REPO / match.group(2)).exists(), link


class TestPagesUseTheProjectsVocabulary:
    """Constraint 3, on the surface a flagged buyer's lawyer would read first."""

    #: The communication skill's list of words that do not appear about findings.
    ALSO = re.compile(
        r"\b(suspect\w*|suspicio\w*|scandal\w*|rigged|crusade|watchdog|anti-corruption)\b",
        re.I,
    )

    def test_no_accusatory_word_is_on_a_page(self, audits: dict[str, Audit]) -> None:
        for name, audit in audits.items():
            found = TestFlagsAreNotAccusations.FORBIDDEN.findall(audit.visible)
            assert not found, f"{name}: {found}"

    def test_no_word_the_project_does_not_use_about_findings(
        self, audits: dict[str, Audit]
    ) -> None:
        for name, audit in audits.items():
            match = self.ALSO.search(audit.visible)
            assert match is None, f"{name}: {match and match.group(0)}"

    def test_the_word_scan_can_fail(self) -> None:
        assert self.ALSO.search("a suspicious contract")
        assert TestFlagsAreNotAccusations.FORBIDDEN.search("a fraudulent buyer")

    def test_the_pages_never_claim_artificial_intelligence(
        self, audits: dict[str, Audit]
    ) -> None:
        # Constraint 5 says the core pipeline uses no language model, and the
        # reference site's tagline is the one sentence that would say otherwise.
        for name, audit in audits.items():
            assert not re.search(r"artificial intelligence|\bAI\b", audit.visible), name


class TestWhatThePagesClaimIsWhatTheDocumentsSay:
    """A sentence typed into a template has a second home. These are its anchors."""

    def squash(self, text: str) -> str:
        return " ".join(text.replace("*", "").split()).lower()

    CLAIMS = (
        (
            "index.html",
            "no empirical false-positive rate has been measured",
            "docs/known-issues.md",
            "no empirical false-positive rate has been measured",
        ),
        (
            "index.html",
            "no flag has completed the verification protocol",
            "docs/known-issues.md",
            "none has completed the verification protocol",
        ),
        (
            "index.html",
            "none of it is published",
            "README.md",
            "no flag has been published",
        ),
        (
            "counsel.html",
            "structural suppression is not anonymisation",
            "docs/adr/0010-raw-archive-retention.md",
            "structural suppression is not anonymisation",
        ),
        (
            "flag.html",
            "a single bid is lawful and common",
            "docs/hypotheses/single_bid_in_segment.md",
            "a single bid is lawful, common",
        ),
        (
            "how-it-works.html",
            "does not fully meet this",
            "docs/open-work.md",
            "is not fully met",
        ),
        (
            "flag.html",
            "no flag has completed verification",
            "docs/known-issues.md",
            "none has completed the verification protocol",
        ),
    )

    @pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: f"{c[0]}:{c[1][:30]}")
    def test_a_claim_stands_in_both_places(
        self, claim: tuple[str, str, str, str], audits: dict[str, Audit]
    ) -> None:
        page, said, document, source = claim
        assert said in self.squash(audits[page].visible)
        text = (REPO / document).read_text(encoding="utf-8")
        assert source in self.squash(text), (
            f"{document} no longer says {source!r}; {page} still says {said!r}. "
            "Decide which is true before either is edited to match."
        )


# -- the rule explainer ----------------------------------------------------------------


class TestTheDemoIsTheRealRule:
    def test_the_example_market_produces_a_flag_for_each_single_bid(self) -> None:
        first = demo.cases()[0]
        assert (first.size, first.singles, len(first.flags)) == (60, 6, 6)

    def test_each_way_of_staying_silent_is_shown_being_silent(self) -> None:
        silent = [case for case in demo.cases()[1:4] if not case.flags]
        assert len(silent) == 3

    def test_the_comparison_is_strict_at_the_limit(self) -> None:
        on, under = demo.cases()[3], demo.cases()[4]
        assert on.singles * 100 == rule.SINGLE_BID_RATE_PERCENT * on.size
        assert not on.flags
        assert len(under.flags) == under.singles

    def test_the_example_flag_is_the_rules_own_output(self) -> None:
        flag = demo.example_flag()
        assert (flag.rule, flag.rule_version) == (rule.RULE, rule.RULE_VERSION)
        assert (flag.segment_size, flag.segment_single_bids) == (60, 6)

    @pytest.mark.parametrize("size", [1, 10, 49, 50, 51, 99, 100, 101, 200])
    def test_the_verdict_agrees_with_the_rule_for_every_single_bid_count(
        self, size: int
    ) -> None:
        for singles in range(1, size + 1):
            outcomes = demo.market(size, singles)
            flagged = {flag.source_notice_id for flag in rule.flags(outcomes)}
            first = outcomes[0].source_notice_id
            assert (first in flagged) == (
                demo.verdict(1, size, singles) == "flagged"
            ), (
                size,
                singles,
            )
            if singles < size:
                assert outcomes[-1].source_notice_id not in flagged
                assert (
                    demo.verdict(demo.COMPETITIVE_BIDS, size, singles) == "not-single"
                )

    def test_the_four_outcomes_all_occur(self) -> None:
        seen = {
            demo.verdict(b, n, s)
            for b in (1, 3)
            for n in (10, 60, 200)
            for s in (1, 5, 30)
        }
        assert seen == {"flagged", "not-single", "below-floor", "ordinary"}

    def test_the_market_marks_every_identifier_synthetic(self) -> None:
        for outcome in demo.market(5, 2):
            assert outcome.source_notice_id.startswith(demo.SYNTHETIC)
            assert outcome.country == "XX"

    def test_the_example_is_refused_if_the_rule_stops_producing_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(demo, "cases", lambda: (demo.Case("x", 1, 1, ()),))
        with pytest.raises(AssertionError, match="no longer produces"):
            demo.example_flag()


NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="node is not installed; CI runs this")
class TestTheScriptIsHeldToThePython:
    """The page lets a reader move the numbers. Its script must be the rule."""

    GRID: ClassVar[list[tuple[int, int, int]]] = [
        (bids, size, singles)
        for bids in (0, 1, 2, 7)
        for size in (0, 1, 10, 49, 50, 51, 99, 100, 101, 200, 1000)
        for singles in (
            0,
            1,
            2,
            7,
            14,
            15,
            16,
            29,
            30,
            49,
            50,
            149,
            150,
            151,
            200,
            1000,
        )
    ]

    def run_node(self, program: str, payload: object) -> object:
        result = subprocess.run(
            [NODE or "node", "-e", program],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=60,
            check=True,
        )
        return json.loads(result.stdout)

    def test_the_verdict_matches_over_the_whole_grid(self) -> None:
        program = (
            f"const s = require({json.dumps(str(STATIC / 'site.js'))});"
            "const grid = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
            "console.log(JSON.stringify(grid.map(([b, n, k]) => "
            f"s.verdict(b, n, k, {rule.SEGMENT_FLOOR}, "
            f"{rule.SINGLE_BID_RATE_PERCENT}))));"
        )
        from_node = self.run_node(program, self.GRID)
        from_python = [demo.verdict(*point) for point in self.GRID]
        assert from_node == from_python
        assert set(from_python) == {
            "flagged",
            "not-single",
            "below-floor",
            "ordinary",
        }, "the grid must reach every outcome or agreement proves nothing"

    def test_the_percentage_matches_over_a_grid(self) -> None:
        pairs = [
            (part, whole) for whole in range(1, 260) for part in range(0, whole + 1, 7)
        ]
        program = (
            f"const s = require({json.dumps(str(STATIC / 'site.js'))});"
            "const pairs = JSON.parse(require('fs').readFileSync(0, 'utf8'));"
            "console.log(JSON.stringify(pairs.map(([p, w]) => s.percent(p, w))));"
        )
        assert self.run_node(program, pairs) == [percent(p, w) for p, w in pairs]

    def test_the_page_hands_the_script_the_rules_own_thresholds(
        self, pages: dict[str, str]
    ) -> None:
        assert (
            f'data-floor="{rule.SEGMENT_FLOOR}" '
            f'data-rate="{rule.SINGLE_BID_RATE_PERCENT}"' in pages["flag.html"]
        )


class TestTheChartsTellTheTruth:
    def test_a_bar_is_sized_from_integers_and_labelled_with_its_value(self) -> None:
        out = bar_chart([Bar("a", 100), Bar("b", 50)], value_header="n")
        assert "--r:1" in out and "--r:0.500" in out
        assert "100" in out and "Table view" in out

    def test_labels_are_escaped(self) -> None:
        out = bar_chart([Bar("<script>x</script>", 3)], value_header="n")
        assert "<script>" not in out

    def test_a_part_is_drawn_first_and_a_zero_part_is_omitted(self) -> None:
        both = bar_chart(
            [Bar("a", 10, part=4)], value_header="n", part_label="p", rest_label="r"
        )
        assert both.index("flex:4") < both.index("flex:6")
        assert '<ul class="legend">' in both
        none = bar_chart(
            [Bar("a", 10, part=0)], value_header="n", part_label="p", rest_label="r"
        )
        assert "flex:0" not in none

    def test_a_single_series_has_no_legend(self) -> None:
        assert "legend" not in bar_chart([Bar("a", 1)], value_header="n")

    def test_the_table_twin_carries_every_value(self) -> None:
        out = bar_chart(
            [Bar("a", 1234, part=5)],
            value_header="all",
            part_header="some",
            part_label="p",
            rest_label="r",
        )
        assert "1,234" in out and "some" in out

    def test_exactly_one_cell_is_the_rules_own_pair(self, facts) -> None:  # type: ignore[no-untyped-def]
        table = heat_table(
            facts.hypothesis.sensitivity,
            floor=rule.SEGMENT_FLOOR,
            rate=rule.SINGLE_BID_RATE_PERCENT,
        )
        assert table.count("chosen") == 1
        assert "96</td>" in table.split("chosen")[1][:20]


class TestEachPageSaysWhatItIsFor:
    def test_overview_states_the_measured_figures(
        self, facts, audits: dict[str, Audit]
    ) -> None:  # type: ignore[no-untyped-def]
        text = audits["index.html"].visible
        m = facts.hypothesis.measurement
        for figure in (
            thousands(m.notices),
            thousands(m.population),
            thousands(m.covered),
            str(m.flagged),
        ):
            assert figure in text
        assert "independent project" in text

    def test_how_it_works_shows_every_stage_and_marks_the_unbuilt_one(
        self, facts, audits: dict[str, Audit]
    ) -> None:  # type: ignore[no-untyped-def]
        text = audits["how-it-works.html"].visible.lower()
        for stage in facts.stages:
            assert stage.name in text
        assert "not built" in text

    def test_the_flag_page_shows_the_record_and_every_edge_case(
        self, audits: dict[str, Audit]
    ) -> None:
        text = audits["flag.html"].visible
        for case in demo.cases():
            assert case.label in text
        assert "source_publication_id" in text and "SYNTHETIC-PUBLICATION-001" in text

    def test_status_lists_every_milestone_gate_and_package(
        self, facts, audits: dict[str, Audit]
    ) -> None:  # type: ignore[no-untyped-def]
        text = audits["status.html"].visible
        for milestone in facts.milestones:
            assert milestone.number in text
        for gate in facts.gates:
            assert f"{gate.number}" in text
        for package in facts.corpus.packages:
            assert package.sha256 in text

    def test_counsel_carries_every_question_and_every_decision_status(
        self, facts, pages: dict[str, str], audits: dict[str, Audit]
    ) -> None:  # type: ignore[no-untyped-def]
        source = pages["counsel.html"]
        for instruction in facts.instructions:
            for question in instruction.questions:
                assert html.escape(question.text) in source, question.label
            assert (
                instruction.status.removeprefix("Status: ").split(".")[0]
                in audits["counsel.html"].visible
            )
        assert "data-print" in source

    def test_counsel_states_counts_and_no_values(
        self, facts, audits: dict[str, Audit]
    ) -> None:  # type: ignore[no-untyped-def]
        text = audits["counsel.html"].visible
        assert str(sum(leak.address_shaped for leak in facts.leaks)) in text
        assert thousands(facts.dropped.leaves_dropped) in text
        # A count of something shaped like an address is not the address.
        assert not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text)


class TestWhichItemsWaitOnCounsel:
    """Worked out from what each open item says it needs, not typed."""

    def gate(self, number: str, needs: str) -> Gate:
        return Gate(number, Html(number), Html(needs), "https://example.invalid")

    def test_none_says_nothing(self) -> None:
        assert _needs_counsel((self.gate("3", "a package"),)) == ""

    def test_one_is_named_alone(self) -> None:
        out = _needs_counsel((self.gate("3", "a package"), self.gate("11", "counsel")))
        assert "Items 11 need counsel" in out

    def test_several_are_listed_in_order(self) -> None:
        gates = (
            self.gate("11", "counsel review"),
            self.gate("14", "counsel, then a rebuild"),
            self.gate("15", "Counsel"),
        )
        assert "Items 11, 14 and 15 need counsel" in _needs_counsel(gates)

    def test_the_status_page_names_them(self, audits: dict[str, Audit]) -> None:
        assert "need counsel" in audits["status.html"].visible


class TestTheFrameIsNotSkippable:
    def test_the_strip_is_sticky_and_precedes_the_navigation(
        self, pages: dict[str, str]
    ) -> None:
        css = (STATIC / "site.css").read_text(encoding="utf-8")
        assert re.search(r"\.strip\s*\{[^}]*position:\s*sticky", css)
        for source in pages.values():
            assert source.index('class="strip"') < source.index("<header")

    def test_the_printed_page_keeps_the_strip(self) -> None:
        css = (STATIC / "site.css").read_text(encoding="utf-8")
        printing = css[css.index("@media print") :]
        hidden = re.search(r"([^{}]*)\{\s*display:\s*none\s*!important", printing)
        assert hidden is not None, "the print rules no longer hide anything"
        assert ".strip" not in hidden.group(1)
        assert ".strip {" in printing

    def test_the_static_assets_are_found_by_name(self) -> None:
        assert layout.static("site.css").startswith("/*")
        assert "verdict" in layout.static("site.js")

    def test_scripts_are_only_on_the_pages_that_use_them(
        self, pages: dict[str, str]
    ) -> None:
        with_script = {name for name, source in pages.items() if "<script>" in source}
        assert with_script == {spec.filename for spec in SPECS if spec.script}

    def test_the_specifications_and_the_navigation_agree(self) -> None:
        assert [spec.filename for spec in SPECS] == [name for name, _ in layout.PAGES]

    def test_a_navigation_that_disagrees_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(layout, "PAGES", layout.PAGES[:-1])
        with pytest.raises(AssertionError, match="disagree"):
            render_site(REPO)
