"""Synthetic, offline merge-controller regressions for ADR-0012.

These tests exercise metadata gates, not GitHub's hosted enforcement or human
authorization. Every response, repository identity and SHA below is invented.
No proposed-head code, real credentials or procurement data are loaded.
"""

from __future__ import annotations

import argparse
import builtins
import hashlib
import http.client
import io
import json
import subprocess
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock
from urllib.parse import urlencode

import pytest

from tools import merge_guard as guard

REPOSITORY = "EXAMPLE/merge-guard-fixture"
AUTHOR = "EXAMPLE-CONTRIBUTOR"
NUMBER = 17
BASE = "a" * 40
HEAD = "b" * 40
OTHER = "c" * 40
NOW = datetime(2026, 9, 5, 12, tzinfo=UTC)
ALLOWED_PATH = "tests/test_fetch_archive.py"
UNCHANGED_PATH = "serenata/cli.py"
# Keep expected requirements independent of the controller's constants.
WORKFLOW_JOBS = {
    "ci.yml": ("check (3.12)", "check (3.13)"),
    "dco.yml": ("sign-off",),
    "audit.yml": ("audit",),
}


def policy_data(**overrides: Any) -> dict[str, Any]:
    """Small, explicitly enabled delegation; never read the repository policy."""
    return {
        "enabled": True,
        "repository": REPOSITORY,
        "base": "main",
        "expires_at": NOW + timedelta(days=1),
        "authors": [AUTHOR],
        "paths": [ALLOWED_PATH],
        "max_files": 4,
        "max_lines": 400,
    } | overrides


def write_policy(path: Path, data: dict[str, Any]) -> None:
    """Serialize this fixture's limited TOML values into pytest's temp directory."""
    lines = []
    for key, value in data.items():
        literal = (
            value.isoformat() if isinstance(value, datetime) else json.dumps(value)
        )
        lines.append(f"{key} = {literal}\n")
    path.write_text("".join(lines), encoding="utf-8")


def tree_entry(
    path: str, sha: str, *, mode: str = "100644", kind: str = "blob"
) -> dict[str, Any]:
    return {"path": path, "sha": sha, "mode": mode, "type": kind}


def runs_endpoint(filename: str) -> str:
    query = urlencode({"event": "pull_request", "head_sha": HEAD, "per_page": 100})
    return f"/actions/workflows/{filename}/runs?{query}"


def jobs_endpoint(run: dict[str, Any]) -> str:
    return f"/actions/runs/{run['id']}/attempts/{run['run_attempt']}/jobs?per_page=100"


class FakeGitHub(guard.GitHub):
    """An exact response map: unexpected endpoints fail instead of using HTTP."""

    def __init__(self) -> None:
        super().__init__(REPOSITORY, "EXAMPLE-NOT-A-CREDENTIAL")
        self.responses: dict[str, Any] = {}
        self.calls: list[tuple[str, str, Any]] = []

    def request(
        self, method: str, endpoint: str, body: dict[str, Any] | None = None
    ) -> Any:
        self.calls.append((method, endpoint, deepcopy(body)))
        assert method == "GET"
        assert body is None
        assert endpoint in self.responses, f"Unexpected fake GitHub GET: {endpoint}"
        return deepcopy(self.responses[endpoint])

    @property
    def writes(self) -> list[tuple[str, str, Any]]:
        return [call for call in self.calls if call[0] != "GET" or call[2] is not None]


