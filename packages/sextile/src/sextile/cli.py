"""The pieces both command lines are built from.

Sextile has a command of its own, which can serve or draw any application, and
an application generally wants one too -- if only to say where its data lives.
Neither should have to reimplement the other, so what they share is here.
"""

import argparse
import asyncio
import importlib
import sys
from contextlib import suppress
from typing import Final

from sextile.addressing import PageAddress, UnknownPageError
from sextile.application import Application, PageRequest
from sextile.server import DEFAULT_PORT, serve
from sextile.viewdata.ansi import render_ansi
from sextile.viewdata.frame import Frame

#: How a frame can be shown on a terminal that is not a BBC Micro.
FORMS: Final = ("ansi", "grid", "bytes")

_FORM_HELP: Final = (
    "ansi: colour, as the Beeb would draw it; "
    "grid: character and attribute layers; "
    "bytes: the wire stream, as a hex dump"
)


class ApplicationSpecError(ValueError):
    """A `module:name` that does not name an application."""


def load_application(spec: str) -> Application:
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
    if not isinstance(found, Application) and callable(found):
        found = found()
    if not isinstance(found, Application):
        raise ApplicationSpecError(f"{spec!r} is a {type(found).__name__}, not an application")
    return found


def add_form_arguments(parser: argparse.ArgumentParser) -> None:
    """The arguments deciding how a frame is shown."""
    parser.add_argument("--frame", type=int, default=0, help="Which frame of it (0 for the first)")
    parser.add_argument("--form", choices=FORMS, default="ansi", help=_FORM_HELP)
    parser.add_argument("--no-colour", action="store_true", help="Suppress ANSI colour")


def add_listening_arguments(parser: argparse.ArgumentParser) -> None:
    """The arguments deciding where a service answers."""
    parser.add_argument("--host", default="127.0.0.1", help="Address to listen on")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default {DEFAULT_PORT})"
    )


async def render_page(application: Application, arguments: argparse.Namespace) -> int:
    """Draw one frame of one page, and say where its keys lead."""
    try:
        address = PageAddress(arguments.page)
    except UnknownPageError as error:
        print(error, file=sys.stderr)
        return 2

    await application.startup()
    try:
        page = await application.respond(PageRequest(address=address))
        if page is None:
            print(f"*{address}# is not a page there.", file=sys.stderr)
            return 2
        index = int(arguments.frame)
        found = page.frame(index)
        if found is None:
            print(f"That page has {len(page.frames)} frame(s).", file=sys.stderr)
            return 2
        choices = ", ".join(
            f"{key}->*{destination}#" for key, destination in sorted(found.choices.items())
        )
        print(f"*{address.frame_number(index)}#   choices: {choices}", file=sys.stderr)
        print(rendered(found.frame, arguments.form, colour=not arguments.no_colour))
    finally:
        await application.shutdown()
    return 0


async def run_service(application: Application, arguments: argparse.Namespace) -> int:
    """Answer calls until interrupted."""
    await application.startup()
    try:
        server = await serve(application, host=arguments.host, port=arguments.port)
        print(
            f"Sextile answering on {arguments.host}:{arguments.port}.\n"
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
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hexadecimal = " ".join(f"{byte:02X}" for byte in chunk)
        printable = "".join(chr(byte) if 0x20 <= byte < 0x7F else "." for byte in chunk)
        lines.append(f"{offset:04X}  {hexadecimal:<{width * 3}} |{printable}|")
    return "\n".join(lines)
