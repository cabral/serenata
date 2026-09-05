"""Admission metadata is testable without opening any historical dataset.

All numbers, package identifiers and revisions here are synthetic test inputs,
not measurement evidence. The real hypothesis is checked by test_constraints.
"""

from pathlib import Path

import pytest

from . import test_constraints as constraints
from .test_constraints import assert_hypothesis_admission, classifier_rule_version

METADATA = """Status: building

## Measurement metadata

```toml
[admission]
current_rule_version = 2
current_measurement = "pending"

[measurement]
rule_version = 1
measured_on = 2001-02-01
period_start = 2001-01-01
period_end = 2001-01-31
package_ids = ["200100001", "200100002"]
query_file = "synthetic_rule.sql"
query_revision = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
notice_count = 100
population_count = 120
population_notice_count = 80
covered_count = 90
uncovered_count = 30
flagged_count = 4
flagged_notice_count = 3
```
"""


@pytest.fixture
def hypothesis(tmp_path: Path) -> Path:
    doc = tmp_path / "synthetic_rule.md"
    doc.write_text(METADATA, encoding="utf-8")
    doc.with_suffix(".sql").write_text(
        "SELECT 1; -- synthetic query\n", encoding="utf-8"
    )
    return doc


def replace(doc: Path, old: str, new: str) -> None:
    text = doc.read_text(encoding="utf-8")
    assert text.count(old) == 1, f"test mutation is ambiguous: {old!r}"
    doc.write_text(text.replace(old, new), encoding="utf-8")


def test_historical_building_is_admitted_but_measurement_is_not_current(
    hypothesis: Path,
) -> None:
    assert assert_hypothesis_admission(hypothesis, 2) is False


@pytest.mark.parametrize("status", ["measured", "building", "live"])
@pytest.mark.parametrize("revision", ["working-tree", "b" * 40])
def test_matching_measurement_is_admitted(
    hypothesis: Path, status: str, revision: str
) -> None:
    replace(hypothesis, "Status: building", f"Status: {status}")
    replace(hypothesis, "\nrule_version = 1", "\nrule_version = 2")
    replace(
        hypothesis,
        'current_measurement = "pending"',
        'current_measurement = "measured"',
    )
    replace(hypothesis, "a" * 40, revision)
    assert assert_hypothesis_admission(hypothesis, 2) is True


@pytest.mark.parametrize("status", ["scoped", "rejected", "unmeasured", "unknown"])
def test_implemented_status_must_be_admissible(hypothesis: Path, status: str) -> None:
    replace(hypothesis, "Status: building", f"Status: {status}")
    with pytest.raises(AssertionError, match="implemented hypothesis"):
        assert_hypothesis_admission(hypothesis, 2)


