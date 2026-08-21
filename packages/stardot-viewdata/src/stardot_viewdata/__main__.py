"""Stardot's command line.

Serving and drawing are the framework's, and could be done with

    sextile serve stardot_viewdata:app

but the archive is this application's own, and so is filling it. This command
does both, and defaults the archive's location so that the two halves of the
service agree about where it is without being told twice.

The framework's `render` and `serve` are added to this service's own Click
group; `ingest` and `archive` are the service's own beside them.
"""

import asyncio
import sys
from contextlib import suppress
from pathlib import Path

import click

from sextile import Sextile
from sextile.cli import CONTEXT_SETTINGS, standard_commands
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

#: The archive's location, shared by every subcommand so the halves of the
#: service agree about where it is without being told twice.
_database_option = click.option(
    "--database-filepath",
    type=Path,
    default=DEFAULT_DATABASE_FILEPATH,
    help=f"Where the archive lives (default: {DEFAULT_DATABASE_FILEPATH})",
)


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.version_option(
    __version__, "--version", prog_name="stardot-viewdata", message="%(prog)s %(version)s"
)
@click.pass_context
def main(context: click.Context) -> None:
    """A Viewdata service for the Stardot forum."""
    if context.invoked_subcommand is None:
        click.echo(context.get_help())


def _application(context: click.Context) -> Sextile:
    return build_application(context.params["database_filepath"])


for _command in standard_commands(
    _application, options=[_database_option], page_example="1 or 82489493"
):
    main.add_command(_command)


@main.command(help="Fetch the feed into the archive")
@click.option("--once", is_flag=True, help="Poll once and stop")
@click.option(
    "--seed",
    "seeding",
    is_flag=True,
    help="Sweep every route the board publishes, to fill a new archive",
)
@click.option(
    "--interval",
    type=float,
    default=DEFAULT_POLL_INTERVAL,
    help=f"Seconds between polls (default {DEFAULT_POLL_INTERVAL:.0f})",
)
@_database_option
def ingest(once: bool, seeding: bool, interval: float, database_filepath: Path) -> None:
    """Fetch the feed into the archive."""
    code = asyncio.run(_ingest(database_filepath, once=once, seeding=seeding, interval=interval))
    raise SystemExit(code)


@main.command(help="Report what the archive holds")
@_database_option
def archive(database_filepath: Path) -> None:
    """Report what the archive holds."""
    raise SystemExit(_archive(database_filepath))


async def _ingest(database_filepath: Path, *, once: bool, seeding: bool, interval: float) -> int:
    with Repository.open(database_filepath) as repository:
        async with FeedClient(STARDOT_BASE_URL) as client:
            source = AtomFeedSource(client)
            if seeding:
                print(
                    "Seeding from every route the board publishes. The site asks for "
                    "60 seconds\nbetween requests, so this takes a few minutes.",
                    file=sys.stderr,
                )
                await seed(source, repository, on_result=_report)
            elif once:
                _report(await ingest_once(source, repository))
            else:
                print(
                    f"Polling every {interval:.0f}s. Interrupt to stop.",
                    file=sys.stderr,
                )
                with suppress(KeyboardInterrupt, asyncio.CancelledError):
                    await poll(source, repository, interval=interval, on_result=_report)
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


def _archive(database_filepath: Path) -> int:
    with Repository.open(database_filepath) as repository:
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
    main()
