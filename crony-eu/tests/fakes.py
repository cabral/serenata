# SPDX-License-Identifier: AGPL-3.0-only
"""Stand-ins the tests drive the pipeline with.

A module rather than the conftest so that test files can import the types they
annotate with. It is named `fakes` rather than `support` on purpose: this
repository holds a second test suite with its own `tests/support.py`, and two
top-level modules with one name is a collision waiting for whichever suite
pytest imports second.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FakeClock:
    """A clock that moves only when told to.

    Backoff and rate limiting are both about durations, and a test that measured
    them against the real clock would either take half a minute or flake on a
    loaded machine. `slept` is the record the assertions actually read.
    """

    now: float = 0.0
    slept: list[float] = field(default_factory=list)

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def advance(self, seconds: float) -> None:
        """Move time forward without anyone having waited for it."""
        self.now += seconds


# --- Répertoire national des élus -------------------------------------------
#
# The published headers, verbatim, because that is what the source module reads
# positionally. Copying them here rather than importing them is deliberate: if
# the module's idea of the header drifts from the file's, a fixture that shared
# the module's idea would drift with it and agree with itself forever.

CM_HEADER = (
    "Code du département;Libellé du département;"
    "Code de la collectivité à statut particulier;"
    "Libellé de la collectivité à statut particulier;"
    "Code de la commune;Libellé de la commune;Nom de l'élu;Prénom de l'élu;"
    "Code sexe;Date de naissance;Code de la catégorie socio-professionnelle;"
    "Libellé de la catégorie socio-professionnelle;Date de début du mandat;"
    "Libellé de la fonction;Date de début de la fonction;Code nationalité"
)

MAIRE_HEADER = (
    "Code du département;Libellé du département;"
    "Code de la collectivité à statut particulier;"
    "Libellé de la collectivité à statut particulier;"
    "Code de la commune;Libellé de la commune;Nom de l'élu;Prénom de l'élu;"
    "Code sexe;Date de naissance;Code de la catégorie socio-professionnelle;"
    "Libellé de la catégorie socio-professionnelle;Date de début du mandat;"
    "Date de début de la fonction"
)


@dataclass(frozen=True)
class Elu:
    """One published row. Every name is invented and says so.

    Constraint 1: no real person's record goes into this repository, not even
    with the name changed. `NOMDEXEMPLE` is not a French surname and commune
    code `99001` is not a French commune, so nothing here could be mistaken for
    a finding.
    """

    surname: str = "NOMDEXEMPLE"
    given: str = "PRENOMDEXEMPLE"
    birth_date: str = "1971-04-03"
    commune_code: str = "99001"
    commune_label: str = "COMMUNE D EXEMPLE"
    departement_code: str = "99"
    sex: str = "F"
    csp_code: str = "31"
    mandate_start: str = "2026-03-22"
    function_label: str = ""
    function_start: str = ""
    nationality: str = "FR"

    def cells(self, *, with_function: bool) -> list[str]:
        common = [
            self.departement_code,
            "DEPARTEMENT D EXEMPLE",
            "",
            "",
            self.commune_code,
            self.commune_label,
            self.surname,
            self.given,
            self.sex,
            self.birth_date,
            self.csp_code,
            "CATEGORIE D EXEMPLE",
            self.mandate_start,
        ]
        if with_function:
            return [*common, self.function_label, self.function_start, self.nationality]
        return [*common, self.function_start]


def write_rne_snapshot(
    root: Path,
    snapshot: str,
    *,
    cm_current: list[Elu] | None = None,
    maires_current: list[Elu] | None = None,
    cm_pre_election: list[Elu] | None = None,
    maires_pre_election: list[Elu] | None = None,
    retrieved_at: str = "2026-09-16T00:00:00+00:00",
) -> Path:
    """Write the four published CSVs and a manifest into a raw snapshot."""
    import json

    directory = root / "raw" / "fr-rne-elus" / snapshot
    directory.mkdir(parents=True, exist_ok=True)

    files = {
        "cm_current.csv": (CM_HEADER, cm_current or [], True),
        "maires_current.csv": (MAIRE_HEADER, maires_current or [], False),
        "cm_pre_election.csv": (CM_HEADER, cm_pre_election or [], True),
        "maires_pre_election.csv": (MAIRE_HEADER, maires_pre_election or [], False),
    }

    entries = []
    for name, (header, rows, with_function) in files.items():
        lines = [
            header,
            *(";".join(row.cells(with_function=with_function)) for row in rows),
        ]
        (directory / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        entries.append(
            {
                "source": "fr-rne-elus",
                "url": f"https://example.invalid/{name}",
                "path": name,
                "sha256": "0" * 64,
                "bytes": 0,
                "retrieved_at": retrieved_at,
                "licence": "Licence Ouverte 2.0",
                "status": 200,
            }
        )

    (directory / "manifest.json").write_text(
        json.dumps({"files": entries}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return directory
