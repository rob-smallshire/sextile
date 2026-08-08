"""The pieces both command lines are built from.

Argument plumbing is worth a test of its own: an option that is parsed but never
passed on is the kind of fault that looks like it works.
"""

import argparse
import asyncio
from typing import Any

import pytest
from exemplar import Board

from sextile.application import Application
from sextile.cli import (
    ApplicationSpecError,
    add_listening_arguments,
    load_application,
    run_service,
)
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

        async def fake_serve(application: Application, **keywords: Any) -> _StoppedServer:
            seen.update(keywords)
            return _StoppedServer()

        monkeypatch.setattr("sextile.cli.serve", fake_serve)
        arguments = parse("--host", "0.0.0.0", "--port", "1", "--idle-timeout", "90")
        await run_service(Board(), arguments)
        assert seen == {"host": "0.0.0.0", "port": 1, "idle_timeout": 90.0}

    async def test_zero_becomes_no_timeout_at_all(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        #  `asyncio.wait_for` takes None to mean "wait", and zero seconds would
        #  otherwise mean "drop the line immediately", which nobody wants.
        seen: dict[str, Any] = {}

        async def fake_serve(application: Application, **keywords: Any) -> _StoppedServer:
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

        async def fake_serve(application: Application, **keywords: Any) -> _StoppedServer:
            events.append("serving")
            return _StoppedServer()

        monkeypatch.setattr("sextile.cli.serve", fake_serve)
        await run_service(Recording(), parse())
        assert events == ["startup", "serving", "shutdown"]


class TestLoadingAnApplication:
    def test_a_module_and_name(self) -> None:
        assert isinstance(load_application("exemplar:Board"), Application)

    @pytest.mark.parametrize(
        "spec", ["exemplar", "exemplar:", ":Board", "nosuchmodule:app", "exemplar:Missing"]
    )
    def test_a_specification_that_names_no_application(self, spec: str) -> None:
        with pytest.raises(ApplicationSpecError):
            load_application(spec)

    def test_something_that_is_not_an_application(self) -> None:
        with pytest.raises(ApplicationSpecError):
            load_application("exemplar:ITEMS")
