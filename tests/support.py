"""Builders for the tests: a stand-in TED, a clock that never ticks, notices.

Nothing here touches the network or a real clock. Package fixtures are built
in memory with obviously synthetic notice IDs, per ``tests/fixtures/README.md``.
"""

from __future__ import annotations

import gzip
import io
import tarfile
from pathlib import Path
from typing import Any

#: An impossible notice ID: real TED numbers are nowhere near this range.
SYNTHETIC_NOTICE = "00000001_2026.xml"

PACKAGE_PREFIX = "20260817_157"
OJS_NUMBER = "157/2026"
PACKAGE_ID = "202600157"


def make_package(
    prefix: str = PACKAGE_PREFIX, notices: tuple[str, ...] = (SYNTHETIC_NOTICE,)
) -> bytes:
    """A gzipped tar shaped like a TED daily package, with fake notices."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        for name in notices:
            body = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                f"<ContractNotice><SyntheticFixture>{name}</SyntheticFixture>"
                "</ContractNotice>"
            ).encode()
            info = tarfile.TarInfo(f"{prefix}/{name}")
            info.size = len(body)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


def search_body(ojs_number: str | None = OJS_NUMBER, count: int = 1) -> dict[str, Any]:
    """A Search API response carrying ``count`` notices."""
    notice: dict[str, Any] = {} if ojs_number is None else {"ojs-number": ojs_number}
    return {
        "notices": [dict(notice) for _ in range(count)],
        "totalNoticeCount": count,
        "iterationNextToken": None,
        "timedOut": False,
    }


class FakeClock:
    """A monotonic clock that only moves when something sleeps on it."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.slept: list[float] = []

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds

    def monotonic(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


#: Namespaces an eForms notice declares. Repeated here rather than imported
#: from `serenata.eforms` on purpose: a fixture that took its namespaces from
#: the code under test would still pass if that code renamed one.
CAC = "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
CBC = "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2"
EXT = "urn:oasis:names:specification:ubl:schema:xsd:CommonExtensionComponents-2"
EFAC = "http://data.europa.eu/p27/eforms-ubl-extension-aggregate-components/1"
EFBC = "http://data.europa.eu/p27/eforms-ubl-extension-basic-components/1"
EFEXT = "http://data.europa.eu/p27/eforms-ubl-extensions/1"

#: An impossible TED publication number, per tests/fixtures/README.md.
SYNTHETIC_PUBLICATION = "00000001-2026"

#: Ditto for the notice's UUID: nothing that could be mistaken for a real one.
SYNTHETIC_NOTICE_ID = "00000000-0000-0000-0000-000000000001"


def notice_xml(
    *,
    root: str = "ContractNotice",
    notice_id: str = SYNTHETIC_NOTICE_ID,
    publication_id: str = SYNTHETIC_PUBLICATION,
    publication_date: str = "2026-08-17+02:00",
    language: str = "ENG",
    body: str = "",
    extension: str = "",
) -> bytes:
    """A synthetic eForms notice carrying whatever ``body`` adds.

    Deliberately richer than the parse tests' builder: the normalise stage reads
    the publication block, the notice language and the extension, and a fixture
    without them exercises none of the columns that matter.
    """
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<{root} xmlns="urn:oasis:names:specification:ubl:schema:xsd:{root}-2"
        xmlns:cac="{CAC}" xmlns:cbc="{CBC}" xmlns:ext="{EXT}"
        xmlns:efac="{EFAC}" xmlns:efbc="{EFBC}" xmlns:efext="{EFEXT}">
  <cbc:ID>{notice_id}</cbc:ID>
  <cbc:NoticeLanguageCode>{language}</cbc:NoticeLanguageCode>
  {body}
  <ext:UBLExtensions><ext:UBLExtension><ext:ExtensionContent>
    <efext:EformsExtension>
      <efac:Publication>
        <efbc:NoticePublicationID>{publication_id}</efbc:NoticePublicationID>
        <efbc:PublicationDate>{publication_date}</efbc:PublicationDate>
      </efac:Publication>
      {extension}
    </efext:EformsExtension>
  </ext:ExtensionContent></ext:UBLExtension></ext:UBLExtensions>
</{root}>""".encode()


def make_notice_package(
    notices: dict[str, bytes], prefix: str = PACKAGE_PREFIX
) -> bytes:
    """A gzipped tar shaped like a TED daily package, carrying real notices.

    `make_package` above builds the shape the fetch tests need and nothing
    readable inside; this one carries documents the parse and normalise stages
    can actually read.
    """
    buffer = io.BytesIO()
    # gzip stamps the current time into its header unless told not to, which
    # would make the same notices a different package on every run — and this
    # package feeds tests that compare bytes.
    with (
        gzip.GzipFile(fileobj=buffer, mode="wb", mtime=0) as compressed,
        tarfile.open(fileobj=compressed, mode="w") as archive,
    ):
        for name, body in notices.items():
            info = tarfile.TarInfo(f"{prefix}/{name}")
            info.size = len(body)
            info.mtime = 0
            archive.addfile(info, io.BytesIO(body))
    return buffer.getvalue()


#: The committed sample, as it sits unpacked: one directory named the way TED
#: names a package's members, one XML file per notice.
SAMPLE = Path(__file__).resolve().parent.parent / "data" / "sample"


def sample_notices() -> dict[str, bytes]:
    """Every notice in the committed sample, by member name."""
    return {
        path.name: path.read_bytes()
        for path in sorted((SAMPLE / PACKAGE_PREFIX).glob("*.xml"))
    }


def sample_package(destination: Path) -> Path:
    """Pack the committed sample into a package, the shape `fetch` archives.

    The notices are committed as XML rather than as a ``.tar.gz`` because a
    fixture nobody can read in a diff is a fixture nobody checks — and this one
    exists to be checked. Packing them here costs a line and gives the tests the
    same input the pipeline takes in production.
    """
    package = destination / f"{PACKAGE_ID}.tar.gz"
    package.write_bytes(make_notice_package(sample_notices()))
    return package
