"""A calendar, as a Viewdata service.

The framework's worked example, written to be read: everything it shows comes
from the standard library, with no archive, no network and nothing to configure.
It exists to be a second application, so the framework is exercised by a service
with nothing in common with the first.

    1           the index
    2           the date and time now
    3           this month
    32<date>    the month containing a date
    4           the days to come
    42<date>    one day
    9           about
    90          log off
    92 93 94    history, contents, keywords (the framework's own)
"""

import calendar
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Final

from sextile import (
    Custom,
    Lines,
    MenuItem,
    OnOneFrame,
    Page,
    PageLayout,
    PageRequest,
    PageRouter,
    Sextile,
    Shortcut,
    StateKey,
    farewell_page,
    keyed,
    keys,
    menu_page,
    notice_page,
    prose_page,
    standard_pages,
)
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour

SERVICE_NAME: Final = "CALENDAR"

#: How far ahead the days-to-come menu looks.
DAYS_AHEAD: Final = 28


#: How the service finds out the time: any callable answering a datetime.
type Clock = Callable[[], datetime]

#: What the clock is held under. The one thing this service depends on that is
#: not a pure function, and so the one thing it holds.
CLOCK: Final = StateKey[Clock]("clock")

_WEEKDAYS: Final = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")

#: Collects the pages declared below, spread into the service in build_application.
router = PageRouter()


def _now(request: PageRequest) -> datetime:
    return request.state[CLOCK]()


def _today(request: PageRequest) -> date:
    return _now(request).date()


# -- the pages ---------------------------------------------------------------


@router.page("1", name="main", title="The index", keywords=("MAIN", "INDEX"))
async def main(request: PageRequest) -> Page:
    """Show today's date and a menu of the four pages the service offers."""
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


@router.page(
    "2", name="now", title="The time now", detail="to the second",
    keywords=("TIME", "NOW"),
)
async def now_page(request: PageRequest) -> Page:
    """Show the date and time now, with the key that asks again."""
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
    "3", name="this_month", title="This month", detail="as a grid",
    keywords=("MONTH",),
)
async def this_month(request: PageRequest) -> Page:
    """Show the current month as a grid."""
    return _month_page(request, _today(request))


@router.page("32{day:date}", name="month", title="One month")
async def month(request: PageRequest, day: date) -> Page:
    """Show the month a given day falls in, as a grid."""
    return _month_page(request, day)


@router.page(
    "4", name="ahead", title="The days to come", detail=f"the next {DAYS_AHEAD}",
    keywords=("AHEAD",),
)
async def ahead(request: PageRequest) -> Page:
    """List the next `DAYS_AHEAD` days, each with how far off it is in words."""
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
    """Show one day, with its place in the week, the month and the year."""
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
    return PageLayout(
        title=_month_name(day),
        shortcuts=[
            Shortcut(key="1", destination=app.address_for("month", day=day), label="month")
        ],
        neighbours=request.neighbours,
        item_noun="day",
        parts=[Lines(lines)],
    ).build(request)


@router.page("9", name="about", title="About this service", keywords=("ABOUT", "HELP"))
async def about(request: PageRequest) -> Page:
    """Say what the service is and why a calendar was chosen for it."""
    return prose_page(
        request,
        "A calendar, served as Viewdata frames.",
        "It exists to demonstrate that Sextile is a framework and not one "
        "service: nothing here knows about forums, and nothing in the framework "
        "knows about calendars.",
        "Everything it shows comes from the standard library.",
    )


#  Titled, so the log-off page is listed in the contents, where a reader looks
#  for how to ring off.
@router.page("90", name="goodbye", title="Log off", keywords=("BYE",))
async def goodbye(request: PageRequest) -> Page:
    """Show the farewell frame, after which the line drops."""
    return farewell_page(request, "GOODBYE", "Thank you for calling.", "", "Ring off.")


def build_application(now: Clock | None = None) -> Sextile:
    """Assemble the service, optionally told how to find out the time.

    Args:
        now: What reads the current time, for a test to control. The real UTC
            clock by default. It is a parameter because the clock is the one
            thing this service depends on that is not a pure function, and a
            service whose pages change under it cannot otherwise be tested. A
            service with nothing to inject would write `app = Sextile(...)` at
            module level instead of a factory.

    Returns:
        The service, its own pages spread with the framework's history, contents
        and keywords pages mapped into this numbering.
    """
    reading = now or (lambda: datetime.now(UTC))

    @asynccontextmanager
    async def lifespan(app: Sextile) -> AsyncIterator[None]:
        app.state[CLOCK] = reading
        yield

    return Sextile(
        name=SERVICE_NAME.title(),
        pages=[*router, *standard_pages(history="92", contents="93", keywords="94")],
        lifespan=lifespan,
    )


# -- drawing -----------------------------------------------------------------


def _month_page(request: PageRequest, day: date) -> Page:
    app = request.app
    weeks = calendar.Calendar().monthdayscalendar(day.year, day.month)
    previous, following = _months_either_side(day)
    return PageLayout(
        title=_month_name(day).upper(),
        #  A grid is the whole of the page's content and is placed by cell, so
        #  it is a `Custom` part rather than a flowing one.
        parts=[
            OnOneFrame(
                Custom(
                    rows=1 + len(weeks),
                    draw=lambda canvas, row: _draw_month(canvas, row, day, weeks),
                )
            )
        ],
        shortcuts=[
            Shortcut(
                key=keys.PREVIOUS_ITEM,
                destination=app.address_for("month", day=previous),
                with_arrow=True,
            ),
            Shortcut(
                key=keys.NEXT_ITEM,
                destination=app.address_for("month", day=following),
                with_arrow=True,
            ),
        ],
        item_noun="month",
    ).build(request)


def _draw_month(
    canvas: Canvas, row: int, day: date, weeks: Sequence[Sequence[int]]
) -> None:
    """Draw the weekday headings and the weeks beneath them, from `row` down."""
    canvas.row(row).text("  ".join(weekday[:2] for weekday in _WEEKDAYS), Colour.CYAN)
    for offset, week in enumerate(weeks):
        cells = " ".join(f"{number:>3}" if number else "   " for number in week)
        #  The week the day falls in is coloured, not the day: a colour attribute
        #  occupies a cell, and a row of seven three-column figures has no spare
        #  one to put it in.
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
