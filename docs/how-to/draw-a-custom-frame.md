# Draw a custom frame

A how-to guide: draw a masthead or a grid cell by cell with a `Custom` part, or a
whole title frame with `title_page`.

The calendar's month page is a `Custom` part: a grid placed cell by cell. With
the clock fixed, it draws the same month every build:

```{sextile-frame}
:show-code:

from datetime import UTC, datetime

from calendar_viewdata import build_application

app = build_application(now=lambda: datetime(2026, 8, 1, tzinfo=UTC))
frame = fetch(app, "3")  # "this month", as a grid
```
