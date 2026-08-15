# Sequences

A tutorial step: a day knows the days either side of it, so a reader can step along
the run they came through without going back to the menu.

## Wire the day into its run

The days-to-come menu is a sequence, and a page reached from it should let the
reader step to the next and the previous — `D` and `A` — as well as back. A page
does not track that itself: the session does, and hands it to the page as
`request.neighbours`. The day page passes those to its `PageLayout`, names what the
sequence steps between with `item_noun`, and now says how far off the day is. Its
whole self, the file's other pages unchanged around it:

```{sextile-frame}
:page: "4"
:keys: "2"
:show-code:

import calendar
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta

from sextile import (
    Lines, MenuItem, Page, PageLayout, PageRequest, PageRouter, Sextile, StateKey,
    keyed, keys, menu_page, notice_page, prose_page,
)

SERVICE_NAME = "CALENDAR"
DAYS_AHEAD = 28

type Clock = Callable[[], datetime]
CLOCK = StateKey[Clock]("clock")
router = PageRouter()


def _now(request: PageRequest) -> datetime:
    return request.state[CLOCK]()


def _today(request: PageRequest) -> date:
    return _now(request).date()


def _long_date(day: date) -> str:
    return day.strftime("%A %d %B %Y")


def _month_name(day: date) -> str:
    return day.strftime("%B %Y")


def _in_words(gap: timedelta) -> str:
    days = gap.days
    if days == 0:
        return "today"
    if days == 1:
        return "tomorrow"
    if days == -1:
        return "yesterday"
    if days > 0:
        return f"in {days} days"
    return f"{-days} days ago"


@router.page("1", name="main", title="The index", keywords=("MAIN", "INDEX"))
async def main(request: PageRequest) -> Page:
    app = request.app
    return menu_page(
        request,
        title=SERVICE_NAME,
        preamble=[_long_date(_today(request))],
        items=[app.menu_item("now"), app.menu_item("ahead"), app.menu_item("about")],
    )


@router.page(
    "2", name="now", title="The time now", detail="to the second", keywords=("TIME", "NOW"),
)
async def now_page(request: PageRequest) -> Page:
    moment = _now(request)
    return notice_page(
        request,
        _long_date(moment.date()),
        "",
        moment.strftime("%H:%M:%S"),
        moment.tzname() or "",
        "",
        f"Key {keyed(keys.REFRESH)} to ask again.",
    )


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


@router.page("42{day:date}", name="day", title="One day")
async def one_day(request: PageRequest, day: date) -> Page:
    _, week, _ = day.isocalendar()
    length = 366 if calendar.isleap(day.year) else 365
    lines = [
        _long_date(day),
        "",
        f"Day {day.timetuple().tm_yday} of {length}",
        f"Week {week}",
        f"ISO {day.isoformat()}",
        "",
        _in_words(day - _today(request)),
    ]
    return PageLayout(
        title=_month_name(day),
        neighbours=request.neighbours,
        item_noun="day",
        parts=[Lines(lines)],
    ).build(request)


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

The frame above is the second day of the list, reached by keying `2` from it. Its
footer offers `A` and `D` to step to the day before and after, because it was
reached through a sequence; a day reached by its number alone offers neither, there
being no run to step along. `item_noun="day"` is why the footer says so in days.
