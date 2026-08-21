"""The pieces both command lines are built from.

Argument plumbing is worth a test of its own: an option parsed but never passed
on is the kind of fault that looks like it works. The commands are Click, so a
test drives them through a `CliRunner` and reads back what the options became.
"""

import asyncio
from typing import Any

import click
import pytest
from click.testing import CliRunner
from exemplar import Board

from sextile.application import Sextile
from sextile.cli import (
    ApplicationSpecError,
    load_application,
    rendered,
    standard_commands,
)
from sextile.page import Page
from sextile.pages import notice_page
from sextile.requests import PageRequest
from sextile.routing import PageRoute
from sextile.server import DEFAULT_IDLE_TIMEOUT, DEFAULT_MAX_CONNECTIONS, DEFAULT_PORT


async def _greeting(request: PageRequest, **fields: object) -> Page:
    return notice_page(request, "Hello.")


_APP = Sextile(pages=[PageRoute("1", _greeting, name="hello", title="Hello")])


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


def _service(*, load: Any = lambda context: _APP, options: Any = ()) -> click.Group:
    """A service's Click group: the shared render and serve, and nothing else."""

    @click.group()
    def cli() -> None: ...

    for command in standard_commands(load, options=options):
        cli.add_command(command)
    return cli


def _intercept_serve(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Replace `serve` with one that records what it was called with."""
    seen: dict[str, Any] = {}

    async def fake_serve(application: Sextile, **keywords: Any) -> _StoppedServer:
        seen.update(keywords)
        seen["application"] = application
        return _StoppedServer()

    monkeypatch.setattr("sextile.cli.serve", fake_serve)
    return seen


class TestListeningArguments:
    def test_the_defaults(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = _intercept_serve(monkeypatch)
        result = CliRunner().invoke(_service(), ["serve"])
        assert result.exit_code == 0
        assert seen["host"] == "127.0.0.1"
        assert seen["port"] == DEFAULT_PORT
        assert seen["idle_timeout"] == DEFAULT_IDLE_TIMEOUT
        assert seen["max_connections"] == DEFAULT_MAX_CONNECTIONS

    def test_an_idle_timeout_is_read_as_seconds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = _intercept_serve(monkeypatch)
        CliRunner().invoke(_service(), ["serve", "--idle-timeout", "90"])
        assert seen["idle_timeout"] == 90.0

    def test_a_fractional_timeout_is_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        #  Not useful on a real line, but a test that wants one wants it short.
        seen = _intercept_serve(monkeypatch)
        CliRunner().invoke(_service(), ["serve", "--idle-timeout", "0.5"])
        assert seen["idle_timeout"] == 0.5

    def test_zero_becomes_no_timeout_at_all(self, monkeypatch: pytest.MonkeyPatch) -> None:
        #  `asyncio.wait_for` takes None to mean "wait", and zero seconds would
        #  otherwise mean "drop the line immediately", which nobody wants.
        seen = _intercept_serve(monkeypatch)
        CliRunner().invoke(_service(), ["serve", "--idle-timeout", "0"])
        assert seen["idle_timeout"] is None

    def test_a_negative_timeout_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        #  It would otherwise release the line before the greeting arrived.
        seen = _intercept_serve(monkeypatch)
        result = CliRunner().invoke(_service(), ["serve", "--idle-timeout", "-1"])
        assert result.exit_code == 2
        assert seen == {}


class TestRunningAService:
    """What `serve` is actually called with, which is the point of the options."""

    def test_the_listening_options_are_passed_on(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = _intercept_serve(monkeypatch)
        result = CliRunner().invoke(
            _service(), ["serve", "--host", "0.0.0.0", "--port", "1", "--idle-timeout", "90"]
        )
        assert result.exit_code == 0
        assert seen["host"] == "0.0.0.0"
        assert seen["port"] == 1
        assert seen["idle_timeout"] == 90.0

    def test_zero_max_connections_becomes_no_ceiling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = _intercept_serve(monkeypatch)
        CliRunner().invoke(_service(), ["serve", "--max-connections", "0"])
        assert seen["max_connections"] is None

    def test_the_application_is_started_and_stopped_around_it(
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
        result = CliRunner().invoke(_service(load=lambda context: Recording()), ["serve"])
        assert result.exit_code == 0
        assert events == ["startup", "serving", "shutdown"]


class TestTheIdleWarning:
    def test_it_is_left_to_the_server_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        #  None asks for half the idle timeout, which only the server knows.
        seen = _intercept_serve(monkeypatch)
        CliRunner().invoke(_service(), ["serve"])
        assert seen["warn_after"] is None

    def test_a_time_can_be_given(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = _intercept_serve(monkeypatch)
        CliRunner().invoke(_service(), ["serve", "--warn-after", "30"])
        assert seen["warn_after"] == 30.0

    def test_zero_turns_it_off(self, monkeypatch: pytest.MonkeyPatch) -> None:
        seen = _intercept_serve(monkeypatch)
        CliRunner().invoke(_service(), ["serve", "--warn-after", "0"])
        assert seen["warn_after"] == 0.0


class TestRenderingThroughTheCommand:
    def test_render_draws_the_page(self) -> None:
        result = CliRunner().invoke(_service(), ["render", "--page", "1"])
        assert result.exit_code == 0
        assert "Hello." in result.output

    def test_render_without_a_page_is_refused_before_the_app_is_built(self) -> None:
        built: list[bool] = []

        def load(context: click.Context) -> Sextile:
            built.append(True)
            return _APP

        result = CliRunner().invoke(_service(load=load), ["render"])
        assert result.exit_code == 2
        assert built == []

    def test_the_form_options_reach_render(self) -> None:
        result = CliRunner().invoke(_service(), ["render", "--page", "1", "--form", "bytes"])
        assert result.exit_code == 0

    def test_a_service_option_reaches_both_commands(self) -> None:
        seen: dict[str, Any] = {}

        def load(context: click.Context) -> Sextile:
            seen["database"] = context.params["database"]
            return _APP

        option = click.option("--database", default="here")
        cli = _service(load=load, options=[option])
        result = CliRunner().invoke(cli, ["render", "--page", "1"])
        assert result.exit_code == 0
        assert seen["database"] == "here"


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


class TestTheHelpFormats:
    #  Issue #1: argparse treated a help string as a printf template, so a literal
    #  % in one crashed --help. Click does not, but the help must still format.

    def test_serve_help_is_shown(self) -> None:
        result = CliRunner().invoke(_service(), ["serve", "--help"])
        assert result.exit_code == 0
        assert "warn" in result.output.lower()

    def test_render_help_is_shown(self) -> None:
        result = CliRunner().invoke(_service(), ["render", "--help"])
        assert result.exit_code == 0
        assert "--page" in result.output


class TestTheSextileCommandLine:
    """The framework's own command line, over a module:name."""

    def test_no_command_prints_help_and_succeeds(self) -> None:
        from sextile.__main__ import main

        result = CliRunner().invoke(main, [])
        assert result.exit_code == 0
        assert "serve" in result.output and "render" in result.output

    def test_serve_help_formats(self) -> None:
        from sextile.__main__ import main

        result = CliRunner().invoke(main, ["serve", "--help"])
        assert result.exit_code == 0
        assert "--max-connections" in result.output

    def test_render_needs_an_application(self) -> None:
        from sextile.__main__ import main

        result = CliRunner().invoke(main, ["render", "--page", "1"])
        assert result.exit_code == 2
