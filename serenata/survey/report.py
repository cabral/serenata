"""Aggregate notice shapes across archived packages into a citable report.

The output is deterministic: the same archive produces the same document, byte
for byte. It carries no generation timestamp — provenance is the package ids and
their SHA-256 checksums, which say more about what was surveyed than a clock
does, and keep the committed report diffable.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree.ElementTree import ParseError

from serenata.packages import notice_members
from serenata.survey.paths import (
    NotEForms,
    NoticeRejected,
    NoticeShape,
    read_notice,
)

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
    #: Members whose root element is the legacy TED one. A format this survey
    #: has no vocabulary for, not a document it failed to read.
    skipped_legacy: int = 0
    #: Members that are neither: XML in the package that no reader here claims.
    #: Kept apart from the legacy count because the two ask for different work
    #: — one is open-work #3, the other is a package carrying something nobody
    #: expected.
    not_notices: int = 0
    unreadable: int = 0
    packages: list[str] = field(default_factory=list)
    root_types: Counter[str] = field(default_factory=Counter)
    subtypes: Counter[str] = field(default_factory=Counter)
    countries: Counter[str] = field(default_factory=Counter)
    #: path -> notices carrying a value for it
    valued: Counter[str] = field(default_factory=Counter)
    #: path -> the most times it occurred inside one record, anywhere surveyed.
    #: 1 means the path never repeats within the record that owns it, which is
    #: what a scalar column in the data model requires.
    max_per_record: Counter[str] = field(default_factory=Counter)
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
        for path, times in shape.max_per_record:
            if times > self.max_per_record[path]:
                self.max_per_record[path] = times

    def presence(self, path: str) -> float:
        return self.valued[path] / self.notices if self.notices else 0.0


def survey_package(package: Path, into: Survey | None = None) -> Survey:
    """Read every eForms notice in an archived daily package.

    Which members those are is decided by `read_notice`, from the root element
    each document declares — the parse stage's test, adopted here so the two
    readers of a package cannot disagree about what it contains. This used to
    be read off the filename, and a filename is a claim: an eForms notice
    delivered under a legacy-style name was parsed by one stage and counted as
    skipped by the other.

    Members are streamed out of the tarball rather than extracted to disk; a
    package holds a few thousand notices and roughly 200 MB uncompressed.
    """
    survey = into if into is not None else Survey()
    survey.packages.append(package.name)

    for _name, handle in notice_members(package):
        try:
            # Streamed, not read whole: one notice in this package is 40 MB.
            survey.add(read_notice(handle))
        except NotEForms as rejected:
            # A format rather than a failure, and a cheap one to find: the
            # refusal lands on the first start event, so a member in another
            # format costs one read rather than a walk through its elements.
            if rejected.legacy:
                survey.skipped_legacy += 1
            else:
                survey.not_notices += 1
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
    if survey.not_notices:
        add(
            f"- {survey.not_notices:,} members skipped — XML whose root element "
            "is neither an eForms notice nor a legacy TED one"
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
    add(
        "**Max/record** is the most times the path was seen inside a single "
        "record — a lot, an organisation, a lot result, or the notice itself "
        "for paths outside those. **1 means the path never repeats**, which is "
        "what a scalar column in [`data-model.md`](data-model.md) requires; "
        "anything higher is a set, and a column that stored one of those values "
        "would be storing an arbitrary one. `tests/test_normalise_model.py` "
        "checks the model against this column."
    )
    add("")
    add("| Present | Countries | Max/record | Path |")
    add("|---:|---:|---:|---|")
    for path, count in sorted(survey.valued.items(), key=lambda kv: (-kv[1], kv[0])):
        share = 100 * count / survey.notices if survey.notices else 0
        countries = len(survey.path_countries.get(path, set()))
        add(
            f"| {share:.1f}% | {countries} | {survey.max_per_record[path]} | `{path}` |"
        )
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
