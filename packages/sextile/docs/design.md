# Sextile, as built

What is here, why each piece exists, and which decisions are load-bearing. For
how to *use* it, see [writing-an-application.md](writing-an-application.md).

Sextile is a Viewdata application server. It owns the connection, the session,
the routing and the bytes; an application owns the pages. The dividing line is
`Application.respond`, and the framework has no vocabulary for what a service
might be about.

## The shape of the thing

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
   routing     Router, Converter, Route                 which page is which
            |
   page        Page, PageFrame                          what an application returns
            |
   application Application, Sextile, PageRequest        the seam
            |
   keys     |  the four movements
            v
   session/    commands, session                        one caller's conversation
            |
            v
   server      asyncio TCP                              answering calls
                                                        cli, __main__ drive it
```

Dependencies point downward, and there is no third-party dependency at all: a
framework for talking to terminals over a socket needs nothing the standard
library does not have.

## The lifecycle, which is the whole design

A Viewdata terminal is a display and nothing else. It holds the frame on screen
and *not one thing besides* — not the page it came from, not the menu that led
there, not who is logged in. Everything of that kind is held at the server, for
as long as the line is up.

That is the opposite of the web, where the client carries a cookie and the
server may forget, and it is why the shapes here differ from a web framework's
in three specific ways:

**The connection is the session.** There is no session store, no identifier, no
expiry policy. `Session` is an object that lives as long as the socket, and
`PageRequest.session` is a plain mutable mapping hanging off it.

**A handler is a function of a request, not of a page number.** Two callers
keying the same number can legitimately be shown different things — because of
the menu they arrived through, and later because of who they are.

**Everything is async.** Not for concurrency at scale — a viewdata board serves
a handful of callers — but because a handler that goes to a database or an HTTP
API would otherwise stop every other caller while it waited.

## Addressing

`PageAddress` wraps a digit string, validated non-empty and ASCII. That is the
framework's only notion of what a page is called.

The alternative was to be generic over an application-supplied reference type,
which is what the original Stardot-shaped code did. Strings won because the page
number is the one name that everyone shares — the reader keying it, the terminal
displaying it, the application answering it, and whoever writes it on a beermat.
History, the back key, mounting and linking between applications all become
ordinary operations on a value that needs to know nothing about what it names.

No length limit is imposed: page numbers were measured to have no practical
limit on Commstar. What bounds a request is the command parser's own patience
(`ENTRY_LIMIT`, 32 characters).

A frame letter — the `b` in `82489493b` — is *not* part of an address. It names a
continuation of a page too long for one screen, it appears only on screen, and a
reader never keys it.

## Routing

A pattern is literal digits and named fields, compiled to an anchored regular
expression: `82{post_id:int}`, `32{day:date}`, `32{year:int(4)}{month:int(2)}`.

**Why patterns at all**, rather than a dictionary of numbers? Because a page
number's fields are the board's own identifiers, and a service has as many pages
as it has posts. The pattern is also read *backwards* by `address_for`, which is
what stops a numbering scheme existing in two places and drifting apart.

**Terminated requests are what make this workable.** `*8#` and `*82489493#` are
unambiguously different, so page numbers need only be distinct, not prefix-free.
Fields may therefore vary in width and stay short. A URL router cannot do this;
a viewdata one can, because the reader presses a terminator.

Two rules keep matching predictable, and both are enforced rather than
documented:

- **Most literal wins.** Candidates are tried by how many characters of the
  pattern are fixed digits, most first, so `90` beats `9{n:int}` however they
  were registered. A table whose meaning changed when someone reordered it would
  be no use. Ties keep registration order, `sort` being stable.
- **Fields must be separable.** A page number has no separators, so all but the
  last field running together must have a width known in advance. Two bare `int`
  fields adjacent are refused at registration, not matched arbitrarily.

**Converters** are `(field_pattern, width, parse, format)`. `parse` may raise
`ValueError` to reject digits the pattern could not — the 31st of February
passes any regex worth writing — in which case matching moves on to the next
candidate rather than failing. `format` output is re-checked against the field's
own pattern, so `address_for` refuses to build an address that names nothing.

