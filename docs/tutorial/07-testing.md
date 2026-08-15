# Testing a service

A tutorial step: drive the calendar the way a caller does, so a change that breaks
a page is caught before a reader keys it.

## Fetch a page in a test

`sextile.testing.fetch` builds a request for a page and answers it in process, with
no socket; `text_of` reads the characters of the frame back. With the clock fixed,
a page's words are known, so a test can assert them:

```python
from datetime import UTC, datetime

from sextile.testing import fetch, text_of
from my_calendar import build_application


def calendar() -> object:
    return build_application(now=lambda: datetime(2026, 8, 1, tzinfo=UTC))


async def test_the_index_shows_today() -> None:
    app = calendar()
    await app.startup()
    assert "Saturday 01 August 2026" in text_of(await fetch(app, "1"))
    await app.shutdown()
```

`build_application` takes the clock for exactly this: a test hands it a fixed one,
and the pages that read it are otherwise pure functions of the request.

## Drive a session

`connect` opens the service and rings it up, yielding a caller who presses keys
with `press` and reads the screen with `screen` — the whole session, not one page.
This keys `*3#` to reach the month, then `0` to come back:

```python
from sextile.testing import connect


async def test_the_month_and_the_way_back() -> None:
    async with connect(calendar()) as caller:
        await caller.press("*3#")
        assert "AUGUST 2026" in caller.screen
        await caller.press("0")
        assert "CALENDAR" in caller.screen
```

## The quick look

Between tests, `sextile render my_calendar:app --page 3` draws a frame to the
terminal, and `--form html` writes a page to open in a browser. This is the month,
the clock fixed so it is the same every build:

```{sextile-frame}
:page: "3"

from datetime import UTC, datetime

from calendar_viewdata import build_application

app = build_application(now=lambda: datetime(2026, 8, 1, tzinfo=UTC))
```

## Your calendar

Your file is now the framework's own worked example,
`calendar_viewdata/application.py`, line for line. The shipped file adds a
docstring to each page and a module docstring with the numbering table — the
documentation the {doc}`reference <../reference/api/modules/sextile>` renders — and
nothing else:

```{literalinclude} ../../packages/calendar-viewdata/src/calendar_viewdata/application.py
:language: python
```
