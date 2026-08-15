"""The pieces both command lines are built from.

Sextile has a command of its own, which can serve or draw any application, and
an application generally needs one too -- if only to say where its data lives.
Neither should have to reimplement the other, so what they share is here.
"""

import argparse
import asyncio
import importlib
import logging
import sys
from collections.abc import Callable
from contextlib import suppress
from html import escape
from typing import Final

from sextile.application import Sextile
from sextile.page import PageAddress, UnknownPageError, keyed
from sextile.server import (
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_PORT,
    DEFAULT_WARN_FRACTION,
    serve,
)
from sextile.viewdata.ansi import render_ansi
from sextile.viewdata.frame import Frame
from sextile.viewdata.html import font_face, render_html, stylesheet

__all__ = [
    "ApplicationSpecError",
    "add_form_arguments",
    "add_listening_arguments",
    "add_standard_subcommands",
    "render_page",
    "run_service",
    "run_standard",
]

#: How a frame can be shown on a terminal that is not a BBC Micro.
FORMS: Final = ("ansi", "grid", "bytes", "html")

_FORM_HELP: Final = (
    "html: a self-contained web page, drawn with Bedstead; "
    "ansi: colour, as the Beeb would draw it; "
    "grid: character and attribute layers; "
    "bytes: the wire stream, as a hex dump"
)


class ApplicationSpecError(ValueError):
    """A `module:name` that does not name an application."""


def load_application(spec: str) -> Sextile:
    """Load the application a `module:name` specification names.

    Args:
        spec: A `module:name`, the same shape a WSGI or ASGI server takes: what
            is served is chosen when the server starts, not when it is written.

    Returns:
        The application. A callable is called, so a factory works as well as an
        instance.

    Raises:
        ApplicationSpecError: If the spec is malformed, the module will not
            import, the name is absent, or the value is not a `Sextile`.
    """
    module_name, separator, attribute = spec.partition(":")
    if not module_name or not separator or not attribute:
        raise ApplicationSpecError(f"{spec!r} is not a module:name specification")
    try:
        module = importlib.import_module(module_name)
    except ImportError as error:
        raise ApplicationSpecError(f"{module_name!r} cannot be imported: {error}") from error
    try:
        found = getattr(module, attribute)
    except AttributeError:
        raise ApplicationSpecError(f"{module_name!r} has no {attribute!r}") from None
    if not isinstance(found, Sextile) and callable(found):
        found = found()
    if not isinstance(found, Sextile):
        raise ApplicationSpecError(f"{spec!r} is a {type(found).__name__}, not an application")
    return found


def add_form_arguments(parser: argparse.ArgumentParser) -> None:
    """Add to a parser the arguments that choose how a frame is shown.

    Args:
        parser: The parser to add `--frame`, `--form` and `--no-colour` to.
    """
    parser.add_argument("--frame", type=int, default=0, help="Which frame of it (0 for the first)")
    parser.add_argument("--form", choices=FORMS, default="ansi", help=_FORM_HELP)
    parser.add_argument("--no-colour", action="store_true", help="Suppress ANSI colour")


def add_listening_arguments(parser: argparse.ArgumentParser) -> None:
    """Add to a parser the arguments for where a service answers and for how long.

    Args:
        parser: The parser to add `--host`, `--port`, `--idle-timeout` and
            `--warn-after` to.
    """
    parser.add_argument("--host", default="127.0.0.1", help="Address to listen on")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default {DEFAULT_PORT})"
    )
    parser.add_argument(
        "--idle-timeout",
        type=_seconds,
        default=DEFAULT_IDLE_TIMEOUT,
        metavar="SECONDS",
        help=(
            f"Release a caller who says nothing for this long "
            f"(default {DEFAULT_IDLE_TIMEOUT:.0f}; 0 to hold the line indefinitely)"
        ),
    )
    parser.add_argument(
        "--warn-after",
        type=_seconds,
        default=None,
        metavar="SECONDS",
        help=(
            "Warn a silent caller after this long, with a bar that drains "
            f"(default: {DEFAULT_WARN_FRACTION:.0%} of the idle timeout; 0 for no warning)"
        ),
    )


def _seconds(text: str) -> float:
    """A non-negative number of seconds, for argparse to report on."""
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number of seconds") from None
    if value < 0:
        #  A negative timeout would release the line before the greeting had
        #  finished arriving, which looks like a fault rather than a setting.
        raise argparse.ArgumentTypeError(f"{text!r} is not a length of time")
    return value


async def render_page(application: Sextile, arguments: argparse.Namespace) -> int:
    """Render one frame of one page to standard output, its keys to standard error.

    Args:
        application: The service to fetch the page from.
        arguments: The parsed `--page`, `--frame`, `--form` and `--no-colour`.

    Returns:
        A process exit code: 0 drawn, 2 where the page, frame or number is not
        there.
    """
    try:
        address = PageAddress(arguments.page)
    except UnknownPageError as error:
        print(error, file=sys.stderr)
        return 2

    await application.startup()
    try:
        page = await application.fetch(address)
        if page is None:
            print(f"{keyed(address)} is not a page there.", file=sys.stderr)
            return 2
        index = int(arguments.frame)
        found = page.frame(index)
        if found is None:
            print(f"That page has {len(page.frames)} frame(s).", file=sys.stderr)
            return 2
        choices = ", ".join(
            f"{key}->*{destination}#" for key, destination in sorted(found.choices.items())
        )
        print(
            f"{keyed(address.frame_number(index))}   choices: {choices}",
            file=sys.stderr,
        )
        print(
            rendered(
                found.frame,
                arguments.form,
                colour=not arguments.no_colour,
                title=keyed(address.frame_number(index)),
            )
        )
    finally:
        await application.shutdown()
    return 0