@pytest.mark.parametrize("status", ["measured", "live"])
def test_historical_evidence_cannot_claim_current_measurement_or_live_status(
    hypothesis: Path, status: str
) -> None:
    replace(hypothesis, "Status: building", f"Status: {status}")
    with pytest.raises(AssertionError, match="version-matching measurement"):
        assert_hypothesis_admission(hypothesis, 2)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("Status: building", "", "exactly one Status"),
        ("Status: building", "Status: building\nStatus: live", "exactly one Status"),
        ("Status: building", "Status: building someday", "implemented hypothesis"),
        ("## Measurement metadata", "## Something else", "one Measurement metadata"),
        ("```toml", "```json", "one fenced TOML"),
        ("```toml", "```toml\ninvalid = [", "invalid measurement TOML"),
        ("[admission]", "[other]", "admission and measurement tables"),
        (
            "[measurement]",
            "[measurement]\nunexpected = 1",
            "unknown measurement fields",
        ),
        (
            "current_rule_version = 2",
            "current_rule_version = true",
            "positive integers",
        ),
        (
            "current_rule_version = 2",
            "current_rule_version = 1",
            "differs from classifier",
        ),
        ("\nrule_version = 1", "\nrule_version = 0", "positive integers"),
        ("\nrule_version = 1", "\nrule_version = 1.0", "positive integers"),
        ("\nrule_version = 1", '\nrule_version = "1"', "positive integers"),
        ("\nrule_version = 1", "\nrule_version = true", "positive integers"),
        ("\nrule_version = 1", "\nrule_version = 3", "future rule"),
        (
            'current_measurement = "pending"',
            'current_measurement = "measured"',
            "must be 'pending'",
        ),
        (
            'current_measurement = "pending"',
            'current_measurement = "TODO"',
            "must be 'pending'",
        ),
        ("\nrule_version = 1", "\nrule_version = 2", "must be 'measured'"),
        (
            "period_start = 2001-01-01",
            'period_start = "2001-01-01"',
            "TOML local dates",
        ),
        (
            "period_start = 2001-01-01",
            "period_start = 2001-01-01T00:00:00",
            "TOML local dates",
        ),
        (
            "period_start = 2001-01-01",
            "period_start = 2001-02-02",
            "period_start <= period_end",
        ),
        (
            "period_end = 2001-01-31",
            "period_end = 2001-02-02",
            "period_start <= period_end",
        ),
        (
            "measured_on = 2001-02-01",
            "measured_on = 2001-02-30",
            "invalid measurement TOML",
        ),
        (
            'query_file = "synthetic_rule.sql"',
            'query_file = "other.sql"',
            "companion SQL file",
        ),
        (
            'query_file = "synthetic_rule.sql"',
            'query_file = "../synthetic_rule.sql"',
            "companion SQL file",
        ),
        ("a" * 40, "working-tree", "historical SQL requires"),
        ("a" * 40, "abc1234", "historical SQL requires"),
        ("a" * 40, "z" * 40, "historical SQL requires"),
    ],
)
def test_invalid_metadata_is_rejected(
    hypothesis: Path, old: str, new: str, message: str
) -> None:
    replace(hypothesis, old, new)
    with pytest.raises(AssertionError, match=message):
        assert_hypothesis_admission(hypothesis, 2)


@pytest.mark.parametrize(
    "line",
    [line for line in METADATA.splitlines() if " = " in line],
)
def test_every_metadata_field_is_required(hypothesis: Path, line: str) -> None:
    replace(hypothesis, line + "\n", "")
    with pytest.raises(AssertionError, match="fields"):
        assert_hypothesis_admission(hypothesis, 2)


@pytest.mark.parametrize(
    "packages",
    [
        "[]",
        '"200100001"',
        "[200100001]",
        "[true]",
        '["200100001", "200100001"]',
        '["200100002", "200100001"]',
        '["200100000"]',
        '["000000001"]',
        '["20010001"]',
        '["2001000010"]',
        '["200100001.tar.gz"]',
        '["1/2001"]',
        '["2001abcde"]',
        '["200000001"]',
        '["200200001"]',
    ],
)
def test_invalid_corpus_packages_are_rejected(hypothesis: Path, packages: str) -> None:
    replace(hypothesis, '["200100001", "200100002"]', packages)
    with pytest.raises(AssertionError, match="package_ids"):
        assert_hypothesis_admission(hypothesis, 2)


