# State and the lifespan

A tutorial step: the service learns what time it is, and holds it in the one place
a service holds anything.

## Hold the clock as state

A calendar has to know the time, and reading it is the one thing the service does
that is not a pure function of its input. So the service holds a clock. A
`StateKey` names it; the service's lifespan — an `async` context manager run once
around the whole service — puts the clock in `app.state` under that key; and a
`build_application` factory lets a caller pass a clock in, defaulting to the real
one.

```{note}
Session state and service state are different. Session state is one caller's own,
lasting as long as the line is up (`request.session`). Service state is shared
across callers for the life of the service, opened in the lifespan and read back
through a `StateKey` (`request.state`). The clock is service state: every caller
sees the same one.
```

## Read it in a page

A page reads the clock from the request — never a global — so the whole service
runs on whatever clock the lifespan opened, and a test can open a fixed one. The
time page, `*2#`, shows it to the second, and `*NOW#` reaches it by keyword. The
whole file so far, its menu now dated:

```{sextile-frame}
:page: "1"
:show-code:

import calendar
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

from sextile import (
    MenuItem, Page, PageRequest, PageRouter, Sextile, StateKey,
    keyed, keys, menu_page, notice_page, prose_page,
)

SERVICE_NAME = "CALENDAR"

type Clock = Callable[[], datetime]
CLOCK = StateKey[Clock]("clock")
router = PageRouter()


def _now(request: PageRequest) -> datetime:
    return request.state[CLOCK]()


def _today(request: PageRequest) -> date:
    return _now(request).date()


def _long_date(day: date) -> str:
    return day.strftime("%A %d %B %Y")


@router.page("1", name="main", title="The index", keywords=("MAIN", "INDEX"))
async def main(request: PageRequest) -> Page:
    app = request.app
    return menu_page(
        request,
        title=SERVICE_NAME,
        preamble=[_long_date(_today(request))],
        items=[app.menu_item("now"), app.menu_item("about")],
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


@router.page("42{day:date}", name="day", title="One day")
async def one_day(request: PageRequest, day: date) -> Page:
    _, week, _ = day.isocalendar()
    length = 366 if calendar.isleap(day.year) else 365
    return notice_page(
        request,
        _long_date(day),
        "",
        f"Day {day.timetuple().tm_yday} of {length}",
        f"Week {week}",
        f"ISO {day.isoformat()}",
    )


@router.page("9", name="about", title="About this service", keywords=("ABOUT", "HELP"))
async def about(request: PageRequest) -> Page:
    return prose_page(
        request,
        "A calendar, served as Viewdata frames.",
        "It exists to demonstrate that Sextile is a framework and not one "
        "service: nothing here knows about forums, and nothing in the framework "
        "knows about calendars.",
        "Everything it shows comes from the standard library.",
    )


def build_application(now: Clock | None = None) -> Sextile:
    reading = now or (lambda: datetime.now(UTC))

    @asynccontextmanager
    async def lifespan(app: Sextile) -> AsyncIterator[None]:
        app.state[CLOCK] = reading
        yield

    return Sextile(name=SERVICE_NAME, pages=[*router], lifespan=lifespan)


app = build_application(now=lambda: datetime(2026, 8, 1, tzinfo=UTC))
```

The last line is the tutorial's: it fixes the clock to 1 August 2026 so every frame
here is the same on every build. Your file writes `app = build_application()`, for
the real clock — the factory takes the clock as a parameter precisely so that a
test, in step 7, can hand it a fixed one. Here is the time page it draws:

```{sextile-frame}
:page: "2"

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime

from sextile import (
    Page, PageRequest, PageRouter, Sextile, StateKey, keyed, keys, notice_page,
)

CLOCK = StateKey[Callable[[], datetime]]("clock")
router = PageRouter()


def _long_date(day: date) -> str:
    return day.strftime("%A %d %B %Y")


@router.page("2", name="now", title="The time now")
async def now_page(request: PageRequest) -> Page:
    moment = request.state[CLOCK]()
    return notice_page(
        request,
        _long_date(moment.date()),
        "",
        moment.strftime("%H:%M:%S"),
        moment.tzname() or "",
        "",
        f"Key {keyed(keys.REFRESH)} to ask again.",
    )


@asynccontextmanager
async def lifespan(app: Sextile) -> AsyncIterator[None]:
    app.state[CLOCK] = lambda: datetime(2026, 8, 1, tzinfo=UTC)
    yield


app = Sextile(name="CALENDAR", pages=[*router], lifespan=lifespan)
```
