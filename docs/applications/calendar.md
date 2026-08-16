# The calendar

A worked example: a calendar as a Viewdata service. It is the framework's own
example, built from the standard library alone — no archive, no network and
nothing to configure — so the framework is exercised by a service with nothing in
common with a forum.

## The numbering

Its pages, from the module's own docstring:

```{literalinclude} ../../packages/calendar-viewdata/src/calendar_viewdata/application.py
:lines: 8-16
```

## Running it

```sh
uv run sextile serve calendar_viewdata:app          # answer calls
uv run sextile render calendar_viewdata:app --page 3   # or just draw a page
```

## This month

`build_application(now=)` takes the clock, so a fixed one draws the same month
every time:

```{sextile-frame}
:page: "3"
:show-code:

from datetime import UTC, datetime

from calendar_viewdata import build_application

app = build_application(now=lambda: datetime(2026, 8, 1, tzinfo=UTC))
```

The calendar's design note records that it needed no framework change at all,
which is the point of a second application: everything it draws — the month grid,
the days to come, the about page — is built from the parts the framework already
had. What the framework lacked was found by the two services that are not made of
the standard library, on the {doc}`stardot` and {doc}`weather` pages.