async def run_service(application: Sextile, arguments: argparse.Namespace) -> int:
    """Serve the application until interrupted.

    Args:
        application: The service to serve.
        arguments: The parsed listening arguments.

    Returns:
        A process exit code, 0 once interrupted.
    """
    #  Zero means hold the line indefinitely, which is what `asyncio.wait_for`
    #  spells as no timeout at all. Zero seconds would otherwise mean releasing
    #  a caller the instant they stopped typing.
    idle_timeout = arguments.idle_timeout or None
    await application.startup()
    try:
        server = await serve(
            application,
            host=arguments.host,
            port=arguments.port,
            idle_timeout=idle_timeout,
            warn_after=arguments.warn_after,
        )
        print(
            f"Sextile answering on {arguments.host}:{arguments.port}, "
            f"{_releasing(idle_timeout)}.\n"
            f"Dial it with:  tcpser -v 25232 -s 9600 -l 4 -t sS "
            f"-n 1={arguments.host}:{arguments.port}\n"
            f"Or try it with:  nc {arguments.host} {arguments.port}",
            file=sys.stderr,
        )
        async with server:
            with suppress(KeyboardInterrupt, asyncio.CancelledError):
                await server.serve_forever()
    finally:
        await application.shutdown()
    return 0


def _releasing(idle_timeout: float | None) -> str:
    """What the service will do with a caller who says nothing."""
    if idle_timeout is None:
        return "holding idle callers indefinitely"
    return f"releasing idle callers after {idle_timeout:.0f}s"


def add_standard_subcommands(
    subcommands: "argparse._SubParsersAction[argparse.ArgumentParser]",
    *,
    configure: Callable[[argparse.ArgumentParser], None] = lambda parser: None,
    page_example: str = "1",
) -> None:
    """Add the `render` and `serve` subcommands every service's command line shares.

    A service adds its own subcommands to the same `subcommands` afterwards --
    Stardot its `ingest`, the weather its `import-places`. `run_standard`
    dispatches the two added here.

    Args:
        subcommands: The action returned by `parser.add_subparsers`, to add
            `render` and `serve` to.
        configure: Called with each of the two subparsers, to add the arguments
            a service needs to find its own data, such as a database path. The
            same call runs against both, so `render` and `serve` agree about
            where the data lives without the service saying it twice.
        page_example: A page number to show in `render --page`'s help, such as
            `"1 or 82489493"`.
    """
    render = subcommands.add_parser("render", help="Show a frame without a BBC Micro")
    render.add_argument("--page", help=f"Render a page by its number, such as {page_example}")
    add_form_arguments(render)
    configure(render)

    serve = subcommands.add_parser("serve", help="Answer calls from terminals")
    add_listening_arguments(serve)
    configure(serve)


def run_standard(
    arguments: argparse.Namespace,
    load: Callable[[argparse.Namespace], Sextile],
) -> int | None:
    """Run `render` or `serve`, or return None where the command is neither.

    The counterpart of `add_standard_subcommands`: a service's `main` calls this
    and, where it returns None, dispatches its own subcommands instead.

    Args:
        arguments: The parsed command line, whose `command` selects what runs.
        load: Builds the service from the arguments, called only for a command
            that needs it, so an unfindable data path fails no earlier than the
            command that reads it.

    Returns:
        The process exit status for `render` or `serve`, or None where the
        command is one the caller handles itself.
    """
    if arguments.command == "render":
        if arguments.page is None:
            print("Nothing to render: pass --page <number>.", file=sys.stderr)
            return 2
        return asyncio.run(render_page(load(arguments), arguments))
    if arguments.command == "serve":
        #  A server logs page by page as it answers; without this the middleware's
        #  lines would go nowhere. The timestamp is what a log of a long-running
        #  service is read by.
        logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
        return asyncio.run(run_service(load(arguments), arguments))
    return None


def rendered(frame: Frame, form: str, *, colour: bool, title: str = "") -> str:
    """One frame, in whichever of the forms was asked for.

    Args:
        frame: The frame to draw.
        form: One of `FORMS`.
        colour: Whether the `ansi` form carries colour.
        title: What the `html` form names the page in its `<title>`; ignored by
            the others.
    """
    if form == "ansi":
        return render_ansi(frame, colour=colour)
    if form == "html":
        return _html_page(frame, title)
    if form == "grid":
        characters, attributes = frame.to_grid()
        return "\n".join(
            [
                "characters:",
                *(f"  {row:2d} |{line}|" for row, line in enumerate(characters)),
                "attributes:",
                *(f"  {row:2d} |{line}|" for row, line in enumerate(attributes)),
            ]
        )
    return hex_dump(frame.to_bytes())


def _html_page(frame: Frame, title: str = "") -> str:
    """A frame as a self-contained HTML page: the font, the stylesheet, the frame."""
    head = f"<title>{escape(title)}</title>\n" if title else ""
    return (
        f'<!doctype html>\n<meta charset="utf-8">\n{head}<style>\n'
        f"{font_face()}\n{stylesheet()}</style>\n{render_html(frame)}\n"
    )


def hex_dump(data: bytes, width: int = 16) -> str:
    """Lay bytes out as offset, hexadecimal and printable characters.

    Args:
        data: The bytes to show.
        width: How many bytes to a line.

    Returns:
        The dump, one line a row of `width` bytes, with unprintable bytes
        shown as full stops.
    """
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hexadecimal = " ".join(f"{byte:02X}" for byte in chunk)
        printable = "".join(chr(byte) if 0x20 <= byte < 0x7F else "." for byte in chunk)
        lines.append(f"{offset:04X}  {hexadecimal:<{width * 3}} |{printable}|")
    return "\n".join(lines)
