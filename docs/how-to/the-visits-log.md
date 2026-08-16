# The visits log

A how-to guide: record what is read, and let the framework's readership pages
show it back.

```{sextile-frame}
:hide-lines: 36-49
:show-code:

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sextile import Page, PageRequest, PageRouter, Sextile, StateKey, notice_page, standard_pages
from sextile.middleware import record_visits
from sextile.visits import SqliteVisits, Visits

VISITS = StateKey[Visits]("visits")

router = PageRouter()


@router.page("11", name="news", title="Headlines")
async def news(request: PageRequest) -> Page:
    return notice_page(request, "Nothing yet.")


@router.page("12", name="sport", title="Sport")
async def sport(request: PageRequest) -> Page:
    return notice_page(request, "Rained off.")


@asynccontextmanager
async def lifespan(app: Sextile) -> AsyncIterator[None]:
    with SqliteVisits.open(":memory:") as visits:
        app.state[VISITS] = visits
        yield


app = Sextile(
    name="News",
    pages=[*router, *standard_pages(recent="9", visits=VISITS)],
    middleware=[record_visits(VISITS)],
    lifespan=lifespan,
)

import asyncio

from sextile.testing import connect, fetch

async def _recent() -> Page:
    async with connect(app, start="1") as caller:
        await caller.press("*11#")
        await caller.press("*12#")
        await caller.press("*11#")
        return await fetch(app, "9")

page = asyncio.run(_recent())
```

`record_visits(VISITS)` middleware notes every page built under a `StateKey` the
lifespan opens a `SqliteVisits` under; `standard_pages(recent="9", visits=VISITS)`
routes the framework's own "looked at lately" page at `9`, reading that same log.
`popular=` and `callers=` add the most-read page and the caller count the same
way. Each caller is an opaque token, so the count says how many and nothing about
who.
