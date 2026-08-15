"""The pieces both command lines are built from.

Argument plumbing is worth a test of its own: an option that is parsed but never
passed on is the kind of fault that looks like it works.
"""

import argparse
import asyncio
from typing import Any

import pytest
from exemplar import Board

from sextile.application import Sextile
from sextile.cli import (
    ApplicationSpecError,
    add_listening_arguments,
    add_standard_subcommands,
    load_application,
    rendered,
    run_service,
    run_standard,
)
from sextile.page import Page
from sextile.pages import notice_page
from sextile.requests import PageRequest
from sextile.routing import PageRoute
from sextile.server import DEFAULT_IDLE_TIMEOUT, DEFAULT_PORT


def parse(*argv: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    add_listening_arguments(parser)
    return parser.parse_args(argv)


class TestListeningArguments:
    def test_the_defaults(self) -> None:
        arguments = parse()
        assert arguments.host == "127.0.0.1"
        assert arguments.port == DEFAULT_PORT
        assert arguments.idle_timeout == DEFAULT_IDLE_TIMEOUT

    def test_an_idle_timeout_is_read_as_seconds(self) -> None:
        assert parse("--idle-timeout", "90").idle_timeout == 90.0

    def test_a_fractional_timeout_is_allowed(self) -> None:
        #  Not useful on a real line, but a test that wants one wants it short.
        assert parse("--idle-timeout", "0.5").idle_timeout == 0.5

    def test_zero_is_accepted_and_means_never(self) -> None:
        assert parse("--idle-timeout", "0").idle_timeout == 0.0

    def test_a_negative_timeout_is_refused(self) -> None:
        #  It would otherwise release the line before the greeting arrived.
        with pytest.raises(SystemExit):
            parse("--idle-timeout", "-1")


class _StoppedServer:
    """An asyncio.Server that gives up as soon as it is asked to run."""

    def __init__(self) -> None:
        self.sockets: tuple[()] = ()

    async def __aenter__(self) -> "_StoppedServer":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def serve_forever(self) -> None:
        raise asyncio.CancelledError


class TestRunningAService:
    """What `serve` is actually called with, which is the point of the options."""

    async def test_the_listening_options_are_passed_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: dict[str, Any] = {}

        async def fake_serve(application: Sextile, **keywords: Any) -> _StoppedServer:
            seen.update(keywords)
            return _StoppedServer()

        monkeypatch.setattr("sextile.cli.serve", fake_serve)
        arguments = parse("--host", "0.0.0.0", "--port", "1", "--idle-timeout", "90")
        await run_service(Board(), arguments)
        assert seen["host"] == "0.0.0.0"
        assert seen["port"] == 1
        assert seen["idle_timeout"] == 90.0

    async def test_zero_becomes_no_timeout_at_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #  `asyncio.wait_for` takes None to mean "wait", and zero seconds would
        #  otherwise mean "drop the line immediately", which nobody wants.
        seen: dict[str, Any] = {}

        async def fake_serve(application: Sextile, **keywords: Any) -> _StoppedServer:
            seen.update(keywords)
            return _StoppedServer()

        monkeypatch.setattr("sextile.cli.serve", fake_serve)
        await run_service(Board(), parse("--idle-timeout", "0"))
        assert seen["idle_timeout"] is None

    async def test_the_application_is_started_and_stopped_around_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        events: list[str] = []

        class Recording(Board):
            async def startup(self) -> None:
                events.append("startup")

            async def shutdown(self) -> None:
                events.append("shutdown")

        async def fake_serve(application: Sextile, **keywords: Any) -> _StoppedServer:
            events.append("serving")
            return _StoppedServer()

        monkeypatch.setattr("sextile.cli.serve", fake_serve)
        await run_service(Recording(), parse())
        assert events == ["startup", "serving", "shutdown"]


class TestRenderingAFrame:
    def test_the_html_form_is_a_self_contained_page_with_a_title(self) -> None:
        from sextile.viewdata.frame import Frame

        page = rendered(Frame(), "html", colour=True, title="*3#")
        assert page.startswith("<!doctype html>")
        assert "<title>*3#</title>" in page
        assert "@font-face" in page  # the font is embedded, so it opens from disk
        assert '<pre class="viewdata">' in page


class TestLoadingAnApplication:
    def test_a_module_and_name(self) -> None:
        assert isinstance(load_application("exemplar:Board"), Sextile)

    @pytest.mark.parametrize(
        "spec", ["exemplar", "exemplar:", ":Board", "nosuchmodule:app", "exemplar:Missing"]
    )
    def test_a_specification_that_names_no_application(self, spec: str) -> None:
        with pytest.raises(ApplicationSpecError):
            load_application(spec)

    def test_something_that_is_not_an_application(self) -> None:
        with pytest.raises(ApplicationSpecError):
            load_application("exemplar:ITEMS")


class TestTheIdleWarning:
    def test_it_is_left_to_the_server_by_default(self) -> None:
        #  None asks for half the idle timeout, which only the server knows.
        assert parse().warn_after is None

    def test_a_time_can_be_given(self) -> None:
        assert parse("--warn-after", "30").warn_after == 30.0

    def test_zero_turns_it_off(self) -> None:
        assert parse("--warn-after", "0").warn_after == 0.0

    async def test_it_is_passed_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen: dict[str, Any] = {}

        async def fake_serve(application: Sextile, **keywords: Any) -> _StoppedServer:
            seen.update(keywords)
            return _StoppedServer()

        monkeypatch.setattr("sextile.cli.serve", fake_serve)
        await run_service(Board(), parse("--warn-after", "30"))
        assert seen["warn_after"] == 30.0


async def _greeting(request: PageRequest, **fields: object) -> Page:
    return notice_page(request, "Hello.")


_APP = Sextile(pages=[PageRoute("1", _greeting, name="hello", title="Hello")])


def with_standard_subcommands(
    *,
    configure: Any = lambda parser: None,
    page_example: str = "1",
) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subcommands = parser.add_subparsers(dest="command")
    add_standard_subcommands(subcommands, configure=configure, page_example=page_example)
    return parser


class TestStandardSubcommands:
    """The `render` and `serve` a service's command line shares."""

    def test_render_takes_the_form_arguments(self) -> None:
        arguments = with_standard_subcommands().parse_args(["render", "--page", "1"])
        assert arguments.command == "render"
        assert arguments.page == "1"
        assert arguments.form == "ansi"

    def test_serve_takes_the_listening_arguments(self) -> None:
        arguments = with_standard_subcommands().parse_args(["serve", "--port", "1"])
        assert arguments.command == "serve"
        assert arguments.port == 1

    def test_configure_reaches_both_subcommands(self) -> None:
        def configure(parser: argparse.ArgumentParser) -> None:
            parser.add_argument("--database-filepath", default="here")

        parser = with_standard_subcommands(configure=configure)
        assert parser.parse_args(["render", "--page", "1"]).database_filepath == "here"
        assert parser.parse_args(["serve"]).database_filepath == "here"


class TestRunningAStandardCommand:
    def test_an_unknown_command_is_left_to_the_caller(self) -> None:
        arguments = argparse.Namespace(command="ingest")
        assert run_standard(arguments, load=lambda _: _APP) is None

    def test_render_without_a_page_is_refused_before_the_app_is_built(self) -> None:
        loaded: list[bool] = []

        def load(_: argparse.Namespace) -> Sextile:
            loaded.append(True)
            return _APP

        arguments = with_standard_subcommands().parse_args(["render"])
        assert run_standard(arguments, load=load) == 2
        assert loaded == []

    def test_render_draws_the_page(self) -> None:
        arguments = with_standard_subcommands().parse_args(["render", "--page", "1"])
        assert run_standard(arguments, load=lambda _: _APP) == 0

    def test_serve_is_run(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_serve(application: Sextile, **keywords: Any) -> _StoppedServer:
            return _StoppedServer()

        monkeypatch.setattr("sextile.cli.serve", fake_serve)
        arguments = with_standard_subcommands().parse_args(["serve"])
        assert run_standard(arguments, load=lambda _: _APP) == 0
