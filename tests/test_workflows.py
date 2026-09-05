"""Narrow CI source checks and executable DCO regressions (ADR-0009).

The lexical checks cover action references and inline uv commands, not YAML
semantics or GitHub's hosted permissions/required checks. Do not grow a partial
YAML parser here. DCO tests execute the marked workflow shell against disposable
synthetic Git histories; no repository hooks, remote access or new dependencies.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path
from textwrap import dedent

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"
NAMES = ("ci", "audit", "contract", "dco")
ACTION_LINE = re.compile(r"^\s*(?:-\s+)?uses:\s*(.+)$", re.MULTILINE)
PINNED_ACTION = re.compile(r"[\w.-]+/[\w./-]+@[0-9a-f]{40}\s+#\s+v\d[\w.-]*")
UV_LINE = re.compile(r"^\s*run:\s*(uv\s+.+)$", re.MULTILINE)


def check_action_pins(text: str) -> None:
    """Reject mutable refs in the workflows' line-oriented action declarations."""
    references = ACTION_LINE.findall(text)
    assert references, "No action declarations checked"
    for reference in references:
        assert PINNED_ACTION.fullmatch(reference), reference


def check_inline_uv_locks(text: str) -> None:
    """Check the inline commands used here, not arbitrary embedded shell code."""
    commands = UV_LINE.findall(text)
    assert commands, "No inline uv commands checked"
    for command in commands:
        tokens = shlex.split(command)
        assert tokens[1] in {"run", "sync"}, command
        assert tokens[2:3] == ["--locked"], command


def check_ci_measurement_gate(text: str) -> None:
    """CI's inline pytest invocation must opt into the pre-merge evidence gate."""
    commands = [
        shlex.split(command)
        for command in UV_LINE.findall(text)
        if shlex.split(command)[:4] == ["uv", "run", "--locked", "pytest"]
    ]
    assert commands, "No CI pytest invocation checked"
    for tokens in commands:
        assert "--require-current-measurements" in tokens[4:], (
            "CI pytest must require current measurements before merge"
        )


def dco_script() -> str:
    """Extract explicitly marked shell, without interpreting the surrounding YAML."""
    text = (WORKFLOWS / "dco.yml").read_text(encoding="utf-8")
    begin = "# BEGIN DCO CHECK (exercised by tests/test_workflows.py)"
    end = "# END DCO CHECK"
    assert text.count(begin) == text.count(end) == 1
    script = dedent(text.split(begin)[1].split(end)[0])
    assert "${{" not in script, "Pass event values through env, not shell source"
    assert script.strip(), "No DCO shell checked"
    return script


class TestWorkflowSource(unittest.TestCase):
    def test_action_references_are_immutable_with_version_comments(self) -> None:
        for name in NAMES:
            with self.subTest(workflow=name):
                check_action_pins((WORKFLOWS / f"{name}.yml").read_text())

    def test_mutable_or_undocumented_action_refs_are_rejected(self) -> None:
        sha = "a" * 40
        for reference in (
            "actions/checkout@v7 # v7",
            "actions/checkout@main # v7",
            "actions/checkout@abcdef0 # v7",
            f"actions/checkout@{sha}",
        ):
            with self.subTest(reference=reference), self.assertRaises(AssertionError):
                check_action_pins(f"      - uses: {reference}\n")
        check_action_pins(f"      - uses: actions/checkout@{sha} # v7\n")

    def test_inline_uv_commands_keep_the_lockfile(self) -> None:
        for name in ("ci", "audit", "contract"):
            with self.subTest(workflow=name):
                check_inline_uv_locks((WORKFLOWS / f"{name}.yml").read_text())

    def test_unlocked_uv_commands_are_rejected(self) -> None:
        for command in ("uv sync", "uv run pytest", "uv run pip-audit"):
            with self.subTest(command=command), self.assertRaises(AssertionError):
                check_inline_uv_locks(f"        run: {command}\n")

    def test_ci_requires_current_measurements(self) -> None:
        check_ci_measurement_gate((WORKFLOWS / "ci.yml").read_text(encoding="utf-8"))

    def test_ci_without_the_premerge_measurement_gate_is_rejected(self) -> None:
        text = (WORKFLOWS / "ci.yml").read_text(encoding="utf-8")
        self.assertEqual(text.count("--require-current-measurements"), 1)
        with self.assertRaisesRegex(AssertionError, "before merge"):
            check_ci_measurement_gate(
                text.replace(" --require-current-measurements", "")
            )
        with self.assertRaisesRegex(AssertionError, "No CI pytest"):
            check_ci_measurement_gate("run: uv run --locked ruff check .\n")


