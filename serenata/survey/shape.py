"""Measure the dataset the pipeline produces, as a citable document.

`paths.py` measures the notices going in. This measures the rows coming out:
how many, how populated, and how often the things this project warns about
actually occur. The numbers it reports were, until it existed, measured by hand
with scripts that were never committed — true when written, and silent when they
stopped being.

Four of them are worth a reader's attention, and all four are things the project
says about its own output rather than about procurement:

- **Statuses.** Every value column carries one (ADR-0006), and the distribution
  is how a classifier author sees what a field's population really is. A column
  that is 90% `absent` is not a column to build a base rate on without saying so.
- **The `-1` sentinel.** eForms publishes a withheld value rather than omitting
  it. Counting them says how much of the dataset would be misread by anything
  that casts an amount without reading its status.
- **Contact-shaped values.** The personal-data drop list matches paths, and
  cannot catch a publisher who types an address into a field that is not a
  contact field. This counts how often that happened. **It reports counts and
  never values** — printing them would publish the personal data the count
  exists to measure.
- **Key uniqueness.** Every table claims a key. The notice UUID looked like one
  and was not; the check is cheap and the claim is load-bearing.

Deterministic, per constraint 4: counts from archived input, sorted output, no
clock. The same archive produces the same document byte for byte.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from serenata.normalise import TABLES, Status, notice_rows
from serenata.normalise.model import Kind, Table
from serenata.parse import Unparsed, parse_package
from serenata.survey.report import ATTRIBUTION, LICENCE

#: What eForms publishes in place of a value the publisher withheld. Not a
#: price, not a count: `docs/known-issues.md` has the measured cases.
SENTINEL = "-1"

#: An address-shaped value. Deliberately loose — the question is whether
#: something address-shaped reached a column that should not hold one, and a
#: strict grammar would answer a different question.
_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")

#: A local part shaped like a person's own address rather than an office's:
#: `firstname.lastname@`. Counted separately because it is the case with legal
#: weight.
_PERSONAL_LOCAL_PART = re.compile(r"^[a-zA-Z]{2,}[._][a-zA-Z]{2,}$")


@dataclass
class Shape:
    """What the rows of one or more packages look like, in counts only."""

    packages: list[tuple[str, str]] = field(default_factory=list)
    notices: int = 0
    unparsed: int = 0
    unnormalised: int = 0
    #: table -> rows written
    rows: Counter[str] = field(default_factory=Counter)
    #: "table.column" -> status -> rows
    statuses: dict[str, Counter[str]] = field(default_factory=dict)
    #: "table.column" -> values that are exactly the withheld sentinel
    sentinels: Counter[str] = field(default_factory=Counter)
    #: "table.column" -> values carrying something address-shaped
    contact_shaped: Counter[str] = field(default_factory=Counter)
    #: the subset of those shaped like a person's own address
    personal_shaped: Counter[str] = field(default_factory=Counter)
    #: table -> rows sharing a key with another row
    key_collisions: Counter[str] = field(default_factory=Counter)
    #: notice UUIDs carrying more than one publication
    repeated_notice_ids: int = 0
    #: every key seen per table, to find collisions without holding the rows
    _keys: dict[str, Counter[tuple[str, ...]]] = field(default_factory=dict)
    _notice_ids: Counter[str] = field(default_factory=Counter)

    def add(self, rows: dict[str, list[dict[str, object]]]) -> None:
        """Fold one notice's rows in."""
        self.notices += 1
        for table in TABLES:
            for row in rows[table.name]:
                self.rows[table.name] += 1
                self._add_key(table, row)
                for column in table.columns:
                    if column.structural:
                        continue
                    self._add_column(table, column.name, column.kind, row)
        for row in rows["notice"]:
            self._notice_ids[str(row["source_notice_id"])] += 1

    def _add_key(self, table: Table, row: dict[str, object]) -> None:
        key = tuple(str(row.get(name)) for name in table.key)
        self._keys.setdefault(table.name, Counter())[key] += 1

    def _add_column(
        self, table: Table, name: str, kind: Kind, row: dict[str, object]
    ) -> None:
        where = f"{table.name}.{name}"
        status = row.get(f"{name}_status")
        if isinstance(status, str):
            self.statuses.setdefault(where, Counter())[status] += 1

        value = row.get(name)
        values = value if kind is Kind.SET and isinstance(value, list) else [value]
        for item in values:
            if not isinstance(item, str):
                continue
            if item == SENTINEL:
                self.sentinels[where] += 1
            for match in _EMAIL.findall(item):
                self.contact_shaped[where] += 1
                if _PERSONAL_LOCAL_PART.match(match.split("@")[0]):
                    self.personal_shaped[where] += 1

    def finish(self) -> None:
        """Derive what could only be known once every row had been seen."""
        for name, keys in self._keys.items():
            extra = sum(count - 1 for count in keys.values() if count > 1)
            if extra:
                self.key_collisions[name] = extra
        self.repeated_notice_ids = sum(
            1 for count in self._notice_ids.values() if count > 1
        )


