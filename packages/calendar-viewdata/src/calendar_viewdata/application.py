"""A calendar, as a Viewdata service.

It exists to be a second application. Sextile is meant to be a general framework,
not the first service reworked to look like one, and the way to test that is to
write something with nothing in common with the first and see what the framework
asks for. Everything here comes out of the standard library: no archive, no
network, nothing to configure.

It is also the worked example the framework's documentation is written against,
so it is meant to be read.

    1           the index
    2           the date and time now
    3           this month
    32<date>    the month containing a date
    4           the days to come
    42<date>    one day
    9           about
    90          goodbye

A service is a list of pages given to a constructor, and a page is an ordinary
function. Nothing here closes over anything: a page takes the clock from what
the service holds and the numbering from the service itself, both through the
request it is given.
"""

import calendar
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Final, Protocol

from sextile import (
    Page,
    PageRequest,
    PageRoute,
    Sextile,
    StateKey,
    farewell_page,
    keyed,
    keys,
    menu_page,
    notice_page,
    prose_page,
    standard_pages,
)
from sextile.formatting import Lines, MenuItem
from sextile.layout import Drawn, OnFirstFrame, PageLayout, Shortcut
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour

SERVICE_NAME: Final = "CALENDAR"

#: How far ahead the days-to-come menu looks.
DAYS_AHEAD: Final = 28

class Clock(Protocol):
    """How the service finds out the time: any callable answering a datetime."""

    def __call__(self) -> datetime: ...


#: What the clock is held under, in what the service holds. It is the only
#: thing this service depends on that is not a pure function, which is why it
#: is a parameter at all: a service whose pages change under it cannot
#: otherwise be tested.
CLOCK: Final = StateKey[Clock]("clock")

_WEEKDAYS: Final = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


def _now(request: PageRequest) -> datetime:
    return request.state[CLOCK]()


def _today(request: PageRequest) -> date:
    return _now(request).date()


# -- the pages ---------------------------------------------------------------


async def main(request: PageRequest) -> Page:
    """The index: today's date, and the four pages the service offers."""
    app = request.app
    today = _today(request)
    return menu_page(
        request,
        title=SERVICE_NAME,
        preamble=[_long_date(today)],
        items=[
            app.menu_item("now"),
            #  Not the registered "as a grid": which month it is says more here
            #  than how it is drawn, and only the page in front of the reader
            #  can know the date.
            MenuItem("This month", _month_name(today), app.address_for("this_month")),
            app.menu_item("ahead"),
            app.menu_item("about"),
        ],
    )


async def now_page(request: PageRequest) -> Page:
    """The time now, to the second, with the key that asks again."""
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


async def this_month(request: PageRequest) -> Page:
    """The current month as a grid, taken from the request's own clock."""
    return _month_page(request, _today(request))


async def month(request: PageRequest, day: date) -> Page:
    """The month a given day falls in, as a grid."""
    return _month_page(request, day)


async def ahead(request: PageRequest) -> Page:
    """The next `DAYS_AHEAD` days, each with how far off it is in words."""
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


async def one_day(request: PageRequest, day: date) -> Page:
    """One day, with its place in the week, the month and the year."""
    app = request.app
    _, weeks_in_year, _ = day.isocalendar()
    lines = [
        _long_date(day),
        "",
        f"Day {day.timetuple().tm_yday} of {366 if calendar.isleap(day.year) else 365}",
        f"Week {weeks_in_year}",
        f"ISO {day.isoformat()}",
        "",
        _in_words(day - _today(request)),
    ]
    #  Whichever menu the reader came through decides what "next" means, and a
    #  day reached by keying its number came through none: the layout wires
    #  `A`/`D` to whichever neighbours the request carries, and names neither
    #  where there are none.
    return PageLayout(
        title=_month_name(day),
        shortcuts=[
            Shortcut(key="1", destination=app.address_for("month", day=day), says="month")
        ],
        neighbours=request.neighbours,
        item_noun="day",
        parts=[Lines(said=lines)],
    ).build(request)


async def about(request: PageRequest) -> Page:
    """What the service is, and why a calendar was chosen for it."""
    return prose_page(
        request,
        "A calendar, served as Viewdata frames.",
        "It exists to demonstrate that Sextile is a framework and not one "
        "service: nothing here knows about forums, and nothing in the framework "
        "knows about calendars.",
        "Everything it shows comes from the standard library.",
    )


