"""The framework's own command line.

It can serve or draw any application, named the way a WSGI or ASGI server names
one:

    sextile serve stardot_viewdata:app
    sextile render stardot_viewdata:app --page 82489493
    sextile render --demo

The demonstration frame needs no application, being a picture of what the
framework itself can draw.
"""

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from sextile import __version__
from sextile.cli import (
    ApplicationSpecError,
    add_form_arguments,
    add_listening_arguments,
    load_application,
    render_page,
    rendered,
    run_service,
)
from sextile.demo import demo_frame


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sextile", description="A framework for Viewdata services"
    )
    parser.add_argument("--version", action="version", version=f"sextile {__version__}")
    subcommands = parser.add_subparsers(dest="command")

    render = subcommands.add_parser("render", help="Show a frame without a BBC Micro")
    render.add_argument(
        "application",
        nargs="?",
        help="The application to draw, as module:name",
    )
    render.add_argument("--demo", action="store_true", help="Render the demonstration frame")
    render.add_argument("--page", help="Render a page by its number, such as 1 or 82489493")
    add_form_arguments(render)

    serve_command = subcommands.add_parser("serve", help="Answer calls from terminals")
    serve_command.add_argument("application", help="The application to serve, as module:name")
    add_listening_arguments(serve_command)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    match arguments.command:
        case "render":
            return _render(arguments)
        case "serve":
            return _serve(arguments)
        case _:
            parser.print_help()
            return 0


def _render(arguments: argparse.Namespace) -> int:
    if arguments.demo:
        print(rendered(demo_frame(), arguments.form, colour=not arguments.no_colour))
        return 0
    if arguments.application is None or arguments.page is None:
        print(
            "Nothing to render: pass --demo, or an application and --page <number>.",
            file=sys.stderr,
        )
        return 2
    try:
        application = load_application(arguments.application)
    except ApplicationSpecError as error:
        print(error, file=sys.stderr)
        return 2
    return asyncio.run(render_page(application, arguments))


def _serve(arguments: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
    try:
        application = load_application(arguments.application)
    except ApplicationSpecError as error:
        print(error, file=sys.stderr)
        return 2
    return asyncio.run(run_service(application, arguments))


if __name__ == "__main__":
    sys.exit(main())
