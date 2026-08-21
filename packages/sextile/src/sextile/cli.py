"""The pieces both command lines are built from.

Sextile has a command of its own, which can serve or draw any application, and
an application generally needs one too -- if only to say where its data lives.
Neither should have to reimplement the other, so what they share is here.

The command line is Click. A service builds its own `click.Group` and adds the
`render` and `serve` commands `standard_commands` returns; the framework's own
command line is that same pair over a `module:name`.
"""

import asyncio
import importlib
import logging
import sys
from collections.abc import Callable, Sequence
from contextlib import suppress
from html import escape
from typing import Any, Final

import click

from sextile.application import Sextile
from sextile.page import PageAddress, UnknownPageError, keyed
from sextile.server import (
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_MAX_CONNECTIONS,
    DEFAULT_PORT,
    DEFAULT_WARN_FRACTION,
    serve,
)
from sextile.viewdata.ansi import render_ansi
from sextile.viewdata.frame import Frame
from sextile.viewdata.html import font_face, render_html, stylesheet

__all__ = [
    "CONTEXT_SETTINGS",
    "ApplicationSpecError",
    "form_options",
    "listening_options",
    "load_application",
    "render_page",
    "run_service",
    "standard_commands",
]

#: How a frame can be shown on a terminal that is not a BBC Micro.
FORMS: Final = ("ansi", "grid", "bytes", "html")

_FORM_HELP: Final = (
    "html: a self-contained web page, drawn with Bedstead; "
    "ansi: colour, as the Beeb would draw it; "
    "grid: character and attribute layers; "
    "bytes: the wire stream, as a hex dump"
)

#: `-h` as well as `--help`, the way argparse offered both, on every command.
CONTEXT_SETTINGS: Final = {"help_option_names": ["-h", "--help"]}


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
    #  Resolve the module from the working directory as well as the installed
    #  packages, the way an ASGI server does: `sextile serve my_service:app` is
    #  run beside the file it names, which is not otherwise on the path when the
    #  command is an installed console script.
    if "" not in sys.path:
        sys.path.insert(0, "")
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


#: A Click decorator: something that adds options to a command and returns it.
_Decorator = Callable[[Any], Any]


def form_options(command: Any) -> Any:
    """Add `--frame`, `--form` and `--no-colour` to a Click command.

    Args:
        command: The command to add them to.

    Returns:
        The command, so it composes as a decorator.
    """
    #  Applied last-to-first: Click reverses the options it collects, so this
    #  order is what `--help` lists top to bottom (frame, form, no-colour).
    command = click.option("--no-colour", is_flag=True, help="Suppress ANSI colour")(command)
    command = click.option(
        "--form", type=click.Choice(FORMS), default="ansi", help=_FORM_HELP
    )(command)
    return click.option(
        "--frame", type=int, default=0, help="Which frame of it (0 for the first)"
    )(command)


def listening_options(command: Any) -> Any:
    """Add `--host`, `--port`, `--idle-timeout`, `--warn-after` and `--max-connections`.

    Args:
        command: The command to add them to.

    Returns:
        The command, so it composes as a decorator.
    """
    #  Applied last-to-first: Click reverses the options it collects, so this is
    #  the order `--help` lists (host, port, idle-timeout, warn-after, then max).
    command = click.option(
        "--max-connections",
        type=int,
        default=DEFAULT_MAX_CONNECTIONS,
        metavar="N",
        help=(
            f"How many callers may be on the line at once "
            f"(default {DEFAULT_MAX_CONNECTIONS}; 0 for no ceiling)"
        ),
    )(command)
    command = click.option(
        "--warn-after",
        type=click.FloatRange(min=0),
        default=None,
        metavar="SECONDS",
        help=(
            "Warn a silent caller after this long, with a bar that drains "
            f"(default: {DEFAULT_WARN_FRACTION * 100:.0f} percent of the idle "
            "timeout; 0 for no warning)"
        ),
    )(command)
    command = click.option(
        "--idle-timeout",
        type=click.FloatRange(min=0),
        default=DEFAULT_IDLE_TIMEOUT,
        metavar="SECONDS",
        help=(
            f"Release a caller who says nothing for this long "
            f"(default {DEFAULT_IDLE_TIMEOUT:.0f}; 0 to hold the line indefinitely)"
        ),
    )(command)
    command = click.option(
        "--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default {DEFAULT_PORT})"
    )(command)
    return click.option("--host", default="127.0.0.1", help="Address to listen on")(command)


async def render_page(
    application: Sextile,
    *,
    page: str,
    frame: int = 0,
    form: str = "ansi",
    colour: bool = True,
) -> int:
    """Render one frame of one page to standard output, its keys to standard error.

    Args:
        application: The service to fetch the page from.
        page: The page number to draw.
        frame: Which frame of a page that runs to several, the first by default.
        form: One of `FORMS`.
        colour: Whether the `ansi` form carries colour.

    Returns:
        A process exit code: 0 drawn, 2 where the page, frame or number is not
        there.
    """
    try:
        address = PageAddress(page)
    except UnknownPageError as error:
        print(error, file=sys.stderr)
        return 2

    await application.startup()
    try:
        drawn = await application.fetch(address)
        if drawn is None:
            print(f"{keyed(address)} is not a page there.", file=sys.stderr)
            return 2
        found = drawn.frame(frame)
        if found is None:
            print(f"That page has {len(drawn.frames)} frame(s).", file=sys.stderr)
            return 2
        choices = ", ".join(
            f"{key}->*{destination}#" for key, destination in sorted(found.choices.items())
        )
        print(
            f"{keyed(address.frame_number(frame))}   choices: {choices}",
            file=sys.stderr,
        )
        print(
            rendered(
                found.frame,
                form,
                colour=colour,
                title=keyed(address.frame_number(frame)),
            )
        )
    finally:
        await application.shutdown()
    return 0


