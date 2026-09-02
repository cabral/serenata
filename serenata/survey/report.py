"""Aggregate notice shapes across archived packages into a citable report.

The output is deterministic: the same archive produces the same document, byte
for byte. It carries no generation timestamp — provenance is the package ids and
their SHA-256 checksums, which say more about what was surveyed than a clock
does, and keep the committed report diffable.
"""

from __future__ import annotations

import tarfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree.ElementTree import ParseError

from serenata.survey.paths import NoticeRejected, NoticeShape, read_notice

#: eForms notice filenames carry eight digits and a year; legacy TED schema
#: notices carry six. This survey covers eForms only, and counts the rest rather
#: than quietly dropping them.
EFORMS_DIGITS = 8

#: Reuse of TED data is conditioned on acknowledging the source (Commission
#: Decision 2011/833/EU). Generated into every report rather than pasted into
#: the file, so regenerating cannot quietly drop it. See docs/data-reuse.md.
ATTRIBUTION = (
    # The en dash in the year range is the form the official copyright notice
    # uses; this is a legal acknowledgement, so it is reproduced rather than
    # normalised to an ASCII hyphen.
    "© European Union, 1998–2026. Source: [TED](https://ted.europa.eu), the "  # noqa: RUF001
    "Supplement to the Official Journal of the European Union. Reuse authorised "
    "under Commission Decision 2011/833/EU; see "
    "[data-reuse.md](data-reuse.md). This report is a derived measurement — it "
    "carries element paths and frequencies, never field values."
)

#: The licence this project grants over its own measurements (ADR-0004).
#: Distinct from the AGPL-3.0 covering the code: neither grant implies the
#: other, and a dataset with no stated terms is unclear rather than free.
#: Generated for the same reason as ATTRIBUTION above.
LICENCE = (
    "Licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) by "
    "the Serenata Europa project. This grant covers the measurements in this "
    "report; the underlying TED material stays under the terms above, and the "
    "project's code is separately licensed AGPL-3.0-only. See "
    "[ADR-0004](adr/0004-dataset-licence.md)."
)


@dataclass
class Survey:
    """Counts accumulated over every notice surveyed."""

    notices: int = 0
    skipped_legacy: int = 0
    unreadable: int = 0
    packages: list[str] = field(default_factory=list)
    root_types: Counter[str] = field(default_factory=Counter)
    subtypes: Counter[str] = field(default_factory=Counter)
    countries: Counter[str] = field(default_factory=Counter)
    #: path -> notices carrying a value for it
    valued: Counter[str] = field(default_factory=Counter)
    #: path -> notices where it appears only as a container or blank element
    empty: Counter[str] = field(default_factory=Counter)
    #: path -> the country codes of notices that populate it
    path_countries: dict[str, set[str]] = field(default_factory=dict)

    def add(self, shape: NoticeShape) -> None:
        self.notices += 1
        self.root_types[shape.root_type] += 1
        if shape.subtype:
            self.subtypes[shape.subtype] += 1
        for code in shape.countries:
            self.countries[code] += 1
        for path in shape.valued_paths:
            self.valued[path] += 1
            self.path_countries.setdefault(path, set()).update(shape.countries)
        for path in shape.empty_paths:
            self.empty[path] += 1

    def presence(self, path: str) -> float:
        return self.valued[path] / self.notices if self.notices else 0.0


def is_eforms(member_name: str) -> bool:
    """eForms notices are named with eight digits and the year."""
    stem = Path(member_name).name.split("_")[0]
    return stem.isdigit() and len(stem) == EFORMS_DIGITS


def survey_package(package: Path, into: Survey | None = None) -> Survey:
    """Read every eForms notice in an archived daily package.

    Members are streamed out of the tarball rather than extracted to disk; a
    package holds a few thousand notices and roughly 200 MB uncompressed.
    """
    survey = into if into is not None else Survey()
    survey.packages.append(package.name)

    with tarfile.open(package, "r:gz") as archive:
        for member in archive:
            if not member.isfile() or not member.name.endswith(".xml"):
                continue
            if not is_eforms(member.name):
                survey.skipped_legacy += 1
                continue
            handle = archive.extractfile(member)
            if handle is None:  # pragma: no cover - a directory entry named .xml
                survey.unreadable += 1
                continue
            try:
                # Streamed, not read whole: one notice in this package is 40 MB.
                survey.add(read_notice(handle))
            except (ParseError, NoticeRejected):
                # Counted and reported rather than aborting a 3,000-notice run
                # on one bad document. render() surfaces the count.
                survey.unreadable += 1
    return survey


