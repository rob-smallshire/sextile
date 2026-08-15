# Frames and keys

A tutorial step: a menu too long for one screen, and the keys a reader turns its
frames with.

## Teach the service the time

A calendar has to know what day it is. The service holds that as service state: a
`StateKey` the service's lifespan fills, that a page reads back from the request.
This is the one thing the service holds; step 5 comes back to why it is held this
way, and not read from the clock at each page. A `build_application` factory lets
a caller pass the clock in — a test will, later — and defaults it to the real one.

Add the clock, an `ahead` page listing the days to come, and the factory. The
whole file so far:

```{sextile-frame}
:page: "4"
:show-code:

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

from sextile import (
    MenuItem, Page, PageRequest, PageRouter, Sextile, StateKey,
    menu_page, notice_page, prose_page,
)

SERVICE_NAME = "CALENDAR"
DAYS_AHEAD = 28

type Clock = Callable[[], datetime]
CLOCK = StateKey[Clock]("clock")
router = PageRouter()


def _today(request: PageRequest) -> date:
    return request.state[CLOCK]().date()


def _in_words(gap: timedelta) -> str:
    return {0: "today", 1: "tomorrow"}.get(gap.days, f"in {gap.days} days")


@router.page("1", name="main", title="The index", keywords=("MAIN", "INDEX"))
async def main(request: PageRequest) -> Page:
    app = request.app
    return menu_page(
        request,
        title=SERVICE_NAME,
        items=[app.menu_item("ahead"), app.menu_item("about")],
    )


@router.page("42{day:date}", name="day", title="One day")
async def one_day(request: PageRequest, day: date) -> Page:
    return notice_page(request, day.strftime("%A %d %B %Y"))


@router.page(
    "4", name="ahead", title="The days to come",
    detail=f"the next {DAYS_AHEAD}", keywords=("AHEAD",),
)
async def ahead(request: PageRequest) -> Page:
    app = request.app
    today = _today(request)
    days = [today + timedelta(days=offset) for offset in range(DAYS_AHEAD)]
    return menu_page(
        request,
        items=[
            MenuItem(
                day.strftime("%A %d %B %Y"),
                _in_words(day - today),
                app.address_for("day", day=day),
            )
            for day in days
        ],
    )


@router.page("9", name="about", title="About this service", keywords=("ABOUT",))
async def about(request: PageRequest) -> Page:
    return prose_page(request, "A calendar, served as Viewdata frames.")


def build_application(now: Clock | None = None) -> Sextile:
    reading = now or (lambda: datetime.now(UTC))

    @asynccontextmanager
    async def lifespan(app: Sextile) -> AsyncIterator[None]:
        app.state[CLOCK] = reading
        yield

    return Sextile(name=SERVICE_NAME, pages=[*router], lifespan=lifespan)


app = build_application(now=lambda: datetime(2026, 8, 1, tzinfo=UTC))
```

The last line is the tutorial's: it fixes the clock to 1 August 2026 so the frame
is the same on every build. Your file writes `app = build_application()`, for the
real clock — that is what `sextile serve my_calendar:app` runs.

## Turn the frames

Twenty-eight days will not fit nine to a screen, so `menu_page` spreads them over
several [frames](../reference/glossary.md). The footer names only the keys that do
something here: on this first frame there is nowhere up to go, so it offers `S`
(page down) and not `W`.

The second frame, `*4b#`, reached with `:frame: 1`:

```{sextile-frame}
:page: "4"
:frame: 1

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

from sextile import (
    MenuItem, Page, PageRequest, PageRouter, Sextile, StateKey, menu_page, notice_page,
)

CLOCK = StateKey[Callable[[], datetime]]("clock")
router = PageRouter()


def _in_words(gap: timedelta) -> str:
    return {0: "today", 1: "tomorrow"}.get(gap.days, f"in {gap.days} days")


@router.page("42{day:date}", name="day", title="One day")
async def one_day(request: PageRequest, day: date) -> Page:
    return notice_page(request, day.strftime("%A %d %B %Y"))


@router.page("4", name="ahead", title="The days to come")
async def ahead(request: PageRequest) -> Page:
    app = request.app
    today = request.state[CLOCK]().date()
    days = [today + timedelta(days=offset) for offset in range(28)]
    return menu_page(
        request,
        items=[
            MenuItem(day.strftime("%A %d %B %Y"), _in_words(day - today), app.address_for("day", day=day))
            for day in days
        ],
    )


@asynccontextmanager
async def lifespan(app: Sextile) -> AsyncIterator[None]:
    app.state[CLOCK] = lambda: datetime(2026, 8, 1, tzinfo=UTC)
    yield


app = Sextile(name="CALENDAR", pages=[*router], lifespan=lifespan)
```

It offers `W` to go back up as well. `#` turns to the next frame — it is the key a
Viewdata reader tries first — and `0` always returns to the index. `A` and `D` do
nothing here yet; the next step wires them.

```{note}
Choices and moves are different keys. A choice — a menu's digit — leads somewhere
new. A move — `W`, `S`, `#`, `0` — pages or steps within where the reader already
is. The footer keeps them apart, and a page only offers the moves it can make.
```
