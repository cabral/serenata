"""What constraint 2 removes, measured rather than asserted.

`docs/personal-data.md` says which fields carry a natural person's data and
`serenata/parse/personal_data.py` drops them before they reach a record. What
neither says is **how much that costs**, and the question comes up every time
someone asks why the pipeline does not simply mirror TED and filter later: the
data is already public, so what is actually lost by dropping it early?

This answers it from the archive. It walks the raw notices *before* the drop is
applied, counts every leaf the drop list rejects, and — the part that matters —
checks each rejected path against the columns of `serenata.normalise.model`.

The answer for OJ S 157/2026 is that **no dropped path is a modelled column**.
Every one is a contact block, a beneficial owner, a named committee member, or a
free-text privacy reason. Core classifiers read structured fields only
(constraint 5), so a pipeline that kept this data would compute the same flags
from it — which is the measurement that makes "we keep it for analysis" fail the
purpose test under data minimisation, not merely the one that makes the
comparison uninteresting.

One real cost survives that argument and the report names it:
`efac:UltimateBeneficialOwner`. Beneficial ownership is genuinely analysable and
genuinely gone. It is person-level data by definition, so recovering it is a
decision for counsel rather than a schema change — see docs/open-work.md.

**Counts and paths only, never values.** The elements being counted are the ones
that carry names, e-mail addresses and telephone numbers; a report that printed
them would publish exactly what it exists to show has been removed.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO
from xml.etree.ElementTree import ParseError

from serenata.eforms import (
    LEGACY_ROOT,
    ROOT,
    NoticeRejected,
    is_eforms_root,
    stream_elements,
)
from serenata.normalise.model import TABLES
from serenata.packages import notice_members
from serenata.parse.personal_data import DROPPED_SEGMENTS, is_dropped
from serenata.survey.report import ATTRIBUTION, LICENCE

#: The subtree whose loss is a capability trade rather than a free win.
BENEFICIAL_OWNER = "efac:UltimateBeneficialOwner"


def modelled_paths() -> frozenset[str]:
    """Every absolute element path the normalised model reads a column from."""
    found: set[str] = set()
    for table in TABLES:
        for column in table.columns:
            if not column.structural and column.path:
                found.add(f"{table.container}/{column.path}")
    return frozenset(found)


@dataclass
class Dropped:
    """How much the drop list removes, and from where."""

    packages: list[tuple[str, str]] = field(default_factory=list)
    notices: int = 0
    #: Notices in a format whose drop list does not exist yet (legacy TED).
    unmeasured: int = 0
    unreadable: int = 0
    leaves: int = 0
    #: Absolute path -> leaves removed
    removed: Counter[str] = field(default_factory=Counter)

    @property
    def total_removed(self) -> int:
        return sum(self.removed.values())

    def by_subtree(self) -> Counter[str]:
        """Removals grouped by the drop rule that rejected them."""
        grouped: Counter[str] = Counter()
        for path, count in self.removed.items():
            segments = path.split("/")
            rule = next(
                (s for s in segments if s in DROPPED_SEGMENTS),
                "efac:FieldsPrivacy/efbc:ReasonDescription",
            )
            grouped[rule] += count
        return grouped

    def collisions_with_the_model(self) -> list[str]:
        """Dropped paths that a modelled column also reads.

        Must be empty. A path in both would mean the model declares a column the
        parse stage refuses to fill — a contradiction between two documents that
        are each meant to be authoritative.
        """
        modelled = modelled_paths()
        return sorted(path for path in self.removed if path in modelled)


def checksum(package: Path) -> str:
    digest = hashlib.sha256()
    with package.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _count_notice(handle: IO[bytes], into: Dropped) -> None:
    """Count one notice's leaves, reading the raw XML before the drop.

    Paths are rooted at `ROOT` — the same vocabulary `personal_data.is_dropped`
    matches against — rather than at the document's own root element, so a
    contract notice and an award notice report the same path for the same field.

    Raises `NoticeRejected` for a format whose drop list does not exist, which
    is the legacy TED case. Counting zero removals for a legacy notice would
    report the drop list as complete over data it has never been written for.
    """
    stack: list[str] = [ROOT]
    children: list[int] = [0]
    root_seen = False
    for event, qname, element in stream_elements(handle):
        if event == "start":
            if not root_seen:
                # The document's own root stands in for `ROOT`, so a contract
                # notice and an award notice report the same path for a field.
                root_seen = True
                name = element.tag.rpartition("}")[2]
                if not is_eforms_root(element.tag):
                    raise NoticeRejected(
                        f"{'legacy TED' if name == LEGACY_ROOT else name} notice: "
                        "no drop list has been written for this format, so "
                        "nothing here can be measured (open-work #3)"
                    )
                continue
            children[-1] += 1
            stack.append(qname)
            children.append(0)
            continue
        if len(stack) == 1:
            continue
        if children[-1] == 0:
            into.leaves += 1
            path = "/".join(stack)
            if is_dropped(path):
                into.removed[path] += 1
        stack.pop()
        children.pop()


def dropped_package(package: Path, into: Dropped | None = None) -> Dropped:
    """Measure one archived package, reading raw notices before the drop."""
    found = into if into is not None else Dropped()
    found.packages.append((package.name, checksum(package)))

    for _name, handle in notice_members(package):
        try:
            _count_notice(handle, found)
        except NoticeRejected:
            found.unmeasured += 1
            continue
        except ParseError:
            found.unreadable += 1
            continue
        found.notices += 1
    return found


def render(found: Dropped) -> str:
    """Render the measurement as the Markdown document the docs cite."""
    lines: list[str] = []
    add = lines.append

    add("# What the personal-data drop removes")
    add("")
    add(
        "[`personal-data.md`](personal-data.md) says which fields carry a "
        "natural person's data; this says how much of the archive that is and "
        "what analysis it costs. Generated by "
        "`python -m serenata.survey --report dropped`; regenerating against the "
        "same packages reproduces this file byte for byte."
    )
    add("")
    add(
        "**Paths and counts only.** No value appears here. The elements counted "
        "are the ones carrying names, e-mail addresses and telephone numbers, "
        "so a report that printed them would publish what it exists to show has "
        "been removed."
    )
    add("")
    add(f"> {ATTRIBUTION}")
    add(">")
    add(f"> {LICENCE}")
    add("")

    add("## What was measured")
    add("")
    add(f"- **{found.notices:,} eForms notices** from {len(found.packages)} package(s)")
    for name, digest in sorted(found.packages):
        add(f"  - `{name}` — `sha256:{digest}`")
    if found.unmeasured:
        add(
            f"- {found.unmeasured:,} notices in a format whose drop list does "
            "not exist yet, so nothing was measured for them"
        )
    if found.unreadable:
        add(f"- {found.unreadable:,} notices could not be read")
    add("")

    share = 100 * found.total_removed / found.leaves if found.leaves else 0.0
    add(
        f"**{found.total_removed:,} of {found.leaves:,} leaf elements "
        f"({share:.1f}%) are dropped before they reach a record.**"
    )
    add("")

    add("## By the rule that rejected them")
    add("")
    add("| Rule | Leaves removed |")
    add("|---|---:|")
    for rule, count in sorted(found.by_subtree().items(), key=lambda kv: -kv[1]):
        add(f"| `{rule}` | {count:,} |")
    add("")

    add("## What this costs the analysis")
    add("")
    collisions = found.collisions_with_the_model()
    if collisions:
        add(
            "**A dropped path is also a modelled column.** That is a "
            "contradiction between `personal-data.md` and `data-model.md`, and "
            "one of them is wrong:"
        )
        add("")
        for path in collisions:
            add(f"- `{path}`")
    else:
        add(
            "**No dropped path is a column of the normalised model.** Every "
            "removal is a contact block, a beneficial owner, a named committee "
            "member, or a free-text privacy reason — never an amount, a date, a "
            "code, a bid count or a company identifier. Core classifiers read "
            "structured fields only (constraint 5), so a pipeline that kept this "
            "data would compute the same flags from it."
        )
    add("")
    owner = sum(
        count for path, count in found.removed.items() if BENEFICIAL_OWNER in path
    )
    if owner:
        add(
            f"**The exception worth naming: {owner:,} of the removals are "
            f"`{BENEFICIAL_OWNER}`.** Beneficial ownership is genuinely "
            "analysable — shell structures and conflicts of interest are read "
            "from it — and it is genuinely gone. A beneficial owner is a natural "
            "person by definition, so this is a capability the project has "
            "traded away deliberately rather than a gap to be closed by a schema "
            "change. `open-work.md` carries it as a decision for counsel."
        )
        add("")

    add("## Every dropped path")
    add("")
    add("| Leaves | Path |")
    add("|---:|---|")
    for path, count in sorted(found.removed.items(), key=lambda kv: (-kv[1], kv[0])):
        add(f"| {count:,} | `{path}` |")
    add("")
    return "\n".join(lines) + "\n"
