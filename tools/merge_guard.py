"""Read-only metadata eligibility checker, outside the pipeline (ADR-0012).

Deploy a reviewed copy and policy outside coding-agent workspaces. No imports,
commands, artifacts, caches or dependencies from the proposed head are executed.
GitHub responses are evidence, never instructions. Refusals contain static codes,
not PR text, paths, credentials or response bodies. No write or merge API;
eligibility reports do not authorize action.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

WORKFLOWS = {
    "ci.yml": {"check (3.12)", "check (3.13)"},
    "dco.yml": {"sign-off"},
    "audit.yml": {"audit"},
}
REQUIRED_CHECKS = set().union(*WORKFLOWS.values())
SHA = re.compile(r"[0-9a-f]{40}")
# This ceiling cannot be broadened by a policy file. Even these executable tests
# require an explicit, task-specific delegation, not a claim that tests are safe.
TEST_SCOPE = {
    "tests/test_eforms_xml_guard.py",
    "tests/test_fetch_archive.py",
    "tests/test_fetch_client.py",
    "tests/test_fetch_packages.py",
}
MAX_RESPONSE = 4 * 1024 * 1024


class Hold(Exception):
    """A static reason why no action may be taken."""


def require(condition: object, code: str) -> None:
    if not condition:
        raise Hold(code)


@dataclass(frozen=True)
class Policy:
    enabled: bool
    repository: str
    base: str
    expires_at: datetime
    authors: tuple[str, ...]
    paths: frozenset[str]
    max_files: int
    max_lines: int
    digest: str

    @classmethod
    def load(cls, path: Path) -> Policy:
        raw = path.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
        require(
            set(data)
            == {
                "enabled",
                "repository",
                "base",
                "expires_at",
                "authors",
                "paths",
                "max_files",
                "max_lines",
            },
            "policy_schema",
        )
        require(type(data["enabled"]) is bool, "policy_schema")
        require(
            isinstance(data["repository"], str)
            and re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", data["repository"]),
            "policy_repository",
        )
        require(data["base"] == "main", "policy_base")
        expiry = data["expires_at"]
        require(
            isinstance(expiry, datetime) and expiry.tzinfo is not None,
            "policy_expiry",
        )
        for field in ("authors", "paths"):
            require(
                isinstance(data[field], list)
                and all(isinstance(item, str) and item for item in data[field])
                and len(set(data[field])) == len(data[field]),
                "policy_schema",
            )
        require(set(data["paths"]) <= TEST_SCOPE, "policy_scope")
        for field, ceiling in (("max_files", 4), ("max_lines", 400)):
            require(
                type(data[field]) is int and 0 < data[field] <= ceiling,
                "policy_limits",
            )
        return cls(
            data["enabled"],
            data["repository"],
            data["base"],
            expiry,
            tuple(data["authors"]),
            frozenset(data["paths"]),
            data["max_files"],
            data["max_lines"],
            hashlib.sha256(raw).hexdigest(),
        )

    def active(self, now: datetime) -> None:
        require(self.enabled, "delegation_disabled")
        require(now < self.expires_at, "delegation_expired")
        require(self.authors and self.paths, "delegation_empty")


class GitHub:
    """Fixed-origin, GET-only REST client: no redirects or response body logging."""

    def __init__(self, repository: str, token: str) -> None:
        self.prefix = f"/repos/{repository}"
        self.token = token

    def request(
        self, method: str, endpoint: str, body: dict[str, Any] | None = None
    ) -> Any:
        require(method == "GET", "request_method")
        require(body is None, "request_body")
        connection = http.client.HTTPSConnection("api.github.com", timeout=30)
        try:
            connection.request(
                "GET",
                self.prefix + endpoint,
                body=None,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "User-Agent": "Serenata-merge-guard",
                },
            )
            response = connection.getresponse()
            require(response.status == 200, "github_request_failed")
            require(
                'rel="next"' not in (response.getheader("Link") or ""),
                "github_pagination",
            )
            payload = response.read(MAX_RESPONSE + 1)
            require(len(payload) <= MAX_RESPONSE, "github_response_size")
            return json.loads(payload)
        finally:
            connection.close()

    def get(self, endpoint: str) -> Any:
        return self.request("GET", endpoint)


@dataclass(frozen=True)
class Decision:
    number: int
    head: str
    base: str
    policy: str
    runs: tuple[tuple[int, int], ...]


def check_protection(protection: dict[str, Any]) -> None:
    """Require classic protection; unknown/ruleset-only configurations hold."""
    require(protection["enforce_admins"]["enabled"] is True, "admin_bypass")
    for setting in ("allow_force_pushes", "allow_deletions"):
        require(protection[setting]["enabled"] is False, "unsafe_protection")
    require(
        protection["required_conversation_resolution"]["enabled"] is True,
        "conversation_resolution",
    )
    status = protection["required_status_checks"]
    require(status["strict"] is True, "stale_branch_allowed")
    checks = status["checks"]
    for name in REQUIRED_CHECKS:
        require(
            any(
                check["context"] == name and check["app_id"] == 15368
                for check in checks
            ),
            "required_check_missing",
        )
    reviews = protection.get("required_pull_request_reviews")
    if reviews:
        bypass = reviews.get("bypass_pull_request_allowances", {})
        require(not any(bypass.values()), "review_bypass")
    # Nonzero review requirements remain authoritative: this controller never
    # approves reviews or bypasses GitHub's merge protection.


def tree_inventory(tree: dict[str, Any]) -> dict[str, Any]:
    """Reject ambiguous or malformed entries before building an inventory."""
    items = tree["tree"]
    require(isinstance(items, list), "invalid_tree")
    entries: dict[str, Any] = {}
    modes = {
        "blob": {"100644", "100755", "120000"},
        "tree": {"040000"},
        "commit": {"160000"},
    }
    for entry in items:
        require(isinstance(entry, dict), "invalid_tree")
        path, kind, mode, sha = (
            entry.get(key) for key in ("path", "type", "mode", "sha")
        )
        require(
            isinstance(path, str)
            and path
            and all(part not in {"", ".", ".."} for part in path.split("/"))
            and "\x00" not in path
            and path not in entries,
            "invalid_tree",
        )
        require(
            isinstance(kind, str)
            and isinstance(mode, str)
            and mode in modes.get(kind, set())
            and isinstance(sha, str)
            and SHA.fullmatch(sha),
            "invalid_tree",
        )
        entries[path] = entry
    return entries


def check_files(
    comparison: dict[str, Any],
    tree: dict[str, Any],
    base_tree: dict[str, Any],
    head: str,
    base: str,
    policy: Policy,
) -> None:
    # Immutable comparison, not the mutable /pulls/N/files view. One commit
    # directly on the trusted base also excludes reverted/out-of-scope history.
    require(
        all(
            type(comparison[field]) is int
            for field in ("behind_by", "ahead_by", "total_commits")
        ),
        "non_linear_change",
    )
    require(
        comparison["status"] == "ahead"
        and comparison["behind_by"] == 0
        and comparison["ahead_by"] == comparison["total_commits"] == 1
        and comparison["merge_base_commit"]["sha"] == base,
        "non_linear_change",
    )
    commits = comparison["commits"]
    require(
        len(commits) == 1
        and commits[0]["sha"] == head
        and [parent["sha"] for parent in commits[0]["parents"]] == [base],
        "non_linear_change",
    )
    files = comparison["files"]
    count = len(files)
    require(type(count) is int and 0 < count <= policy.max_files, "change_size")
    require(
        tree["truncated"] is False and base_tree["truncated"] is False,
        "incomplete_tree",
    )
    entries = tree_inventory(tree)
    old_entries = tree_inventory(base_tree)

    # Independent inventory of changed blobs/modes, including deletions and
    # symlinks. Tree objects themselves change when descendants change.
    def leaves(items: dict[str, Any]) -> dict[str, tuple[str, str]]:
        return {
            path: (entry["mode"], entry["sha"])
            for path, entry in items.items()
            if entry["type"] != "tree"
        }

    old, new = leaves(old_entries), leaves(entries)
    changed = {
        path for path in old.keys() | new.keys() if old.get(path) != new.get(path)
    }
    require(changed == {file["filename"] for file in files}, "incomplete_files")
    seen: set[str] = set()
    lines = 0
    for file in files:
        path = file["filename"]
        require(path in policy.paths and path not in seen, "outside_delegation")
        seen.add(path)
        require(
            file["status"] == "modified" and "previous_filename" not in file,
            "unsupported_change",
        )
        entry = entries.get(path, {})
        require(
            entry.get("type") == "blob" and entry.get("mode") == "100644",
            "non_regular_file",
        )
        previous = old_entries.get(path, {})
        require(
            previous.get("type") == "blob" and previous.get("mode") == "100644",
            "non_regular_file",
        )
        require(
            type(file["changes"]) is int and file["changes"] > 0, "unmeasured_change"
        )
        lines += file["changes"]
    require(lines <= policy.max_lines, "change_size")


def check_runs(
    api: GitHub, number: int, head: str, base: str
) -> tuple[tuple[int, int], ...]:
    evidence = []
    for filename, expected_jobs in WORKFLOWS.items():
        workflow = api.get(f"/actions/workflows/{filename}")
        require(
            workflow["path"] == f".github/workflows/{filename}"
            and workflow["state"] == "active",
            "workflow_identity",
        )
        query = urlencode({"event": "pull_request", "head_sha": head, "per_page": 100})
        response = api.get(f"/actions/workflows/{filename}/runs?{query}")
        runs = response["workflow_runs"]
        require(response["total_count"] == len(runs) and runs, "incomplete_runs")
        # Require every matching run to finish successfully. This conservative
        # rule cannot hide a failed/pending rerun of an older run behind a newer
        # green run. Selective reruns with incomplete inventories also hold.
        require(
            all(
                item["status"] == "completed" and item["conclusion"] == "success"
                for item in runs
            ),
            "competing_run_not_successful",
        )
        run = max(runs, key=lambda item: (item["run_number"], item["run_attempt"]))
        require(
            run["workflow_id"] == workflow["id"]
            and run["path"] == workflow["path"]
            and run["event"] == "pull_request"
            and run["head_sha"] == head
            and run["head_repository"]["full_name"]
            == api.prefix.removeprefix("/repos/"),
            "run_identity",
        )
        require(
            any(
                pr["number"] == number
                and pr["head"]["sha"] == head
                and pr["base"]["sha"] == base
                for pr in run["pull_requests"]
            ),
            "run_revision",
        )
        require(
            run["status"] == "completed" and run["conclusion"] == "success",
            "run_not_successful",
        )
        run_id, attempt = run["id"], run["run_attempt"]
        require(
            type(run_id) is int and type(attempt) is int and run_id > 0 and attempt > 0,
            "run_identity",
        )
        response = api.get(
            f"/actions/runs/{run_id}/attempts/{attempt}/jobs?per_page=100"
        )
        jobs = response["jobs"]
        require(
            response["total_count"] == len(jobs) == len(expected_jobs)
            and {job["name"] for job in jobs} == expected_jobs,
            "job_inventory",
        )
        require(
            all(
                job["run_id"] == run_id
                and job["head_sha"] == head
                and job["status"] == "completed"
                and job["conclusion"] == "success"
                for job in jobs
            ),
            "job_not_successful",
        )
        evidence.append((run_id, attempt))
    return tuple(evidence)


def inspect(
    api: GitHub, policy: Policy, number: int, base: str, now: datetime
) -> Decision:
    policy.active(now)
    require(
        type(number) is int and number > 0 and SHA.fullmatch(base), "request_identity"
    )
    pr = api.get(f"/pulls/{number}")
    require(
        pr["number"] == number
        and pr["state"] == "open"
        and pr["draft"] is False
        and pr["merged"] is False,
        "pr_not_open",
    )
    require(
        pr["base"]["repo"]["full_name"] == policy.repository
        and pr["head"]["repo"]["full_name"] == policy.repository,
        "fork_or_repository",
    )
    require(
        pr["base"]["ref"] == policy.base and pr["base"]["sha"] == base, "base_changed"
    )
    head = pr["head"]["sha"]
    require(
        isinstance(head, str) and SHA.fullmatch(head) and head != base, "head_identity"
    )
    require(pr["user"]["login"] in policy.authors, "author_not_delegated")
    require(
        pr["mergeable"] is True and pr["mergeable_state"] == "clean", "not_mergeable"
    )
    branch = api.get(f"/branches/{quote(policy.base, safe='')}")
    require(
        branch["protected"] is True and branch["commit"]["sha"] == base,
        "unprotected_or_stale_base",
    )
    check_protection(api.get(f"/branches/{quote(policy.base, safe='')}/protection"))
    comparison = api.get(f"/compare/{base}...{head}")
    tree = api.get(f"/git/trees/{head}?recursive=1")
    base_tree = api.get(f"/git/trees/{base}?recursive=1")
    check_files(comparison, tree, base_tree, head, base, policy)
    runs = check_runs(api, number, head, base)
    return Decision(number, head, base, policy.digest, runs)


def revalidate(api: GitHub, policy_path: Path, decision: Decision) -> Decision:
    """Recheck policy and live evidence without writing or authorizing action."""
    policy = Policy.load(policy_path)
    require(policy.digest == decision.policy, "delegation_changed")
    current = inspect(api, policy, decision.number, decision.base, datetime.now(UTC))
    require(current == decision, "evidence_changed")
    latest = Policy.load(policy_path)
    require(latest.digest == decision.policy, "delegation_changed")
    latest.active(datetime.now(UTC))
    return current


def run(args: argparse.Namespace) -> None:
    require(not args.merge, "merge_execution_not_implemented")
    policy = Policy.load(args.policy)
    policy.active(datetime.now(UTC))
    token = os.environ.get("GH_TOKEN", "")
    require(token, "credential_missing")
    api = GitHub(policy.repository, token)
    decision = inspect(
        api, policy, args.pull_request, args.trusted_base, datetime.now(UTC)
    )
    print(
        json.dumps(
            {
                "decision": "eligible_not_authorized_by_report",
                "pull_request": decision.number,
                "head": decision.head,
                "base": decision.base,
                "policy_sha256": decision.policy,
                "runs": decision.runs,
            },
            sort_keys=True,
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--trusted-base", required=True)
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument(
        "--merge",
        action="store_true",
        help="Rejected legacy flag; merge execution is not implemented",
    )
    args = parser.parse_args()
    try:
        run(args)
        return 0
    except Hold as exc:
        print(json.dumps({"decision": "hold", "reason": str(exc)}))
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        AttributeError,
        RecursionError,
        http.client.HTTPException,
    ):
        print(
            json.dumps(
                {"decision": "hold", "reason": "invalid_or_unavailable_evidence"}
            )
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
