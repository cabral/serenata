"""Every pipeline stage exists as an importable module documenting its contract."""

import importlib

import pytest

STAGE_MODULES = [
    "serenata_europa",
    "serenata_europa.fetch",
    "serenata_europa.parse",
    "serenata_europa.normalise",
    "serenata_europa.classify",
]


@pytest.mark.parametrize("name", STAGE_MODULES)
def test_stage_module_is_documented(name):
    module = importlib.import_module(name)
    assert module.__doc__, f"{name} must document its stage contract"
