# Working on Sextile

A uv workspace holding a Viewdata application-server framework and the services
built on it.

```
packages/sextile/              the framework: connections, sessions, routing,
                               page numbering, frames on the wire
packages/stardot-viewdata/     the Stardot phpBB forum, as Viewdata
packages/calendar-viewdata/    a calendar; the framework's worked example
```

Read [docs/architecture.md](docs/architecture.md) first; it explains the
layering and, more usefully, where the seams are and why. Then
[docs/target-architecture.md](docs/target-architecture.md) for where this is
going — a phpBB extension replacing the Atom feed — and
[docs/writing-an-application.md](docs/writing-an-application.md),
[docs/rendering.md](docs/rendering.md) or
[docs/navigation.md](docs/navigation.md) depending on which end you are working
at.

## The two invariants

They are the point of the whole arrangement, and both are checkable.

1. **Nothing in `packages/sextile/` may know about a forum, phpBB or Stardot.**
   Not in the code, and preferably not in the comments — a framework that
   explains itself in terms of posts will grow a dependency on them sooner or
   later. `calendar-viewdata` exists to keep this honest: if a page there ever
   needs something the framework offers only because Stardot wanted it, the seam
   has moved.

2. **Nothing in an application may reach into the framework's internals.** The
   surface is `sextile`'s top-level exports plus `sextile.viewdata` for drawing.
   Both are stated in the packaging, so an import in the wrong direction fails.

## How this project is built

**Test-first, in small increments.** Name the next behaviour, write the failing
test, make it pass, tidy. The awkward parts here are nearly all pure functions
over values — transliteration, routing, HTML to blocks, layout, command parsing
— and the two impure edges, HTTP and sockets, sit behind narrow interfaces that
are easy to fake.

**Measure the BBC end; do not assume it.** Several things that a reasonable
reading of the documentation would get wrong were settled by driving real
Commstar under Beebium:

- attributes must travel as `ESC` + code + 0x40; the SAA5050's own 0x80-0x9F
  codes simply vanish on Prestel's 7E1 line;
- a frame is 24 rows of 40, column 40 wraps by itself, and the bottom-right cell
  wraps to the top-left rather than scrolling;
- `RETURN` transmits 0x5F, not 0x23;
- page numbers have no practical length limit.

The spikes that established these are in `docs/spikes/`. They need a local
Beebium checkout and are not part of the test suite. Findings are written up in
[docs/viewdata-encoding.md](docs/viewdata-encoding.md), which separates what was
verified from what was inferred. **Keep that distinction** in anything new.

Beebium's own source is a good oracle where a spike would be slow:
`~/Code/beebium/src/core/include/beebium/Saa5050.hpp` and
`docs/discussion/teletext-repertoire-choice.md` settled the per-row attribute
reset and corroborated the character set.

**Say so when something is missing.** An empty menu with no explanation looks
like a fault, and on a service that answers slowly by design a reader cannot
tell the difference. Pages with nothing to show say why. Note the difference
between that and a page that does not exist: a handler returns `None` for the
second, and the session says so without moving the reader.

**Record limitations as tests.** What the feed cannot tell us is pinned by tests
in `packages/stardot-viewdata/tests/`, so a change in the board's configuration
surfaces as a failure rather than going unnoticed. See
[feed-limitations.md](packages/stardot-viewdata/docs/feed-limitations.md).

## Conventions

- `uv` for everything: `uv run pytest`, `uv run ruff check .`, `uv run mypy`.
  All three run over the whole workspace, and all three must pass. `mypy` is
  `--strict`, including the tests.
- Path variables use the `_filepath`, `_dirpath` suffixes, not `_dir`/`_file`.
- Comments explain *why*, and are worth writing where a choice looks arbitrary
  but is not. There are many such choices here.
- Commit at each working increment. Do not push; that is the user's call.

## Politeness is not optional

Stardot asks for a 60-second crawl delay and forbids several paths, including
`viewtopic.php?p=` — which is exactly the page that would reveal a post's topic
id. Both are enforced in `stardot_viewdata/feed/`, whose `robots.py` is
hand-written because Python's `urllib.robotparser` reads Stardot's file wrongly
and would permit what the board forbids.

Test fixtures under `packages/stardot-viewdata/tests/data/` were captured from
the live board. Prefer re-using them to making fresh requests.

## Trying it

```sh
uv run sextile render --demo                        # a frame, without a Beeb
uv run sextile serve calendar_viewdata:app          # a whole service, no forum
uv run stardot-viewdata render --page 1             # a page, plus where its keys lead
uv run stardot-viewdata ingest --seed               # fill a new archive (an hour or more)
uv run stardot-viewdata ingest                      # then poll every 5 minutes
uv run stardot-viewdata serve                       # answer calls on port 6850
nc localhost 6850                                   # and call it
```

`serve` and `ingest` both default to `sextile.sqlite` **in the working
directory**, so run them from the same place.

[docs/open-questions.md](docs/open-questions.md) lists what is known to be
missing, and what is deliberately not done.
