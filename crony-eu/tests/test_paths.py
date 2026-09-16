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


class TestSnapshots:
    """How `crony stage` finds its input without asking what day it is."""

    def make(self, root: Path, *names: str) -> Layout:
        layout = Layout(root)
        for name in names:
            layout.raw("fr-rne-elus", name).mkdir(parents=True)
        return layout

    def test_none_fetched_yet(self, tmp_path: Path) -> None:
        assert Layout(tmp_path).snapshots("fr-rne-elus") == []
        assert Layout(tmp_path).latest_snapshot("fr-rne-elus") is None

    def test_they_come_back_oldest_first(self, tmp_path: Path) -> None:
        layout = self.make(tmp_path, "2026-09-16", "2026-08-01", "2026-09-02")

        assert layout.snapshots("fr-rne-elus") == [
            "2026-08-01",
            "2026-09-02",
            "2026-09-16",
        ]

    def test_the_latest_is_the_most_recent_date(self, tmp_path: Path) -> None:
        # ISO dates sort lexically the way they sort chronologically, which is
        # the whole reason the directory is named one.
        layout = self.make(tmp_path, "2026-09-16", "2026-08-01")

        assert layout.latest_snapshot("fr-rne-elus") == "2026-09-16"

    def test_a_stray_file_is_not_a_snapshot(self, tmp_path: Path) -> None:
        layout = self.make(tmp_path, "2026-09-16")
        (tmp_path / "raw" / "fr-rne-elus" / "notes.txt").write_text(
            "", encoding="utf-8"
        )

        assert layout.snapshots("fr-rne-elus") == ["2026-09-16"]

    def test_one_source_does_not_see_another(self, tmp_path: Path) -> None:
        layout = self.make(tmp_path, "2026-09-16")

        assert layout.snapshots("fr-decp") == []
