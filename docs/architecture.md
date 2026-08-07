# How this is put together

Two things live here: a framework, and a service built on it.

```
packages/sextile/              the framework
packages/stardot-viewdata/     the Stardot forum, as Viewdata
packages/calendar-viewdata/    a calendar, as Viewdata
```

The framework depends on nothing; the applications depend on it and not on each
other. That is stated in the packaging rather than left as a convention, so an
import in the wrong direction fails rather than merely being regrettable.

[target-architecture.md](target-architecture.md) says where all this is going,
and why — the phpBB extension, and the phases between here and it.

## The framework

```
   viewdata/   charset, controls, encoding, frame       a screen
            |  canvas, wrapping, layout                 putting things on one
            |  chrome, footer, command_line             its furniture
            |  ansi                                     seeing it without a Beeb
            v
   content/    blocks, transliterate                    what is to be shown
            |
   addressing  PageAddress                              what a page is called
            |
   routing     patterns, converters, aliases            which page is which
            |
   page.py     Page, PageFrame                          what an application returns
            |
   application Application, Sextile, PageRequest        the seam
            |
   keys.py  |  the four movements
            v
   session/    commands, session                        one caller's conversation
            |
            v
   server.py   asyncio TCP                              answering calls
                                                        cli.py, __main__.py drive it
```

Dependencies point downward. `viewdata/` knows nothing of applications;
`content/` knows nothing of screens; nothing anywhere knows of forums.

Two narratives follow the arrows end to end and are the quickest way in:
[rendering.md](rendering.md) takes one document to the wire, and
[navigation.md](navigation.md) takes one keypress to a reply. To write a service
of your own, [writing-an-application.md](writing-an-application.md).

## The seams, and why they are there

**`application.py` — the `Application` base class.** The one that matters. An
application answers `respond(request) -> Page | None`, and everything about
connections, sessions, protocol and routing is on the other side of it. The
framework has no way to reach into an application and no vocabulary for what one
might be about.

`respond` returns `None` rather than a notice when a page is not there, because
the two are shown differently: a page that exists is somewhere the reader has
gone, and a page that does not is something said to a reader who has not moved.
Only the first belongs in the history.

**A handler is a function of a request, not of a page number.** A Viewdata
terminal is a display and nothing else, so everything a session knows is held at
the server. Two callers keying the same number can legitimately be shown
different things — because of where they came from, and later because of who
they are. `PageRequest` carries the captured fields, the arrival, and a mapping
that lives as long as the connection.

**`page.py` — `Page` and `PageFrame`.** A page builder returns frames *and* what
each key does while a given frame is showing, because frame b of a listing
offers a different nine choices from frame a. Choices are keyed by character
rather than by digit, so a page can offer `D` for next or `R` for reply without
the type changing. The session consults this and nothing else to answer a
keypress.

**`server.py` — no transport knowledge.** A plain TCP server. tcpser is already
the ip232 endpoint an emulator connects to, so a service is dialled exactly as
any other viewdata board is and needs no ip232 code at all. If Sextile ever
speaks ip232 or a real serial port directly, that is a new module beside this
one, not a change to it.

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

**`viewdata/footer.py`** decides what the prompt gives up when the row will not
hold it all. Forty cells is not many and the longest prompt already fills the
row exactly, so the next key added will not fit. Each item carries a priority
and the renderer sheds labels first, from the least important upward, then whole
items — the key last, because the key is what the reader presses and the label
only teaches it. `0 menu` outlasts everything: a reader who cannot read the
screen still needs to leave it.

**`viewdata/encoding.py`** guards the fact that the wire has two namespaces
sharing the C0 range: a bare `0x0C` clears the screen, while `ESC 0x4C` selects
normal height. Confusing them produces a display wrong in ways that look like
transport corruption.

**`routing.py`** refuses two variable-width fields running together, and tries
candidates most-literal-first rather than in registration order. Both are about
a routing table whose meaning must not change when someone tidies it.

**`keys.py`** names the four movements once, because there are two spellings of
them — `WASD` and the BBC's own cursor keys, which arrive as the viewdata
cursor-control codes. The parser and the session both read it, so the two cannot
drift apart.

## The applications

`stardot-viewdata` holds an archive, an Atom ingest, a phpBB HTML parser and
Stardot's information architecture. Its own documents are under
[packages/stardot-viewdata/docs/](../packages/stardot-viewdata/docs/), of which
[page-numbering.md](../packages/stardot-viewdata/docs/page-numbering.md) is the
one to read first.

`calendar-viewdata` exists to keep the framework honest. It has nothing in
common with a forum and depends on nothing but the standard library, so if a
page there ever needs something the framework offers only because Stardot wanted
it, the seam has moved.

## Testing

Unit tests throughout, written first. Each package's tests live with it, which
is the part that matters: the framework's suite cannot reach a forum fixture
even by accident.

Real data wherever the real data has a shape worth respecting —
`packages/stardot-viewdata/tests/data/` holds feeds and a `robots.txt` taken
from the live board. Real data has repeatedly found things invented data would
not: per-topic feeds carrying no `<category>`, a post id recoverable from `<id>`
when the link is unusable, and phpBB's feed stripping newlines from code
listings.

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
