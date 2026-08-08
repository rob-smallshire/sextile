"""A calendar, as a Viewdata service.

It exists to be a second application. Sextile claims to be a framework rather
than one service with the serial numbers filed off, and the way to find out is
to write something that has nothing whatever to do with the first one and see
what the framework asks for. Everything here comes out of the standard library:
no archive, no network, nothing to configure.

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
"""

import calendar
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, timedelta
from typing import Final

from sextile import Page, PageAddress, PageFrame, PageRequest, Sextile, keys, page
from sextile.addressing import keyed
from sextile.templates import HOME_KEY, Menu, MenuItem, Prose
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import fitted
from sextile.viewdata.footer import (
    ROOM,
    FooterItem,
    Priority,
    movement,
    render_footer,
)
from sextile.viewdata.frame import COLUMNS, Frame

SERVICE_NAME: Final = "CALENDAR"


#: How far ahead the days-to-come menu looks.
DAYS_AHEAD: Final = 28

_WEEKDAYS: Final = ("MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN")


class CalendarApplication(Sextile):
    """The calendar service: its pages, and where its keys lead."""

    def __init__(self, now: Callable[[], datetime] | None = None) -> None:
        """Build the service, optionally told how to find out the time.

        The clock is a parameter because a service whose pages change under it
        cannot otherwise be tested. It is the only thing this application
        depends on that is not a pure function.
        """
        super().__init__(name=SERVICE_NAME.title())
        self._now = now or (lambda: datetime.now(UTC))

    @property
    def today(self) -> date:
        return self._now().date()

    # -- the pages ----------------------------------------------------------

    @page("1", title="The index", keywords=("MAIN", "INDEX"))
    async def main(self, request: PageRequest) -> Page:
        return self._menu(
            request.address,
            title=SERVICE_NAME,
            preamble=[_long_date(self.today), ""],
            items=[
                ("The time now", "to the second", self.address_for("now")),
                ("This month", _month_name(self.today), self.address_for("this_month")),
                ("The days to come", f"the next {DAYS_AHEAD}", self.address_for("ahead")),
                ("About this service", "", self.address_for("about")),
            ],
        )

    @page(
        "2",
        name="now",
        title="The time now",
        detail="to the second",
        keywords=("TIME", "NOW"),
    )
    async def now_page(self, request: PageRequest) -> Page:
        moment = self._now()
        return self._notice(
            request.address,
            None,
            [
                _long_date(moment.date()),
                "",
                moment.strftime("%H:%M:%S"),
                moment.tzname() or "",
                "",
                f"Key {keyed(keys.REFRESH)} to ask again.",
            ],
        )

    @page("3", title="This month", detail="as a grid", keywords=("MONTH",))
    async def this_month(self, request: PageRequest) -> Page:
        return self._month_page(request.address, self.today)

    @page("32{day:date}", title="One month")
    async def month(self, request: PageRequest, day: date) -> Page:
        return self._month_page(request.address, day)

    @page("4", title="The days to come", detail="the next 28", keywords=("AHEAD",))
    async def ahead(self, request: PageRequest) -> Page:
        today = self.today
        days = [today + timedelta(days=offset) for offset in range(DAYS_AHEAD)]
        return self._menu(
            request.address,
            items=[
                (
                    _long_date(day),
                    _in_words(day - today),
                    self.address_for("day", day=day),
                )
                for day in days
            ],
        )

    @page("42{day:date}", title="One day")
    async def day(self, request: PageRequest, day: date) -> Page:
        _, weeks_in_year, _ = day.isocalendar()
        lines = [
            _long_date(day),
            "",
            f"Day {day.timetuple().tm_yday} of {366 if calendar.isleap(day.year) else 365}",
            f"Week {weeks_in_year}",
            f"ISO {day.isoformat()}",
            "",
            _in_words(day - self.today),
        ]
        #  Whichever menu the reader came through decides what "next" means, and
        #  a day reached by keying its number came through none. A frame names
        #  only the keys that do something on it, so the prompt is built from
        #  the same description as the choices.
        choices = {
            "0": self.address_for("main"),
            "1": self.address_for("month", day=day),
        }
        if request.arrival.preceding is not None:
            choices["A"] = request.arrival.preceding
        if request.arrival.following is not None:
            choices["D"] = request.arrival.following
        return Page(
            frames=(
                PageFrame(
                    frame=self._notice_frame(
                        request.address,
                        _month_name(day),
                        lines,
                        prompt=_prompt(
                            set(choices),
                            selecting=False,
                            item="day",
                            offering=[FooterItem("1", "month", Priority.PRIMARY)],
                        ),
                    ),
                    choices=choices,
                ),
            )
        )

    @page(
        "92",
        name="history",
        title="Where you have been",
        detail="this call, newest first",
        keywords=("HISTORY",),
    )
    async def _history(self, request: PageRequest) -> Page:
        """The framework's page, at this service's number."""
        return await self.history(request)

    @page(
        "94",
        name="names",
        title="Words you can key",
        detail="instead of a page number",
        keywords=("KEYWORDS", "WORDS"),
    )
    async def _names(self, request: PageRequest) -> Page:
        """The framework's page, at this service's number."""
        return await self.names(request)

    @page(
        "93",
        name="contents",
        title="Every page",
        detail="and the number that fetches it",
        keywords=("PAGES",),
    )
    async def _contents(self, request: PageRequest) -> Page:
        """The framework's page, at this service's number."""
        return await self.contents(request)

    @page("9", title="About this service", keywords=("ABOUT", "HELP"))
    async def about(self, request: PageRequest) -> Page:
        return Prose.of(
            "A calendar, served as Viewdata frames.",
            "It exists to demonstrate that Sextile is a framework and not one "
            "service: nothing here knows about forums, and nothing in the "
            "framework knows about calendars.",
            "Everything it shows comes from the standard library.",
            title=self._headed(request.address),
            home=self.index,
        ).build(request.address)

    #  Listed: the contents page is a directory of numbers that do something,
    #  and a reader looking for how to ring off should find it there.
    @page("90", title="Ring off", keywords=("BYE",))
    async def goodbye(self, request: PageRequest) -> Page:
        return self._farewell("GOODBYE", ["Thank you for calling.", "", "Ring off."])

    def _farewell(self, title: str, lines: list[str]) -> Page:
        """The last thing a caller sees: no chrome, and room beneath to type.

        A footer offering the index would be a lie on a page there is no coming
        back from, and the reader needs somewhere blank for the cursor to be
        left -- they are about to be talking to their modem.
        """
        canvas = Canvas()
        canvas.row(0).text(title, Colour.CYAN)
        for offset, line in enumerate(lines):
            if line:
                canvas.row(2 + offset).text(fitted(line, COLUMNS - 1), Colour.WHITE)
        return Page(frames=(PageFrame(frame=canvas.frame),), hang_up=True)

    # -- drawing ------------------------------------------------------------

    def _month_page(self, address: PageAddress, day: date) -> Page:
        canvas = Canvas()
        draw_chrome(
            canvas,
            title=_month_name(day).upper(),
            page_number=address.frame_number(0),
            prompt=_prompt({"A", "D"}, selecting=False, item="month"),
        )
        canvas.row(CONTENT_FIRST_ROW).text(
            "  ".join(weekday[:2] for weekday in _WEEKDAYS), Colour.CYAN
        )
        weeks = calendar.Calendar().monthdayscalendar(day.year, day.month)
        for offset, week in enumerate(weeks):
            cells = " ".join(f"{number:>3}" if number else "   " for number in week)
            #  The week the day falls in, rather than the day itself: a colour
            #  attribute occupies a cell, and there is no spare cell inside a
            #  row of seven three-column figures to put one in.
            colour = Colour.YELLOW if day.day in week else Colour.WHITE
            canvas.row(CONTENT_FIRST_ROW + 1 + offset).text(cells.rstrip(), colour)

        previous, following = _months_either_side(day)
        choices = {
            "0": self.address_for("main"),
            "A": self.address_for("month", day=previous),
            "D": self.address_for("month", day=following),
        }
        return Page(frames=(PageFrame(frame=canvas.frame, choices=choices),))

    def _headed(self, address: PageAddress) -> str:
        """What goes at the top of a page: what it was registered as, shouted.

        A page that names itself in its decorator and again in its own chrome
        has two copies to keep in step. Pages whose heading is not their name
        -- a month's name, a day's date -- say so.
        """
        return self.describe(address).upper()

    def _menu(
        self,
        address: PageAddress,
        *,
        title: str | None = None,
        items: list[tuple[str, str, PageAddress]],
        preamble: list[str] | None = None,
    ) -> Page:
        """A menu, dealt nine to a frame by the framework's template."""
        return Menu(
            title=title if title is not None else self._headed(address),
            entries=[
                MenuItem(text=text, detail=detail, destination=where)
                for text, detail, where in items
            ],
            home=self.index,
            preamble=preamble or (),
        ).build(address)

    def _notice(
        self, address: PageAddress, title: str | None, lines: list[str]
    ) -> Page:
        """A page that simply says something, with no choices but the way back."""
        return Page(
            frames=(
                PageFrame(
                    frame=self._notice_frame(
                        address,
                        title if title is not None else self._headed(address),
                        lines,
                        prompt=_prompt(set(), selecting=False),
                    ),
                    choices={"0": self.address_for("main")},
                ),
            )
        )

    def _notice_frame(
        self, address: PageAddress, title: str, lines: list[str], *, prompt: str
    ) -> Frame:
        canvas = Canvas()
        draw_chrome(
            canvas, title=title, page_number=address.frame_number(0), prompt=prompt
        )
        for offset, line in enumerate(lines[:CONTENT_ROWS]):
            if line:
                canvas.row(CONTENT_FIRST_ROW + offset).text(fitted(line, COLUMNS - 1), Colour.WHITE)
        return canvas.frame


# -- helpers ----------------------------------------------------------------


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


def _prompt(
    moves: set[str],
    *,
    selecting: bool,
    item: str = "item",
    offering: Sequence[FooterItem] = (),
) -> str:
    """Name every key that does something here, and no key that does not.

    The framework has the words -- the same ones the templates use -- so a page
    built by hand and a page built by a template say the same thing about the
    same key, and a frame with room to spare says it in full.
    """
    items = []
    if selecting:
        items.append(FooterItem("1-9", "select", Priority.PRIMARY))
    items += offering
    items += movement(moves, item=item)
    items.append(FooterItem(HOME_KEY, "index", Priority.ESSENTIAL))
    return render_footer(items, ROOM)
