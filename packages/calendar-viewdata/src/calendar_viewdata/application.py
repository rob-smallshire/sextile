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
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Final

from sextile import Page, PageAddress, PageFrame, PageRequest, Sextile
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import COLUMNS, Frame

SERVICE_NAME: Final = "CALENDAR"

#: A reader selects with one keypress, so nine is the most a frame can offer.
CHOICES_PER_FRAME: Final = 9

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
        super().__init__()
        self._now = now or (lambda: datetime.now(UTC))
        self._register()

    def _register(self) -> None:
        self.page("1", name="main")(self.main)
        self.page("2", name="now")(self.now_page)
        self.page("3", name="this_month")(self.this_month)
        self.page("32{day:date}", name="month")(self.month)
        self.page("4", name="ahead")(self.ahead)
        self.page("42{day:date}", name="day")(self.day)
        self.page("9", name="about")(self.about)
        self.page("90", name="goodbye")(self.goodbye)

        for keyword, route in (
            ("MAIN", "main"),
            ("INDEX", "main"),
            ("TIME", "now"),
            ("NOW", "now"),
            ("MONTH", "this_month"),
            ("AHEAD", "ahead"),
            ("ABOUT", "about"),
            ("HELP", "about"),
            ("BYE", "goodbye"),
        ):
            self.alias(keyword, self.address_for(route))

    @property
    def today(self) -> date:
        return self._now().date()

    # -- the pages ----------------------------------------------------------

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

    async def now_page(self, request: PageRequest) -> Page:
        moment = self._now()
        return self._notice(
            request.address,
            "THE TIME NOW",
            [
                _long_date(moment.date()),
                "",
                moment.strftime("%H:%M:%S"),
                moment.tzname() or "",
                "",
                "Key *09# to ask again.",
            ],
        )

    async def this_month(self, request: PageRequest) -> Page:
        return self._month_page(request.address, self.today)

    async def month(self, request: PageRequest, day: date) -> Page:
        return self._month_page(request.address, day)

    async def ahead(self, request: PageRequest) -> Page:
        today = self.today
        days = [today + timedelta(days=offset) for offset in range(DAYS_AHEAD)]
        return self._menu(
            request.address,
            title="THE DAYS TO COME",
            items=[
                (
                    _long_date(day),
                    _in_words(day - today),
                    self.address_for("day", day=day),
                )
                for day in days
            ],
        )

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
        offered = ["1 month"]
        if request.arrival.preceding is not None:
            choices["A"] = request.arrival.preceding
        if request.arrival.following is not None:
            choices["D"] = request.arrival.following
        axis = _axis("A" in choices, "D" in choices, "day")
        if axis:
            offered.append(axis)
        offered.append("0 menu")
        return Page(
            frames=(
                PageFrame(
                    frame=self._notice_frame(
                        request.address, _month_name(day), lines, prompt=", ".join(offered)
                    ),
                    choices=choices,
                ),
            )
        )

    async def about(self, request: PageRequest) -> Page:
        return self._notice(
            request.address,
            "ABOUT",
            [
                "A calendar, served as Viewdata frames.",
                "",
                "It exists to demonstrate that Sextile is",
                "a framework and not one service: nothing",
                "here knows about forums, and nothing in",
                "the framework knows about calendars.",
                "",
                "Everything it shows comes from the",
                "standard library.",
            ],
        )

    async def goodbye(self, request: PageRequest) -> Page:
        return self._farewell("GOODBYE", ["Thank you for calling.", "", "Ring off."])

    async def timed_out(self) -> Page:
        return self._farewell(
            "RINGING OFF", ["No reply for some time.", "", "The line has been released."]
        )

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
                canvas.row(2 + offset).text(_fitted(line), Colour.WHITE)
        return Page(frames=(PageFrame(frame=canvas.frame),), hang_up=True)

    # -- drawing ------------------------------------------------------------

    def _month_page(self, address: PageAddress, day: date) -> Page:
        canvas = Canvas()
        draw_chrome(
            canvas,
            title=_month_name(day).upper(),
            page_number=address.frame_number(0),
            prompt="←A―D→ month, 0 menu",
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

    def _menu(
        self,
        address: PageAddress,
        *,
        title: str,
        items: list[tuple[str, str, PageAddress]],
        preamble: list[str] | None = None,
    ) -> Page:
        """Deal items nine to a frame, each with a line of detail beneath."""
        lead = preamble or []
        capacity = min(CHOICES_PER_FRAME, max((CONTENT_ROWS - len(lead)) // 2, 1))
        batches = [
            items[start : start + capacity] for start in range(0, len(items), capacity)
        ] or [[]]
        frames = []
        for index, batch in enumerate(batches):
            canvas = Canvas()
            moves = set()
            if index > 0:
                moves.add("W")
            if index + 1 < len(batches):
                moves.update({"S", "#"})
            draw_chrome(
                canvas,
                title=title,
                page_number=address.frame_number(index),
                prompt=_prompt(moves, selecting=bool(batch)),
            )
            row = CONTENT_FIRST_ROW
            for line in lead:
                if line:
                    canvas.row(row).text(_fitted(line), Colour.WHITE)
                row += 1
            choices = {"0": self.address_for("main")}
            for offset, (text, detail, destination) in enumerate(batch):
                choices[str(offset + 1)] = destination
                canvas.row(row).text(f"{offset + 1} ", Colour.YELLOW).text(
                    _fitted(text, COLUMNS - 4), Colour.WHITE
                )
                row += 1
                if detail and row < CONTENT_FIRST_ROW + CONTENT_ROWS:
                    canvas.row(row).skip(2).text(_fitted(detail, COLUMNS - 4), Colour.GREEN)
                row += 1
            frames.append(
                PageFrame(frame=canvas.frame, choices=choices, moves=frozenset(moves))
            )
        return Page(frames=tuple(frames))

    def _notice(self, address: PageAddress, title: str, lines: list[str]) -> Page:
        """A page that simply says something, with no choices but the way back."""
        return Page(
            frames=(
                PageFrame(
                    frame=self._notice_frame(address, title, lines, prompt="0 menu"),
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
                canvas.row(CONTENT_FIRST_ROW + offset).text(_fitted(line), Colour.WHITE)
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


def _axis(before: bool, after: bool, what: str) -> str:
    """One axis of movement, named only where it goes somewhere."""
    if before and after:
        return f"←A―D→ {what}"
    if after:
        return f"D→ {what}"
    if before:
        return f"←A {what}"
    return ""


def _prompt(moves: set[str], *, selecting: bool) -> str:
    parts = []
    if selecting:
        parts.append("1-9 select")
    if "W" in moves and "S" in moves:
        parts.append("←W―S→ frame")
    elif "S" in moves:
        parts.append("S→ frame")
    elif "W" in moves:
        parts.append("←W frame")
    parts.append("0 menu")
    return ", ".join(parts)


def _fitted(text: str, cells: int = COLUMNS - 1) -> str:
    return text[:cells]
