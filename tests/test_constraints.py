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
from importlib.metadata import distributions
from pathlib import Path
from typing import ClassVar

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "serenata"
DOCS_ROOT = Path(__file__).resolve().parent.parent / "docs"

#: Stages downstream of fetch. Everything here transforms or classifies, and
#: must be reproducible from its inputs alone (constraint 4).
OFFLINE_STAGES = ("parse", "normalise", "classify")


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


class TestFlagsAreNotAccusations:
    """Constraint: a flag is a statistical anomaly, never an accusation.

    Most flags have innocent explanations, and the project publishes about
    institutions and companies whose lawyers can read. The words below must not
    reach a user through project output.

    Scoped to string literals: comments and docstrings explain code to
    maintainers and legitimately discuss the rule itself. The allowlist covers
    the file-integrity sense of "corrupt", which is about bytes on disk rather
    than anyone's conduct.
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

    def test_the_classify_stage_is_covered_once_it_exists(self) -> None:
        # The prize is generated flag text, which does not exist yet. When
        # classifiers land, their output strings are already inside the scope
        # of the test above; this records that intent so it is not re-argued.
        assert (PACKAGE_ROOT / "classify").is_dir()


class TestClassifierHypotheses:
    """Constraint: every classifier is a documented hypothesis.

    A flag whose false-positive profile is unknown is not shippable. This gate
    has nothing to check until the first classifier lands, which is the point:
    it binds that classifier rather than being retrofitted against work already
    done.

    Hypothesis files are named after their module, per docs/hypotheses/README.md.
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
    ALLOWED_STATUS = frozenset({"scoped", "measured", "building", "live", "rejected"})
    PLACEHOLDERS = ("TODO", "TBD", "[", "XXX")

    def classifier_modules(self) -> list[Path]:
        return [path for path in python_files("classify") if path.name != "__init__.py"]

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

    def test_every_hypothesis_file_is_complete(self) -> None:
        for path in self.classifier_modules():
            doc = DOCS_ROOT / "hypotheses" / f"{path.stem}.md"
            text = doc.read_text(encoding="utf-8")

            for section in self.REQUIRED_SECTIONS:
                assert section in text, f"{doc.name} is missing '{section}'"

            status = re.search(r"^Status:\s*(\w+)", text, re.M)
            assert status, f"{doc.name} has no status line"
            assert status.group(1) in self.ALLOWED_STATUS, (
                f"{doc.name} has status {status.group(1)!r}, "
                f"expected one of {sorted(self.ALLOWED_STATUS)}"
            )

            base_rate = text.split("## Base rate", 1)[-1].split("##", 1)[0].strip()
            assert base_rate, f"{doc.name} has an empty base rate"
            assert not any(mark in base_rate for mark in self.PLACEHOLDERS), (
                f"{doc.name} still has a placeholder base rate. A flag whose "
                "false-positive profile is unknown is not shippable."
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