class TestDcoShell(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="serenata-dco-")
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name)
        # Ignore developer Git overrides, signing configuration and hooks.
        self.env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        self.env.update(
            HOME=str(self.repo),
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME="EXAMPLE CONTRIBUTOR",
            GIT_AUTHOR_EMAIL="contributor@example.invalid",
            GIT_COMMITTER_NAME="EXAMPLE CONTRIBUTOR",
            GIT_COMMITTER_EMAIL="contributor@example.invalid",
        )
        self.git(
            "init", "-q", "--initial-branch=main", "--object-format=sha1", "--template="
        )
        self.base = self.commit("Synthetic historical commit without sign-off")

    def git(self, *args: str) -> str:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.hooksPath=/dev/null",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=self.repo,
            env=self.env,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.stdout.strip()

    def commit(self, message: str) -> str:
        self.git("commit", "--allow-empty", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def check_dco(
        self, head: str, *, base: str | None = None, env: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", dco_script()],
            cwd=self.repo,
            env={**self.env, "BASE": self.base if base is None else base, "HEAD": head}
            | (env or {}),
            capture_output=True,
            text=True,
            timeout=10,
        )

    def test_signed_commit_passes_without_checking_historical_base(self) -> None:
        head = self.commit(
            "Synthetic change\n\nSigned-off-by: EXAMPLE CONTRIBUTOR <a@example.invalid>"
        )
        result = self.check_dco(head)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Every commit", result.stdout)

    def test_tabbed_subject_cannot_fake_signoff_or_become_log_commands(self) -> None:
        head = self.commit("Synthetic\tspoofed column\t::warning::UNTRUSTED_SUBJECT")
        result = self.check_dco(head)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(head[:10], result.stdout)
        self.assertNotIn("UNTRUSTED_SUBJECT", result.stdout + result.stderr)

    def test_empty_or_body_only_signoff_is_not_a_trailer(self) -> None:
        for message in (
            "Synthetic change\n\nSigned-off-by:",
            "Synthetic change\n\nSigned-off-by:   ",
            "Synthetic change\n\nSigned-off-by: example\n\nNot a trailer block.",
        ):
            with self.subTest(message=message):
                self.git("checkout", "--detach", self.base)
                result = self.check_dco(self.commit(message))
                self.assertNotEqual(result.returncode, 0)

    def test_signed_tip_does_not_hide_an_unsigned_earlier_commit(self) -> None:
        unsigned = self.commit("Synthetic unsigned change")
        head = self.commit("Synthetic signed tip\n\nSigned-off-by: EXAMPLE CONTRIBUTOR")
        result = self.check_dco(head)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(unsigned[:10], result.stdout)
        self.assertNotIn(head[:10], result.stdout)

    def test_invalid_or_missing_commit_ids_fail_closed(self) -> None:
        for invalid in ("", "--all", "$(touch INJECTED)", "f" * 40):
            for field in ("BASE", "HEAD"):
                with self.subTest(value=invalid, field=field):
                    result = self.check_dco(self.base, env={field: invalid})
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Every commit", result.stdout)
        self.assertFalse((self.repo / "INJECTED").exists())

    def test_non_commit_object_id_is_rejected(self) -> None:
        tree = self.git("rev-parse", "HEAD^{tree}")
        for field in ("BASE", "HEAD"):
            with self.subTest(field=field):
                result = self.check_dco(self.base, env={field: tree})
                self.assertNotEqual(result.returncode, 0)

    def test_merge_is_exempt_but_its_unsigned_side_commit_is_not(self) -> None:
        for signed in (True, False):
            with self.subTest(signed=signed):
                self.git("checkout", "-B", "topic", self.base)
                message = "Synthetic topic commit"
                if signed:
                    message += "\n\nSigned-off-by: EXAMPLE CONTRIBUTOR"
                topic = self.commit(message)
                self.git("checkout", "-B", "main", self.base)
                self.commit(
                    "Synthetic main commit\n\nSigned-off-by: EXAMPLE CONTRIBUTOR"
                )
                self.git("merge", "--no-ff", "-m", "Synthetic unsigned merge", "topic")
                result = self.check_dco(self.git("rev-parse", "HEAD"))
                self.assertEqual(result.returncode, 0 if signed else 1, result.stderr)
                if not signed:
                    self.assertIn(topic[:10], result.stdout)

    def test_base_advancing_does_not_require_it_to_be_head_ancestor(self) -> None:
        self.git("checkout", "-b", "topic")
        head = self.commit("Synthetic PR change\n\nSigned-off-by: EXAMPLE CONTRIBUTOR")
        self.git("checkout", "main")
        advanced_base = self.commit("Synthetic upstream commit without sign-off")
        result = self.check_dco(head, base=advanced_base)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_git_failure_is_not_mistaken_for_an_empty_successful_check(self) -> None:
        # Simulate failures after revision validation, in both the range walk
        # and trailer lookup. The wrapper never calls a networked Git command.
        real_git = subprocess.run(
            ["bash", "--noprofile", "--norc", "-c", "command -v git"],
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        bin_dir = self.repo / "bin"
        bin_dir.mkdir()
        wrapper = bin_dir / "git"
        wrapper.write_text(
            '#!/bin/bash\nif [[ "$1" == "$FAIL_GIT_COMMAND" ]]; then exit 42; fi\n'
            f'exec {shlex.quote(real_git)} "$@"\n',
            encoding="utf-8",
        )
        wrapper.chmod(0o700)
        head = self.commit("Synthetic change\n\nSigned-off-by: EXAMPLE CONTRIBUTOR")
        for command in ("rev-list", "show"):
            with self.subTest(command=command):
                result = self.check_dco(
                    head,
                    env={
                        "PATH": f"{bin_dir}{os.pathsep}{self.env['PATH']}",
                        "FAIL_GIT_COMMAND": command,
                    },
                )
                self.assertEqual(result.returncode, 42)
                self.assertNotIn("Every commit", result.stdout)