def checksum(package: Path) -> str:
    """The SHA-256 of a package, so the report says what it measured."""
    digest = hashlib.sha256()
    with package.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def shape_package(package: Path, into: Shape | None = None) -> Shape:
    """Normalise one archived package in memory and measure the rows."""
    shape = into if into is not None else Shape()
    shape.packages.append((package.name, checksum(package)))
    for outcome in parse_package(package):
        if isinstance(outcome, Unparsed):
            shape.unparsed += 1
            continue
        try:
            shape.add(notice_rows(outcome))
        except LookupError:
            # Counted, not hidden: a notice the model cannot map is a fact
            # about the model, and a report that dropped it would say the
            # dataset was complete.
            shape.unnormalised += 1
    return shape


def render(shape: Shape) -> str:
    """Render the measurement as the Markdown document the docs cite."""
    lines: list[str] = []
    add = lines.append

    add("# Dataset shape")
    add("")
    add(
        "What the normalise stage produces, measured rather than remembered: "
        "how many rows, how populated each column is, and how often the things "
        "this project warns about actually occur. Generated by "
        "`python -m serenata.survey --report shape`; regenerating against the "
        "same packages reproduces this file byte for byte."
    )
    add("")
    add(
        "**Counts only.** No field value appears in this document, which is "
        "what lets it measure address-shaped values in columns that should not "
        "hold them without republishing them."
    )
    add("")
    add(f"> {ATTRIBUTION}")
    add(">")
    add(f"> {LICENCE}")
    add("")

    add("## What was measured")
    add("")
    add(f"- **{shape.notices:,} notices** from {len(shape.packages)} package(s)")
    for name, digest in sorted(shape.packages):
        add(f"  - `{name}` — `sha256:{digest}`")
    if shape.unparsed:
        add(f"- {shape.unparsed:,} members could not be parsed")
    if shape.unnormalised:
        add(f"- {shape.unnormalised:,} notices could not be mapped into the model")
    add("")

    add("## Rows")
    add("")
    add("| Table | Rows | Rows sharing a key |")
    add("|---|---:|---:|")
    for table in TABLES:
        collisions = shape.key_collisions[table.name]
        add(f"| `{table.name}` | {shape.rows[table.name]:,} | {collisions:,} |")
    add("")
    add(
        "**Rows sharing a key** must be zero: every table is keyed on the "
        "publication plus what identifies the row within it. The notice UUID "
        "looked like a key and is not — "
        f"**{shape.repeated_notice_ids:,}** notice UUIDs here carry more than "
        "one publication."
    )
    add("")

    add("## Withheld values published as a sentinel")
    add("")
    if shape.sentinels:
        add(
            "eForms publishes a withheld value rather than omitting it. A column "
            "below holds that sentinel, and anything casting it to a number "
            "reads a lawful deferral as a negative quantity."
        )
        add("")
        add("| Column | Values that are `-1` |")
        add("|---|---:|")
        for where, count in sorted(shape.sentinels.items()):
            add(f"| `{where}` | {count:,} |")
    else:
        add("No column in these packages carries the `-1` sentinel.")
    add("")

    add("## Address-shaped values where none belongs")
    add("")
    add(
        "The personal-data drop list matches element paths and cannot catch a "
        "publisher who types a contact address into a field that is not a "
        "contact field. This is how often that happened, by column, with the "
        "subset whose local part is shaped like a person's own address "
        "(`firstname.lastname@`) counted separately."
    )
    add("")
    if shape.contact_shaped:
        add("| Column | Address-shaped | Shaped like a person's |")
        add("|---|---:|---:|")
        for where, count in sorted(shape.contact_shaped.items()):
            add(f"| `{where}` | {count:,} | {shape.personal_shaped[where]:,} |")
    else:
        add("No column in these packages carries an address-shaped value.")
    add("")

    add("## Column population")
    add("")
    add(
        "The share of rows in each status (ADR-0006). `absent` is "
        '"not provided", never "false" and never zero, and a base rate '
        "computed over rows where a field is absent is a base rate over the "
        "wrong denominator."
    )
    add("")
    statuses = [status.value for status in Status]
    add("| Column | Rows | " + " | ".join(statuses) + " |")
    add("|---|---:|" + "---:|" * len(statuses))
    for where in sorted(shape.statuses):
        counts = shape.statuses[where]
        total = sum(counts.values())
        cells = []
        for status in statuses:
            count = counts.get(status, 0)
            cells.append(f"{100 * count / total:.1f}%" if total and count else "—")
        add(f"| `{where}` | {total:,} | " + " | ".join(cells) + " |")
    add("")

    return "\n".join(lines) + "\n"
