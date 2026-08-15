"""Stardot's command line.

Serving and drawing are the framework's, and could be done with

    sextile serve stardot_viewdata:app

but the archive is this application's own, and so is filling it. This command
does both, and defaults the archive's location so that the two halves of the
service agree about where it is without being told twice.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from contextlib import suppress
from pathlib import Path

from sextile import Sextile
from sextile.cli import add_standard_subcommands, run_standard
from stardot_viewdata import __version__
from stardot_viewdata.application import DEFAULT_DATABASE_FILEPATH, build_application
from stardot_viewdata.feed.client import FeedClient
from stardot_viewdata.feed.ingest import (
    DEFAULT_POLL_INTERVAL,
    IngestResult,
    ingest_once,
    poll,
    seed,
)
from stardot_viewdata.feed.source import STARDOT_BASE_URL, AtomFeedSource
from stardot_viewdata.store.repository import Repository


def build_parser() -> argparse.ArgumentParser:
    """The command line this service answers to, subcommands and all."""
    parser = argparse.ArgumentParser(
        prog="stardot-viewdata", description="A Viewdata service for the Stardot forum"
    )
    parser.add_argument("--version", action="version", version=f"stardot-viewdata {__version__}")
    subcommands = parser.add_subparsers(dest="command")

    add_standard_subcommands(
        subcommands, configure=_add_database_argument, page_example="1 or 82489493"
    )

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

    return parser


def _add_database_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--database-filepath",
        type=Path,
        default=DEFAULT_DATABASE_FILEPATH,
        help=f"Where the archive lives (default: {DEFAULT_DATABASE_FILEPATH})",
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one command.

    Args:
        argv: The arguments after the program name, or None to take
            them from `sys.argv`.

    Returns:
        The process exit status: nought where the command succeeded.
    """
    parser = build_parser()
    arguments = parser.parse_args(argv)

    standard = run_standard(arguments, load=_application)
    if standard is not None:
        return standard

    match arguments.command:
        case "ingest":
            return asyncio.run(_ingest(arguments))
        case "archive":
            return _archive(arguments)
        case _:
            parser.print_help()
            return 0


def _application(arguments: argparse.Namespace) -> Sextile:
    return build_application(arguments.database_filepath)


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
                    await poll(source, repository, interval=arguments.interval, on_result=_report)
        print(f"{repository.count_posts()} posts held.", file=sys.stderr)
    return 0


def _report(result: IngestResult) -> None:
    #  Seeding and polling both run for minutes at a time, so progress has to
    #  appear as it happens rather than only when the output buffer flushes.
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


if __name__ == "__main__":
    sys.exit(main())
