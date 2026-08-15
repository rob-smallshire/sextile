# Menus and page numbers

A tutorial step: a menu on `*1#` whose entries lead to other pages, one of them a
whole family of pages addressed by date.

## Collect the pages in a router

Declaring pages beside their functions with a `PageRouter`, rather than on the app
directly, is the form a service grows into: the pages are a module of their own,
spread into the service in one line. Page 1 is now a menu, with an about page and a
page for a single day:

```{sextile-frame}
:page: "1"
:show-code:

import calendar
from datetime import date

from sextile import (
    MenuItem, Page, PageRequest, PageRouter, Sextile, menu_page, notice_page, prose_page,
)

SERVICE_NAME = "CALENDAR"
router = PageRouter()


@router.page("1", name="main", title="The index", keywords=("MAIN", "INDEX"))
async def main(request: PageRequest) -> Page:
    app = request.app
    return menu_page(
        request,
        title=SERVICE_NAME,
        items=[
            MenuItem("New Year's Day", "1 January 2026", app.address_for("day", day=date(2026, 1, 1))),
            app.menu_item("about"),
        ],
    )


@router.page("42{day:date}", name="day", title="One day")
async def one_day(request: PageRequest, day: date) -> Page:
    _, week, _ = day.isocalendar()
    length = 366 if calendar.isleap(day.year) else 365
    return notice_page(
        request,
        day.strftime("%A %d %B %Y"),
        "",
        f"Day {day.timetuple().tm_yday} of {length}",
        f"Week {week}",
        f"ISO {day.isoformat()}",
    )


@router.page("9", name="about", title="About this service", keywords=("ABOUT",))
async def about(request: PageRequest) -> Page:
    return prose_page(request, "A calendar, served as Viewdata frames.")


app = Sextile(name=SERVICE_NAME, pages=[*router])
```

`@router.page` registers a page and everything the service says about it: its
number, its `name`, its `title` (the header, and the words a menu shows for it),
and the `keywords` a reader can key instead of the number. `menu_page` numbers its
entries `1`–`9`, so a reader chooses with one keypress.

## Link to a page by its name

`app.menu_item("about")` builds a menu entry from a registered page — its title
and its number — so the menu never respells a number. `app.address_for("day",
day=...)` is the same read backwards: it builds a page number from a route's
pattern and its fields.

## Address a family of pages

The `day` page's pattern is `42{day:date}`: the literal `42`, then a `date` field.
The `date` converter reads the eight digits after `42` as a `date` and hands it to
the handler, so `*4220260101#` is 1 January 2026 — everything it shows comes from
that one date:

```{sextile-frame}
:page: "4220260101"

import calendar
from datetime import date

from sextile import Page, PageRequest, PageRouter, Sextile, notice_page

router = PageRouter()


@router.page("42{day:date}", name="day", title="One day")
async def one_day(request: PageRequest, day: date) -> Page:
    _, week, _ = day.isocalendar()
    length = 366 if calendar.isleap(day.year) else 365
    return notice_page(
        request,
        day.strftime("%A %d %B %Y"),
        "",
        f"Day {day.timetuple().tm_yday} of {length}",
        f"Week {week}",
        f"ISO {day.isoformat()}",
    )


app = Sextile(name="CALENDAR", pages=[*router])
```

One page number, `*4220260101#`, drawn by the same code as `*1#`. From the menu,
key `1` to reach it; or key `*ABOUT#` from anywhere to reach the about page by its
keyword.
