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
   viewdata/|  charset, controls, encoding, frame        a screen
            |  canvas, wrapping, layout                  putting things on one
            |  chrome, footer, command_line              its furniture
            |  ansi                                      seeing it without a Beeb
            v
   pages/      numbering, page, router, demo             what a page number means
            |
   keys.py  |  the four movements                        shared by the two below
            v
   session/    commands, session                         one caller's conversation
            |
            v
   server.py   asyncio TCP                               answering calls
                                                         __main__.py drives it all
```

Dependencies point downward only. `viewdata/` knows nothing of forums;
`content/` knows nothing of screens; `feed/` knows nothing of either.

Two narratives follow the arrows end to end, and are the quickest way in:
[rendering.md](rendering.md) takes one post from the archive to the wire, and
[navigation.md](navigation.md) takes one keypress from the terminal to a reply.

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

**`viewdata/command_line.py`** draws over one row rather than redrawing the
frame, because Commstar does not echo a page request and repainting forty cells
per keystroke flickers once the cursor is on. It leaves the cursor where the
next character goes, which is what makes a typed character cost one byte and a
rub-out three.

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
in. Days are London days because that is where the board's readers are. It is
deliberately synchronous, reached through `asyncio.to_thread` at the boundary,
which is why the connection is opened `check_same_thread=False` and every
statement runs under a lock.

**`keys.py`** names the four movements once, because there are two spellings of
them — `WASD` and the BBC's own cursor keys, which arrive as the viewdata
cursor-control codes. The parser and the router both read it, so the two cannot
drift apart.

## Testing

Unit tests throughout, written first, against real captured data wherever the
real data has a shape worth respecting — `tests/data/` holds feeds and a
`robots.txt` taken from the live board. Real data has repeatedly found things
invented data would not: per-topic feeds carrying no `<category>`, a post id
recoverable from `<id>` when the link is unusable, and phpBB's feed stripping
newlines from code listings.

One lesson about fixtures, learned three refetches in. A test asserting the
first post's author is `komadori` pins today's feed, not the parser. Concrete
values belong on `topic-28000-feed.xml`, a closed thread from 2023 that does not
move; tests over the board feed should assert *shape*.

Facts about the BBC end were **measured, not assumed**. The scripts that settled
each question are indexed in [spikes/README.md](spikes/README.md); they need a
local Beebium checkout and are not part of the suite. What they established is
written up in [viewdata-encoding.md](viewdata-encoding.md), which distinguishes
what was verified from what was inferred.

**Limitations are recorded as tests**, so that a change in the board's
configuration surfaces as a failure rather than going unnoticed. Two such tests
have already inverted: one asserting listings arrive without line breaks, and
one asserting no post carries a topic id. Both now assert the opposite, the
administrators having fixed the feed. That is the mechanism working.
