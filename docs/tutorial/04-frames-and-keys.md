# Frames and keys

A tutorial step: a menu too long for one screen, and the keys a reader turns its
frames with.

## List the days to come

Add a page listing the next twenty-eight days, each with how far off it is in
words. It is an ordinary `menu_page`; the new part is that its entries do not fit
on one screen. Add this, and `app.menu_item("ahead")` to the index menu:

```{sextile-frame}
:page: "4"
:frames: a,b
:show-code:
:hide-lines: 1-25,53-61

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

from sextile import (
    MenuItem, Page, PageRequest, PageRouter, Sextile, StateKey, menu_page, notice_page,
)

CLOCK = StateKey[Callable[[], datetime]]("clock")
router = PageRouter()


def _long_date(day: date) -> str:
    return day.strftime("%A %d %B %Y")


def _today(request: PageRequest) -> date:
    return request.state[CLOCK]().date()


@router.page("42{day:date}", name="day", title="One day")
async def one_day(request: PageRequest, day: date) -> Page:
    return notice_page(request, _long_date(day))


DAYS_AHEAD = 28


def _in_words(gap: timedelta) -> str:
    days = gap.days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    return f"in {days} days"


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
            MenuItem(_long_date(day), _in_words(day - today), app.address_for("day", day=day))
            for day in days
        ],
    )


@asynccontextmanager
async def lifespan(app: Sextile) -> AsyncIterator[None]:
    app.state[CLOCK] = lambda: datetime(2026, 8, 1, tzinfo=UTC)
    yield


app = Sextile(name="CALENDAR", pages=[*router], lifespan=lifespan)
```

## Turn the frames

Twenty-eight days will not fit nine to a screen, so `menu_page` spreads them over
several [frames](../reference/glossary.md). The footer names only the keys that do
something on that frame: the first offers `S` to page down but no `W`, there being
nowhere up to go; the second offers both. `#` turns to the next frame — the key a
Viewdata reader tries without being told — and `0` always returns to the index.
`A` and `D` do nothing here yet; the next step wires them.

```{note}
Choices and moves are different keys. A choice — a menu's digit — leads somewhere
new. A move — `W`, `S`, `#`, `0` — pages or steps within where the reader already
is. The footer keeps them apart, and a page offers only the moves it can make.
```
