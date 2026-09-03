"""Regenerate `serenata/normalise/sdk_privacy.py` from the eForms SDK.

**This script reaches the network. The pipeline never does.** It is run by hand
when the SDK gains a privacy code, and what it writes is a vendored data file
the normalise stage reads offline (constraint 4, ADR-0008).

    uv run python tools/generate_sdk_privacy.py

What it extracts is one table: the `privacy.code` a publisher writes into
`efac:FieldsPrivacy/efbc:FieldIdentifierCode`, against the field that code
withholds. That relation is the SDK's to state, not ours to infer, which is the
whole reason this file exists rather than a hand-written dictionary.

Two checks run before anything is written, and both fail loudly:

**The versions have to agree.** Notices published on one day declare three
different SDK versions, so a mapping true of only the newest would be wrong for
two thirds of a package. Every version in `VERSIONS` is fetched and compared;
a code whose target moved between them is reported and the file is not written.

**A predicate-stripped path has to stay unique.** The SDK identifies a field by
an XPath that may carry a predicate — `pro-acc` and `dir-awa-jus` are the *same*
element distinguished only by `@listName`. This project's paths carry no
predicates (ADR-0005), so where stripping one merges two SDK fields the code
cannot be resolved to a column here. The generator records which fields collide;
`serenata/normalise/privacy.py` refuses them.

The SDK is published by the Publications Office of the European Union under
CC BY 4.0, which is why the generated file carries an attribution line.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import httpx

#: The SDK versions checked against each other. The first three are the ones
#: real notices declare in `cbc:CustomizationID` — measured across OJ S
#: 157/2026: 1,993 notices on 1.13, 906 on 1.14, 291 on 1.12 — and the last is
#: the newest stable release, so a mapping that has moved since shows up here.
VERSIONS = ("1.12.0", "1.13.3", "1.14.2", "1.15.1")

SOURCE = (
    "https://raw.githubusercontent.com/OP-TED/eForms-SDK/{version}/fields/fields.json"
)

OUTPUT = (
    Path(__file__).resolve().parent.parent / "serenata" / "normalise" / "sdk_privacy.py"
)

USER_AGENT = "serenata-europa (+https://github.com/cabral/serenata)"

#: An XPath predicate: `cac:Foo[cbc:Bar/@listName='x']/cbc:Baz`.
PREDICATE = re.compile(r"\[[^\]]*\]")

HEADER = '''"""Which eForms privacy code withholds which field. Generated — do not edit.

Regenerate with `uv run python tools/generate_sdk_privacy.py`, which is where
the reasoning and the checks live. This file is data: the pipeline reads it
offline, and nothing here reaches the network (constraint 4).

A publisher marks a field non-public by writing its code into
`efac:FieldsPrivacy/efbc:FieldIdentifierCode` and publishing a placeholder — an
amount as `-1` — in the field itself. This table says which field each code
names, so `serenata.normalise.privacy` can mark that column `withheld` instead
of letting a classifier read the placeholder as a quantity (ADR-0006, ADR-0008).

Source: eForms SDK `fields/fields.json`, published by the Publications Office
of the European Union under CC BY 4.0 (https://github.com/OP-TED/eForms-SDK).
Generated from the versions in `SDK_VERSIONS` below, whose privacy mappings are
identical across all of them. See docs/adr/0008-eforms-sdk-privacy-mapping.md.
"""

from __future__ import annotations

from typing import NamedTuple

#: The SDK versions this table was generated from and verified identical across.
SDK_VERSIONS: tuple[str, ...] = {versions_tuple}


class PrivacyField(NamedTuple):
    """One field a privacy code withholds, as the SDK defines it."""

    #: The value published in `efbc:FieldIdentifierCode`.
    code: str
    #: The SDK's own identifier for the withheld field, e.g. `BT-720-Tender`.
    field_id: str
    #: The field's absolute XPath, verbatim, predicates included.
    xpath: str
    #: Other SDK fields whose XPath is identical once predicates are stripped.
    #: Non-empty means this code cannot be resolved to a column in a model that
    #: does not carry predicates, because two different fields share the path.
    shares_path_with: tuple[str, ...]


PRIVACY_FIELDS: tuple[PrivacyField, ...] = (
'''


def fetch(version: str) -> dict[str, Any]:
    response = httpx.get(
        SOURCE.format(version=version),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=60.0,
    )
    response.raise_for_status()
    body: dict[str, Any] = response.json()
    return body


def mapping(fields: list[dict[str, Any]]) -> dict[str, set[tuple[str, str]]]:
    """code -> {(field id, xpath)}, for every field the SDK marks withholdable."""
    found: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for field in fields:
        privacy = field.get("privacy")
        if privacy:
            found[privacy["code"]].add((field["id"], field["xpathAbsolute"]))
    return dict(found)


def collisions(fields: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    """field id -> other field ids sharing its predicate-stripped XPath."""
    by_path: dict[str, set[str]] = defaultdict(set)
    for field in fields:
        by_path[PREDICATE.sub("", field["xpathAbsolute"])].add(field["id"])
    return {
        field["id"]: tuple(
            sorted(by_path[PREDICATE.sub("", field["xpathAbsolute"])] - {field["id"]})
        )
        for field in fields
    }


def main() -> int:
    documents = {version: fetch(version) for version in VERSIONS}
    mappings = {
        version: mapping(document["fields"]) for version, document in documents.items()
    }

    reference = VERSIONS[-1]
    disagreements = {
        version: sorted(
            code
            for code in set(mappings[reference]) | set(found)
            if mappings[reference].get(code) != found.get(code)
        )
        for version, found in mappings.items()
    }
    disagreeing = {v: codes for v, codes in disagreements.items() if codes}
    if disagreeing:
        print(
            "The SDK versions disagree about which field a code withholds, so "
            "one vendored table cannot serve them all. Codes that moved:"
        )
        for version, codes in disagreeing.items():
            print(f"  {version} vs {reference}: {', '.join(codes)}")
        return 1

    shared = collisions(documents[reference]["fields"])
    rows = sorted(
        (code, field_id, xpath, shared.get(field_id, ()))
        for code, fields in mappings[reference].items()
        for field_id, xpath in fields
    )

    versions = ", ".join(VERSIONS)
    body = HEADER.format(versions_tuple=repr(VERSIONS))
    for code, field_id, xpath, sharers in rows:
        body += "    PrivacyField(\n"
        body += f"        {code!r},\n        {field_id!r},\n        {xpath!r},\n"
        body += f"        {sharers!r},\n"
        body += "    ),\n"
    body += ")\n"

    OUTPUT.write_text(body, encoding="utf-8")
    resolvable = sum(1 for *_, sharers in rows if not sharers)
    print(
        f"{OUTPUT.relative_to(Path.cwd())}: {len(rows)} fields, "
        f"{len(mappings[reference])} codes, identical across {versions}. "
        f"{len(rows) - resolvable} share a predicate-stripped path and are "
        "refused."
    )
    print("Run `uv run ruff format` on it, then review the diff.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
