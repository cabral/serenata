"""The raw archive: fetched packages and the manifests that vouch for them.

Raw files are ground truth. Once a package is archived, its bytes are never
rewritten — a re-fetch whose content matches is a no-op, and one whose content
differs is a conflict a human has to look at, not something to silently
resolve. Every package is stored beside a manifest recording where it came
from and what it hashed to, so a later stage can prove the bytes it read are
the bytes TED served.
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from serenata.fetch.ojs import OjsIssue

#: Bumped when the manifest's shape changes in a way readers must notice.
MANIFEST_VERSION = 1

_HASH_CHUNK_BYTES = 1 << 20


class ArchiveConflict(RuntimeError):
    """An archived package/manifest pair is incomplete or fails verification."""


@dataclass(frozen=True)
class PackageManifest:
    """Provenance for one archived daily package.

    ``fetched_at`` is wall-clock and therefore provenance only: the
    determinism constraint binds transform and classify outputs, and nothing
    derived may depend on this timestamp (ADR-0002).
    """

    package_id: str
    ojs_number: str
    publication_date: str
    source_url: str
    sha256: str
    size_bytes: int
    member_prefix: str | None
    fetched_at: str
    manifest_version: int = MANIFEST_VERSION

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> PackageManifest:
        known = {field: raw.get(field) for field in cls.__dataclass_fields__}
        return cls(**known)  # type: ignore[arg-type]

    def to_json(self) -> str:
        # Sorted keys and a trailing newline so a manifest is diffable and
        # stable across writes.
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


def sha256_of(path: Path) -> str:
    """Checksum a file without reading it all into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(_HASH_CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def package_member_prefix(path: Path) -> str | None:
    """The directory every notice in the package sits under (``20260817_157``).

    Reading one tar header is enough, and it is the cheapest available check
    that the package we received is the day we asked for.
    """
    try:
        with tarfile.open(path, "r:gz") as archive:
            first = archive.next()
    except (tarfile.TarError, OSError):
        return None
    if first is None:
        return None
    head = first.name.strip("/").split("/", 1)[0]
    return head or None


def expected_member_prefix(issue: OjsIssue, publication_date: date) -> str:
    """The member prefix a package for this issue and date should carry."""
    return f"{publication_date.strftime('%Y%m%d')}_{issue.number:03d}"


class RawArchive:
    """Filesystem layout for fetched packages, rooted at ``root``."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def package_path(self, issue: OjsIssue) -> Path:
        return (
            self.root / "ted" / "daily" / str(issue.year) / f"{issue.package_id}.tar.gz"
        )

    def manifest_path(self, issue: OjsIssue) -> Path:
        package = self.package_path(issue)
        return package.with_name(f"{issue.package_id}.manifest.json")

    def read_manifest(self, issue: OjsIssue) -> PackageManifest | None:
        path = self.manifest_path(issue)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ArchiveConflict(f"manifest {path} is unreadable: {exc}") from exc
        if not isinstance(raw, dict):
            raise ArchiveConflict(f"manifest {path} is not a JSON object")
        return PackageManifest.from_dict(raw)

    def write_manifest(self, issue: OjsIssue, manifest: PackageManifest) -> Path:
        """Publish complete JSON atomically; preserve the prior manifest on failure."""
        path = self.manifest_path(issue)
        path.parent.mkdir(parents=True, exist_ok=True)
        # Stage on the same filesystem so replacement is atomic. A failed write
        # must leave either the prior manifest or no manifest, never partial JSON.
        with TemporaryDirectory(prefix=f".{path.name}-", dir=path.parent) as temporary:
            pending = Path(temporary) / path.name
            pending.write_text(manifest.to_json(), encoding="utf-8")
            pending.replace(path)
        return path

    def holds(self, issue: OjsIssue) -> bool:
        """Whether both the package and its manifest are present."""
        return (
            self.package_path(issue).is_file() and self.manifest_path(issue).is_file()
        )

    def has_artifacts(self, issue: OjsIssue) -> bool:
        """Whether either archive path is occupied and must be verified before fetch."""
        return any(
            path.exists() or path.is_symlink()
            for path in (self.package_path(issue), self.manifest_path(issue))
        )

    def verify(self, issue: OjsIssue) -> PackageManifest:
        """Confirm the archived bytes still match their manifest.

        Raises ``ArchiveConflict`` for an incomplete pair or mismatching bytes —
        an interrupted, corrupted or replaced archive is a fact to surface,
        never to paper over by refetching.
        """
        manifest = self.read_manifest(issue)
        if manifest is None:
            raise ArchiveConflict(f"no manifest for OJ S {issue}")

        package = self.package_path(issue)
        if not package.is_file():
            raise ArchiveConflict(f"manifest for OJ S {issue} has no package beside it")

        actual = sha256_of(package)
        if actual != manifest.sha256:
            raise ArchiveConflict(
                f"{package} has checksum {actual}, but its manifest records "
                f"{manifest.sha256}; raw files are immutable, so this needs a human"
            )
        return manifest
