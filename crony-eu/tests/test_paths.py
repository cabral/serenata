# SPDX-License-Identifier: AGPL-3.0-only
"""The data directory layout, and the two properties the pipeline leans on."""

from __future__ import annotations

from pathlib import Path

from crony_eu.paths import Layout


class TestLayout:
    def test_every_directory_hangs_off_the_root(self, tmp_path: Path) -> None:
        layout = Layout(tmp_path)
        produced = [
            layout.raw("fr-decp", "2026-09-16"),
            layout.manifest("fr-decp", "2026-09-16"),
            layout.staged("fr-decp", "2026-09-16"),
            layout.reports(),
            layout.judgments(),
            layout.flags("F1", "abc123"),
            layout.case("deadbeef0000"),
            layout.logs(),
        ]
        assert all(tmp_path in path.parents for path in produced)

    def test_the_snapshot_is_given_not_guessed(self, tmp_path: Path) -> None:
        # The property constraint 4 rests on: no stage asks the time, so the
        # same inputs write the same paths on any day.
        first = Layout(tmp_path).raw("fr-decp", "2026-09-16")
        second = Layout(tmp_path).raw("fr-decp", "2026-09-16")
        assert first == second
        assert "2026-09-16" in str(first)

    def test_the_manifest_sits_inside_its_snapshot(self, tmp_path: Path) -> None:
        layout = Layout(tmp_path)
        snapshot = layout.raw("fr-decp", "2026-09-16")
        assert layout.manifest("fr-decp", "2026-09-16").parent == snapshot

    def test_reports_cannot_collide_with_a_source(self, tmp_path: Path) -> None:
        # `_reports` lives under `staged/` beside the sources. No source is
        # called `_reports`, and the leading underscore is why.
        layout = Layout(tmp_path)
        assert layout.reports().name.startswith("_")
        assert layout.reports().parent == layout.staged("x", "y").parent.parent


class TestCreate:
    def test_it_makes_the_fixed_directories(self, tmp_path: Path) -> None:
        Layout(tmp_path).create()

        for name in ("raw", "staged", "matched", "flags", "cases", "logs"):
            assert (tmp_path / name).is_dir()
        assert (tmp_path / "staged" / "_reports").is_dir()

    def test_it_is_safe_to_run_twice(self, tmp_path: Path) -> None:
        layout = Layout(tmp_path)
        layout.create()
        (tmp_path / "raw" / "keep-me").mkdir()

        layout.create()

        assert (tmp_path / "raw" / "keep-me").is_dir(), (
            "a rerun destroyed existing data"
        )
