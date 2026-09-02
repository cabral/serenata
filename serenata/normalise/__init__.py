"""Stage 3: intermediate records into the documented relational model.

One model spans eForms and legacy TED (the contract is ``docs/data-model.md``,
and `serenata.normalise.model` is that document in executable form); output is
Parquet, queried with DuckDB (ADR-0001). Field provenance and absence are
recorded explicitly: "not provided" and "not applicable" are different facts.
Deterministic — same input data produces the same bytes.

Legacy TED notices do not reach this stage: parse refuses them until their
field mappings have been measured, so what arrives here is eForms.

    from serenata.normalise import normalise_package
    result = normalise_package(
        Path("data/raw/ted/daily/2026/202600157.tar.gz"),
        Path("data/normalised"),
    )
    print(result.describe())

The rows for one notice can also be built without writing anything, which is
what a test or an exploratory query wants:

    from serenata.normalise import notice_rows
    rows = notice_rows(parsed_notice)
"""

from serenata.normalise.dataset import (
    PARTITION,
    ROW_GROUP_SIZE,
    WRITER,
    Dataset,
    Normalised,
    Unnormalised,
    default_dataset_root,
    normalise_notices,
    normalise_package,
    package_part,
    schema_of,
    write_dataset,
)
from serenata.normalise.model import TABLES, Kind, Status, Table, table
from serenata.normalise.rows import RepeatedValue, notice_rows, publication_year

__all__ = [
    "PARTITION",
    "ROW_GROUP_SIZE",
    "TABLES",
    "WRITER",
    "Dataset",
    "Kind",
    "Normalised",
    "RepeatedValue",
    "Status",
    "Table",
    "Unnormalised",
    "default_dataset_root",
    "normalise_notices",
    "normalise_package",
    "notice_rows",
    "package_part",
    "publication_year",
    "schema_of",
    "table",
    "write_dataset",
]
