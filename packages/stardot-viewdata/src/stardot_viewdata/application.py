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
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import Final

from sextile import Page, PageAddress, PageRoute, Parting, Sextile, routes_in
from sextile.handlers import contents, history, names
from stardot_viewdata import handlers
from stardot_viewdata.handlers import ARCHIVE, SERVICE_NAME, day_title, ringing_off, unknown_page
from stardot_viewdata.store.repository import Repository

#: Named for the service rather than for the framework serving it, and
#: relative to the working directory, so `serve` and `ingest` must be run from
#: the same place.
DEFAULT_DATABASE_FILEPATH: Final = Path("stardot.sqlite")

#: What the service is made of: its own pages, declared beside the functions
#: that build them and gathered in the order the numbering runs, and three the
#: framework builds and hands over as handlers, mapped into this numbering.
PAGES: Final = (
    *routes_in(handlers),
    PageRoute("92", history, title="Where you have been",
              detail="this call, newest first", keywords=("HISTORY", "BEEN")),
    PageRoute("93", contents, title="Every page",
              detail="and the number that fetches it",
              keywords=("PAGES", "CONTENTS")),
    PageRoute("94", names, title="Words you can key",
              detail="instead of a page number", keywords=("KEYWORDS", "WORDS")),
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
    async def lifespan(app: Sextile) -> AsyncIterator[Mapping[str, object]]:
        if repository is not None:
            yield ARCHIVE.holding(repository)
            return
        ours = await asyncio.to_thread(Repository.open, database_filepath)
        try:
            yield ARCHIVE.holding(ours)
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

    @app.on_describe
    def better_words(address: PageAddress) -> str | None:
        """What to call a page where one is listed rather than shown.

        Only the pages whose numbers carry a field need saying here: the rest
        are titled where they are registered, and the framework reads those.
        "One post" is the right title in a list of *kinds* of page and the
        wrong one in a list of pages a reader has been to, which is what this
        overrides. Returning None means the registration's own words will do.

        Subjects and forum names are deliberately not looked up. A history
        frame lists nine pages, which would be nine queries for a label, and
        the page number beside each entry already says which post it is.
        """
        found = app.route(address)
        if found is not None and found.params:
            match found.name, found.params:
                case "post", {"post_id": int() as post_id}:
                    return f"Post {post_id}"
                case "topic", {"topic_id": int() as topic_id}:
                    return f"Topic {topic_id}"
                case "forum", {"forum_id": int() as forum_id}:
                    return f"Forum {forum_id}"
                case "contributor", {"user_id": int() as user_id}:
                    return f"Contributor {user_id}"
                case "day", {"day": date() as day}:
                    return day_title(day)
        return None

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
