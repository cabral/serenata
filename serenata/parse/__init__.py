"""Stage 2: eForms and legacy-TED XML into typed intermediate records.

Runs offline against the archived raw files. Notices from late 2024 onward
are eForms (UBL-based XML); earlier ones use the legacy TED schemas. Source
fields that could contain a natural person's name (contact persons, sole
traders) are dropped here, at ingestion — they never reach intermediate
records or storage. Every record keeps its source notice ID.

**Legacy notices are refused, not parsed.** The mapping from legacy TED
elements into the data model has never been measured, because no archived
package contains a legacy notice, and guessing which of them can carry a
person's name is exactly the guess constraint 2 exists to forbid. A legacy
notice raises with a message saying so. Open-work #3 is the work that lifts it.

What parse produces is the notice's structure with its personal data gone —
values keyed by the element path they came from (ADR-0005), grouped by the
repeatable container they belong to. Building the relational model out of those
records is normalise's job, against `docs/data-model.md`.

    from serenata.parse import parse_package
    for outcome in parse_package(Path("data/raw/ted/daily/2026/202600157.tar.gz")):
        if isinstance(outcome, Unparsed):
            ...  # a notice that could not be read, named and counted
        else:
            ...  # its records
"""

from serenata.parse.notice import read_notice
from serenata.parse.packages import Outcome, Unparsed, parse_package
from serenata.parse.personal_data import (
    is_dropped,
    suppressed_for_natural_person,
)
from serenata.parse.records import (
    CONTAINERS,
    NOTICE,
    Field,
    ParsedNotice,
    Record,
)

__all__ = [
    "CONTAINERS",
    "NOTICE",
    "Field",
    "Outcome",
    "ParsedNotice",
    "Record",
    "Unparsed",
    "is_dropped",
    "parse_package",
    "read_notice",
    "suppressed_for_natural_person",
]
