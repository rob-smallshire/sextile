"""The pieces both command lines are built from.

Sextile has a command of its own, which can serve or draw any application, and
an application generally needs one too -- if only to say where its data lives.
Neither should have to reimplement the other, so what they share is here.
"""

import argparse
import asyncio
import importlib
import sys
from contextlib import suppress
from typing import Final

from sextile.addressing import PageAddress, UnknownPageError, keyed
from sextile.application import Sextile
from sextile.server import (
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_PORT,
    DEFAULT_WARN_FRACTION,
    serve,
)
from sextile.viewdata.ansi import render_ansi
from sextile.viewdata.frame import Frame

__all__ = [
    "ApplicationSpecError",
    "add_form_arguments",
    "add_listening_arguments",
    "render_page",
    "run_service",
]

#: How a frame can be shown on a terminal that is not a BBC Micro.
FORMS: Final = ("ansi", "grid", "bytes")

_FORM_HELP: Final = (
    "ansi: colour, as the Beeb would draw it; "
    "grid: character and attribute layers; "
    "bytes: the wire stream, as a hex dump"
)


class ApplicationSpecError(ValueError):
    """A `module:name` that does not name an application."""


def load_application(spec: str) -> Sextile:
    """The application a `module:name` specification names.

    The same shape as a WSGI or ASGI server's, and for the same reason: the
    thing being served is chosen when the server is started, not when it is
    written. A callable is called, so a factory works as well as an instance.
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
    """The arguments deciding how a frame is shown."""
    parser.add_argument("--frame", type=int, default=0, help="Which frame of it (0 for the first)")
    parser.add_argument("--form", choices=FORMS, default="ansi", help=_FORM_HELP)
    parser.add_argument("--no-colour", action="store_true", help="Suppress ANSI colour")


def add_listening_arguments(parser: argparse.ArgumentParser) -> None:
    """The arguments deciding where a service answers, and for how long."""
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
    """Draw one frame of one page, and say where its keys lead."""
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
        print(rendered(found.frame, arguments.form, colour=not arguments.no_colour))
    finally:
        await application.shutdown()
    return 0


async def run_service(application: Sextile, arguments: argparse.Namespace) -> int:
    """Answer calls until interrupted."""
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


def rendered(frame: Frame, form: str, *, colour: bool) -> str:
    """One frame, in whichever of the three forms was asked for."""
    if form == "ansi":
        return render_ansi(frame, colour=colour)
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