class FixtureBuilder:
    """A green PR, immutable inventories and trusted workflow evidence to mutate."""

    def __init__(self, policy_path: Path) -> None:
        self.policy_path = policy_path
        self.set_policy()
        self.api = FakeGitHub()
        self.pr = {
            "number": NUMBER,
            "state": "open",
            "draft": False,
            "merged": False,
            "base": {
                "repo": {"full_name": REPOSITORY},
                "ref": "main",
                "sha": BASE,
            },
            "head": {"repo": {"full_name": REPOSITORY}, "sha": HEAD},
            "user": {"login": AUTHOR},
            "mergeable": True,
            "mergeable_state": "clean",
        }
        self.branch = {"protected": True, "commit": {"sha": BASE}}
        self.protection = {
            "enforce_admins": {"enabled": True},
            "allow_force_pushes": {"enabled": False},
            "allow_deletions": {"enabled": False},
            "required_conversation_resolution": {"enabled": True},
            "required_status_checks": {
                "strict": True,
                "checks": [
                    {"context": name, "app_id": 15368}
                    for names in WORKFLOW_JOBS.values()
                    for name in names
                ],
            },
            "required_pull_request_reviews": {
                "required_approving_review_count": 1,
                "bypass_pull_request_allowances": {
                    "users": [],
                    "teams": [],
                    "apps": [],
                },
            },
        }
        self.comparison = {
            "status": "ahead",
            "behind_by": 0,
            "ahead_by": 1,
            "total_commits": 1,
            "merge_base_commit": {"sha": BASE},
            "commits": [{"sha": HEAD, "parents": [{"sha": BASE}]}],
            "files": [{"filename": ALLOWED_PATH, "status": "modified", "changes": 5}],
        }
        self.base_tree = {
            "truncated": False,
            "tree": [
                tree_entry("tests", "1" * 40, mode="040000", kind="tree"),
                tree_entry(ALLOWED_PATH, "2" * 40),
                tree_entry(UNCHANGED_PATH, "3" * 40),
            ],
        }
        self.head_tree = deepcopy(self.base_tree)
        # Directory object changes are not themselves file changes.
        self.head_tree["tree"][0]["sha"] = "4" * 40
        self.head_tree["tree"][1]["sha"] = "5" * 40
        self.api.responses.update(
            {
                f"/pulls/{NUMBER}": self.pr,
                "/branches/main": self.branch,
                "/branches/main/protection": self.protection,
                f"/compare/{BASE}...{HEAD}": self.comparison,
                f"/git/trees/{HEAD}?recursive=1": self.head_tree,
                f"/git/trees/{BASE}?recursive=1": self.base_tree,
            }
        )
        self.workflows: dict[str, dict[str, Any]] = {}
        self.run_lists: dict[str, dict[str, Any]] = {}
        self.job_lists: dict[str, dict[str, Any]] = {}
        for index, (filename, names) in enumerate(WORKFLOW_JOBS.items(), start=1):
            workflow = {
                "id": index,
                "path": f".github/workflows/{filename}",
                "state": "active",
            }
            run = {
                "id": 100 + index,
                "run_number": 10,
                "run_attempt": 1,
                "workflow_id": workflow["id"],
                "path": workflow["path"],
                "event": "pull_request",
                "head_sha": HEAD,
                "head_repository": {"full_name": REPOSITORY},
                "pull_requests": [
                    {"number": NUMBER, "head": {"sha": HEAD}, "base": {"sha": BASE}}
                ],
                "status": "completed",
                "conclusion": "success",
            }
            jobs = {
                "total_count": len(names),
                "jobs": [
                    {
                        "name": name,
                        "run_id": run["id"],
                        "head_sha": HEAD,
                        "status": "completed",
                        "conclusion": "success",
                    }
                    for name in names
                ],
            }
            self.workflows[filename] = workflow
            self.run_lists[filename] = {"total_count": 1, "workflow_runs": [run]}
            self.job_lists[filename] = jobs
            self.api.responses[f"/actions/workflows/{filename}"] = workflow
            self.api.responses[runs_endpoint(filename)] = self.run_lists[filename]
            self.api.responses[jobs_endpoint(run)] = jobs

    def set_policy(self, **overrides: Any) -> None:
        write_policy(self.policy_path, policy_data(**overrides))
        self.policy = guard.Policy.load(self.policy_path)

    @property
    def expected(self) -> guard.Decision:
        return guard.Decision(
            NUMBER, HEAD, BASE, self.policy.digest, ((101, 1), (102, 1), (103, 1))
        )

    def inspect(self) -> guard.Decision:
        return guard.inspect(self.api, self.policy, NUMBER, BASE, NOW)

    def run(self, filename: str = "ci.yml") -> dict[str, Any]:
        return self.run_lists[filename]["workflow_runs"][0]

    def assert_hold(self, code: str) -> None:
        """Every inspection refusal must also hold during read-only revalidation."""
        with pytest.raises(guard.Hold, match=f"^{code}$"):
            self.inspect()
        assert self.api.writes == []
        with pytest.raises(guard.Hold, match=f"^{code}$"):
            guard.revalidate(self.api, self.policy_path, self.expected)
        assert self.api.writes == []


@pytest.fixture
def fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FixtureBuilder:
    class DatetimeType(type):
        def __instancecheck__(cls, instance: Any) -> bool:
            # TOML still returns real datetimes, which Policy.load validates.
            return isinstance(instance, datetime)

    class FixedDatetime(datetime, metaclass=DatetimeType):
        current = NOW

        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            assert tz is UTC
            return cls.current

    # Revalidation's expiry checks must not fail as the real calendar moves.
    monkeypatch.setattr(guard, "datetime", FixedDatetime)
    return FixtureBuilder(tmp_path / "synthetic-policy.toml")


