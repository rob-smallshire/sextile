# calendar-viewdata

A calendar, served as Viewdata frames.

```sh
uv run sextile serve calendar_viewdata:app
nc localhost 16650
```

```
    1           the index
    2           the date and time now
    3           this month
    32<date>    the month containing a date, as 3220260802
    4           the days to come
    42<date>    one of them
    9           about
    90          goodbye
```

## Why it exists

To be a *second* application. Sextile is meant to be a general framework, not the
first service reworked to look like one, and the only way to test that is to
write something with nothing in common with the first and see what the framework
asks for.

It is deliberately small and depends on nothing but the standard library and
Sextile: no archive, no network, nothing to configure. That makes it the worked
example the framework's documentation is written against —
[writing-an-application.md](../sextile/docs/writing-an-application.md) — and a
reasonable thing to copy when starting a service of your own.

The one thing it depends on that is not a pure function is the clock, which is
therefore a constructor argument. A service whose pages change under it cannot
be tested otherwise.

[docs/design.md](docs/design.md) is the design as built, and the worked example
in the documentation, [docs/applications/calendar.md](../../docs/applications/calendar.md),
draws a page of it live.

MIT licensed.
