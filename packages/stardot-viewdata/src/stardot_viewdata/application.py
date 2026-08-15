"""Stardot, as a Viewdata service.

The assembly alone: the archive the service holds, its own pages mapped into the
numbering beside the framework's history, contents and keywords, and the words
it uses for a page it has not got. The handlers are in `handlers`, each declared
beside its function.
"""

import asyncio
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Final

from sextile import Page, PageRequest, PageRoute, Sextile, standard_pages
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
    """Assemble the service, from an archive on disk or one already open.

    Args:
        database_filepath: Where the archive lives, opened when the service
            starts and closed when it stops. Ignored where `repository` is given.
        repository: An open archive to serve from, for a test or a caller that
            holds one for another purpose. It is left open when the service
            stops, since it belongs to whoever passed it.
        pages: The service's pages; the default is its own list spread with the
            framework's. A test passes another to move a page and watch
            everything that names it follow.

    Returns:
        The service, its archive held under `ARCHIVE`, with its own not-found
        and timed-out pages.
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
    async def unknown(request: PageRequest, target: str) -> Page:
        return unknown_page(request, target)

    @app.on_timed_out
    async def released(request: PageRequest, frame_index: int) -> Page:
        return ringing_off(request)

    return app


__all__ = [
    "DEFAULT_DATABASE_FILEPATH",
    "PAGES",
    "SERVICE_NAME",
    "build_application",
]
