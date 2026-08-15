# The framework's pages, and drawing your own

A tutorial step: the pages the framework brings for free, a page you draw cell by
cell, and how a caller rings off.

## Draw a month as a grid

A menu and a notice are laid out for you. A month is not either: it is a grid,
placed by cell. For that a page hands the layout a `Custom` part — a block of a
stated height it draws itself, given a `Canvas` — and reaches, once, into
`sextile.viewdata` for the `Canvas` and the `Colour`. Add the drawing and the two
month pages:

```{sextile-frame}
:page: "3"
:show-code:
:hide-lines: 1-23,65-73

import calendar
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

from sextile import (
    Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile, Shortcut, StateKey, keys,
)
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour

CLOCK = StateKey[Callable[[], datetime]]("clock")
router = PageRouter()


def _today(request: PageRequest) -> date:
    return request.state[CLOCK]().date()


def _month_name(day: date) -> str:
    return day.strftime("%B %Y")


_WEEKDAYS = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def _months_either_side(day: date) -> tuple[date, date]:
    first = day.replace(day=1)
    previous = (first - timedelta(days=1)).replace(day=1)
    following = (first + timedelta(days=31)).replace(day=1)
    return previous, following


def _draw_month(canvas: Canvas, row: int, day: date, weeks: list[list[int]]) -> None:
    canvas.row(row).text("  ".join(weekday[:2] for weekday in _WEEKDAYS), Colour.CYAN)
    for offset, week in enumerate(weeks):
        cells = " ".join(f"{number:>3}" if number else "   " for number in week)
        colour = Colour.YELLOW if day.day in week else Colour.WHITE
        canvas.row(row + 1 + offset).text(cells.rstrip(), colour)


def _month_page(request: PageRequest, day: date) -> Page:
    app = request.app
    weeks = calendar.Calendar().monthdayscalendar(day.year, day.month)
    previous, following = _months_either_side(day)
    return PageLayout(
        title=_month_name(day).upper(),
        parts=[OnOneFrame(Custom(rows=1 + len(weeks), draw=lambda canvas, row: _draw_month(canvas, row, day, weeks)))],
        shortcuts=[
            Shortcut(key=keys.PREVIOUS_ITEM, destination=app.address_for("month", day=previous), with_arrow=True),
            Shortcut(key=keys.NEXT_ITEM, destination=app.address_for("month", day=following), with_arrow=True),
        ],
        item_noun="month",
    ).build(request)


@router.page("3", name="this_month", title="This month", detail="as a grid", keywords=("MONTH",))
async def this_month(request: PageRequest) -> Page:
    return _month_page(request, _today(request))


@router.page("32{day:date}", name="month", title="One month")
async def month(request: PageRequest, day: date) -> Page:
    return _month_page(request, day)


@asynccontextmanager
async def lifespan(app: Sextile) -> AsyncIterator[None]:
    app.state[CLOCK] = lambda: datetime(2026, 8, 1, tzinfo=UTC)
    yield


app = Sextile(name="CALENDAR", pages=[*router], lifespan=lifespan)
```

`Custom(rows=..., draw=...)` is given the canvas and the row it starts on, and
draws the weekday heads and the weeks under them. The week the day falls in is
coloured, not the day: a colour attribute takes a cell, and a row of seven figures
has none to spare. The two `Shortcut`s wire `A` and `D` to the months either side.
Give the one-day page a shortcut to its month too, and add "this month" to the
index menu.

## Take the framework's own pages

`standard_pages` returns routes for the pages every service can offer — where a
caller has been, every page and its number, the words they can key — at whatever
numbers you give them. Spread them into the service beside your own, and rename the
factory's assembly:

```python
return Sextile(
    name=SERVICE_NAME.title(),
    pages=[*router, *standard_pages(history="92", contents="93", keywords="94")],
    lifespan=lifespan,
)
```

Each carries the framework's own title, detail and keywords, drawn from what it
already knows through `app.title_for`, so a contents page cannot drift from the
service it lists. This is `*93#`:

```{sextile-frame}
:page: "93"

from sextile import Page, PageRequest, PageRouter, Sextile, notice_page, standard_pages

router = PageRouter()


@router.page("1", name="main", title="The index", keywords=("MAIN",))
async def main(request: PageRequest) -> Page:
    return notice_page(request, "the index")


@router.page("2", name="now", title="The time now", detail="to the second")
async def now_page(request: PageRequest) -> Page:
    return notice_page(request, "the time")


app = Sextile(
    name="Calendar",
    pages=[*router, *standard_pages(history="92", contents="93", keywords="94")],
)
```

## Ring off

`*90#` says goodbye and drops the line. `farewell_page` is the shape for it: no way
home, since there is none, and a hang-up once it has been shown.

```{sextile-frame}
:page: "90"

from sextile import Page, PageRequest, PageRouter, Sextile, farewell_page

router = PageRouter()


@router.page("90", name="goodbye", title="Log off", keywords=("BYE",))
async def goodbye(request: PageRequest) -> Page:
    return farewell_page(request, "GOODBYE", "Thank you for calling.", "", "Ring off.")


app = Sextile(name="CALENDAR", pages=[*router])
```
