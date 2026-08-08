# calendar-viewdata, as built

A calendar, served as Viewdata frames. It is small on purpose and has two jobs,
only one of which is telling you the date.

## Why it exists

**To hold the framework to its claim.** Sextile says it is a framework rather
than one service with the serial numbers filed off. That was unfalsifiable while
there was one application, and that application was the one the framework had
been cut out of. A second service with nothing whatever in common with a forum
is the test, and this is it.

The result of the test, recorded here because it will not be obvious later: it
needed **no change to the framework**, and its tests passed the first time they
were run. What it did find was a bug in itself — a month page whose footer
offered a `1-9 select` it had not got, which is exactly the rule the framework's
documentation states and exactly the rule that is easy to break.

**To be the worked example.**
[writing-an-application.md](../../sextile/docs/writing-an-application.md) is
written against this package, so it is meant to be read rather than merely to
work. It is also a reasonable thing to copy when starting a service.

## The pages

```
1                  the index, with today's date
2                  the date and time now, to the second
3                  this month, as a grid
32{day:date}       the month containing a date, as 3220260802
4                  the days to come, twenty-eight of them, nine to a frame
42{day:date}       one of them
9                  about
90                 goodbye, which sets hang_up
```

A whole date is one `date` field rather than three `int(n)` fields, because the
converter parses it into a `datetime.date` and rejects the 31st of February,
which three independent integers cannot.

Keywords: `*MAIN#`, `*INDEX#`, `*NOW#`, `*TIME#`, `*MONTH#`, `*AHEAD#`,
`*ABOUT#`, `*HELP#`, `*BYE#`.

What each page exercises, since that is half the point:

| Page | What it is there to prove |
|---|---|
| `3`, `32<date>` | a `date` field; the horizontal keys walking months |
| `4` | a menu across several frames, and the sequence running past a frame's end |
| `42<date>` | `request.arrival` — neighbours offered only to a reader who came through the menu |
| `2` | that `*09#` means something: the clock is read each time it is asked |
| `90` | `hang_up` |

## Decisions

**The clock is a constructor argument.** `CalendarApplication(now=...)` takes a
callable returning an aware `datetime`, defaulting to `datetime.now(UTC)`. It is
the only thing here that is not a pure function, and a service whose pages
change under it cannot be tested otherwise.

**Nothing but the standard library.** No archive, no network, nothing to
configure. That is what makes it a fair test of the framework: anything it needs
is either in Python or in Sextile, and if a page here ever wants something
Sextile offers only because a forum wanted it, the seam has moved.

**The month grid highlights the whole week** containing the day, not the day
itself. A colour attribute occupies a cell, and there is no spare cell inside a
row of seven three-column figures to put one in. This is the framework's central
constraint arriving in a service that has nothing to do with forums, which is
mildly reassuring.

**Every frame names only the keys that do something on it.** The day page builds
its prompt and its choices from the same description, since it offers `1` for
the month always and the horizontal keys only sometimes. The month page names
the months either side and nothing else.

## What it duplicates

A menu builder — nine choices to a frame, a line of detail beneath each, `0` for
the index — much like Stardot's. That is a viewdata convention rather than
either service's, and it belongs in the framework. It is not there yet because
with two examples the shared shape is a guess; with a third it would be
evidence. Noted in [open-questions.md](../../../docs/open-questions.md) rather
than acted on.