Built in: `int` (variable width, leading zero refused so one page cannot have
two numbers), `int(n)` (exactly *n* digits, zero-padded — the leading-zero rule
inverts, because with the width settled the padding is what guarantees one
spelling), and `date` (eight digits, `YYYYMMDD`). Applications register their
own, optionally parameterised.

**Aliases** map keywords to addresses: `*MAIN#` for `*1#`. Prestel was almost
entirely numeric, but other viewdata services took keywords and there is no
reason to be bound by Prestel's database conventions. Keywords must be ASCII
alphanumeric, because the command parser accumulates nothing else, and may not
be all digits, because digits name themselves.

## The application seam

```python
class Application(ABC):
    async def respond(self, request: PageRequest) -> Page | None: ...
    @property
    def home(self) -> PageAddress: ...
    def resolve(self, target: str) -> PageAddress: ...
    async def not_found(self, target: str) -> Page: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

A base class rather than a `Protocol`, because the useful part is the defaults:
resolving digits, saying so when a page is not here, and doing nothing on
startup. Only `respond` must be written. `Sextile` is the routing implementation
and is what nearly every service will subclass or instantiate.

**`respond` returns `None` rather than a notice** when there is no such page.
The two are shown differently and the session needs to tell them apart: a page
that exists is somewhere the reader has *gone*, and enters the history; a page
that does not is something *said* to a reader who has not moved. This was
discovered by writing the session, not designed in advance.

**Lifespan** is `startup`/`shutdown`, called once each by whatever is running
the application. The server does not call them: a server that opened an
application's database would be a server with an opinion about what an
application is. `sextile.cli.run_service` does it.

**Mounting** hands every address beginning with a prefix to another application,
and gives it the address **unchanged**. That is not what a web framework does
and cannot be here: the application draws the page number into the frame itself,
so a number stripped of its prefix would be drawn as one the reader could not
key back. The prefix decides *who* answers and nothing more. A mount at `""`
takes everything not answered locally, which is how a service that is one
application rather than several is assembled.

## Pages and frames

```python
Page(frames: tuple[PageFrame, ...], hang_up: bool = False)
PageFrame(frame: Frame, choices: Mapping[str, PageAddress], moves: frozenset[str])
```

**Choices belong to the frame, not the page**, because frame b of a listing
offers a different nine destinations from frame a. The session consults the
showing frame and nothing else to answer a keypress. That is the entire reason
this type exists rather than a handler returning bare frames.

Choices are keyed by **character**, not digit, so a page can offer `D` for next
or `R` for reply without the type changing.

`moves` are kept apart from `choices` because they name no destination: they
step between frames of the page already showing.

**A page does not carry its own address.** What was asked for is the session's,
and a page that named itself as well would be one more thing that could
disagree.

**`hang_up` lets a page end the call.** The framework has no notion of a logoff
page and should not acquire one: which number means goodbye is the application's
affair.

`Page.destinations` is the run of pages a menu offered, across all frames, in
order — digits only and never `0`, since the way back is on every page and
counting it would make "next" mean something other than what the menu appeared
to offer. This is the sequence the horizontal keys walk.

## The session

`Session` holds the address, the page, the frame index, a history of
(address, frame) places bounded at 32, the sequence the reader is walking, and
the caller's state mapping.

The first page is built by `greeting()` rather than by the constructor, because
an application answers when asked and asking has to be awaited.

**Commands** (`session/commands.py`) recognise **syntax only**. Whether `MAIN`
or `82489493` names anything is the application's business, and whether `D` does
anything is the showing frame's. That is what keeps viewdata's numeric keypad
from being baked in.

```
*<payload><term>   go somewhere        DELETE   rub out; over the star, cancel
*<term>            the next frame      *        cancel a request being typed
*0<term>           back                **       cancel and begin again
*00<term>          this frame again    <key>    select
*09<term>          build it afresh
```

`*00` and `*09` differ in exactly one way: the first sends what is in hand, the
second asks the application again. That is the difference a reader wants when
the board has moved on since they arrived.

`**` is not a special case. A star while typing cancels, so `**` is cancel
followed by begin — which leaves an empty buffer, exactly what Prestel's `**`
did, without the parser knowing the sequence exists.

Three bytes terminate a request: `0x5F` (what Prestel's RETURN transmits,
measured), `0x23` (`#` from an ordinary terminal) and `0x0D`. Accepting all
three costs nothing and means the service can be driven equally from a BBC Micro
and from `nc`. A line feed after a carriage return is swallowed as the other
half of one terminator — it has to be told apart from a bare `0x0A`, which is
the BBC's cursor-down key.

