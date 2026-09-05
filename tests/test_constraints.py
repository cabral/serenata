"""The hard constraints, made executable.

`CLAUDE.md` states six constraints that bind every change in this repository.
Three of them are legal rather than stylistic, and all six were, until this
file existed, enforced by a reviewer remembering to check. That is a weak place
to keep a legal commitment.

Each test below enforces one constraint and says why the constraint exists.
Some pass vacuously today — the classifier gates have no classifiers to check.
That is deliberate: a gate written before the code it governs is binding from
the first commit of that code, and a gate written afterwards is a retrofit
argued against work someone has already done.

What these cannot do is in `docs/open-work.md`: whether a hypothesis is
genuinely falsifiable, whether a schema field can carry a person's name, and
whether a flag's framing is fair are human judgements. These gates make the
mechanical constraints unbreakable so that attention is free for those.
"""

from __future__ import annotations

import ast
import re
import tomllib
from datetime import date
from importlib.metadata import distributions
from pathlib import Path
from typing import ClassVar

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "serenata"
DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"

#: Everything downstream of fetch: it transforms, classifies, or reports on
#: archived input, and must be reproducible from that input alone (constraint
#: 4). ``survey`` is here because the data model cites its numbers, so a report
#: that changed between runs would be worse than no report.
OFFLINE_STAGES = ("parse", "normalise", "classify", "survey")


def python_files(*within: str) -> list[Path]:
    """Every module under ``serenata/``, or under the named subpackages."""
    roots = [PACKAGE_ROOT / name for name in within] if within else [PACKAGE_ROOT]
    return sorted(path for root in roots for path in root.rglob("*.py"))


def module_name(path: Path) -> str:
    """``serenata.fetch.client`` for the module at that path."""
    relative = path.relative_to(PACKAGE_ROOT.parent).with_suffix("")
    parts = [part for part in relative.parts if part != "__init__"]
    return ".".join(parts)


def imported_modules(path: Path) -> set[str]:
    """Every module name imported by ``path``, as written.

    Both halves of an import are recorded: ``import a.b`` and ``from a.b
    import c`` both yield ``a.b``, and the top-level ``a`` is included so a
    denylist can match either granularity.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
                found.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
            found.add(node.module.split(".")[0])
    return found


def called_attributes(path: Path) -> set[str]:
    """Dotted names of attributes referenced in ``path`` (``datetime.now``)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            found.add(f"{node.value.id}.{node.attr}")
        elif isinstance(node, ast.Name):
            found.add(node.id)
    return found


