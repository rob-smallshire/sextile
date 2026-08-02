"""Command-line entry point for Sextile."""

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from sextile import __version__
from sextile.content.html import parse_post_body
from sextile.feed.client import FeedClient
from sextile.feed.ingest import (
    DEFAULT_POLL_INTERVAL,
    IngestResult,
    ingest_once,
    poll,
    seed,
)
from sextile.feed.source import STARDOT_BASE_URL, AtomFeedSource
from sextile.model import Post
from sextile.pages.demo import demo_frame
from sextile.pages.numbering import UnknownPageError, format_page_number, parse_page_number
from sextile.pages.router import resolve
from sextile.server import DEFAULT_PORT, serve
from sextile.store.repository import Repository
from sextile.viewdata.ansi import render_ansi
from sextile.viewdata.frame import Frame
from sextile.viewdata.layout import lay_out

DEFAULT_DATABASE_FILEPATH = Path("sextile.sqlite")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sextile", description="A Viewdata service for Stardot")
    parser.add_argument("--version", action="version", version=f"sextile {__version__}")
    subcommands = parser.add_subparsers(dest="command")

    render = subcommands.add_parser("render", help="Show a frame without a BBC Micro")
    render.add_argument("--demo", action="store_true", help="Render the demonstration frame")
    render.add_argument("--post", type=int, help="Render a post from the archive, by its id")
    render.add_argument("--page", help="Render a page by its number, such as 1 or 82489493")
    render.add_argument("--frame", type=int, default=0, help="Which frame of it (0 for the first)")
    _add_database_argument(render)
    render.add_argument(
        "--form",
        choices=["ansi", "grid", "bytes"],
        default="ansi",
        help=(
            "ansi: colour, as the Beeb would draw it; "
            "grid: character and attribute layers; "
            "bytes: the wire stream, as a hex dump"
        ),
    )
    render.add_argument("--no-colour", action="store_true", help="Suppress ANSI colour")

    ingest = subcommands.add_parser("ingest", help="Fetch the feed into the archive")
    ingest.add_argument("--once", action="store_true", help="Poll once and stop")
    ingest.add_argument(
        "--seed",
        action="store_true",
        help="Sweep every route the board publishes, to fill a new archive",
    )
    ingest.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL,
        help=f"Seconds between polls (default {DEFAULT_POLL_INTERVAL:.0f})",
    )
    _add_database_argument(ingest)

    archive = subcommands.add_parser("archive", help="Report what the archive holds")
    _add_database_argument(archive)

    serve_command = subcommands.add_parser("serve", help="Answer calls from terminals")
    serve_command.add_argument("--host", default="127.0.0.1", help="Address to listen on")
    serve_command.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Port to listen on (default {DEFAULT_PORT})"
    )
    _add_database_argument(serve_command)

    return parser


def _add_database_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database-filepath",
        type=Path,
        default=DEFAULT_DATABASE_FILEPATH,
        help=f"Where the archive lives (default: {DEFAULT_DATABASE_FILEPATH})",
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(argv)

    match arguments.command:
        case "render":
            return _render(arguments)
        case "ingest":
            return asyncio.run(_ingest(arguments))
        case "archive":
            return _archive(arguments)
        case "serve":
            return asyncio.run(_serve(arguments))
        case _:
            parser.print_help()
            return 0


def _render(arguments: argparse.Namespace) -> int:
    if arguments.demo:
        frame = demo_frame()
    elif arguments.page is not None:
        found_page = _page_frame(arguments)
        if found_page is None:
            return 2
        frame = found_page
    elif arguments.post is not None:
        found = _post_frame(arguments)
        if found is None:
            return 2
        frame = found
    else:
        print("Nothing to render: pass --demo, --page <number> or --post <id>.", file=sys.stderr)
        return 2
    print(_rendered(frame, arguments.form, colour=not arguments.no_colour))
    return 0


def _page_frame(arguments: argparse.Namespace) -> Frame | None:
    try:
        reference = parse_page_number(arguments.page)
    except UnknownPageError as error:
        print(error, file=sys.stderr)
        return None
    with Repository.open(arguments.database_filepath) as repository:
        page = resolve(reference, repository)
    index = int(arguments.frame)
    found = page.frame(index)
    if found is None:
        print(f"That page has {len(page.frames)} frame(s).", file=sys.stderr)
        return None
    choices = ", ".join(
        f"{digit}->*{format_page_number(destination)}#"
        for digit, destination in sorted(found.choices.items())
    )
    print(f"*{page.frame_number(index)}#   choices: {choices}", file=sys.stderr)
    return found.frame


