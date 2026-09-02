"""Measure which eForms fields notices actually populate.

An analysis tool, not a pipeline stage: it reads archived packages and writes a
document the data model is designed against (`docs/open-work.md` #2). It sits
inside the package rather than in a scripts directory so that the constraint
gates, type checking and tests apply to it — the data model will cite its
numbers, so those numbers have to be reproducible.

Offline and deterministic. It counts field *presence* and never reads a value
into its output: some of these elements can carry a natural person's name, and
constraint 2 does not bend for a report.

    python -m serenata.survey data/raw/ted/daily/2026/*.tar.gz -o docs/field-usage.md
"""

from serenata.survey.paths import (
    EFORMS_PREFIXES,
    NoticeRejected,
    NoticeShape,
    read_notice,
)
from serenata.survey.report import Survey, is_eforms, render, survey_package

__all__ = [
    "EFORMS_PREFIXES",
    "NoticeRejected",
    "NoticeShape",
    "Survey",
    "is_eforms",
    "read_notice",
    "render",
    "survey_package",
]