def render(survey: Survey) -> str:
    """Render the survey as the Markdown document the data model cites."""
    lines: list[str] = []
    add = lines.append

    add("# eForms field usage")
    add("")
    add(
        "Which eForms elements notices actually populate, measured rather than "
        "read off the specification. eForms permits far more fields than any "
        "notice uses and usage varies by member state, so a data model designed "
        "from the spec would carry columns that are empty in practice and miss "
        "the ones that matter."
    )
    add("")
    add(
        "Generated by `serenata.survey` from archived packages. Regenerating "
        "against the same archive reproduces this file byte for byte; see "
        "[open-work #2](open-work.md"
        "#2-survey-which-eforms-fields-notices-actually-populate)."
    )
    add("")
    add(f"> {ATTRIBUTION}")
    add(">")
    add(f"> {LICENCE}")
    add("")

    add("## What was surveyed")
    add("")
    add(
        f"- **{survey.notices:,} eForms notices** from "
        f"{len(survey.packages)} daily package(s)"
    )
    for name in sorted(survey.packages):
        add(f"  - `{name}`")
    if survey.skipped_legacy:
        add(
            f"- {survey.skipped_legacy:,} legacy TED schema notices skipped — "
            "this survey covers eForms only"
        )
    if survey.unreadable:
        add(f"- {survey.unreadable:,} members could not be read")
    add("")
    add(
        "Paths are namespace-prefixed element paths, with the varying notice "
        "root normalised to `notice`. They are not eForms BT codes: mapping a "
        "path to its BT code needs the eForms SDK, which this offline survey "
        "does not carry."
    )
    add("")

    add("### Notice types")
    add("")
    add("| Root element | Notices |")
    add("|---|---:|")
    for name, count in sorted(
        survey.root_types.items(), key=lambda kv: (-kv[1], kv[0])
    ):
        add(f"| `{name}` | {count:,} |")
    add("")

    add("### Notice subtypes")
    add("")
    add("| Subtype | Notices |")
    add("|---|---:|")
    for name, count in sorted(survey.subtypes.items(), key=lambda kv: (-kv[1], kv[0])):
        add(f"| {name} | {count:,} |")
    add("")

    add("### Countries named")
    add("")
    add(
        "The countries each notice names, not a single attributed buyer country "
        "— a notice can name organisations in several states. Enough to show "
        "whether a field is used union-wide or only in some member states."
    )
    add("")
    add("| Country | Notices naming it |")
    add("|---|---:|")
    for name, count in sorted(survey.countries.items(), key=lambda kv: (-kv[1], kv[0])):
        add(f"| {name} | {count:,} |")
    add("")

    add("## Field usage")
    add("")
    add(
        "**Present** is the share of notices carrying a non-empty value. "
        "**Countries** is how many distinct countries appear in notices that "
        "populate the path — a low count against a high presence means the "
        "field is concentrated in a few member states."
    )
    add("")
    add("| Present | Countries | Path |")
    add("|---:|---:|---|")
    for path, count in sorted(survey.valued.items(), key=lambda kv: (-kv[1], kv[0])):
        share = 100 * count / survey.notices if survey.notices else 0
        countries = len(survey.path_countries.get(path, set()))
        add(f"| {share:.1f}% | {countries} | `{path}` |")
    add("")

    container_only = sorted(set(survey.empty) - set(survey.valued))
    add("## Never populated")
    add("")
    add(
        f"{len(container_only):,} paths appeared only as containers or blank "
        "elements across every notice surveyed. A path here is either "
        "structural or genuinely unused, and the data model should not carry a "
        "column for it without a reason that is not in this data."
    )
    add("")
    for path in container_only:
        add(f"- `{path}`")
    add("")

    return "\n".join(lines) + "\n"
