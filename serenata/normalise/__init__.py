"""Stage 3: intermediate records into the documented relational model.

One model spans eForms and legacy TED (the contract is ``docs/data-model.md``);
output is Parquet, queried with DuckDB (ADR-0001). Field provenance and
absence are recorded explicitly: "not provided" and "not applicable" are
different facts. Deterministic — same input data produces the same bytes.
"""