@pytest.mark.parametrize(
    "key",
    [
        "notice_count",
        "population_count",
        "population_notice_count",
        "covered_count",
        "uncovered_count",
        "flagged_count",
        "flagged_notice_count",
    ],
)
@pytest.mark.parametrize("value", ["-1", "true", "1.5", '"120"'])
def test_counts_are_strict_nonnegative_integers(
    hypothesis: Path, key: str, value: str
) -> None:
    line = next(line for line in METADATA.splitlines() if line.startswith(key + " = "))
    replace(hypothesis, line, f"{key} = {value}")
    with pytest.raises(AssertionError, match="counts must be nonnegative integers"):
        assert_hypothesis_admission(hypothesis, 2)


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        ("population_count = 120", "population_count = 0", "must be positive"),
        (
            "population_notice_count = 80",
            "population_notice_count = 0",
            "population notice",
        ),
        (
            "population_notice_count = 80",
            "population_notice_count = 101",
            "population notice",
        ),
        ("population_count = 120", "population_count = 79", "population notice"),
        ("notice_count = 100", "notice_count = 0", "population notice"),
        ("covered_count = 90", "covered_count = 91", "must equal population_count"),
        ("uncovered_count = 30", "uncovered_count = 29", "must equal population_count"),
        ("flagged_count = 4", "flagged_count = 91", "exceeds covered_count"),
        ("flagged_notice_count = 3", "flagged_notice_count = 5", "flagged notice"),
        (
            "population_notice_count = 80",
            "population_notice_count = 2",
            "flagged notice",
        ),
        ("flagged_count = 4", "flagged_count = 0", "flagged notice"),
        ("flagged_notice_count = 3", "flagged_notice_count = 0", "flagged notice"),
    ],
)
def test_inconsistent_counts_are_rejected(
    hypothesis: Path, old: str, new: str, message: str
) -> None:
    replace(hypothesis, old, new)
    with pytest.raises(AssertionError, match=message):
        assert_hypothesis_admission(hypothesis, 2)


def test_zero_flags_are_a_valid_measurement(hypothesis: Path) -> None:
    replace(hypothesis, "flagged_count = 4", "flagged_count = 0")
    replace(hypothesis, "flagged_notice_count = 3", "flagged_notice_count = 0")
    assert assert_hypothesis_admission(hypothesis, 2) is False


@pytest.mark.parametrize("empty", [False, True])
def test_companion_sql_must_exist_and_be_nonempty(
    hypothesis: Path, empty: bool
) -> None:
    sql = hypothesis.with_suffix(".sql")
    if empty:
        sql.write_text(" \n", encoding="utf-8")
    else:
        sql.unlink()
    with pytest.raises(AssertionError, match=r"companion SQL file is (empty|missing)"):
        assert_hypothesis_admission(hypothesis, 2)


@pytest.mark.parametrize("duplicate_section", [False, True])
def test_duplicate_measurement_is_rejected(
    hypothesis: Path, duplicate_section: bool
) -> None:
    addition = METADATA.split("## Measurement metadata\n", 1)[1]
    if duplicate_section:
        addition = "\n## Measurement metadata\n" + addition
    hypothesis.write_text(METADATA + addition, encoding="utf-8")
    with pytest.raises(AssertionError, match="expected one"):
        assert_hypothesis_admission(hypothesis, 2)


