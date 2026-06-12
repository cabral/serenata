"""Stage 2: eForms and legacy-TED XML into typed intermediate records.

Runs offline against the archived raw files. Notices from late 2024 onward
are eForms (UBL-based XML); earlier ones use the legacy TED schemas. Source
fields that could contain a natural person's name (contact persons, sole
traders) are dropped here, at ingestion — they never reach intermediate
records or storage. Every record keeps its source notice ID.
"""