class TestMergeGuard:
    """ADR-0012 gates fail closed; eligibility is not authorization to merge."""

    def test_inspect_is_read_only_and_uses_immutable_revisions(
        self, fixture: FixtureBuilder
    ) -> None:
        assert fixture.inspect() == fixture.expected
        assert fixture.api.writes == []
        endpoints = [endpoint for _, endpoint, _ in fixture.api.calls]
        assert f"/compare/{BASE}...{HEAD}" in endpoints
        assert f"/git/trees/{HEAD}?recursive=1" in endpoints
        assert f"/git/trees/{BASE}?recursive=1" in endpoints
        assert not any(endpoint.endswith("/files") for endpoint in endpoints)
        assert not any("/contents/" in endpoint for endpoint in endpoints)
        for filename in WORKFLOW_JOBS:
            assert runs_endpoint(filename) in endpoints
            assert jobs_endpoint(fixture.run(filename)) in endpoints

    def test_revalidate_reinspects_without_writes_or_intent_logging(
        self, fixture: FixtureBuilder, capsys: pytest.CaptureFixture[str]
    ) -> None:
        decision = fixture.inspect()
        initial_calls = list(fixture.api.calls)
        fixture.api.calls.clear()

        current = guard.revalidate(fixture.api, fixture.policy_path, decision)

        assert current == decision
        assert current is not decision
        assert fixture.api.calls == initial_calls
        assert fixture.api.writes == []
        assert capsys.readouterr() == ("", "")

    def test_policy_digest_binds_exact_bytes(self, fixture: FixtureBuilder) -> None:
        raw = fixture.policy_path.read_bytes()
        assert fixture.policy.digest == hashlib.sha256(raw).hexdigest()
        fixture.policy_path.write_bytes(raw + b"# same authority, different bytes\n")
        with pytest.raises(guard.Hold, match=r"^delegation_changed$"):
            guard.revalidate(fixture.api, fixture.policy_path, fixture.expected)
        assert fixture.api.calls == []

    @pytest.mark.parametrize(
        ("overrides", "code"),
        [
            ({"enabled": False}, "delegation_disabled"),
            ({"expires_at": NOW}, "delegation_expired"),
            ({"expires_at": NOW - timedelta(seconds=1)}, "delegation_expired"),
            ({"authors": []}, "delegation_empty"),
            ({"paths": []}, "delegation_empty"),
        ],
    )
    def test_inactive_policy_never_reads_or_writes_github(
        self, fixture: FixtureBuilder, overrides: dict[str, Any], code: str
    ) -> None:
        fixture.set_policy(**overrides)
        fixture.assert_hold(code)
        assert fixture.api.calls == []

    @pytest.mark.parametrize(
        ("field", "value", "code"),
        [
            ("enabled", 1, "policy_schema"),
            ("enabled", "true", "policy_schema"),
            ("authors", AUTHOR, "policy_schema"),
            ("authors", [AUTHOR, AUTHOR], "policy_schema"),
            ("authors", [""], "policy_schema"),
            ("authors", [1], "policy_schema"),
            ("paths", ALLOWED_PATH, "policy_schema"),
            ("paths", [ALLOWED_PATH, ALLOWED_PATH], "policy_schema"),
            ("repository", "../EXAMPLE/repository", "policy_repository"),
            ("repository", "https://example.invalid/repository", "policy_repository"),
            ("base", "development", "policy_base"),
            ("expires_at", "2026-09-06T12:00:00Z", "policy_expiry"),
            ("expires_at", NOW.replace(tzinfo=None), "policy_expiry"),
            ("paths", ["serenata/cli.py"], "policy_scope"),
            ("paths", ["tests/test_merge_guard.py"], "policy_scope"),
            ("paths", ["tests/*.py"], "policy_scope"),
            ("max_files", True, "policy_limits"),
            ("max_files", 0, "policy_limits"),
            ("max_files", 5, "policy_limits"),
            ("max_lines", True, "policy_limits"),
            ("max_lines", 0, "policy_limits"),
            ("max_lines", 401, "policy_limits"),
            ("max_lines", 4.5, "policy_limits"),
        ],
    )
    def test_policy_rejects_invalid_schema_and_scope(
        self, fixture: FixtureBuilder, field: str, value: Any, code: str
    ) -> None:
        write_policy(fixture.policy_path, policy_data(**{field: value}))
        with pytest.raises(guard.Hold, match=f"^{code}$"):
            guard.Policy.load(fixture.policy_path)
        with pytest.raises(guard.Hold, match=f"^{code}$"):
            guard.revalidate(fixture.api, fixture.policy_path, fixture.expected)
        assert fixture.api.calls == []

    @pytest.mark.parametrize("change", ["extra-key", "missing-key"])
    def test_policy_keys_must_match_exactly(
        self, fixture: FixtureBuilder, change: str
    ) -> None:
        data = policy_data()
        if change == "extra-key":
            data["allow_everything"] = True
        else:
            del data["enabled"]
        write_policy(fixture.policy_path, data)
        with pytest.raises(guard.Hold, match=r"^policy_schema$"):
            guard.revalidate(fixture.api, fixture.policy_path, fixture.expected)
        assert fixture.api.calls == []

    @pytest.mark.parametrize("side", ["head", "base"])
    def test_fork_or_wrong_repository_holds(
        self, fixture: FixtureBuilder, side: str
    ) -> None:
        fixture.pr[side]["repo"]["full_name"] = "EXAMPLE-FORK/synthetic"
        fixture.assert_hold("fork_or_repository")

    @pytest.mark.parametrize(
        ("field", "value", "code"),
        [
            ("number", NUMBER + 1, "pr_not_open"),
            ("state", "closed", "pr_not_open"),
            ("draft", True, "pr_not_open"),
            ("merged", True, "pr_not_open"),
            ("mergeable", None, "not_mergeable"),
            ("mergeable", False, "not_mergeable"),
            ("mergeable_state", "blocked", "not_mergeable"),
        ],
    )
    def test_pr_must_still_be_open_and_mergeable(
        self, fixture: FixtureBuilder, field: str, value: Any, code: str
    ) -> None:
        fixture.pr[field] = value
        fixture.assert_hold(code)

    def test_author_must_be_explicitly_delegated(self, fixture: FixtureBuilder) -> None:
        fixture.pr["user"]["login"] = "EXAMPLE-OTHER-CONTRIBUTOR"
        fixture.assert_hold("author_not_delegated")

    @pytest.mark.parametrize("head", [BASE, "main", "b" * 39, "B" * 40, None])
    def test_head_must_be_a_distinct_full_sha(
        self, fixture: FixtureBuilder, head: Any
    ) -> None:
        fixture.pr["head"]["sha"] = head
        fixture.assert_hold("head_identity")

    @pytest.mark.parametrize("field", ["sha", "ref"])
    def test_pr_base_is_bound_to_trusted_revision(
        self, fixture: FixtureBuilder, field: str
    ) -> None:
        fixture.pr["base"][field] = OTHER if field == "sha" else "development"
        fixture.assert_hold("base_changed")

    @pytest.mark.parametrize("change", ["unprotected", "advanced"])
    def test_live_branch_must_be_protected_and_unchanged(
        self, fixture: FixtureBuilder, change: str
    ) -> None:
        if change == "unprotected":
            fixture.branch["protected"] = False
        else:
            fixture.branch["commit"]["sha"] = OTHER
        fixture.assert_hold("unprotected_or_stale_base")

    @pytest.mark.parametrize(
        ("setting", "enabled", "code"),
        [
            ("enforce_admins", False, "admin_bypass"),
            ("allow_force_pushes", True, "unsafe_protection"),
            ("allow_deletions", True, "unsafe_protection"),
            ("required_conversation_resolution", False, "conversation_resolution"),
        ],
    )
    def test_protection_cannot_allow_bypasses(
        self, fixture: FixtureBuilder, setting: str, enabled: bool, code: str
    ) -> None:
        fixture.protection[setting]["enabled"] = enabled
        fixture.assert_hold(code)

    def test_strict_status_checks_are_required(self, fixture: FixtureBuilder) -> None:
        fixture.protection["required_status_checks"]["strict"] = False
        fixture.assert_hold("stale_branch_allowed")

    @pytest.mark.parametrize(
        "name", ["check (3.12)", "check (3.13)", "sign-off", "audit"]
    )
    @pytest.mark.parametrize("change", ["missing", "wrong-app"])
    def test_required_check_names_and_app_identity(
        self, fixture: FixtureBuilder, name: str, change: str
    ) -> None:
        checks = fixture.protection["required_status_checks"]["checks"]
        check = next(item for item in checks if item["context"] == name)
        if change == "missing":
            checks.remove(check)
        else:
            check["app_id"] = 999
        fixture.assert_hold("required_check_missing")

    @pytest.mark.parametrize("kind", ["users", "teams", "apps"])
    def test_review_bypass_allowances_hold(
        self, fixture: FixtureBuilder, kind: str
    ) -> None:
        reviews = fixture.protection["required_pull_request_reviews"]
        reviews["bypass_pull_request_allowances"][kind] = [{"id": 99}]
        fixture.assert_hold("review_bypass")

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("status", "diverged"),
            ("behind_by", 1),
            ("behind_by", False),
            ("ahead_by", 2),
            ("ahead_by", True),
            ("total_commits", 2),
            ("total_commits", True),
            ("merge_base_commit", {"sha": OTHER}),
            ("commits", []),
            ("commits", [{"sha": OTHER, "parents": [{"sha": BASE}]}]),
            ("commits", [{"sha": HEAD, "parents": []}]),
            ("commits", [{"sha": HEAD, "parents": [{"sha": OTHER}]}]),
            (
                "commits",
                [{"sha": HEAD, "parents": [{"sha": BASE}, {"sha": OTHER}]}],
            ),
            (
                "commits",
                [
                    {"sha": OTHER, "parents": [{"sha": BASE}]},
                    {"sha": HEAD, "parents": [{"sha": OTHER}]},
                ],
            ),
        ],
    )
    def test_only_one_commit_directly_atop_base_is_eligible(
        self, fixture: FixtureBuilder, field: str, value: Any
    ) -> None:
        fixture.comparison[field] = value
        fixture.assert_hold("non_linear_change")

    @pytest.mark.parametrize("side", ["head_tree", "base_tree"])
    def test_both_recursive_trees_must_be_complete(
        self, fixture: FixtureBuilder, side: str
    ) -> None:
        getattr(fixture, side)["truncated"] = True
        fixture.assert_hold("incomplete_tree")

    @pytest.mark.parametrize("side", ["head_tree", "base_tree"])
    @pytest.mark.parametrize("conflicting", [False, True])
    def test_duplicate_tree_paths_hold(
        self, fixture: FixtureBuilder, side: str, conflicting: bool
    ) -> None:
        entries = getattr(fixture, side)["tree"]
        duplicate = deepcopy(entries[2])
        if conflicting:
            duplicate["sha"] = OTHER
        entries.insert(0, duplicate)
        fixture.assert_hold("invalid_tree")

    @pytest.mark.parametrize("side", ["head_tree", "base_tree"])
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("path", None),
            ("path", ""),
            ("path", "/absolute"),
            ("path", "a//b"),
            ("path", "a/../b"),
            ("path", "a/./b"),
            ("path", "a\x00b"),
            ("type", None),
            ("type", "unknown"),
            ("type", "commit"),
            ("mode", None),
            ("mode", "unknown"),
            ("sha", None),
            ("sha", "short"),
            ("sha", "z" * 40),
        ],
    )
    def test_malformed_tree_entries_hold(
        self, fixture: FixtureBuilder, side: str, field: str, value: Any
    ) -> None:
        getattr(fixture, side)["tree"][2][field] = value
        fixture.assert_hold("invalid_tree")

    @pytest.mark.parametrize("side", ["head_tree", "base_tree"])
    @pytest.mark.parametrize("inventory", [None, {}, [None]])
    def test_malformed_tree_inventory_holds(
        self, fixture: FixtureBuilder, side: str, inventory: Any
    ) -> None:
        getattr(fixture, side)["tree"] = inventory
        fixture.assert_hold("invalid_tree")

    @pytest.mark.parametrize("change", ["modified", "added", "removed", "mode"])
    def test_full_tree_detects_changes_omitted_from_compare_files(
        self, fixture: FixtureBuilder, change: str
    ) -> None:
        # A short, otherwise allowed diff must not hide an out-of-scope leaf.
        leaves = fixture.head_tree["tree"]
        if change == "modified":
            leaves[2]["sha"] = OTHER
        elif change == "added":
            leaves.append(tree_entry("serenata/EXAMPLE_NEW.py", OTHER))
        elif change == "removed":
            leaves.pop(2)
        else:
            leaves[2]["mode"] = "100755"
        fixture.assert_hold("incomplete_files")

    def test_compare_cannot_claim_an_unchanged_file(
        self, fixture: FixtureBuilder
    ) -> None:
        fixture.head_tree["tree"][1] = deepcopy(fixture.base_tree["tree"][1])
        fixture.assert_hold("incomplete_files")

    def test_complete_diff_still_cannot_broaden_delegated_paths(
        self, fixture: FixtureBuilder
    ) -> None:
        fixture.head_tree["tree"][2]["sha"] = OTHER
        fixture.comparison["files"].append(
            {"filename": UNCHANGED_PATH, "status": "modified", "changes": 1}
        )
        fixture.assert_hold("outside_delegation")

    def test_hard_scope_is_not_an_implicit_delegation(
        self, fixture: FixtureBuilder
    ) -> None:
        other_allowed = "tests/test_fetch_client.py"
        fixture.base_tree["tree"].append(tree_entry(other_allowed, "6" * 40))
        fixture.head_tree["tree"].append(tree_entry(other_allowed, "7" * 40))
        fixture.comparison["files"].append(
            {"filename": other_allowed, "status": "modified", "changes": 1}
        )
        fixture.assert_hold("outside_delegation")

    def test_duplicate_file_rows_hold(self, fixture: FixtureBuilder) -> None:
        fixture.comparison["files"].append(deepcopy(fixture.comparison["files"][0]))
        fixture.assert_hold("outside_delegation")

    @pytest.mark.parametrize(
        "status", ["added", "removed", "renamed", "copied", "changed", "unchanged"]
    )
    def test_unsupported_file_status_holds(
        self, fixture: FixtureBuilder, status: str
    ) -> None:
        fixture.comparison["files"][0]["status"] = status
        fixture.assert_hold("unsupported_change")

    def test_previous_filename_cannot_disguise_a_rename(
        self, fixture: FixtureBuilder
    ) -> None:
        fixture.comparison["files"][0]["previous_filename"] = "EXAMPLE_OLD.py"
        fixture.assert_hold("unsupported_change")

    @pytest.mark.parametrize("side", ["head_tree", "base_tree"])
    @pytest.mark.parametrize(
        ("mode", "kind"),
        [
            ("100755", "blob"),
            ("120000", "blob"),
            ("160000", "commit"),
        ],
    )
    def test_old_and_new_files_must_be_regular_nonexecutable_blobs(
        self, fixture: FixtureBuilder, side: str, mode: str, kind: str
    ) -> None:
        entry = getattr(fixture, side)["tree"][1]
        entry.update(mode=mode, type=kind)
        fixture.assert_hold("non_regular_file")

    @pytest.mark.parametrize("side", ["head_tree", "base_tree"])
    def test_modified_file_must_exist_in_both_trees(
        self, fixture: FixtureBuilder, side: str
    ) -> None:
        getattr(fixture, side)["tree"].pop(1)
        fixture.assert_hold("non_regular_file")

    @pytest.mark.parametrize("changes", [True, 0, -1, "5", 1.5, None])
    def test_line_counts_must_be_positive_integers(
        self, fixture: FixtureBuilder, changes: Any
    ) -> None:
        fixture.comparison["files"][0]["changes"] = changes
        fixture.assert_hold("unmeasured_change")

    @pytest.mark.parametrize("size", [0, 5])
    def test_empty_or_oversized_file_inventory_holds(
        self, fixture: FixtureBuilder, size: int
    ) -> None:
        fixture.comparison["files"] = fixture.comparison["files"] * size
        fixture.assert_hold("change_size")

    def test_line_limit_is_inclusive(self, fixture: FixtureBuilder) -> None:
        fixture.comparison["files"][0]["changes"] = 400
        assert fixture.inspect() == fixture.expected
        fixture.comparison["files"][0]["changes"] = 401
        fixture.assert_hold("change_size")

    @pytest.mark.parametrize("filename", list(WORKFLOW_JOBS))
    @pytest.mark.parametrize(
        ("field", "value"),
        [("path", ".github/workflows/EXAMPLE.yml"), ("state", "disabled_manually")],
    )
    def test_workflow_path_and_enabled_identity(
        self, fixture: FixtureBuilder, filename: str, field: str, value: str
    ) -> None:
        fixture.workflows[filename][field] = value
        fixture.assert_hold("workflow_identity")

    @pytest.mark.parametrize("change", ["empty", "truncated"])
    def test_run_inventory_must_be_nonempty_and_complete(
        self, fixture: FixtureBuilder, change: str
    ) -> None:
        response = fixture.run_lists["ci.yml"]
        if change == "empty":
            response.update(total_count=0, workflow_runs=[])
        else:
            response["total_count"] = 2
        fixture.assert_hold("incomplete_runs")

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("workflow_id", 999),
            ("path", ".github/workflows/EXAMPLE.yml"),
            ("event", "push"),
            ("head_sha", OTHER),
            ("head_repository", {"full_name": "EXAMPLE-FORK/synthetic"}),
            ("id", True),
            ("id", 0),
            ("run_attempt", True),
            ("run_attempt", 0),
        ],
    )
    def test_run_identity_is_not_just_a_green_check_name(
        self, fixture: FixtureBuilder, field: str, value: Any
    ) -> None:
        fixture.run()[field] = value
        fixture.assert_hold("run_identity")

    @pytest.mark.parametrize("change", ["missing", "number", "head", "base"])
    def test_run_pr_revision_must_match_both_commit_shas(
        self, fixture: FixtureBuilder, change: str
    ) -> None:
        run = fixture.run()
        if change == "missing":
            run["pull_requests"] = []
        elif change == "number":
            run["pull_requests"][0]["number"] = NUMBER + 1
        else:
            run["pull_requests"][0][change]["sha"] = OTHER
        fixture.assert_hold("run_revision")

    @pytest.mark.parametrize("older_first", [False, True])
    def test_latest_run_is_selected_by_number_not_response_order_or_id(
        self, fixture: FixtureBuilder, older_first: bool
    ) -> None:
        latest = deepcopy(fixture.run())
        # An older run with a larger ID and attempt must not win selection.
        older = dict(latest, id=999, run_number=9, run_attempt=7)
        runs = [older, latest] if older_first else [latest, older]
        fixture.run_lists["ci.yml"].update(total_count=2, workflow_runs=runs)
        assert fixture.inspect() == fixture.expected
        assert fixture.api.writes == []
        assert not any("/runs/999/" in endpoint for _, endpoint, _ in fixture.api.calls)

    @pytest.mark.parametrize("higher_attempt_first", [False, True])
    def test_latest_attempt_uses_its_own_complete_job_inventory(
        self, fixture: FixtureBuilder, higher_attempt_first: bool
    ) -> None:
        first = deepcopy(fixture.run())
        rerun = dict(first, run_attempt=2)
        runs = [rerun, first] if higher_attempt_first else [first, rerun]
        fixture.run_lists["ci.yml"].update(total_count=2, workflow_runs=runs)
        fixture.api.responses[jobs_endpoint(rerun)] = deepcopy(
            fixture.job_lists["ci.yml"]
        )
        decision = fixture.inspect()
        assert decision == replace(
            fixture.expected, runs=((101, 2), (102, 1), (103, 1))
        )
        assert ("GET", jobs_endpoint(rerun), None) in fixture.api.calls
        assert ("GET", jobs_endpoint(first), None) not in fixture.api.calls
        assert fixture.api.writes == []

    @pytest.mark.parametrize("run_number", [9, 11])
    @pytest.mark.parametrize(
        ("status", "conclusion"),
        [
            ("queued", None),
            ("in_progress", None),
            ("completed", "failure"),
            ("completed", "cancelled"),
            ("completed", "skipped"),
        ],
    )
    def test_green_run_cannot_hide_failed_or_pending_competing_rerun(
        self, fixture: FixtureBuilder, run_number: int, status: str, conclusion: Any
    ) -> None:
        competing = dict(
            fixture.run(),
            id=999,
            run_number=run_number,
            run_attempt=2,
            status=status,
            conclusion=conclusion,
        )
        fixture.run_lists["ci.yml"]["workflow_runs"].append(competing)
        fixture.run_lists["ci.yml"]["total_count"] = 2
        fixture.assert_hold("competing_run_not_successful")

    @pytest.mark.parametrize("change", ["missing", "extra", "duplicate", "truncated"])
    def test_job_names_and_inventory_must_match_exactly(
        self, fixture: FixtureBuilder, change: str
    ) -> None:
        response = fixture.job_lists["ci.yml"]
        jobs = response["jobs"]
        if change == "missing":
            jobs.pop()
        elif change == "extra":
            jobs.append(dict(jobs[0], name="EXAMPLE-extra-job"))
        elif change == "duplicate":
            jobs[1]["name"] = jobs[0]["name"]
        response["total_count"] = len(jobs) + (change == "truncated")
        fixture.assert_hold("job_inventory")

    def test_selective_rerun_cannot_borrow_jobs_from_first_attempt(
        self, fixture: FixtureBuilder
    ) -> None:
        rerun = fixture.run()
        rerun["run_attempt"] = 2
        first_jobs = fixture.job_lists["ci.yml"]["jobs"]
        fixture.api.responses[jobs_endpoint(rerun)] = {
            "total_count": 1,
            "jobs": [deepcopy(first_jobs[0])],
        }
        fixture.assert_hold("job_inventory")

    @pytest.mark.parametrize("filename", list(WORKFLOW_JOBS))
    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("run_id", 999),
            ("head_sha", OTHER),
            ("status", "in_progress"),
            ("conclusion", "skipped"),
            ("conclusion", "neutral"),
            ("conclusion", "failure"),
        ],
    )
    def test_every_required_job_must_succeed_on_the_selected_run_and_head(
        self, fixture: FixtureBuilder, filename: str, field: str, value: Any
    ) -> None:
        fixture.job_lists[filename]["jobs"][0][field] = value
        fixture.assert_hold("job_not_successful")

    @pytest.mark.parametrize("change", ["run-id", "attempt"])
    def test_revalidate_holds_when_successful_run_evidence_changes(
        self, fixture: FixtureBuilder, change: str
    ) -> None:
        decision = fixture.inspect()
        run = fixture.run()
        if change == "run-id":
            run["id"] = 999
            run["run_number"] += 1
        else:
            run["run_attempt"] += 1
        jobs = deepcopy(fixture.job_lists["ci.yml"])
        for job in jobs["jobs"]:
            job["run_id"] = run["id"]
        fixture.api.responses[jobs_endpoint(run)] = jobs
        with pytest.raises(guard.Hold, match=r"^evidence_changed$"):
            guard.revalidate(fixture.api, fixture.policy_path, decision)
        assert fixture.api.writes == []

    def test_revalidate_holds_when_head_moves_even_to_eligible_evidence(
        self, fixture: FixtureBuilder
    ) -> None:
        decision = fixture.inspect()
        fixture.pr["head"]["sha"] = OTHER
        fixture.comparison["commits"][0]["sha"] = OTHER
        for filename in WORKFLOW_JOBS:
            run = fixture.run(filename)
            run["head_sha"] = OTHER
            run["pull_requests"][0]["head"]["sha"] = OTHER
            for job in fixture.job_lists[filename]["jobs"]:
                job["head_sha"] = OTHER
        for endpoint in list(fixture.api.responses):
            if HEAD in endpoint:
                fixture.api.responses[endpoint.replace(HEAD, OTHER)] = (
                    fixture.api.responses.pop(endpoint)
                )
        with pytest.raises(guard.Hold, match=r"^evidence_changed$"):
            guard.revalidate(fixture.api, fixture.policy_path, decision)
        assert fixture.api.writes == []

    def test_revalidate_reloads_policy_after_reinspection(
        self, fixture: FixtureBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decision = fixture.inspect()
        real_inspect = guard.inspect

        def revoke_after_inspection(*args: Any, **kwargs: Any) -> guard.Decision:
            current = real_inspect(*args, **kwargs)
            write_policy(fixture.policy_path, policy_data(enabled=False))
            return current

        monkeypatch.setattr(guard, "inspect", revoke_after_inspection)
        with pytest.raises(guard.Hold, match=r"^delegation_changed$"):
            guard.revalidate(fixture.api, fixture.policy_path, decision)
        assert fixture.api.writes == []

    def test_revalidate_rechecks_expiry_after_reinspection(
        self, fixture: FixtureBuilder, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        decision = fixture.inspect()
        real_inspect = guard.inspect

        def expire_after_inspection(*args: Any, **kwargs: Any) -> guard.Decision:
            current = real_inspect(*args, **kwargs)
            monkeypatch.setattr(guard.datetime, "current", fixture.policy.expires_at)
            return current

        monkeypatch.setattr(guard, "inspect", expire_after_inspection)
        with pytest.raises(guard.Hold, match=r"^delegation_expired$"):
            guard.revalidate(fixture.api, fixture.policy_path, decision)
        assert fixture.api.writes == []


@pytest.fixture
def http_transport(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Replace only the connection boundary; exercise the actual REST client."""
    factory = Mock()
    response = factory.return_value.getresponse.return_value
    response.status = 200
    response.getheader.return_value = None
    response.read.return_value = b"{}"
    monkeypatch.setattr(guard.http.client, "HTTPSConnection", factory)
    return factory


class TestReadOnlyHTTP:
    @pytest.mark.parametrize(
        "endpoint",
        ["/pulls/17", "https://example.invalid/EXAMPLE", "//example.invalid/EXAMPLE"],
    )
    def test_fixed_origin_and_bodyless_get(
        self, http_transport: Mock, endpoint: str
    ) -> None:
        api = guard.GitHub(REPOSITORY, "EXAMPLE-NOT-A-CREDENTIAL")
        assert api.get(endpoint) == {}
        http_transport.assert_called_once_with("api.github.com", timeout=30)
        connection = http_transport.return_value
        args, kwargs = connection.request.call_args
        assert args == ("GET", f"/repos/{REPOSITORY}{endpoint}")
        assert kwargs["body"] is None
        assert kwargs["headers"]["Authorization"] == "Bearer EXAMPLE-NOT-A-CREDENTIAL"
        connection.getresponse.return_value.read.assert_called_once_with(
            guard.MAX_RESPONSE + 1
        )
        connection.close.assert_called_once_with()

    @pytest.mark.parametrize(
        "method", ["PUT", "POST", "PATCH", "DELETE", "HEAD", "get"]
    )
    def test_non_get_rejected_before_connection(
        self, http_transport: Mock, method: str
    ) -> None:
        with pytest.raises(guard.Hold, match=r"^request_method$"):
            guard.GitHub(REPOSITORY, "EXAMPLE").request(method, "/pulls/17")
        http_transport.assert_not_called()

    @pytest.mark.parametrize("body", [{}, {"EXAMPLE": "payload"}])
    def test_even_empty_body_rejected_before_connection(
        self, http_transport: Mock, body: dict[str, Any]
    ) -> None:
        with pytest.raises(guard.Hold, match=r"^request_body$"):
            guard.GitHub(REPOSITORY, "EXAMPLE").request("GET", "/pulls/17", body)
        http_transport.assert_not_called()

    @pytest.mark.parametrize(
        "status", [201, 204, 301, 302, 303, 307, 308, 401, 403, 500]
    )
    def test_redirects_and_errors_denied_without_following_or_reading_body(
        self, http_transport: Mock, status: int
    ) -> None:
        connection = http_transport.return_value
        response = connection.getresponse.return_value
        response.status = status
        response.getheader.return_value = "https://example.invalid/EXAMPLE"
        with pytest.raises(guard.Hold, match=r"^github_request_failed$"):
            guard.GitHub(REPOSITORY, "EXAMPLE").get("/pulls/17")
        assert http_transport.call_count == connection.request.call_count == 1
        response.read.assert_not_called()
        connection.close.assert_called_once_with()

    def test_pagination_denied_without_following_or_reading_body(
        self, http_transport: Mock
    ) -> None:
        connection = http_transport.return_value
        response = connection.getresponse.return_value
        response.getheader.return_value = (
            '<https://example.invalid/EXAMPLE>; rel="next"'
        )
        with pytest.raises(guard.Hold, match=r"^github_pagination$"):
            guard.GitHub(REPOSITORY, "EXAMPLE").get("/pulls/17")
        assert http_transport.call_count == connection.request.call_count == 1
        response.read.assert_not_called()
        connection.close.assert_called_once_with()

    @pytest.mark.parametrize("extra", [0, 1])
    def test_response_size_bound_is_inclusive(
        self, http_transport: Mock, extra: int
    ) -> None:
        connection = http_transport.return_value
        response = connection.getresponse.return_value
        response.read.return_value = b"{}" + b" " * (guard.MAX_RESPONSE - 2 + extra)
        api = guard.GitHub(REPOSITORY, "EXAMPLE")
        if extra:
            with pytest.raises(guard.Hold, match=r"^github_response_size$"):
                api.get("/pulls/17")
        else:
            assert api.get("/pulls/17") == {}
        response.read.assert_called_once_with(guard.MAX_RESPONSE + 1)
        connection.close.assert_called_once_with()


@pytest.fixture
def cli(fixture: FixtureBuilder, monkeypatch: pytest.MonkeyPatch) -> list[str]:
    argv = [
        "merge-guard",
        "--policy",
        str(fixture.policy_path),
        "--trusted-base",
        BASE,
        "--pull-request",
        str(NUMBER),
    ]
    monkeypatch.setattr(guard.sys, "argv", argv)
    monkeypatch.setenv("GH_TOKEN", "EXAMPLE-NOT-A-CREDENTIAL")
    return argv


def assert_cli_hold(capsys: pytest.CaptureFixture[str], reason: str) -> None:
    assert guard.main() == 2
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == {"decision": "hold", "reason": reason}


class TestReadOnlyCLI:
    @pytest.mark.parametrize("enabled", [False, True])
    def test_merge_rejected_before_policy_credentials_or_network_even_if_green(
        self,
        fixture: FixtureBuilder,
        cli: list[str],
        http_transport: Mock,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        enabled: bool,
    ) -> None:
        fixture.set_policy(enabled=enabled)
        if enabled:
            assert fixture.inspect() == fixture.expected
        cli.append("--merge")
        forbidden = Mock(side_effect=AssertionError("Must reject before access"))
        monkeypatch.setattr(guard.Policy, "load", forbidden)
        monkeypatch.setattr(
            guard, "os", SimpleNamespace(environ=SimpleNamespace(get=forbidden))
        )
        monkeypatch.setattr(guard, "inspect", forbidden)
        assert_cli_hold(capsys, "merge_execution_not_implemented")
        forbidden.assert_not_called()
        http_transport.assert_not_called()

    def test_disabled_policy_before_credentials_or_network(
        self,
        fixture: FixtureBuilder,
        cli: list[str],
        http_transport: Mock,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fixture.set_policy(enabled=False)
        forbidden = Mock(side_effect=AssertionError("Disabled policy must stop here"))
        monkeypatch.setattr(
            guard, "os", SimpleNamespace(environ=SimpleNamespace(get=forbidden))
        )
        assert_cli_hold(capsys, "delegation_disabled")
        forbidden.assert_not_called()
        http_transport.assert_not_called()

    def test_missing_credential_before_network(
        self,
        cli: list[str],
        http_transport: Mock,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.delenv("GH_TOKEN")
        assert_cli_hold(capsys, "credential_missing")
        http_transport.assert_not_called()

    def test_lock_option_removed(
        self, cli: list[str], http_transport: Mock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        cli.extend(["--lock", "EXAMPLE-LOCK"])
        with pytest.raises(SystemExit) as exc:
            guard.main()
        assert exc.value.code == 2
        assert "unrecognized arguments: --lock" in capsys.readouterr().err
        http_transport.assert_not_called()

    @pytest.mark.parametrize(
        "payload", [b'{"EXAMPLE-PRIVATE":', b"\xffEXAMPLE-PRIVATE", b"[]", b"null"]
    )
    def test_malformed_json_or_evidence_is_sanitized(
        self,
        cli: list[str],
        http_transport: Mock,
        capsys: pytest.CaptureFixture[str],
        payload: bytes,
    ) -> None:
        connection = http_transport.return_value
        connection.getresponse.return_value.read.return_value = payload
        assert_cli_hold(capsys, "invalid_or_unavailable_evidence")
        connection.close.assert_called_once_with()

    @pytest.mark.parametrize("stage", ["request", "getresponse", "read"])
    @pytest.mark.parametrize("error", [OSError, http.client.HTTPException])
    def test_transport_failures_are_sanitized_closed_and_not_retried(
        self,
        cli: list[str],
        http_transport: Mock,
        capsys: pytest.CaptureFixture[str],
        stage: str,
        error: type[Exception],
    ) -> None:
        connection = http_transport.return_value
        target = connection.getresponse.return_value if stage == "read" else connection
        getattr(target, stage).side_effect = error("EXAMPLE-PRIVATE")
        assert_cli_hold(capsys, "invalid_or_unavailable_evidence")
        assert http_transport.call_count == connection.request.call_count == 1
        connection.close.assert_called_once_with()

    def test_default_reports_eligibility_without_writes_or_candidate_execution(
        self,
        fixture: FixtureBuilder,
        cli: list[str],
        http_transport: Mock,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        fixture.comparison["files"][0]["patch"] = (
            '+raise AssertionError("EXAMPLE-CANDIDATE-MUST-NOT-EXECUTE")'
        )
        connection = http_transport.return_value

        def response_bytes(limit: int) -> bytes:
            assert limit == guard.MAX_RESPONSE + 1
            args, kwargs = connection.request.call_args
            method, path = args
            assert path.startswith(fixture.api.prefix)
            endpoint = path.removeprefix(fixture.api.prefix)
            return json.dumps(
                fixture.api.request(method, endpoint, kwargs["body"])
            ).encode()

        connection.getresponse.return_value.read.side_effect = response_bytes
        # Warm argparse's standard-library helpers before forbidding code loading.
        argparse.ArgumentParser()
        original_open = io.open
        original_import = builtins.__import__

        def only_read_policy(
            file: Any, mode: str = "r", *args: Any, **kwargs: Any
        ) -> Any:
            assert Path(file) == fixture.policy_path
            assert mode == "rb"
            return original_open(file, mode, *args, **kwargs)

        def only_stdlib_imports(name: str, *args: Any, **kwargs: Any) -> Any:
            assert name.partition(".")[0] in guard.sys.stdlib_module_names
            return original_import(name, *args, **kwargs)

        forbidden = Mock(side_effect=AssertionError("No code execution or imports"))
        with monkeypatch.context() as scoped:
            scoped.setattr(io, "open", only_read_policy)
            scoped.setattr(builtins, "open", only_read_policy)
            scoped.setattr(builtins, "exec", forbidden)
            scoped.setattr(builtins, "eval", forbidden)
            scoped.setattr(subprocess, "Popen", forbidden)
            scoped.setattr(guard.os, "system", forbidden)
            scoped.setattr(guard, "revalidate", forbidden)
            scoped.setattr(builtins, "__import__", only_stdlib_imports)
            assert guard.main() == 0
        forbidden.assert_not_called()
        captured = capsys.readouterr()
        assert captured.err == ""
        assert json.loads(captured.out) == {
            "decision": "eligible_not_authorized_by_report",
            "pull_request": NUMBER,
            "head": HEAD,
            "base": BASE,
            "policy_sha256": fixture.policy.digest,
            "runs": [[101, 1], [102, 1], [103, 1]],
        }
        assert fixture.api.writes == []
        assert len(fixture.api.calls) == 15
        assert connection.close.call_count == 15