def _post_frame(arguments: argparse.Namespace) -> Frame | None:
    with Repository.open(arguments.database_filepath) as repository:
        post: Post | None = repository.post(arguments.post)
    if post is None:
        print(f"No post {arguments.post} in the archive.", file=sys.stderr)
        return None
    frames = lay_out(parse_post_body(post.content_html))
    index = int(arguments.frame)
    if not 0 <= index < len(frames):
        print(f"That post has {len(frames)} frame(s).", file=sys.stderr)
        return None
    print(
        f"{post.subject}  -- {post.author_name}, "
        f"frame {index + 1} of {len(frames)}  *82{post.post_id}#",
        file=sys.stderr,
    )
    return frames[index]


async def _ingest(arguments: argparse.Namespace) -> int:
    with Repository.open(arguments.database_filepath) as repository:
        async with FeedClient(STARDOT_BASE_URL) as client:
            source = AtomFeedSource(client)
            if arguments.seed:
                print(
                    "Seeding from every route the board publishes. The site asks for "
                    "60 seconds\nbetween requests, so this takes a few minutes.",
                    file=sys.stderr,
                )
                await seed(source, repository, on_result=_report)
            elif arguments.once:
                _report(await ingest_once(source, repository))
            else:
                print(
                    f"Polling every {arguments.interval:.0f}s. Interrupt to stop.",
                    file=sys.stderr,
                )
                with suppress(KeyboardInterrupt, asyncio.CancelledError):
                    await poll(
                        source, repository, interval=arguments.interval, on_result=_report
                    )
        print(f"{repository.count_posts()} posts held.", file=sys.stderr)
    return 0


def _report(result: IngestResult) -> None:
    #  Seeding and polling both run for minutes at a time, so progress has to
    #  appear as it happens rather than when the buffer decides.
    if result.failed:
        print(f"  {result.route}: could not be fetched: {result.failure}", file=sys.stderr)
        return
    print(
        f"  {result.route}: {result.seen} offered, {result.added} new{_ingest_note(result)}",
        flush=True,
    )
    for problem in result.problems:
        print(f"    problem: {problem}", file=sys.stderr, flush=True)


def _ingest_note(result: IngestResult) -> str:
    if result.window_may_have_drained:
        return "  (all new -- the window may have drained between polls)"
    return ""


async def _serve(arguments: argparse.Namespace) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
    with Repository.open(arguments.database_filepath) as repository:
        server = await serve(repository, host=arguments.host, port=arguments.port)
        print(
            f"Sextile answering on {arguments.host}:{arguments.port}, "
            f"{repository.count_posts()} posts held.\n"
            f"Dial it with:  tcpser -v 25232 -s 9600 -l 4 -t sS "
            f"-n 1={arguments.host}:{arguments.port}\n"
            f"Or try it with:  nc {arguments.host} {arguments.port}",
            file=sys.stderr,
        )
        async with server:
            with suppress(KeyboardInterrupt, asyncio.CancelledError):
                await server.serve_forever()
    return 0


def _archive(arguments: argparse.Namespace) -> int:
    with Repository.open(arguments.database_filepath) as repository:
        print(f"{repository.count_posts()} posts held")
        days = repository.days(limit=10)
        if days:
            print("\nMost recent days:")
            for day, count in days:
                print(f"  {day}  {count:3d} posts   *32{day:%Y%m%d}#")
        forums = repository.forums()
        if forums:
            print("\nForums seen:")
            for forum_id, name, count in forums:
                print(f"  *42{forum_id}#  {count:3d} posts   {name}")
    return 0


def _rendered(frame: Frame, form: str, *, colour: bool) -> str:
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
    return _hex_dump(frame.to_bytes())


def _hex_dump(data: bytes, width: int = 16) -> str:
    lines = []
    for offset in range(0, len(data), width):
        chunk = data[offset : offset + width]
        hexadecimal = " ".join(f"{byte:02X}" for byte in chunk)
        printable = "".join(chr(byte) if 0x20 <= byte < 0x7F else "." for byte in chunk)
        lines.append(f"{offset:04X}  {hexadecimal:<{width * 3}} |{printable}|")
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
