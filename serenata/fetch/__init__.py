"""Stage 1: download notices from TED and archive the raw XML.

The only stage allowed to touch the network. Raw files are archived
byte-for-byte as fetched and are immutable afterwards: they are the ground
truth that every derived record points back to. Uses the documented TED
Search API and daily bulk packages only — never scraping the website — with
polite rate limits and a User-Agent identifying this project.

The unit of archiving is a publication day, not a notice: one request per day
instead of thousands, addressed by the OJ S issue the Search API resolves for
that date. ADR-0002 records why, and the verified facts behind it.
"""

from serenata.fetch.archive import (
    ArchiveConflict,
    PackageManifest,
    RawArchive,
    sha256_of,
)
from serenata.fetch.client import FetchError, RetryPolicy, TedClient
from serenata.fetch.ojs import OjsIssue, dates_in_range, issue_for_date
from serenata.fetch.packages import (
    DayResult,
    Outcome,
    default_archive_root,
    fetch_range,
    iter_fetch_range,
)

__all__ = [
    "ArchiveConflict",
    "DayResult",
    "FetchError",
    "OjsIssue",
    "Outcome",
    "PackageManifest",
    "RawArchive",
    "RetryPolicy",
    "TedClient",
    "dates_in_range",
    "default_archive_root",
    "fetch_range",
    "issue_for_date",
    "iter_fetch_range",
    "sha256_of",
]
