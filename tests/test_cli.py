"""CLI contract: implemented stages run, unimplemented ones refuse honestly."""

import pytest

from serenata.cli import IMPLEMENTED, STAGES, build_parser, main


def test_help_lists_every_stage(capsys):
    with pytest.raises(SystemExit) as excinfo:
        build_parser().parse_args(["--help"])
    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    for stage in STAGES:
        assert stage in help_text


@pytest.mark.parametrize("stage", sorted(set(STAGES) - IMPLEMENTED))
def test_unimplemented_stages_are_stubs(stage, capsys):
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


class TestFetchArguments:
    def test_fetch_requires_a_start_date(self):
        with pytest.raises(SystemExit) as excinfo:
            main(["fetch"])
        assert excinfo.value.code == 2

    def test_a_malformed_date_is_rejected(self, capsys):
        with pytest.raises(SystemExit) as excinfo:
            main(["fetch", "--from", "17-08-2026"])
        assert excinfo.value.code == 2
        assert "YYYY-MM-DD" in capsys.readouterr().err

    def test_a_backwards_range_is_rejected_before_any_request(self, capsys):
        code = main(["fetch", "--from", "2026-08-19", "--to", "2026-08-17"])
        assert code == 2
        assert "precedes" in capsys.readouterr().err

    def test_fetch_help_documents_the_archive_default(self, capsys):
        with pytest.raises(SystemExit):
            build_parser().parse_args(["fetch", "--help"])
        assert "data/raw" in capsys.readouterr().out
