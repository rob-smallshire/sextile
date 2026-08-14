# How this is put together

Two kinds of thing live here: a framework, and services built on it.

```
packages/sextile/              the framework: connections, sessions, routing,
                               page numbering, frames on the wire
packages/stardot-viewdata/     the Stardot phpBB forum, as Viewdata
packages/calendar-viewdata/    a calendar; the framework's worked example
packages/weather-viewdata/     the weather, from met.no and a local gazetteer
```

The framework depends on nothing at all; the applications depend on it and not
on each other. That is stated in the packaging rather than left as a convention,
so an import in the wrong direction fails rather than merely being regrettable.

Each is written up as built, and those are the documents to read:

| | |
|---|---|
| [sextile/docs/design.md](../packages/sextile/docs/design.md) | the framework: the seam, addressing, routing, the session, the wire |
| [stardot-viewdata/docs/design.md](../packages/stardot-viewdata/docs/design.md) | the numbering, the archive, the polite ingest, phpBB's HTML |
| [calendar-viewdata/docs/design.md](../packages/calendar-viewdata/docs/design.md) | the second application, and what it was for |
| [weather-viewdata/docs/design.md](../packages/weather-viewdata/docs/design.md) | the third: place search, met.no, drawing the weather, and the twenty-odd things it asked of the framework |
| [sextile/docs/public-surface.md](../packages/sextile/docs/public-surface.md) | which of the framework an application may import, and where that line is currently crossed |
| [sextile/docs/page-layout.md](../packages/sextile/docs/page-layout.md) | a design note, not built: a page as furniture and a list of parts laid out down its frames |

[target-architecture.md](target-architecture.md) says where all this is going
and why — the phpBB extension, and the phases between here and it.
[open-questions.md](open-questions.md) lists what is known to be missing and
what is deliberately not done.

## The seams

Three boundaries do the load-bearing work. Each exists because something on one
side is expected to be replaced.

**`sextile/application.py` — the `Application` base class.** An application
answers `respond(request) -> Page | None`, and everything about connections,
sessions, protocol and routing is on the other side of it. The framework has no
way to reach into an application and no vocabulary for what one might be about.

**`stardot_viewdata/feed/source.py` — the `PostSource` port.** Everything above
it deals in `Post` and `Feed` and has never heard of Atom, phpBB or HTTP. The
Atom adapter is the first implementation; the phpBB Content Provider extension
is the intended second, and should arrive without disturbing the numbering, the
renderer or the session.

**`weather_viewdata/forecast/source.py` — the `ForecastSource` port.** The same
seam again, and the one that shows it is a shape rather than a coincidence:
everything above it deals in `Forecast` and `Moment` and has never heard of
met.no, JSON or HTTP.

**`sextile/visits.py` — the `Visits` port.** The third time the same shape has
been wanted, and the first time in the framework rather than an application: a
log of what has been read, with one SQLite implementation and a protocol narrow
enough to fake. The middleware that writes it and the pages that read it talk to
the protocol, so a service keeping its log elsewhere writes an adapter rather
than going without the pages.

**`sextile/server.py` — no transport knowledge.** A plain TCP server. tcpser is
already the ip232 endpoint an emulator connects to, so a service is dialled
exactly as any other viewdata board is and needs no ip232 code at all. Speaking
ip232 or a real serial port directly would be a new module beside this one, not
a change to it.

## Where to start reading

Two narratives follow the arrows end to end, and are the quickest way in:

- [rendering.md](../packages/sextile/docs/rendering.md) takes one document from
  its source to the wire.
- [navigation.md](../packages/sextile/docs/navigation.md) takes one keypress
  from the terminal to a reply.

To write a service of your own,
[writing-an-application.md](../packages/sextile/docs/writing-an-application.md).

## What was measured rather than assumed

Much of the design rests on facts established by driving real Commstar under
Beebium rather than on documentation: attributes must travel escaped, a frame is
24 × 40 and wraps rather than scrolling, `RETURN` transmits 0x5F, page numbers
have no practical length limit.

The scripts that settled each question are indexed in
[spikes/README.md](spikes/README.md); they need a local Beebium checkout and are
not part of the test suite. What they established is written up in
[viewdata-encoding.md](../packages/sextile/docs/viewdata-encoding.md), which
distinguishes what was **verified** from what was **inferred**. Keep that
distinction in anything new.

## Testing

Unit tests throughout, written first. Each package's tests live with it, which
is the part that matters: the framework's suite cannot reach a forum fixture
even by accident, and it drives a made-up service rather than a real one so that
it cannot come to depend on what a real one happens to be about.

Test module names are unique across the workspace. Two members may both have a
`tests/` directory, but two modules called `test_store` may not, and `mypy`
says so rather than one shadowing the other.

Real data wherever the real data has a shape worth respecting, and limitations
recorded as tests so that a change at the board's end surfaces as a failure. See
each package's design document for the detail.
