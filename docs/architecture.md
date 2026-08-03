# How Sextile is put together

```
    Stardot's Atom feed
            |
   feed/    |  client, robots, atom, source, ingest      fetching, politely
            v
   model.py    Post, Feed                                the domain
            |
   store/   |  repository, schema.sql                    the archive
            v
   content/    html, blocks, transliterate               a post's shape
            |
   viewdata/|  charset, controls, encoding, frame,       a screen
            |  canvas, wrapping, layout, chrome, ansi
            v
   pages/      numbering, router, page                   what a page number means
            |
   session/ |  commands, session                         one caller's conversation
            v
   server.py   asyncio TCP                               answering calls
```

Dependencies point downward only. `viewdata/` knows nothing of forums;
`content/` knows nothing of screens; `feed/` knows nothing of either.

## The seams, and why they are there

Three boundaries were placed deliberately. Each exists because something on one
side is expected to be replaced.

**`feed/source.py` — the `PostSource` port.** Everything above it deals in
`Post` and `Feed` and has never heard of Atom, phpBB or HTTP. The Atom adapter
is the first implementation; a small read-only phpBB extension is the likely
second, and would arrive without disturbing the numbering, the renderer or the
session. This is the seam that matters most, because the feed's limitations
(see [feed-limitations.md](feed-limitations.md)) are the project's main
constraint.

**`pages/page.py` — `Page` and `PageFrame`.** A page builder returns frames
*and* what each key does while a given frame is showing, because frame b of a
day's posts offers a different nine choices from frame a. Choices are keyed by
character rather than digit, so a page can offer `N` for next or `R` for reply
without the type changing. The session consults this and nothing else to answer
a keypress.

**`server.py` — no transport knowledge.** Sextile is a plain TCP server. tcpser
is already the ip232 endpoint an emulator connects to, so Sextile is dialled
exactly as any other viewdata board is and needs no ip232 code at all. If
Sextile ever speaks ip232 or a real serial port directly, that is a new module
beside this one, not a change to it.

## Where the awkwardness lives

**`viewdata/frame.py`** is a fixed 24x40 grid rather than a stream of writes,
because Commstar wraps from the bottom-right cell back to the top-left instead
of scrolling. A serialiser that emitted one cell too many would overwrite the
frame it had just drawn. With a fixed grid that cannot happen.

**`viewdata/canvas.py`** exists because a colour attribute occupies a character
cell. A row that changes colour twice has thirty-eight columns for text, not
forty. Canvas does that accounting so nothing above it has to, which is also why
colour could not be deferred to a later version.

**`viewdata/footer.py`** decides what the prompt gives up when the row will
not hold it all. Forty cells is not many and the longest prompt already fills
the row exactly, so the next key added will not fit. Each item carries a
priority and the renderer sheds labels first, from the least important upward,
then whole items — the key last, because the key is what the reader presses and
the label only teaches it. `0 menu` outlasts everything: a reader who cannot
read the screen still needs to leave it.

**`viewdata/encoding.py`** guards the fact that the wire has two namespaces
sharing the C0 range: a bare `0x0C` clears the screen, while `ESC 0x4C` selects
normal height. Confusing them produces a display wrong in ways that look like
transport corruption.

**`feed/robots.py`** is hand-written because Python's `urllib.robotparser`
returns the *first* matching rule, so Stardot's `Allow: /` masks every
`Disallow` below it and it wrongly permits `viewtopic.php?p=`. RFC 9309 requires
longest-match-wins.

**`store/repository.py`** stores instants in UTC so that ordering by text is
ordering by time, and computes each post's London calendar date once on the way
in. Days are London days because that is where the board's readers are.

## Testing

Unit tests throughout, written first, against real captured data wherever the
real data has a shape worth respecting — `tests/data/` holds feeds and a
`robots.txt` taken from the live board.

Facts about the BBC end were **measured, not assumed**. The scripts that settled
each question are kept in `docs/spikes/`; they need a local Beebium checkout and
are not part of the suite. What they established is written up in
[viewdata-encoding.md](viewdata-encoding.md), which distinguishes what was
verified from what was inferred.
