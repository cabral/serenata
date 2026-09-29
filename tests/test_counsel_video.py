"""The counsel briefing video and the claims it makes (ADR-0014).

`video/counsel-briefing/` is a Node project and CI does not build it. What CI
can do is hold the parts that would embarrass this project if they drifted: a
number on screen that the docs no longer say, a dependency whose licence the
AGPL cannot take, a name in a public repository that nobody has confirmed, a
word the project does not use about a flagged record.

Rendering is checked by whoever renders: `npm run check` in that directory runs
HyperFrames' own lint, layout and contrast gates.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

REPO = Path(__file__).resolve().parent.parent
VIDEO = REPO / "video" / "counsel-briefing"


def normalise(text: str) -> str:
    """Collapse whitespace, because the docs wrap lines and the video does not."""
    return re.sub(r"\s+", " ", text)


def load(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((VIDEO / name).read_text(encoding="utf-8"))
    return data


def doc_text(relative: str) -> str:
    return normalise((REPO / relative).read_text(encoding="utf-8"))


def facts() -> list[tuple[str, dict[str, str]]]:
    return sorted(load("facts.json")["facts"].items())


def questions() -> list[tuple[str, dict[str, str], str]]:
    found = []
    for gate, entry in load("questions.json")["gates"].items():
        for question in entry["questions"]:
            found.append((f"{gate}/{question['id']}", question, entry["doc"]))
    return found


def video_sources() -> list[Path]:
    """The text a viewer could end up reading or hearing."""
    roots = [VIDEO / "src", VIDEO / "scripts"]
    found = [
        path
        for root in roots
        for path in sorted(root.rglob("*"))
        if path.suffix in {".mjs", ".js", ".css"}
    ]
    found += [VIDEO / name for name in ("questions.json", "facts.json", "README.md")]
    found.append(VIDEO / "SCRIPT.md")
    return found


class TestEverythingOnScreenIsInTheDocs:
    """A figure in a video sent to counsel must be one the repository states."""

    def test_there_are_facts_and_questions_to_check(self) -> None:
        # Guards the parametrised tests below: with nothing loaded they would
        # all pass by having nothing to check.
        assert len(facts()) >= 30
        assert len(questions()) >= 25

    @pytest.mark.parametrize("key,fact", facts(), ids=[key for key, _ in facts()])
    def test_the_fact_is_in_its_source_document(
        self, key: str, fact: dict[str, str]
    ) -> None:
        assert normalise(fact["needle"]) in doc_text(fact["doc"]), (
            f"the video shows {key} ({fact['display']!r}) citing {fact['doc']}, "
            f"which no longer says: {fact['needle']!r}. Update facts.json, or "
            "the document if it is the one that is wrong, and rebuild."
        )

    @pytest.mark.parametrize(
        "label,question,doc", questions(), ids=[label for label, _, _ in questions()]
    )
    def test_the_question_is_in_its_source_instruction(
        self, label: str, question: dict[str, str], doc: str
    ) -> None:
        assert normalise(question["needle"]) in doc_text(doc), (
            f"the video asks question {label} but {doc} no longer contains "
            f"{question['needle']!r}. A question cannot be reworded on screen "
            "without the instruction that counsel is sent saying the same."
        )

    def test_the_video_counts_the_questions_it_says_it_counts(self) -> None:
        # The map scene tells counsel "21 numbered questions". Gate 15 has no
        # questionnaire yet, so it is counted separately as open points.
        gates = load("questions.json")["gates"]
        numbered = len(gates["11"]["questions"]) + len(gates["14"]["questions"])
        assert numbered == 21
        assert len(gates["15"]["questions"]) == 4

    def test_the_check_can_actually_fail(self) -> None:
        # A comparison that cannot report a miss would pass over any drift.
        assert normalise("no such sentence appears in this repository") not in (
            doc_text("README.md")
        )

    def test_the_committed_script_shows_every_question(self) -> None:
        # SCRIPT.md is generated. If a question changed and nobody regenerated
        # it, the reviewer reads a script the video no longer follows.
        script = normalise((VIDEO / "SCRIPT.md").read_text(encoding="utf-8"))
        stale = [
            label
            for label, question, _ in questions()
            if normalise(question["text"]) not in script
        ]
        assert not stale, f"run `npm run script` in {VIDEO}: SCRIPT.md lacks {stale}"


class TestToolchain:
    """ADR-0014: HyperFrames, pinned, with no dependency the AGPL cannot take."""

    #: Licences whose terms the AGPL-3.0 accepts, as they appear in the lockfile.
    #: LGPL-3.0-or-later is sharp's prebuilt libvips, fetched at install time and
    #: never distributed by this repository.
    COMPATIBLE = frozenset(
        {
            "MIT",
            "ISC",
            "0BSD",
            "CC0-1.0",
            "Apache-2.0",
            "BSD-2-Clause",
            "BSD-3-Clause",
            "LGPL-3.0-or-later",
        }
    )

    def package(self) -> dict[str, Any]:
        return load("package.json")

    def test_hyperframes_is_the_only_dependency_and_is_pinned_exactly(self) -> None:
        deps = self.package().get("devDependencies", {})
        assert set(deps) == {"hyperframes"}
        assert re.fullmatch(r"\d+\.\d+\.\d+", deps["hyperframes"]), (
            "an exact version, so a render months later runs the same engine"
        )
        assert not self.package().get("dependencies")

    def test_remotion_and_gsap_are_not_used(self) -> None:
        # Both are free to use and neither is under an open-source licence, which
        # constraint 1 requires of every dependency. ADR-0014 has the reasoning.
        lock = load("package-lock.json")["packages"]
        assert not [name for name in lock if re.search(r"gsap|remotion", name)]
        offenders = [
            path.name
            for path in video_sources()
            if path.suffix in {".mjs", ".js", ".css"}
            and re.search(r"gsap|remotion", path.read_text(encoding="utf-8"), re.I)
        ]
        assert not offenders, f"mentioned in {offenders}"

    def test_every_locked_package_has_a_compatible_licence(self) -> None:
        lock = load("package-lock.json")["packages"]
        incompatible = {}
        for name, entry in lock.items():
            if not name:
                continue
            licence = entry.get("license")
            tokens = set(re.findall(r"[A-Za-z0-9.+-]+", licence or ""))
            tokens -= {"AND", "OR", "WITH"}
            if not licence or not tokens <= self.COMPATIBLE:
                incompatible[name] = licence
        assert not incompatible, (
            "constraint 1: every dependency must be AGPL-3.0 compatible, and "
            f"an unstated licence is not a compatible one: {incompatible}"
        )

    def test_the_licence_check_can_actually_fail(self) -> None:
        assert "GPL-2.0-only" not in self.COMPATIBLE
        assert "SEE LICENSE IN LICENSE.md" not in self.COMPATIBLE

    def test_no_script_publishes_or_renders_on_someone_elses_machine(self) -> None:
        # HyperFrames can upload a project or render it on a hosted service.
        # This project handles legal material and does neither.
        scripts = " ".join(self.package()["scripts"].values())
        assert not re.search(r"\b(publish|cloud|lambda|cloudrun)\b", scripts)

    def test_the_wrapper_switches_off_telemetry_and_vision_uploads(self) -> None:
        wrapper = (VIDEO / "scripts" / "hf.mjs").read_text(encoding="utf-8")
        for setting in (
            "HYPERFRAMES_NO_TELEMETRY: '1'",
            "DO_NOT_TRACK: '1'",
            "GEMINI_API_KEY: ''",
        ):
            assert setting in wrapper

    def test_the_sources_fetch_nothing_at_render_time(self) -> None:
        # Determinism (constraint 4) and the render's own rule: no network for
        # required assets. Fonts are vendored under assets/fonts.
        sources = [p for p in video_sources() if p.suffix in {".mjs", ".js", ".css"}]
        offenders = [
            p.name
            for p in sources
            if re.search(r"https?://", p.read_text(encoding="utf-8"))
        ]
        assert not offenders, f"external URLs in {offenders}"

    def test_the_vendored_fonts_travel_with_their_licences(self) -> None:
        fonts = VIDEO / "assets" / "fonts"
        assert sorted(p.name for p in fonts.glob("*.woff2"))
        assert sorted(p.name for p in fonts.glob("OFL-*.txt"))


class TestThePublicRepositoryNamesNoOne:
    """Who the video is addressed to stays on the maintainer's machine."""

    def test_the_recipient_file_is_ignored(self) -> None:
        ignored = (VIDEO / ".gitignore").read_text(encoding="utf-8").splitlines()
        assert "/recipient.local.json" in ignored

    def test_the_committed_example_names_no_one(self) -> None:
        example = load("recipient.example.json")
        assert example
        assert all(value == "" for value in example.values())

    def test_recordings_and_renders_are_not_committed(self) -> None:
        ignored = (VIDEO / ".gitignore").read_text(encoding="utf-8")
        assert "/out/" in ignored
        assert "/assets/vo/*" in ignored