**Ringing off is a page, both ways round.** A service that says goodbye does so
on a page like any other, with `hang_up` set. The involuntary parting has one
too — `Application.timed_out()`, overridable with `@app.on_timed_out` — because
no page number reaches it and something has to ask. Both are whole frames: a
line of text written over whatever was showing is hard to pick out from the
frame it lands on, which is what the first version of this did.

**And the terminal is handed back usable.** Every frame begins by hiding the
cursor, but once the line has gone the reader is talking to their modem again —
`+++`, `ATDT` — and a hidden cursor under a full screen of somebody else's frame
gives them nothing to type at. So the last bytes down the line put the cursor
two rows below the last thing said and turn it on. A parting page should
therefore leave its lower rows blank, and should offer no keys: one saying `0`
for the index would be a key that does nothing, on a page there is no coming
back from.

**Idle callers are warned, then released.** A single-line board held open by
someone who walked away locks everyone else out, so a caller who says nothing
for `--idle-timeout` seconds (fifteen minutes by default) is shown the parting
page above and disconnected. `--idle-timeout 0` holds the line indefinitely, which is right
for a dedicated terminal and wrong for a service anyone can dial. There is no
session timeout distinct from this one: the session lives exactly as long as the
socket, so releasing the line *is* ending the session.

Half way through that silence — `--warn-after` — the footer becomes a bar that
drains, reading `Press a key`, turning red for the last quarter. This is **the
one thing the service says unprompted**, and it is why `_converse` races the
read against a clock rather than merely giving it a deadline.

The bar is **modal**: the first command the reader gives dismisses it and does
nothing else. That is what makes "press a key" honest — a key that both woke the
line and selected from a menu could not be pressed safely by someone who only
wanted to stay connected.

Two details that are less obvious than they look. What is suppressed is the
first *command*, not the first byte: dropping the first byte of a `*8#` that
arrived in one packet would leave `8#` to be read as a selection and a page
turn, where dropping the request entire merely means keying it again. And a
bare `*` produces no command at all, so a reader who wakes the line by starting
a request can carry on typing it.

**Three things want the footer row**: the page's own prompt, a request being
typed, and the bar. The bar wins while it is up, and whichever of the other two
belongs there is put back when it goes.

That includes covering a part-keyed request. Nothing is lost by it — what was
keyed lives in the parser, not on the screen — and the alternative, leaving a
reader unwarned because they had begun typing and then cutting them off
mid-request, is the rudest thing the service could do.

Nothing is swallowed in that case, either. On a page the first key is eaten
because it would otherwise navigate; while a request is being typed no key
navigates — digits accumulate, `*` cancels, DELETE rubs out — so every key goes
on meaning what it always means and the reader picks up where they left off. The
command line is then redrawn in full rather than a byte at a time, since what is
on the row is a bar and not what was displayed before.

It costs one row and never a frame: 45 bytes, a third of a second at 1200 baud,
and only when a cell of the bar actually changes — twenty-five cells over
several minutes, so about twice a minute. Sending only the changed cell would
save almost nothing, because there is no absolute cursor addressing on the wire
and reaching column *c* of the footer row costs `2 + c` bytes of `HOME`, `UP`
and `RIGHT`. Blanking the right-hand end of a full bar is 42 bytes against the
row's 45.