@pytest.fixture
def repository_gate(
    hypothesis: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> constraints.TestClassifierHypotheses:
    """Exercise actual discovery/admission with synthetic source and evidence."""
    classifier = tmp_path / "classify" / "synthetic_rule.py"
    classifier.parent.mkdir()
    classifier.write_text(
        'RULE = "synthetic_rule"\nRULE_VERSION: int = 2\ndef flags(): pass\n',
        encoding="utf-8",
    )
    docs = tmp_path / "hypotheses"
    docs.mkdir()
    doc = docs / hypothesis.name
    text = hypothesis.read_text(encoding="utf-8") + "\n".join(
        f"## {section}\nSome nonempty prose.\n"
        for section in constraints.TestClassifierHypotheses.REQUIRED_SECTIONS
    )
    doc.write_text(text, encoding="utf-8")
    doc.with_suffix(".sql").write_text(
        hypothesis.with_suffix(".sql").read_text(encoding="utf-8"), encoding="utf-8"
    )
    monkeypatch.setattr(constraints, "PACKAGE_ROOT", tmp_path)
    monkeypatch.setattr(constraints, "DOCS_ROOT", tmp_path)
    gate = constraints.TestClassifierHypotheses()
    assert gate.classifier_modules() == [classifier]
    return gate


@pytest.mark.parametrize("required", [False, True])
def test_repository_gate_rejects_prose_instead_of_measurement(
    repository_gate: constraints.TestClassifierHypotheses, required: bool
) -> None:
    doc = constraints.DOCS_ROOT / "hypotheses" / "synthetic_rule.md"
    text = "Status: building\n" + "\n".join(
        f"## {section}\nSome nonempty prose.\n"
        for section in repository_gate.REQUIRED_SECTIONS
    )
    doc.write_text(text, encoding="utf-8")
    with pytest.raises(AssertionError, match="Measurement metadata"):
        repository_gate.test_every_hypothesis_file_is_complete(required)


def test_repository_gate_allows_historical_building_only_for_local_development(
    repository_gate: constraints.TestClassifierHypotheses,
) -> None:
    repository_gate.test_every_hypothesis_file_is_complete(False)
    with pytest.raises(AssertionError, match=r"RULE_VERSION 2.*before merge"):
        repository_gate.test_every_hypothesis_file_is_complete(True)


@pytest.mark.parametrize("status", ["measured", "building", "live"])
@pytest.mark.parametrize("required", [False, True])
def test_repository_gate_accepts_current_measurement(
    repository_gate: constraints.TestClassifierHypotheses, status: str, required: bool
) -> None:
    doc = constraints.DOCS_ROOT / "hypotheses" / "synthetic_rule.md"
    replace(doc, "Status: building", f"Status: {status}")
    replace(doc, "\nrule_version = 1", "\nrule_version = 2")
    replace(doc, 'current_measurement = "pending"', 'current_measurement = "measured"')
    repository_gate.test_every_hypothesis_file_is_complete(required)


def test_repository_gate_checks_every_implemented_classifier(
    repository_gate: constraints.TestClassifierHypotheses,
) -> None:
    """A current earlier rule must not hide a later pending rule."""
    classifier = constraints.PACKAGE_ROOT / "classify" / "aaa_synthetic_current.py"
    classifier.write_text(
        'RULE = "aaa_synthetic_current"\nRULE_VERSION = 1\ndef flags(): pass\n',
        encoding="utf-8",
    )
    docs = constraints.DOCS_ROOT / "hypotheses"
    text = (docs / "synthetic_rule.md").read_text(encoding="utf-8")
    text = (
        text.replace("current_rule_version = 2", "current_rule_version = 1")
        .replace('current_measurement = "pending"', 'current_measurement = "measured"')
        .replace("synthetic_rule.sql", "aaa_synthetic_current.sql")
    )
    (docs / "aaa_synthetic_current.md").write_text(text, encoding="utf-8")
    (docs / "aaa_synthetic_current.sql").write_text("SELECT 1;", encoding="utf-8")
    assert repository_gate.classifier_modules() == [
        classifier,
        classifier.with_name("synthetic_rule.py"),
    ]
    with pytest.raises(AssertionError, match=r"synthetic_rule\.md:.*before merge"):
        repository_gate.test_every_hypothesis_file_is_complete(True)


@pytest.mark.parametrize("declaration", ["RULE_VERSION = 2", "RULE_VERSION: int = 2"])
def test_rule_version_is_read_without_importing(
    tmp_path: Path, declaration: str
) -> None:
    module = tmp_path / "synthetic_rule.py"
    module.write_text(
        f'raise RuntimeError("do not import")\n{declaration}\n', encoding="utf-8"
    )
    assert classifier_rule_version(module) == 2


@pytest.mark.parametrize(
    "declaration",
    [
        "",
        "RULE_VERSION = True",
        "RULE_VERSION = 0",
        "RULE_VERSION = -1",
        'RULE_VERSION = "2"',
        "RULE_VERSION = 2.0",
        "RULE_VERSION = 1 + 1",
        "RULE_VERSION: int",
        "RULE_VERSION = 1\nRULE_VERSION = 2",
    ],
)
def test_invalid_classifier_version_is_rejected(
    tmp_path: Path, declaration: str
) -> None:
    module = tmp_path / "synthetic_rule.py"
    module.write_text(declaration, encoding="utf-8")
    with pytest.raises(AssertionError, match="RULE_VERSION"):
        classifier_rule_version(module)
