"""Stage 1: download notices from TED and archive the raw XML.

The only stage allowed to touch the network. Raw files are archived
byte-for-byte as fetched and are immutable afterwards: they are the ground
truth that every derived record points back to. Uses the documented TED
Search API and daily bulk packages only — never scraping the website — with
polite rate limits and a User-Agent identifying this project.
"""