class TestTheWordsAreTheProjectsWords:
    """CLAUDE.md constraint 3 and the communication rules, applied to the video."""

    FORBIDDEN = re.compile(
        r"\b(corrupt\w*|fraud\w*|guilty|bribe\w*|kickback\w*|suspect\w*|scandal\w*|rigged)\b",
        re.I,
    )

    def test_no_flagged_record_is_called_what_the_project_never_calls_one(
        self,
    ) -> None:
        found = []
        for path in video_sources():
            for number, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if self.FORBIDDEN.search(line):
                    found.append(f"{path.relative_to(REPO)}:{number}")
        assert not found, f"words the project does not use: {found}"

    def test_the_word_check_can_actually_fail(self) -> None:
        assert self.FORBIDDEN.search("this buyer was fraudulent")
        assert not self.FORBIDDEN.search("a statistical anomaly")

    def test_the_independence_statement_is_on_screen(self) -> None:
        # The look is borrowed from serenata.ai, so the disclaimer the README
        # carries has to be in the video as well.
        script = (VIDEO / "SCRIPT.md").read_text(encoding="utf-8")
        assert (
            "Not affiliated with, endorsed by, or run by Open Knowledge Brasil"
            in script
        )

    def test_no_flag_is_shown_with_a_real_value(self) -> None:
        # The example flag on screen names its fields and leaves the values blank;
        # a plausible-looking number there would read as a finding (CLAUDE.md).
        script = (VIDEO / "SCRIPT.md").read_text(encoding="utf-8")
        assert "What a flag carries" in script
        assert not re.search(r"bid count\s+\d", script)
