"""Narrow source regressions for the proposed ADR-0012 automation boundary.

These check the reviewed literal frontmatter/workflow forms, not a general YAML
parser, editor capability enforcement, filesystem confinement or hosted settings.
Executable HTTP and eligibility checks live in test_merge_guard.py.
"""

from pathlib import Path

import pytest

from tools.merge_guard import Hold, Policy

ROOT = Path(__file__).resolve().parent.parent
ROLES = ("plan", "implement", "review", "evidence")


class TestAutomationBoundary:
    """ADR-0012 profiles and manual probe must not imply an installed executor."""

    @pytest.mark.parametrize("role", ROLES)
    def test_profiles_keep_reviewed_model_neutral_tool_sets(self, role: str) -> None:
        text = (ROOT / f".github/agents/serenata-{role}.agent.md").read_text()
        start, header, body = text.split("---", maxsplit=2)
        assert not start
        lines = header.strip().splitlines()
        tools = "[read, search, edit]" if role == "implement" else "[read, search]"
        assert len(lines) == 5
        assert lines[0] == f"name: serenata-{role}"
        assert lines[1].startswith('description: "Use when ')
        assert lines[1].endswith('"')
        assert lines[2:] == [
            f"tools: {tools}",
            "agents: []",
            "disable-model-invocation: true",
        ]
        assert "../../CLAUDE.md" in body
        assert "../../docs/automation/handoffs.md" in body
        assert "HOLD" in body

    def test_repository_policy_is_disabled_empty_and_expired(self) -> None:
        policy = Policy.load(ROOT / ".github/automation-policy.toml")
        assert policy.enabled is False
        assert not policy.authors and not policy.paths
        assert policy.expires_at.year == 2000
        with pytest.raises(Hold, match=r"^delegation_disabled$"):
            policy.active(policy.expires_at)

    def test_manual_probe_keeps_reviewed_read_only_source_form(self) -> None:
        text = (ROOT / ".github/workflows/merge-review.yml").read_text()
        assert "on:\n  workflow_dispatch:\n" in text
        assert "pull_request_target" not in text
        assert ": write" not in text
        assert "permissions:\n  contents: read\n  actions: read\n" in text
        assert "  pull-requests: read\n" in text
        assert "if: github.ref == 'refs/heads/main'" in text
        assert "ref: ${{ github.workflow_sha }}" in text
        assert "persist-credentials: false" in text
        assert text.count("- uses:") == 1
        assert text.count("run:") == 1
        # Inputs go through environment values, never into executable shell.
        command = text.split("        run: >-\n")[1].strip()
        assert command.split() == [
            "python3",
            "-I",
            "tools/merge_guard.py",
            "--policy",
            ".github/automation-policy.toml",
            "--trusted-base",
            '"$TRUSTED_BASE"',
            "--pull-request",
            '"$PR_NUMBER"',
        ]
        assert "${{" not in command
