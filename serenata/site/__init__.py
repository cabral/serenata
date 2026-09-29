"""The site: a view of what the project is and holds, never of its data.

``python -m serenata.site`` renders a handful of self-contained pages from the
repository's own documents, for the people who need something to look at that is
not a terminal: counsel deciding what the project may hold, a journalist asking
what a flag means, a funder asking where it stands.

It is not the pipeline's ``publish`` stage. It reads Markdown and nothing else:
no Parquet, no DuckDB, no archive, no flag. The only flag records on any page are
produced by running the real rule over an invented market, and are labelled as
such on the page. Why that boundary is where it is, and what would have to be
decided before it moves, is `docs/adr/0014-a-site-that-cannot-show-a-flag.md`.
"""

from serenata.site.build import build_site

__all__ = ["build_site"]
