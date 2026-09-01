"""CLI contract: implemented stages run, unimplemented ones refuse honestly."""

import httpx
import pytest

from serenata.cli import IMPLEMENTED, STAGES, build_parser, main

from .support import make_package, search_body


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


class TestFetchRun:
    """The command's own behaviour: what it prints and what it exits with."""

    def test_a_successful_fetch_reports_each_day_and_exits_zero(
        self, client_factory, ted_handler, tmp_path, capsys
    ):
        code = main(
            ["fetch", "--from", "2026-08-17", "--archive", str(tmp_path)],
            open_client=lambda _interval: client_factory(ted_handler),
        )

        out = capsys.readouterr().out
        assert code == 0
        assert "2026-08-17  fetched  OJ S 157/2026" in out
        assert "1 dates considered: 1 fetched" in out

    def test_the_summary_counts_every_outcome(self, client_factory, tmp_path, capsys):
        package = make_package()
        published = {"2026-08-17", "2026-08-18"}

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/notices/search"):
                import json

                query = json.loads(request.content)["query"]
                day = query.split(">=")[1].split(" ")[0]
                stamped = f"{day[:4]}-{day[4:6]}-{day[6:]}"
                return httpx.Response(
                    200, json=search_body(count=1 if stamped in published else 0)
                )
            return httpx.Response(200, content=package)

        code = main(
            [
                "fetch",
                "--from",
                "2026-08-15",
                "--to",
                "2026-08-18",
                "--archive",
                str(tmp_path),
                "--dry-run",
            ],
            open_client=lambda _interval: client_factory(handler),
        )

        assert code == 0
        assert (
            "4 dates considered: 2 not-published, 2 planned" in capsys.readouterr().out
        )

    def test_a_range_that_published_nothing_says_so(
        self, client_factory, tmp_path, capsys
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=search_body(count=0))

        code = main(
            ["fetch", "--from", "2026-08-15", "--archive", str(tmp_path)],
            open_client=lambda _interval: client_factory(handler),
        )

        captured = capsys.readouterr()
        assert code == 0, "a quiet range is not a failure"
        assert "No notices were published" in captured.err

    def test_a_failing_fetch_exits_one_with_the_reason(
        self, client_factory, tmp_path, capsys
    ):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="TED is down")

        code = main(
            ["fetch", "--from", "2026-08-17", "--archive", str(tmp_path)],
            open_client=lambda _interval: client_factory(handler),
        )

        assert code == 1
        assert "serenata fetch:" in capsys.readouterr().err

    def test_an_archive_conflict_exits_one_rather_than_overwriting(
        self, client_factory, ted_handler, tmp_path, capsys
    ):
        argv = ["fetch", "--from", "2026-08-17", "--archive", str(tmp_path)]
        assert main(argv, open_client=lambda _i: client_factory(ted_handler)) == 0

        archived = next(tmp_path.rglob("*.tar.gz"))
        archived.write_bytes(b"tampered")

        code = main(argv, open_client=lambda _i: client_factory(ted_handler))

        assert code == 1
        assert "needs a human" in capsys.readouterr().err

    def test_the_default_archive_root_is_used_when_none_is_given(
        self, client_factory, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.chdir(tmp_path)

        code = main(
            ["fetch", "--from", "2026-08-17"],
            open_client=lambda _i: client_factory(ted_handler_for(make_package())),
        )

        assert code == 0
        assert (tmp_path / "data" / "raw" / "ted" / "daily" / "2026").is_dir()


def ted_handler_for(package: bytes):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/notices/search"):
            return httpx.Response(200, json=search_body())
        return httpx.Response(200, content=package)

    return handler
