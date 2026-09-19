# SPDX-License-Identifier: AGPL-3.0-only
"""Stand-ins the tests drive the pipeline with.

A module rather than the conftest so that test files can import the types they
annotate with. It is named `fakes` rather than `support` on purpose: this
repository holds a second test suite with its own `tests/support.py`, and two
top-level modules with one name is a collision waiting for whichever suite
pytest imports second.
"""

from __future__ import annotations

import zipfile
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq


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


# --- DECP ---------------------------------------------------------------------
#
# The consolidated file's columns, with a type for each and a harmless default.
# Written out here rather than imported from the source module for the same
# reason as the élus header above: a fixture that shared the module's idea of the
# file would agree with a wrong idea forever.

DECP_COLUMNS: dict[str, Any] = {
    "uid": pa.string(),
    "id": pa.string(),
    "nature": pa.string(),
    "acheteur_id": pa.string(),
    "acheteur_nom": pa.string(),
    "titulaire_id": pa.string(),
    "titulaire_typeIdentifiant": pa.string(),
    "titulaire_nom": pa.string(),
    "objet": pa.string(),
    "montant": pa.float64(),
    "codeCPV": pa.string(),
    "procedure": pa.string(),
    "dureeMois": pa.int16(),
    "offresRecues": pa.int16(),
    "dateNotification": pa.date32(),
    "datePublicationDonnees": pa.date32(),
    "typeGroupementOperateurs": pa.string(),
    "lieuExecution_code": pa.string(),
    "idAccordCadre": pa.string(),
    "acheteur_categorie": pa.string(),
    "acheteur_commune_code": pa.string(),
    "acheteur_departement_code": pa.string(),
    "titulaire_categorie": pa.string(),
    "titulaire_activite_code": pa.string(),
    "titulaire_commune_code": pa.string(),
    "titulaire_departement_code": pa.string(),
    "modification_id": pa.int16(),
    "donneesActuelles": pa.bool_(),
    "montant_rationalise": pa.float64(),
    "montant_anomalie": pa.string(),
    "sourceDataset": pa.string(),
    "sourceFile": pa.string(),
}


def decp_row(**overrides: Any) -> dict[str, Any]:
    """One contract row, with every column present and nothing real in it.

    The company and commune names are invented. The SIRET is a generated one
    that passes its checksum, because a fixture whose identifiers all failed
    validation could not tell a working check from one that rejects everything.
    """
    row: dict[str, Any] = dict.fromkeys(DECP_COLUMNS)
    row.update(
        {
            "uid": "TEST-0001",
            "id": "0001",
            "nature": "Marché",
            "acheteur_id": siret("21930001"),
            "acheteur_nom": "Commune de Fixtureville",
            "titulaire_id": siret("81230001"),
            "titulaire_typeIdentifiant": "SIRET",
            "titulaire_nom": "Entreprise Fixture SARL",
            "objet": "Travaux de voirie",
            "montant": 120000.0,
            "dateNotification": date(2024, 5, 14),
            "datePublicationDonnees": date(2024, 6, 1),
            "acheteur_categorie": "Commune",
            "acheteur_commune_code": "93001",
            "acheteur_departement_code": "93",
            "titulaire_categorie": "PME",
            "modification_id": 0,
            "donneesActuelles": True,
            "sourceDataset": "test_platform",
            "sourceFile": "test.json",
        }
    )
    row.update(overrides)
    return row


def luhn_check_digit(body: str) -> str:
    """The digit that makes `body` pass Luhn, for building valid fixtures."""
    total = 0
    for offset, character in enumerate(reversed(body + "0")):
        digit = int(character)
        if offset % 2 == 1:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return str((10 - total % 10) % 10)


def siren(body: str) -> str:
    """A nine-digit SIREN that passes its checksum, from an eight-digit stem."""
    return body + luhn_check_digit(body)


def siret(body: str) -> str:
    """A fourteen-digit SIRET that passes its checksum.

    `body` is the eight-digit stem of the SIREN; the establishment number is
    filled in so that the whole thing checks out, which is what a real one does.
    """
    stem = siren(body) + "0000"
    return stem + luhn_check_digit(stem)


def write_decp(path: Path, rows: list[dict[str, Any]]) -> Path:
    """Write generated rows as a Parquet file shaped like the published one."""
    schema = pa.schema([pa.field(name, kind) for name, kind in DECP_COLUMNS.items()])
    table = pa.Table.from_pylist(
        [{name: row.get(name) for name in DECP_COLUMNS} for row in rows], schema=schema
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


# --- INSEE populations --------------------------------------------------------

POPULATION_HEADER = "GEO;GEO_OBJECT;FREQ;POPREF_MEASURE;TIME_PERIOD;OBS_VALUE"


def write_populations(path: Path, rows: list[tuple[str, str, str, int]]) -> Path:
    """Write a zip shaped like INSEE's, holding a metadata file and a data one.

    Both files are written because the module picks the data one by name, and a
    fixture with only one file could not tell that it picks correctly.
    """
    lines = [POPULATION_HEADER]
    for geo, geo_object, measure, value in rows:
        lines.append(f'"{geo}";"{geo_object}";"A";"{measure}";"2023";"{value}"')

    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "DS_POPULATIONS_REFERENCE_2023_metadata.csv",
            '"COD_VAR";"LIB_VAR";"COD_MOD";"LIB_MOD"\n"FREQ";"Fréquence";"A";"Annuel"\n',
        )
        archive.writestr(
            "DS_POPULATIONS_REFERENCE_2023_data.csv", "\n".join(lines) + "\n"
        )
    return path