async def goodbye(request: PageRequest) -> Page:
    """The farewell frame, after which the line drops."""
    return farewell_page(request, "GOODBYE", "Thank you for calling.", "", "Ring off.")


#: What the service is made of. Everything about a page is on one line of it:
#: where it is in the numbering, what builds it, what it is called where it is
#: listed rather than shown, and the words that reach it.
PAGES: Final = (
    PageRoute("1", main, name="main", title="The index",
              keywords=("MAIN", "INDEX")),
    PageRoute("2", now_page, name="now", title="The time now",
              detail="to the second", keywords=("TIME", "NOW")),
    PageRoute("3", this_month, name="this_month", title="This month",
              detail="as a grid", keywords=("MONTH",)),
    PageRoute("32{day:date}", month, name="month", title="One month"),
    PageRoute("4", ahead, name="ahead", title="The days to come",
              detail=f"the next {DAYS_AHEAD}", keywords=("AHEAD",)),
    PageRoute("42{day:date}", one_day, name="day", title="One day"),
    PageRoute("9", about, name="about", title="About this service",
              keywords=("ABOUT", "HELP")),
    #  Listed: the contents page is a directory of numbers that do something,
    #  and a reader looking for how to ring off should find it there.
    PageRoute("90", goodbye, name="goodbye", title="Log off",
              keywords=("BYE",)),
    #  Three the framework builds and hands over, mapped into this service's
    #  numbering by one call. They are here as much to show what a service gets
    #  for nothing as to be useful: the calendar wrote none of them.
    *standard_pages(history="92", contents="93", keywords="94"),
)


def build_application(now: Callable[[], datetime] | None = None) -> Sextile:
    """The service, optionally told how to find out the time.

    The clock is a parameter because a service whose pages change under it
    cannot otherwise be tested. It is the only thing this application depends
    on that is not a pure function, so it is the only thing the service holds.
    """
    reading = now or (lambda: datetime.now(UTC))

    @asynccontextmanager
    async def lifespan(app: Sextile) -> AsyncIterator[None]:
        app.state[CLOCK] = reading
        yield

    return Sextile(name=SERVICE_NAME.title(), pages=PAGES, lifespan=lifespan)


# -- drawing -----------------------------------------------------------------


def _month_page(request: PageRequest, day: date) -> Page:
    app = request.app
    weeks = calendar.Calendar().monthdayscalendar(day.year, day.month)
    previous, following = _months_either_side(day)
    return PageLayout(
        title=_month_name(day).upper(),
        #  A grid is placed by cell rather than written along its rows. It is
        #  the whole of the page's content, and needs no flowing part at all.
        parts=[
            OnFirstFrame(
                Drawn(
                    rows=1 + len(weeks),
                    draw=lambda canvas, row: _draw_month(canvas, row, day, weeks),
                )
            )
        ],
        shortcuts=[
            Shortcut(
                key=keys.PREVIOUS_ITEM,
                destination=app.address_for("month", day=previous),
                arrow=True,
            ),
            Shortcut(
                key=keys.NEXT_ITEM,
                destination=app.address_for("month", day=following),
                arrow=True,
            ),
        ],
        item_noun="month",
    ).build(request)


def _draw_month(
    canvas: Canvas, row: int, day: date, weeks: Sequence[Sequence[int]]
) -> None:
    """The weekday headings and the weeks beneath them, from `row` down."""
    canvas.row(row).text("  ".join(weekday[:2] for weekday in _WEEKDAYS), Colour.CYAN)
    for offset, week in enumerate(weeks):
        cells = " ".join(f"{number:>3}" if number else "   " for number in week)
        #  The week the day falls in, rather than the day itself: a colour
        #  attribute occupies a cell, and there is no spare cell inside a row
        #  of seven three-column figures to put one in.
        colour = Colour.YELLOW if day.day in week else Colour.WHITE
        canvas.row(row + 1 + offset).text(cells.rstrip(), colour)






# -- helpers -----------------------------------------------------------------


def _month_name(day: date) -> str:
    return day.strftime("%B %Y")


def _long_date(day: date) -> str:
    return day.strftime("%A %d %B %Y")


def _months_either_side(day: date) -> tuple[date, date]:
    first = day.replace(day=1)
    previous = (first - timedelta(days=1)).replace(day=1)
    following = (first + timedelta(days=31)).replace(day=1)
    return previous, following


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