def string_literals(path: Path) -> list[str]:
    """Every string literal in ``path``, excluding docstrings and comments.

    Comments and docstrings explain the code to maintainers; only literals can
    reach a reader of the project's output, which is what constraint 3 governs.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


class TestNetworkIsolation:
    """Constraint: fetching is the only networked stage.

    Every other stage must be reproducible from archived inputs. A network call
    in parse, normalise or classify would make a flag depend on what a remote
    service happened to return that day, which breaks the project's core promise
    that a stranger can rerun the code and get the same rows.
    """

    NETWORK_MODULES = frozenset(
        {"httpx", "socket", "requests", "urllib.request", "http.client", "ftplib"}
    )

    @pytest.mark.parametrize("path", python_files(), ids=lambda p: module_name(Path(p)))
    def test_only_fetch_may_reach_the_network(self, path: Path) -> None:
        offending = self.NETWORK_MODULES & imported_modules(path)
        if module_name(path).startswith("serenata.fetch"):
            return
        assert not offending, (
            f"{module_name(path)} imports {sorted(offending)}. Fetch is the only "
            "networked stage; everything downstream runs against archived files."
        )

    def test_fetch_is_where_the_network_actually_lives(self) -> None:
        # Guards the gate above against becoming vacuous: if the network code
        # moved and nothing imported httpx any more, the parametrised test
        # would still pass while enforcing nothing.
        users = {
            module_name(path)
            for path in python_files()
            if self.NETWORK_MODULES & imported_modules(path)
        }
        assert users, "no module imports a network library; has fetch moved?"
        assert all(name.startswith("serenata.fetch") for name in users)


class TestStructuredFieldsOnly:
    """Constraint: core classifiers read structured eForms/TED fields only.

    No NLP, no LLM calls, no fuzzy matching. If someone asks why a row was
    flagged, the answer must be a rule over named fields — not "the matcher
    decided they were similar". Fuzzy libraries are on the list precisely
    because entity resolution will be tempted to reach for them; that work
    belongs in a documented pipeline stage, not inside a classifier.
    """

    FORBIDDEN = frozenset(
        {
            "transformers",
            "spacy",
            "nltk",
            "gensim",
            "openai",
            "anthropic",
            "langchain",
            "llama_cpp",
            "sentence_transformers",
            "fuzzywuzzy",
            "rapidfuzz",
            "Levenshtein",
            "difflib",
            "sklearn",
            "torch",
        }
    )

    @pytest.mark.parametrize("path", python_files(), ids=lambda p: module_name(Path(p)))
    def test_no_free_text_or_model_libraries(self, path: Path) -> None:
        offending = self.FORBIDDEN & imported_modules(path)
        assert not offending, (
            f"{module_name(path)} imports {sorted(offending)}. Core classifiers "
            "read structured fields only (CLAUDE.md constraint 5)."
        )


class TestDeterminism:
    """Constraint: same input data and same code produce the same bytes.

    Scoped to the stages downstream of fetch. Fetch itself is allowed a clock —
    it records when a package was retrieved, which is provenance, not output —
    and ADR-0002 states that nothing derived may depend on that timestamp.
    """

    FORBIDDEN = frozenset(
        {
            "datetime.now",
            "datetime.today",
            "datetime.utcnow",
            "date.today",
            "time.time",
            "time.monotonic",
            "random",
            "uuid",
        }
    )

    @pytest.mark.parametrize(
        "path", python_files(*OFFLINE_STAGES), ids=lambda p: module_name(Path(p))
    )
    def test_no_clock_or_randomness_downstream_of_fetch(self, path: Path) -> None:
        offending = self.FORBIDDEN & called_attributes(path)
        assert not offending, (
            f"{module_name(path)} uses {sorted(offending)}. Transform and "
            "classify stages must be reproducible: timestamps come from the "
            "data, never the runtime clock, and nothing is unseeded."
        )


def markdown_files() -> list[Path]:
    """Every document a reader of this repository is offered.

    Including `.claude/skills/`, which are project text now: they state the
    rules, and a rule stated in the words it forbids is a rule that has drifted.
    """
    root = PACKAGE_ROOT.parent
    found = [root / name for name in ("README.md", "CONTRIBUTING.md", "CLAUDE.md")]
    for directory in ("docs", ".claude", "tests", "data"):
        found.extend(sorted((root / directory).rglob("*.md")))
    return [path for path in found if path.is_file()]


def quoted_spans(line: str) -> list[tuple[int, int]]:
    """Where this line quotes something, in backticks or double quotes.

    Quoting is how a document names a word without using it. "Never the words
    `corrupt` or `fraud`" states the rule; the same sentence without the marks
    would be indistinguishable, to a gate, from a document that calls somebody
    fraudulent.
    """
    spans: list[tuple[int, int]] = []
    for pattern in (r"`[^`\n]*`", r'"[^"\n]*"', "\u201c[^\u201d\n]*\u201d"):
        spans.extend(
            (match.start(), match.end()) for match in re.finditer(pattern, line)
        )
    return spans


class TestFlagsAreNotAccusations:
    """Constraint: a flag is a statistical anomaly, never an accusation.

    Most flags have innocent explanations, and the project publishes about
    institutions and companies whose lawyers can read. The words below must not
    reach a user through project output.

    Two surfaces, because the project has two. In code the gate reads string
    literals: comments and docstrings explain code to maintainers, and only a
    literal can reach a reader. In markdown it reads everything, because a
    document is nothing but what a reader reads — and the documents are the
    surface a journalist or a flagged buyer's lawyer actually meets first.

    A document that states the rule has to name the words. It may, by quoting
    them; an unquoted one reads as the project's own vocabulary.
    """

    FORBIDDEN = re.compile(
        r"\b(corrupt\w*|fraud\w*|guilty|bribe\w*|kickback\w*)\b", re.I
    )

    #: Reviewed: these describe damaged files, not conduct.
    ALLOWED = frozenset({"corrupted", "corrupt"})

    @pytest.mark.parametrize("path", python_files(), ids=lambda p: module_name(Path(p)))
    def test_no_accusatory_words_in_user_facing_strings(self, path: Path) -> None:
        offenders = [
            (literal, match.group(0))
            for literal in string_literals(path)
            for match in [self.FORBIDDEN.search(literal)]
            if match and match.group(0).lower() not in self.ALLOWED
        ]
        assert not offenders, (
            f"{module_name(path)} has accusatory wording in output: {offenders}. "
            "Flags are statistical anomalies with possible innocent "
            "explanations (CLAUDE.md constraint 3)."
        )

    @pytest.mark.parametrize(
        "path",
        markdown_files(),
        ids=lambda p: str(Path(p).relative_to(PACKAGE_ROOT.parent)),
    )
    def test_no_accusatory_words_in_unquoted_prose(self, path: Path) -> None:
        offenders = []
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            spans = quoted_spans(line)
            for match in self.FORBIDDEN.finditer(line):
                inside = any(
                    start <= match.start() and match.end() <= end
                    for start, end in spans
                )
                if not inside:
                    offenders.append(f"line {number}: {match.group(0)}")
        assert not offenders, (
            f"{path.relative_to(PACKAGE_ROOT.parent)} uses accusatory wording "
            f"unquoted: {offenders}. A "
            "document that states the rule quotes the word; one that uses it "
            "is writing the project's own vocabulary (CLAUDE.md constraint 3)."
        )

    def test_the_markdown_gate_can_actually_fail(self) -> None:
        # The quoting rule is what makes this gate liveable, and it is also how
        # it could quietly stop enforcing anything.
        assert self.FORBIDDEN.search("this buyer was fraudulent")
        assert not quoted_spans("this buyer was fraudulent")
        assert quoted_spans('never the words "fraud" or `guilty`')

    def test_the_classify_stage_is_covered_once_it_exists(self) -> None:
        # The prize is generated flag text, which does not exist yet. When
        # classifiers land, their output strings are already inside the scope
        # of the test above; this records that intent so it is not re-argued.
        assert (PACKAGE_ROOT / "classify").is_dir()


def classifier_rule_version(path: Path) -> int:
    """Read a single literal version without executing classifier code."""
    values = [
        node.value
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "RULE_VERSION"
                for target in node.targets
            )
        )
        or (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "RULE_VERSION"
        )
    ]
    assert len(values) == 1, f"{path.name}: declare RULE_VERSION exactly once"
    value = values[0]
    assert isinstance(value, ast.Constant) and type(value.value) is int, (
        f"{path.name}: RULE_VERSION must be a literal positive integer"
    )
    assert value.value > 0, f"{path.name}: RULE_VERSION must be positive"
    return value.value


def assert_hypothesis_admission(doc: Path, rule_version: int) -> bool:
    """Check implemented-rule metadata; return whether its measurement is current.

    Historical evidence admits only explicitly pending local development, not
    merge readiness. This is not a data rerun, proof of numbers, or human approval.
    """
    text = doc.read_text(encoding="utf-8")
    statuses = re.findall(r"^Status:[ \t]*([^\n]+)$", text, re.M)
    assert len(statuses) == 1, f"{doc.name}: expected exactly one Status line"
    status = statuses[0].strip()
    assert status in {"measured", "building", "live"}, (
        f"{doc.name}: implemented hypothesis cannot have status {status!r}"
    )

    sections = re.findall(
        r"^## Measurement metadata\n(.*?)(?=^## |\Z)", text, re.M | re.S
    )
    assert len(sections) == 1, f"{doc.name}: expected one Measurement metadata section"
    blocks = re.findall(r"^```toml\n(.*?)^```[ \t]*$", sections[0], re.M | re.S)
    assert len(blocks) == 1, f"{doc.name}: expected one fenced TOML measurement block"
    try:
        metadata = tomllib.loads(blocks[0])
    except tomllib.TOMLDecodeError as exc:
        raise AssertionError(f"{doc.name}: invalid measurement TOML: {exc}") from exc

    assert set(metadata) == {"admission", "measurement"}, (
        f"{doc.name}: expected admission and measurement tables only"
    )
    admission = metadata["admission"]
    measurement = metadata["measurement"]
    assert isinstance(admission, dict) and set(admission) == {
        "current_rule_version",
        "current_measurement",
    }, f"{doc.name}: invalid admission fields"
    assert isinstance(measurement, dict) and set(measurement) == {
        "rule_version",
        "measured_on",
        "period_start",
        "period_end",
        "package_ids",
        "query_file",
        "query_revision",
        "notice_count",
        "population_count",
        "population_notice_count",
        "covered_count",
        "uncovered_count",
        "flagged_count",
        "flagged_notice_count",
    }, f"{doc.name}: incomplete or unknown measurement fields"

    versions = (
        rule_version,
        admission["current_rule_version"],
        measurement["rule_version"],
    )
    assert all(type(value) is int and value > 0 for value in versions), (
        f"{doc.name}: rule versions must be positive integers"
    )
    assert admission["current_rule_version"] == rule_version, (
        f"{doc.name}: current_rule_version differs from classifier RULE_VERSION"
    )
    measured_version = measurement["rule_version"]
    assert measured_version <= rule_version, (
        f"{doc.name}: measurement is for a future rule"
    )
    current = measured_version == rule_version
    expected = "measured" if current else "pending"
    assert admission["current_measurement"] == expected, (
        f"{doc.name}: current_measurement must be {expected!r} for these versions"
    )
    assert current or status == "building", (
        f"{doc.name}: {status} requires a version-matching measurement; "
        "historical evidence permits only building with current measurement pending"
    )

    start, end, measured_on = (
        measurement[key] for key in ("period_start", "period_end", "measured_on")
    )
    assert all(type(value) is date for value in (start, end, measured_on)), (
        f"{doc.name}: measurement dates must be TOML local dates"
    )
    assert start <= end <= measured_on, (
        f"{doc.name}: require period_start <= period_end <= measured_on"
    )
    packages = measurement["package_ids"]
    assert isinstance(packages, list) and packages, f"{doc.name}: package_ids is empty"
    assert all(
        isinstance(package, str)
        and re.fullmatch(r"[0-9]{9}", package)
        and start.year <= int(package[:4]) <= end.year
        and int(package[4:]) > 0
        for package in packages
    ), f"{doc.name}: package_ids must be yyyynnnnn IDs within the period's years"
    assert packages == sorted(set(packages)), (
        f"{doc.name}: package_ids must be sorted and unique"
    )

    count_keys = (
        "notice_count",
        "population_count",
        "population_notice_count",
        "covered_count",
        "uncovered_count",
        "flagged_count",
        "flagged_notice_count",
    )
    assert all(
        type(measurement[key]) is int and measurement[key] >= 0 for key in count_keys
    ), f"{doc.name}: counts must be nonnegative integers (not booleans)"
    population = measurement["population_count"]
    notices = measurement["population_notice_count"]
    covered = measurement["covered_count"]
    flagged = measurement["flagged_count"]
    flagged_notices = measurement["flagged_notice_count"]
    assert population > 0, f"{doc.name}: population_count must be positive"
    assert 0 < notices <= min(population, measurement["notice_count"]), (
        f"{doc.name}: population notice counts are inconsistent"
    )
    assert covered + measurement["uncovered_count"] == population, (
        f"{doc.name}: covered_count + uncovered_count must equal population_count"
    )
    assert flagged <= covered, f"{doc.name}: flagged_count exceeds covered_count"
    assert flagged_notices <= min(notices, flagged) and (flagged_notices == 0) == (
        flagged == 0
    ), f"{doc.name}: flagged notice counts are inconsistent"

    query_file = measurement["query_file"]
    assert query_file == doc.with_suffix(".sql").name, (
        f"{doc.name}: query_file must name the companion SQL file"
    )
    assert doc.with_suffix(".sql").is_file(), (
        f"{doc.name}: companion SQL file is missing"
    )
    assert doc.with_suffix(".sql").read_text(encoding="utf-8").strip(), (
        f"{doc.name}: companion SQL file is empty"
    )
    revision = measurement["query_revision"]
    assert isinstance(revision, str) and (
        re.fullmatch(r"[0-9a-f]{40}", revision)
        or (current and revision == "working-tree")
    ), (
        f"{doc.name}: historical SQL requires a full Git revision; "
        "current may use working-tree"
    )
    return current


class TestClassifierHypotheses:
    """Constraint: every classifier is a documented hypothesis.

    A flag whose false-positive profile is unknown is not shippable. Metadata
    sanity is enforceable here; the truth of a measurement and publication
    clearance are not. Historical evidence allows explicitly pending local
    building, never merge readiness. CI requires version-matching evidence via
    --require-current-measurements; passing local tests alone is insufficient.

    Hypothesis files are named after their module, per docs/hypotheses/README.md.

    **What counts as a classifier** is the contract a rule keeps, read from the
    source rather than by importing it: a module-level ``RULE`` and a ``flags``
    function. The package also holds modules that are not classifiers — the
    records, the reader and writer — and requiring a hypothesis for those would
    teach people to write empty ones. A module that keeps half the contract is
    caught by `test_a_rule_is_either_a_classifier_or_not_one`, so the loophole
    is a rule that declares nothing, and such a module cannot be in `RULES`.
    """

    REQUIRED_SECTIONS = (
        "Claim",
        "This flag is wrong if",
        "Fields used",
        "Population and denominator",
        "Base rate",
        "Comparators",
        "Legal check",
    )
    #: What a classifier module declares. All of it, or none of it.
    CONTRACT = ("RULE", "RULE_VERSION", "flags")

    @staticmethod
    def declared(path: Path) -> set[str]:
        """The contract names this module defines at module level."""
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.FunctionDef):
                names.add(node.name)
            elif isinstance(node, ast.Assign):
                names.update(
                    target.id for target in node.targets if isinstance(target, ast.Name)
                )
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.add(node.target.id)
        return names

    def classifier_modules(self) -> list[Path]:
        return [
            path
            for path in python_files("classify")
            if path.name != "__init__.py" and set(self.CONTRACT) <= self.declared(path)
        ]

    def test_a_rule_is_either_a_classifier_or_not_one(self) -> None:
        half = [
            f"{path.stem} declares {sorted(set(self.CONTRACT) & self.declared(path))}"
            for path in python_files("classify")
            if path.name != "__init__.py"
            and set(self.CONTRACT) & self.declared(path)
            and not set(self.CONTRACT) <= self.declared(path)
        ]
        assert not half, (
            f"modules keeping half a classifier's contract: {half}. A module "
            f"declares all of {list(self.CONTRACT)} or none of them, because "
            "the gates below find classifiers by that contract and a partial "
            "one would slip past them."
        )

    def test_every_classifier_is_registered_to_run(self) -> None:
        registered = (PACKAGE_ROOT / "classify" / "__init__.py").read_text(
            encoding="utf-8"
        )
        unregistered = [
            path.stem
            for path in self.classifier_modules()
            if path.stem not in registered
        ]
        assert not unregistered, (
            f"classifiers missing from serenata.classify.RULES: {unregistered}. "
            "A rule nobody runs is a hypothesis nobody tests."
        )

    def test_every_classifier_has_a_hypothesis_file(self) -> None:
        missing = [
            path.stem
            for path in self.classifier_modules()
            if not (DOCS_ROOT / "hypotheses" / f"{path.stem}.md").is_file()
        ]
        assert not missing, (
            f"classifiers without docs/hypotheses/<module>.md: {missing}. "
            "A classifier may not merge without a written hypothesis."
        )

    def test_every_hypothesis_file_is_complete(
        self, require_current_measurements: bool
    ) -> None:
        for path in self.classifier_modules():
            doc = DOCS_ROOT / "hypotheses" / f"{path.stem}.md"
            text = doc.read_text(encoding="utf-8")

            for section in self.REQUIRED_SECTIONS:
                assert section in text, f"{doc.name} is missing '{section}'"

            version = classifier_rule_version(path)
            current = assert_hypothesis_admission(doc, version)
            if require_current_measurements:
                assert current, (
                    f"{doc.name}: current RULE_VERSION {version} requires a "
                    "version-matching measurement before merge; historical evidence "
                    "with current measurement pending permits local development only"
                )


class TestDependencyLicences:
    """Constraint: the project is AGPL-3.0 and every dependency must be compatible.

    Checked against installed metadata rather than a hand audit, because a hand
    audit happens once and a gate happens every run.

    Dev-only tools do not ship with the AGPL work, so the strict reading of the
    constraint binds runtime dependencies. This covers everything installed
    because one rule is easier to maintain honestly than two, and every dev tool
    here is permissive anyway.
    """

    #: Licence metadata is not standardised: the same licence arrives as an
    #: SPDX id ("MPL-2.0"), a human name ("Mozilla Public License 2.0 (MPL
    #: 2.0)"), or an abbreviation ("PSFL"), depending on whether it came from
    #: License-Expression, License, or a classifier. Match on families rather
    #: than exact tokens — a gate with false positives teaches people to add
    #: exceptions reflexively until it means nothing.
    COMPATIBLE = (
        r"\bMIT\b",
        r"\bBSD\b|\b0BSD\b",
        # Apache-1.x is incompatible but effectively extinct on PyPI, and any
        # match still prints the licence string for a human to see.
        r"\bAPACHE\b",
        r"\bMPL\b|\bMOZILLA PUBLIC\b",
        r"\bPSFL?\b|\bPYTHON SOFTWARE FOUNDATION\b",
        r"\bISC\b",
        r"\bCC0\b|\bPUBLIC DOMAIN\b|\bUNLICENSE\b",
        r"\bLGPL\b",
        r"\bAGPL\b|\bGPL\b[^)]*\b3",
    )

    #: Checked first: these fail even if a compatible pattern also matches.
    #: GPL-2.0-only cannot be combined with AGPL-3.0.
    INCOMPATIBLE = (
        r"\bPROPRIETARY\b",
        r"\bCOMMERCIAL\b",
        r"GPL-?2(\.0)?-?ONLY|GPLV2 ONLY",
    )

    #: Packages whose metadata is absent or genuinely ambiguous. Each entry is
    #: a decision someone made after reading the project's own licence file.
    REVIEWED_EXCEPTIONS: ClassVar[dict[str, str]] = {}

    @staticmethod
    def declared_licence(dist) -> str:
        meta = dist.metadata
        expression = meta.get("License-Expression")
        if expression:
            return expression
        declared = meta.get("License")
        if declared and len(declared) < 60:
            return declared
        classifiers = [
            value.split("::")[-1].strip()
            for value in meta.get_all("Classifier") or []
            if value.startswith("License ::")
        ]
        return classifiers[0] if classifiers else ""

    def test_every_installed_dependency_is_agpl_compatible(self) -> None:
        rejected: list[str] = []
        for dist in distributions():
            name = dist.metadata["Name"]
            if not name or name == "serenata":
                continue
            raw = self.REVIEWED_EXCEPTIONS.get(name) or self.declared_licence(dist)
            declared = raw.upper()

            forbidden = any(re.search(p, declared) for p in self.INCOMPATIBLE)
            recognised = any(re.search(p, declared) for p in self.COMPATIBLE)
            if forbidden or not recognised:
                rejected.append(f"{name}: {raw or '(no licence metadata)'}")

        assert not rejected, (
            "dependencies whose licence is not recognised as AGPL-3.0 "
            f"compatible: {sorted(rejected)}. Check the licence before adding a "
            "dependency (CLAUDE.md constraint 1). If the metadata is ambiguous "
            "rather than the licence incompatible, add a reviewed exception."
        )
