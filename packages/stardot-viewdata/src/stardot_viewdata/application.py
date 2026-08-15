"""Stardot, as a Viewdata service.

This is a Sextile application and nothing more: it says which page numbers
exist, what each of them shows, and where the keys lead. Everything about
connections, sessions, frames, control codes and routing belongs to the
framework, and everything about forums belongs here.

The handlers are in `handlers`, each declared beside its function;
`title_frame` draws the masthead and `post_page` divides one post between
frames.
This module is the assembly alone: the archive the service holds, the pages
mapped into the numbering, and the words it uses for a page it has not got.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from sextile import Page, PageRoute, Parting, Sextile, standard_pages
from stardot_viewdata import handlers
from stardot_viewdata.handlers import ARCHIVE, SERVICE_NAME, ringing_off, unknown_page
from stardot_viewdata.store.repository import Repository

#: Named for the service rather than for the framework serving it, and
#: relative to the working directory, so `serve` and `ingest` must be run from
#: the same place.
DEFAULT_DATABASE_FILEPATH: Final = Path("stardot.sqlite")

#: What the service is made of: its own pages, declared beside the functions
#: that build them and gathered in the order the numbering runs, and three the
#: framework builds and hands over as handlers, mapped into this numbering.
PAGES: Final = (
    *handlers.router,
    *standard_pages(history="92", contents="93", keywords="94"),
)


def build_application(
    database_filepath: Path | str = DEFAULT_DATABASE_FILEPATH,
    *,
    repository: Repository | None = None,
    pages: Sequence[PageRoute] = PAGES,
) -> Sextile:
    """Serve from an archive at ``database_filepath``, or from one already open.

    ``pages`` is the service's own list unless given another, which lets a test
    move a page and watch everything that names it follow.

    An archive passed in belongs to whoever passed it and is left open when the
    service stops, which suits a test and a caller that holds the archive for
    some other purpose. An archive opened from ``database_filepath`` is closed
    when the service stops.
    """

    @asynccontextmanager
    async def lifespan(app: Sextile) -> AsyncIterator[None]:
        if repository is not None:
            app.state[ARCHIVE] = repository
            yield
            return
        ours = await asyncio.to_thread(Repository.open, database_filepath)
        try:
            app.state[ARCHIVE] = ours
            yield
        finally:
            await asyncio.to_thread(ours.close)

    app = Sextile(
        name=SERVICE_NAME.title(),
        #  A caller arrives on the title frame once; `0` means the index, which
        #  is not the same page and never has been sent back to.
        home="0",
        index="1",
        pages=pages,
        lifespan=lifespan,
    )

    #  The labels for pages whose number carries a field -- "Post 489493"
    #  rather than "One post" in a list of visited pages -- are declared as
    #  `label=` beside each of those routes in `handlers`, where the title is.
    #  Subjects and forum names are deliberately not looked up: a history frame
    #  lists nine pages, which would be nine queries for a label, and the page
    #  number beside each entry already says which post it is.

    @app.on_not_found
    async def unknown(target: str) -> Page:
        return unknown_page(app, target)

    @app.on_timed_out
    async def released(parting: Parting) -> Page:
        return ringing_off(app, parting)

    return app


__all__ = [
    "DEFAULT_DATABASE_FILEPATH",
    "PAGES",
    "SERVICE_NAME",
    "build_application",
]
