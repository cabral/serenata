"""CLI contract: the documented subcommands exist and honestly refuse to run."""

import pytest

from serenata.cli import STAGES, build_parser, main


def test_help_lists_every_stage(capsys):
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["--help"])
    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    for stage in STAGES:
        assert stage in help_text


@pytest.mark.parametrize("stage", sorted(STAGES))
def test_stages_are_stubs(stage, capsys):
    assert main([stage]) == 2
    assert "not implemented" in capsys.readouterr().err


def test_no_command_is_an_error():
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_unknown_command_is_an_error():
    with pytest.raises(SystemExit) as excinfo:
        main(["audit"])
    assert excinfo.value.code == 2


def test_version_prints_and_exits_zero(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.startswith("serenata ")