async def run_service(
    application: Sextile,
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    idle_timeout: float = DEFAULT_IDLE_TIMEOUT,
    warn_after: float | None = None,
    max_connections: int = DEFAULT_MAX_CONNECTIONS,
) -> int:
    """Serve the application until interrupted.

    Args:
        application: The service to serve.
        host: The address to listen on.
        port: The port to listen on.
        idle_timeout: Seconds a caller may be silent before the line is released;
            0 holds it indefinitely.
        warn_after: Seconds before the draining warning appears, or None for half
            the idle timeout.
        max_connections: How many callers may be on the line at once; 0 for no
            ceiling.

    Returns:
        A process exit code, 0 once interrupted.
    """
    #  Zero means hold the line indefinitely, which is what `asyncio.wait_for`
    #  spells as no timeout at all. Zero seconds would otherwise mean releasing
    #  a caller the instant they stopped typing.
    timeout = idle_timeout or None
    await application.startup()
    try:
        server = await serve(
            application,
            host=host,
            port=port,
            idle_timeout=timeout,
            warn_after=warn_after,
            #  Zero means no ceiling, the way zero means hold the line for the
            #  idle timeout.
            max_connections=max_connections or None,
        )
        print(
            f"Sextile answering on {host}:{port}, "
            f"{_releasing(timeout)}.\n"
            f"Dial it with:  tcpser -v 25232 -s 9600 -l 4 -t sS "
            f"-n 1={host}:{port}\n"
            f"Or try it with:  nc {host} {port}",
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


def standard_commands(
    load: Callable[[click.Context], Sextile],
    *,
    options: Sequence[_Decorator] = (),
    page_example: str = "1",
) -> tuple[click.Command, click.Command]:
    """The `render` and `serve` commands every service's command line shares.

    A service adds these to its own `click.Group`, and its own commands beside
    them -- Stardot its `ingest`, the weather its `import-places`. Click routes to
    each, so there is nothing to dispatch by hand.

    Args:
        load: Builds the application from a command's `click.Context`, whose
            `params` hold the values the `options` collected. Called only for a
            command that needs it, and for `render` only once `--page` is present,
            so an unfindable data path fails no earlier than the command reading
            it.
        options: Click option decorators added to both commands, for the
            arguments a service needs to find its data, such as a database path.
            The same decorators run against both, so `render` and `serve` agree
            about where the data lives without the service saying it twice.
        page_example: A page number to show in `render --page`'s help, such as
            `"1 or 82489493"`.

    Returns:
        The `render` and `serve` commands, for `group.add_command`.

    Example:
        >>> import click
        >>> @click.group()
        ... def app() -> None: ...
        >>> for command in standard_commands(lambda context: ...):  # doctest: +SKIP
        ...     app.add_command(command)
    """

    @click.command(
        "render", context_settings=CONTEXT_SETTINGS, help="Show a frame without a BBC Micro"
    )
    @click.option(
        "--page", default=None, help=f"Render a page by its number, such as {page_example}"
    )
    @form_options
    @click.pass_context
    def render(context: click.Context, /, **_: object) -> None:
        context.exit(_run_render(context, load))

    @click.command(
        "serve", context_settings=CONTEXT_SETTINGS, help="Answer calls from terminals"
    )
    @listening_options
    @click.pass_context
    def serve_command(context: click.Context, /, **_: object) -> None:
        context.exit(_run_serve(context, load))

    for option in options:
        render = option(render)
        serve_command = option(serve_command)
    return render, serve_command


def _load(context: click.Context, load: Callable[[click.Context], Sextile]) -> Sextile | None:
    """Build the application, or print why not and leave the caller to exit 2."""
    try:
        return load(context)
    except ApplicationSpecError as error:
        print(error, file=sys.stderr)
        return None


def _run_render(context: click.Context, load: Callable[[click.Context], Sextile]) -> int:
    """Draw a page for a `render` command, refusing before the data is opened."""
    page = context.params["page"]
    if page is None:
        print("Nothing to render: pass --page <number>.", file=sys.stderr)
        return 2
    application = _load(context, load)
    if application is None:
        return 2
    return asyncio.run(
        render_page(
            application,
            page=page,
            frame=context.params["frame"],
            form=context.params["form"],
            colour=not context.params["no_colour"],
        )
    )


def _run_serve(context: click.Context, load: Callable[[click.Context], Sextile]) -> int:
    """Serve for a `serve` command, logging as it answers."""
    application = _load(context, load)
    if application is None:
        return 2
    #  A server logs page by page as it answers; without this the middleware's
    #  lines would go nowhere. The timestamp is what a log of a long-running
    #  service is read by.
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
    return asyncio.run(
        run_service(
            application,
            host=context.params["host"],
            port=context.params["port"],
            idle_timeout=context.params["idle_timeout"],
            warn_after=context.params["warn_after"],
            max_connections=context.params["max_connections"],
        )
    )


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