**Sequences.** When a reader steps into a page from a menu, the session
remembers the menu's `destinations` and where in them they are, and passes the
neighbours to the handler as `request.arrival`. Walking on with `D` keeps the
sequence; leaving for an unrelated page drops it. The handler only decides
whether to offer what it was told of.

## The wire

Everything in this section was **measured against real Commstar under Beebium**,
not taken from documentation. [viewdata-encoding.md](viewdata-encoding.md)
separates what was verified from what was inferred; the scripts are in
`docs/spikes/`.

- **Attributes travel escaped**: `ESC` then the code plus `0x40`. The SAA5050's
  own `0x80`–`0x9F` codes simply vanish, Prestel mode running the line at 7E1
  with no eighth bit to carry them.
- **Two namespaces share the C0 range.** A bare `0x0C` clears the screen; `ESC
  0x4C` selects normal height. Confusing them produces a display wrong in ways
  that look like transport corruption.
- **A frame is exactly 24 × 40**, and the bottom-right cell wraps to the
  top-left rather than scrolling. Hence `Frame` is a fixed grid rather than a
  stream of writes: a serialiser one cell over would overwrite the frame it had
  just drawn.
- **An attribute occupies a character cell.** A row that changes colour twice
  has thirty-eight columns for text. `Canvas` does that arithmetic so nothing
  above it has to — and it is why colour could not have been deferred, since the
  layout engine would have had to be rewritten around it.
- **Attributes reset at the start of every row**, so rows are written
  independently and white text needs no attribute at all. Read from Beebium's
  `Saa5050::start_of_line()` rather than guessed.

[rendering.md](rendering.md) follows one document from blocks to bytes;
[navigation.md](navigation.md) follows one keypress to a reply.

## Economy

At 1200 baud a full 960-cell frame takes about eight seconds, which is enough to
be worth engineering against.

**Trailing blanks are not sent.** The frame clears the screen first, so a space
at the end of a row overwrites nothing; `CR LF` walks the cursor in two bytes
rather than forty, and after the last row with anything on it nothing is sent at
all. Real pages lose between a third and three quarters of their bytes. A row
filled to all forty columns gets no terminator, since it wraps by itself and a
terminator would skip the row beneath.

**The command line changes a byte at a time.** Commstar does not echo a page
request, so the footer row becomes a command line while one is being typed.
Repainting forty cells per keystroke flickers visibly once the cursor is on, so
a typed character costs one byte and a rub-out three, the cursor being left
exactly where the next character goes.

**The footer sheds gracefully.** Forty cells is not many and the longest prompt
fills the row exactly, so the next key added will not fit. Each item carries a
priority; the renderer drops labels first, from the least important upward, then
whole items — the key last, because the key is what the reader presses and the
label only teaches it. `0 menu` outlasts everything: a reader who cannot read
the screen still needs to leave it.

## Testing

The awkward parts are nearly all pure functions over values — transliteration,
routing, wrapping, layout, command parsing — and the two impure edges, the
socket and any application's I/O, sit behind narrow interfaces.

The framework's own tests drive **a made-up service** (`tests/exemplar.py`): a
menu, some items, a notice and a way out, about nothing in particular. That is
deliberate. If the session or the server needed to know it was serving a forum,
that substitution would not be possible, and the framework would not be one.

## What is deliberately absent

- **No menu builder.** Nine choices to a frame with the way back on `0` is a
  viewdata convention rather than any one service's, and it belongs here
  eventually — but both current applications write their own, and with two
  examples the shared shape is a guess rather than evidence.
- **No transport knowledge.** A plain TCP server. tcpser is already the ip232
  endpoint an emulator connects to, so a service is dialled exactly as any other
  viewdata board is. Speaking ip232 or a real serial port directly would be a new
  module beside `server.py`, not a change to it.
- **No authentication.** The session carries a state mapping so that a service
  can build one; the framework has no opinion about how.
- **No differential frame update.** The cursor positioning it needs is measured
  and works, but trimming already took most of what was available.
