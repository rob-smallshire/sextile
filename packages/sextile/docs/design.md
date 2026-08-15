# Sextile, as built

What is here, why each piece exists, and which decisions are load-bearing. For
how to *use* it, see [writing-an-application.md](writing-an-application.md).

Sextile is a Viewdata application server. It owns the connection, the session,
the routing and the bytes; an application owns the pages. The dividing line is
`Sextile.respond`, and the framework has no vocabulary for what a service
might be about.

## The shape of the thing

```
   viewdata/   charset, controls, encoding, frame       a screen
            |  canvas, wrapping, typesetting            putting things on one
            |  footer, command_line                     its furniture
            |  repaint                                  redrawing part of one
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
   forms       Form, TypeAhead, FieldSet                  a page typed into
            |
   application Sextile, PageRequest                     the seam
            |  PageRoute, Middleware, Lifespan           what a service is made of
            |  middleware  log_pages                     what wraps every page
            |
   layout      PageLayout, parts, furniture             a page as its pieces
            |  formatting  Menu, Listing, Prose         a sequence as a part
            |
   builtin/    contents, names, history                 pages the framework
            |  guidance, readership                     builds from what it knows
            |  handlers                                  the routes that name them
            |
   keys     |  the four movements
            v
   session/    commands, session                        one caller's conversation
            |
            v
   server      asyncio TCP                              answering calls
                                                        cli, __main__ drive it
```

Dependencies point downward, and there is one third-party dependency:
**`anyascii`**, for reducing arbitrary Unicode to letters the G0 set can draw.

This is not a job to do by hand. Romanising the world's writing systems is a
large, specialised subject, and any table written out here would be wrong about
somebody's alphabet: an earlier hand-written one omitted Đ and Ħ, so Đakovo went
out as `?akovo`. Nor are these accented Latin letters: ø, æ, å, þ and ð are
letters in their own right, with their own places in their own alphabets, which
is why Unicode does not decompose them and why each had to be listed by hand.

What is *not* delegated is the part no library can supply: which ASCII
characters the G0 set lacks. There are ten, and `anyascii`'s own output passes
through that table too. One of its outputs is overridden: `anyascii` renders an
emoji as `:tada:`, which suits a medium with room to spare but costs twenty
cells of a forty-cell row here.

## The lifecycle, which is the whole design

A Viewdata terminal is a display and nothing more. It holds the frame on screen
and nothing besides: not the page it came from, not the menu that led there, not
who is logged in. All of that is held at the server, for as long as the line is
up.

This is the opposite of the web, where the client carries a cookie and the
server may forget. It is why the shapes here differ from a web framework's in
three ways:

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
as the original Stardot-shaped code was. Strings won because the page number is
the one name everyone shares: the reader keying it, the terminal displaying it,
the application answering it, and anyone who writes it down. History, the back
key and linking between services all become ordinary operations on a value that
carries nothing about what it names.

No length limit is imposed: page numbers were measured to have no practical
limit on Commstar. A request is bounded instead by the command parser's input
limit (`ENTRY_LIMIT`, 32 characters).

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
class Sextile:
    async def respond(self, request: PageRequest) -> Page | None: ...
    async def ask(self, target: str | PageAddress, ...) -> Page | None: ...
    @property
    def home(self) -> PageAddress: ...
    @property
    def service(self) -> Mapping[str, object]: ...
    def resolve(self, target: str) -> PageAddress: ...
    async def not_found(self, target: str) -> Page: ...
    async def startup(self) -> None: ...
    async def shutdown(self) -> None: ...
```

`Sextile` is the one application class. `respond` routes a page number to a
handler; a service supplies the routes, the keywords and the lifespan, and
overrides the notices through `@app.on_not_found`, `@app.on_failed` and
`@app.on_timed_out` where it wants its own. Resolving digits, saying so when a
page is not here, and doing nothing on startup are the defaults it comes with.

**`respond` returns `None` rather than a notice** when there is no such page.
The two are shown differently, and the session distinguishes them: a page that
exists is somewhere the reader has *gone*, and enters the history; a page that
does not is something *said* to a reader who has not moved. This distinction
emerged from writing the session, not from a plan.

**Lifespan is one async context manager**, given to the constructor. It writes
what the service holds into `app.state` under `StateKey` keys and yields
nothing; a page reads it back as `request.state[KEY]`. Starlette's shape,
adopted for Starlette's reason: setup and teardown written as two handlers must
be kept in step by hand and must store whatever they open where both can reach
it, whereas two halves of one function cannot drift and the resource opened is
an ordinary local held across the `yield`. Starlette deprecated its own
`on_startup`/`on_shutdown` for this; Sextile had them for about an hour.

`startup`/`shutdown` remain as the methods that enter and leave it, called once
each by whatever is running the application. The server does not call them: a
server that opened an application's database would encode an assumption about
what an application is. `sextile.cli.run_service` calls them instead.

**`Sextile.fetch`** assembles a request as a session would, with what the
service holds and the service itself, so that a test, a renderer or a tool need
not. Assembling it by hand at each call site is a step easily forgotten, and a
page reached without it fails in a way unrelated to what was under test.

**No mounting.** Mounting let an application answer a prefix of the numbering by
handing it to another application, the way a web framework assembles a large
service out of small ones. It is gone.

It had no user. Three services are built on this framework and not one of them
mounted anything; only the framework's own tests ever did. And it was not free:
the prefix could not be stripped — a service draws its page number onto
the frame, so a number with its prefix removed would be drawn as one the reader
could not key back — which meant the numbering had to be *merged and disjoint*
rather than nested. Everything that reports across a service then had to see
through the seam: routing, keywords, the contents, `label_for`. A mounted
service had to be handed its own state rather than its host's. And a `history`
page inside a mount could still only name half of where a reader had been,
because a history is about a call and a call crosses the whole namespace.

That is a great deal of machinery for structural scalability no service here
needs. A viewdata service is small and self-contained: forty columns, a few
dozen pages, one archive. The cost was not in the feature but in everything the
feature obliged the rest of the framework to account for.



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

**A page does not carry its own address.** What was asked for is already held by
the session, and a page that named itself as well would be one more thing that
could disagree.

**`hang_up` lets a page end the call.** The framework has no notion of a logoff
page and should not acquire one: which number means goodbye is the application's
affair.

**A page is a value, and a service is a list of them.** `PageRoute` carries the
pattern, the handler, the title, the detail and any keywords, and
`Sextile(pages=[...])` is what a service is made of.

That is not merely tidier. **It makes registration order unobservable**, which
is the root of four separate defects this framework had: a converter could not
be registered in time for a class-declared pattern that used one, because
`self.add_converter` needs a router that `super().__init__` creates and immediately
uses; a module-level application could not open anything, could not resolve a
word of its own, and could not say a page's keywords beside it. Each was
registration order showing through. Given as data, the converters, the pages,
the middleware and the lifespan all arrive in one call and there is no *before*.

A decorator remains for the service that would rather declare a page beside the
handler than in a list. `@app.page(...)` registers it on the application
itself; `@router.page(...)` collects it on a `PageRouter`, for handlers in a
module of their own, spread into the service as `Sextile(pages=[*router, ...])`.
Both build the same `PageRoute` through one shared decorator, and every route
reaches the service through `add_page`, so the two forms cannot diverge.

The words are what the page is called wherever it is listed rather than
shown — in a menu, in the history, in the contents. Saying them once is the
point: a service that names each page in its menu, again wherever one is
listed, and again in its own guide has three copies which do not stay in step,
and that is exactly what Stardot had.

`Sextile.title_for` and `Sextile.label_for` read them, `Sextile.routes()`
lists them, and `Sextile.route(name)` fetches one. **A page given no title is not
advertised** — which is how a title frame or a logoff page stays off the
contents without a flag of its own.

**A contents page comes with the framework, unregistered**, built from those
registrations. Its point is the pages whose numbers carry a field:

```
*5#             By user
*52<user-id>#   One user
```

Nobody can list every user on a screen; everybody holding a user number can be
told where to put it, and only the framework knows the patterns
well enough to say. The list is ordered by number rather than by declaration,
which puts a namespace root next to its members — `5` then `52<user-id>` —
because sorting digits as text is what a scheme whose first digit names a
namespace already means. `Route.keyed` renders one for reading — the converter is
left out, since what a field accepts is the router's business.

(The hyphen in `<user-id>` is the character set, not a typo: G0 has no
underscore — 0x5F is `#` — so transliteration lands on a hyphen, which reads
better anyway.)

**`home` and `index` are different questions.** `home` is where a caller
arrives; `index` is where `0` goes. The same page for most services, and not for
one that opens on a title frame — arrived at once, and never to be sent back to.
`index` defaults to `home`, so a service without a title frame need not know the
distinction exists.

**A page of keywords comes with the framework too**, generated from the aliases:
`Sextile.names`, mapped in the same way. It exists because a service that
offers keywords has to say so somewhere, and the somewhere was a hard-coded list
in Stardot's help page — a list that goes stale the first time a keyword is
added. Words are listed alphabetically, since a reader consulting it is looking
one up rather than browsing, and several words for one page each get a line: the
reader has one of them in mind and wants to find it, not to learn it has
synonyms.

Note what the three built-in pages have in common. Each lists something the
framework already knows — where a caller has been, what patterns are registered,
what words are aliased — so none of them can drift from the service they
describe. A page that has to be kept in step by hand is a page that will not be.

**A history page comes with the framework, unregistered.** The session already
keeps a history so that `*0#` can retrace it one page at a time; showing the
whole of it turns a stack into a map. `Sextile.history` is a handler a
service maps into its own numbering — or does not offer at all:

```python
self.page("92", name="history")(self.history)
self.add_keyword("HISTORY", self.address_for("history"))
```

It can live in the framework because there is nothing service-specific about it.
What it lists are addresses, and what it *calls* them comes from
`Sextile.label_for`, whose default reads the route's own title and fields —
"One post 489493" — so the labels come out in the application's vocabulary
without the framework knowing what a service is about. A route whose number
carries a field says better words with `PageRoute(..., label=...)`, and
`Sextile.match(address)` is the numbering read backwards for anything else that
needs it.

Two details that took a live walk to get right. Keys run 1–9 on *every* frame,
as any other viewdata menu's do, because an entry shown but not selectable is
worse than one not shown; how far back each is goes in the detail line, since
the digit only counts steps on the first frame. And `request.history` is every
page visited *before this request*, which means it ends with the page being left
— the definition that makes key 1 agree with `*0#`. Anything else leaves the page
off by one against the key it exists to save.

**`Page.follows` says where `#` leads once the frames run out.** Prestel's `#`
advanced through a route as well as through the frames of one long page, and
some pages are nothing but an invitation to press it — a title frame, or the
last page of a guide. Without it they are dead ends under the one key a viewdata
reader tries first.

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

**A service has a name, and the framework has none to lend it.** `Sextile(name=
"Stardot")`, read back as `Sextile.name`, is used in the few things the
framework says on a service's behalf. It defaults to empty and no default is
invented: a page thanking a reader for calling *Sextile* would name the
machinery rather than the service they called. For the same reason the `Header`
furniture draws no fallback title — a framework writing its own name across the
top of somebody else's service would repeat the mistake.

**Ringing off is a page, both ways round.** A service that says goodbye does so
on a page like any other, with `hang_up` set. The involuntary parting has one
too — `Sextile.timed_out(request, frame_index)`, overridable with
`@app.on_timed_out`.

That handler is given the `PageRequest` for the page the caller was on — which
carries the address, the history and the session, the same as any handler's —
and a `frame_index` beside it that says which frame, there being no frame on a
request to read off. The terminal keeps none of it, so the one useful thing to
hand over is where they had got to: "You were reading *82489493#" is what lets
somebody dial back in and pick up. Both are whole frames: a line of text written
over whatever was showing is hard to pick out from the frame it lands on, which
is what the first version of this did.

**And the terminal is handed back usable.** Every frame begins by hiding the
cursor, but once the line has gone the reader is talking to their modem again —
`+++`, `ATDT` — and a hidden cursor under a full screen of somebody else's frame
gives them nothing to type at. So the last bytes down the line put the cursor
two rows below the last thing said and turn it on. A parting page should
therefore leave its lower rows blank, and should offer no keys: one saying `0`
for the index would be a key that does nothing, on a page there is no coming
back from.

**A page that will not build costs its page, not the call.** A handler raising
used to end the caller's session, which on a service where a session is a
telephone call means dialling back in and finding your way to where you were —
minutes of a slow line for a fault that was ours. The session catches it, logs
it with its traceback, and shows `Sextile.failed` without moving the reader.

**That is a page of its own** — `@app.on_failed` to override — and deliberately
not the not-found notice. One says the reader asked for something that is not
here; the other says the service could not build something that is. Saying the
first when it is the second sends them away thinking they mistyped, and hides
the fault from whoever could fix it. It names the number so a reader can report
which page it was, and says whose fault it is, because somebody on a 1200 baud
line will otherwise assume they did it.

Logged rather than swallowed: a service that quietly shows a notice for a page
it has but could not draw is a service whose bugs never get found.

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

**Three things compete for the footer row**: the page's own prompt, a request
being typed, and the bar. The bar wins while it is up, and whichever of the
other two belongs there is restored when it goes.

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
neighbours to the handler as `request.neighbours`. Walking on with `D` keeps the
sequence; leaving for an unrelated page drops it. The handler only decides
whether to offer what it was given.

## Drawing

`Canvas` writes a row and accounts for what an attribute costs.
`viewdata/drawing.py` is the layer above: the small operations most pages turn
out to need, each written three or four times before it was put there —
`fitted`, `centred`, `centred_double`, `rule`, `bar`.

Free functions rather than methods, so that a service can write its own beside
them and reach for either without minding which is which. They take a canvas
and a row, and none of them references a page.

`fitted` measures **cells, not characters**, and has no ellipsis: on forty
columns three dots saying "there was more" cost more than the three characters
they would hide.

Mixing text and blocks on one row, placing things at coordinates, and drawing
pictures are all in [graphics.md](graphics.md) — the block grid, the compositor
that works out where the attributes go, and the plan for large lettering.

## Laying out a page

Five places had grown their own version of the same six steps: take a list,
divide it between frames, draw the furniture, write the rows, wire up the keys,
return a `Page`. About 275 lines, and they had drifted: two disagreed about how
much room a lead-in costs, and one advertised a `1-9 select` on a frame with
nothing to select.

That became `Template`, which did the six steps and had a subclass say how tall
an entry was. It did two jobs, and only one of them was available on its own:
the furniture round a frame came with being a sequence part of a homogeneous
sequence, so a page whose content was a grid, a form or a masthead had to draw
its own furniture. Six pages did.

`PageLayout` is the two jobs separated. A page is furniture round the edge of
each frame and a list of parts down the middle, and the parts need not be
sequences. [layout.md](layout.md) is the reference. In brief:

**Filled, then furnished.** The prompt of a frame names `S page down` only
where there is a frame to page down to, so it cannot be drawn until the count
is known. The content occupies rows 2 to 21 and the furniture rows 0, 1, 22 and
23, and they never touch — so the parts are drawn first, onto as many canvases
as they need, and the furniture goes on afterwards when the count is settled.

**A part is drawn once, on every frame, or across as many as it takes**, and a
`FrameBreak` divides a page at a chosen point rather than where the rows run out.
That is what the guide needed: its two frames are two lists, split by what a
reader is doing.

**Content parts claim and furniture reports.** A part says which keys lead
where and what the prompt should call them; a furnishing is handed the
assembled list and draws it. That is the same division as the two passes, seen
from the other side.

**The frame geometry is derived.** `content_rows(furniture)` returns what the
furniture leaves, so a page with none has the whole frame and a two-row prompt
costs a content row. `CONTENT_FIRST_ROW` and `CONTENT_ROWS` were constants and
are not needed.

**Parts concatenate; they do not compete.** Where several flowing parts follow
one another, each takes the rows left to it and the next begins where it ended,
so there is no rule about how many parts may flow. Letting streams contend for a
frame's rows would need a policy to arbitrate between them; a viewdata frame is
twenty rows of forty cells with no floats and no columns, so concatenation
answers every case and no policy is needed.

The layout only stacks parts down the frame. Placing things side by side or at
coordinates within a frame is `viewdata/composition.py`'s job.

The shapes that come with the framework are in `formatting.py`:

| | |
|---|---|
| `Menu` | nine to a frame, numbered, a line of detail beneath each |
| `Listing` | two columns, nothing numbered |
| `Figures` | a label and a right-aligned figure |
| `Lines` | lines drawn as given |
| `Prose` | running text, wrapped |

A service wanting another subclasses `SequencePart` and says how tall an entry is
and how to draw one. The base is generic in what it divides: most of them
divide `Entry` values, `Prose` divides rendered rows.

**A shape that is not written along a row overrides `draw_entry` instead.**
`draw` and `draw_detail` are handed a `RowWriter`, which walks one row from
left to right — the right shape for text and the wrong one for a mosaic
picture, which is placed by cell and may be three rows tall. The weather
service's page of weather symbols is what motivated it.

**A form is a part.** It occupies a row range, draws itself, contributes the
keys its suggestions answer, and says what the prompt should call them. It is
the one part that is not a description — it holds what has been typed — so a
layout carrying one is built for the request it answers rather than kept.

**`charting.py`** turns a run of numbers into a bitmap for the block grid:
`curve` for a line and `bars` for columns standing on the floor. Values arrive
as fractions of the height, never as data — deciding what the top and bottom of
a chart mean is the caller's, and it is the whole of the interesting part
(whether a scale starts at zero, whether it is fixed so two frames compare,
where a threshold falls). A charting module that chose those would be deciding
something only the caller can.

A value sits at the middle of its share of the width, so a chart lines up with
the labels or pictures above it, and the line runs level out to the edges rather
than stopping short. A missing value breaks the line: joining the ends would
draw a claim about an hour there is nothing for.

**One block to a column, and no more.** Filling the blocks between two heights
joins a line four ways and makes a staircase of solid treads; leaving them out
joins it eight ways, corner to corner, which is thinner and reads as a line
rather than as a wall — the same fact the compass's arrows are drawn on. It
costs nothing because the horizontal resolution is the generous one: eight
blocks between one value and the next against nine of height in all, so a line
climbing from floor to ceiling in a single step still rises about a block a
column.

**A page with a field gets its cursor back when a request is cancelled.**
Putting the footer back begins by hiding the cursor — something is about to be
drawn over the row it was on — and nothing turned it on again, so a reader who
opened a `*` request over a search field and thought better of it was left in a
field with no cursor in it. The same two lines cover the idle warning, which
takes the footer row the same way.

**A keystroke that draws nothing still moves the cursor.** A space is a blank
cell written over a blank cell, so the frame comes out identical and the
repaint has no rows to send — and sending nothing leaves the cursor a cell
behind where the form expects it, with every keystroke after it landing one
cell out and every rub-out taking the wrong one. Where nothing moved but the
caret did, the caret alone is sent. Found by typing `ULAN BATOR` into the
weather service; pinned by a test that follows the bytes and works out where
they leave the cursor, rather than by one that looks at the screen.

**`thin_rule`** is the furniture's rule with a sixth of the ink — one block thick
instead of three, in the same separated mosaics and across the same cells. A bar
belongs where a page ends; between two things that are both content it reads as
a second frame beginning.

**`gap` puts blank rows *between* entries**, not after the last of them.
A shape several rows tall needs space around it or two entries read as one block;
charging that space to every entry wastes it at the foot of the frame, where the
furniture's rule already does the same job. It is worth a whole entry per frame
— the weather's day table fits five days where it fitted four.

**The arrow keys move.** A page names its keys in letters, because that is what
its footer and its compass say to a reader, and `with_arrows` offers the arrows
beside them — so the frame *offered* an arrow and nothing turned a pressed one
back into the letter it stood for. Every multi-frame page in the workspace
advertised the cursor keys and none of them moved. `keys.as_letter` does the
translating, in the one place a move is acted on.

**The compass leaves its sideways arm off where a service has no use for it.**
`A` and `D` step through the run of pages a menu offered, and *the framework
does not implement them*: a service wires them to `request.neighbours` -- Stardot
does — or it has no such thing. The weather has no such thing, and was drawing
two keys that do nothing on the one page a reader goes to to find out what the
keys do. `compass(..., items=False)` and `guide(..., show_item_keys=False)`. The up and
down arm is always drawn, frames being something every page has.

## What has been read

A log of page fetches, and the two questions every service asks of one: what
has been looked at lately, and what gets looked at most. Both are the same
shape everywhere, because **a page number is the framework's own vocabulary** —
so the log, the middleware that writes it and the pages that read it are here,
and what a service adds is only its numbering.

`Visits` is a protocol and `SqliteVisits` is one implementation of it, which is
the arrangement every impure edge in this framework has: narrow enough to fake
in a test, and a service that wants its log elsewhere writes forty lines rather
than going without the pages.

**The record is the address.** `321<geoname-id>` is what the reader keyed, what
the router parses back, and what `label_for` names — so there is nothing else to
store and nothing that can come to disagree with it. A prefix filter is then a
namespace filter, which is what a first digit already means: a weather service
asks for `321` and gets its forecasts.

**The caller is a token, not an address.** Counting readers means knowing how
many and nothing else. `record_visits` mints a random token the first time it
sees a session and keeps it in the session, so `count(distinct caller)` answers
the question and answers nothing about who. A service that keeps what it does
not need is a service that has to be trusted about it.

**A page that was not there is logged and not read back.** A count that quietly
omitted the ones nobody could reach would be the wrong count, and the numbers
readers key wrongly are worth knowing — but a number that answers nothing has
no business on a list of somewhere to go.

**Thirty days, and it is a setting.** The trim runs once a day rather than once
a page: a delete on every fetch is a write nobody asked for, and a day is short
enough that the file has a ceiling.

The middleware is made before the service's lifespan has opened anything, so it
takes the `StateKey` the log will be held under rather than the log —
`record_visits(VISITS)` reads `request.state.get(VISITS)` per page. A service
holding nothing under that key still gets its page: the reader is owed it, so
the visit goes unrecorded rather than the page going unsent.

`Sextile.lately_read` and `Sextile.most_read` build two of the three pages, as
menus rather than tables — every row is a page number, so every row is somewhere
to go. A list of what other people have been reading that you cannot follow is a
list that has been written at you.

`Sextile.who_has_called` builds the third: distinct callers over the last day,
week and thirty days. It is the only figure a service keeps about its readers,
and the page says on itself what it counts — a figure about readers that does
not say what it counts invites the worst guess. **A period longer than the log
is kept for reads low, and silently**, so the periods are the service's to pass;
the defaults end at thirty days because that is what the log keeps by default.

**The framework builds four pages, not three.** `history`, `contents`, `names`
— and now `guide`, which was Stardot's, written by hand, and much the better of
the two help pages the workspace had. They live in `sextile/builtin/` with the
readership pages, all five being the same kind of thing: a page built from what
the framework holds already, registered nowhere, mapped in by a service that
wants it. `sextile/handlers.py` is the other half of that — the handlers a
`PageRoute` can name, where these modules are what those handlers reach. A guide is mostly a description of the
framework: the digits, the way home, the syntax of a request, the key that
turns a page, the compass. A description that drifts from the thing it
describes is worse than none, so it is generated from what is actually
answered.

A service passes the rows only it can know — a search field answers letters, a
forecast answers `F` — as `moving` (which joins the first frame, under the
compass) and `asking` (the second). The row for `0` says "back to the main
menu" on a service whose first page is called one and "back to the main index"
on a service whose is called that, taken from the page's own title so the two
cannot disagree.

**A `Listing` carries a long second column on rather than cutting it.** Its
second column gets what is left after the first, so how much room it has depends
on the widest thing in the first: `*3#  Forecast by lat/lon position` fits, and
the same title beside `*321<geoname-id>#` does not. Cut, it reads as a fault
rather than as a shortage of room; carried on to a row with nothing in the first
column, it reads as what it is — which column a thing is in being what tells a
page number from a title that has run on. Two rows at most; a third means the
title should be rewritten. Both the contents page and the words page get it, and the
pagination counts the extra rows.

**A hint and a note are drawn in different colours.** Both were green, so the
service's answer to what had just been typed sat in a block of instructions and
read as more instruction. A hint is advice — the same words on every frame, read
once — where a note is a finding and the most interesting thing on the page:
green and cyan.

**A page may offer `Shortcut`s** — keys carried on every frame, over and above
the digits and the way home. A page's digits belong to its entries and change
from frame to frame; a shortcut does not, and it is for the way out that is not
the way home: a forecast going back to the search that found it, a post going
back to the board it is on. They are named in the prompt, so a page cannot
offer one silently.

**A lead-in may hold a `Block`** — a number of rows and a function to fill them
— for a part of it that is drawn rather than written: a strip of mosaics is
placed by cell and is several rows tall, which is the wrong shape for a line of
text. The pagination counts a block's rows like any other lead-in's, so a
lead-in that takes the whole of the first frame simply leaves no entries on it
and starts them on the second, instead of overrunning the rule. Headings are
drawn only on a frame that has entries to label.

**`wrap_within(text, cells=, rows=)`** puts text into a region that has a
height as well as a width. `wrap_text` takes the width a line may be and nothing
about how many lines there is room for, so every caller with a region to fill
did the same two things by hand: wrap, then take the first however-many lines
and hope.

It wraps and then cuts, with nothing cleverer in between, and that is a measured
result: a greedy fill was the obvious fallback for a region one line short, but
**balanced wrapping never costs a line** — twenty thousand random widths and
word lengths, no exception. It follows from the last line
being free. So text that does not fit is text the region was never going to
hold; size the region for the longest thing it can be handed.

**A preamble line may be `Span`s rather than a string**, where the colours carry
meaning rather than decoration — two clocks side by side, one UTC and one local,
told apart by colour because a label would cost four cells to repeat what the
row above said. The rows it costs are counted the same either way.

**`Prose` is the one that already had its machinery.** `wrap_text`,
`Canvas.paragraph`, the `Document` block model and `viewdata/typesetting.py` were all
there — nested quotations in cyan, listings in green, over-long words split
rather than dropped — and only two pages in the whole workspace used any of it.
Every notice wrote its own lines out pre-broken at forty columns, with empty
strings for the gaps, which has to be redone by hand whenever a word changes.
`Prose.of("...", "...")` reaches the machinery that was already there, and the
wrapped output is identical to what the hand-broken literals produced.

**What a `SequencePart` consumes is the `Entry` protocol** — `text`, `detail`, and a
`destination` that may be `None` — so a service with a richer notion of a menu
entry passes that instead of copying into somebody else's dataclass. `MenuItem`
is there for services with no such notion, and `MenuItem.for_page(app, name)`
builds one from what a page said about itself when it was registered.

Two things the extraction settled that five copies could not. **The preamble
costs only the frame it is on**, where the hand-written versions spent its rows
on every frame. And **the prompt is built from the same description as the
choices**, so a frame cannot name a key it does not answer.

## Forms

A page that answers a keypress by **changing what is on the screen without
going anywhere** — the one thing a viewdata page could not previously do, and
the reason Prestel's response frames were a mechanism bolted on beside the
numbering.

Here it needed very little, because **type-ahead is a menu whose choices change
as you type** and `PageFrame.choices` already meant "what the digits do on this
frame". A form only makes that answer differently between keystrokes. It owns
some rows, says which keys are typing rather than navigating, redraws its rows
when its value changes, and says where its digits lead. The session consults the
choices *first*, so a digit is always a selection and never a character, and
then treats what it finds exactly as a digit on a menu — history, sequences and
the back key keep working with nothing added. `*` is untouched, so a reader is
never trapped in a field.

Two shapes come with the framework:

| | |
|---|---|
| `TypeAhead` | a field, and the best few matches beneath it, each on a digit |
| `FieldSet` | several fields, one live, moved between with TAB and the arrows |

**The frame is redrawn in place**, so what the terminal shows and what the
session holds stay the same thing and `*00#` sends the frame with the reader's
typing on it. Only the form's own rows are compared, so a form cannot disturb
the page around it however wrong it is about itself.

### What the wire allows, which decided the design

Measured on real Commstar rather than reasoned out; the record is
`docs/spikes/spike_suggestion_block.py` and `spike_search_page.py`.

**A row written to all forty columns must not be followed by a cursor down.** It
wraps of its own accord, so the walk to the next row of a block moves down a
second one and a three-row block lands on rows 4, 6 and 8. Every row of a
multi-row repaint is therefore sent trimmed to its last non-blank cell, which
fixes the walk and costs a third fewer bytes; a row that genuinely fills the
line is accounted for rather than refused. `viewdata/repaint.py` carries this.

**Three suggestions, not nine.** Nine rows of name, country and population is
2.9 seconds a keystroke at 1200 baud, where a reader types two characters a
second. Three is one second, and the common keystroke — typing on into a list
that has settled — is **one byte**, because a keypress that changes nothing but
the cell under the cursor sends that character and moves nothing: the cursor is
already where it goes. The command line has done that since it was written; a
field is the same problem.

### What the keypad allows

Narrower than it looks, and it settled the interaction rather than taste.

**Digits are data or they are choices, never both.** On a suggestion list they
choose, so a place whose name holds a digit is found by the letters around it.
On a coordinate form they are data, so `0` cannot be the way out — the one page
in this workspace that cannot honour "0 returns to the index", and its footer
says `*1#` rather than offering a key that would eat a coordinate.

**DELETE reaches the frame.** It was dropped, and rightly: there was nothing a
page could do with it. A field can rub out a letter, and everything else ignores
it as it ignores any key it does not offer.

**TAB shares a byte with cursor right**, which is a gift: tabbing between fields
is the first thing a reader tries, and it arrives as `keys.RIGHT`.

**And the framework stopped translating arrows.** It turned the cursor keys into
WASD in the parser, before any page could see them — a fact about the hardware
made into an opinion about what pressing them should do, imposed on every
service at once. On a coordinate form it is wrong twice over: `W` is West and
`S` is South, so a reader reaching for the up arrow would silently type a letter
into a number. `keys.ARROW_FOR`, `with_arrows` and `with_arrow_choices` offer the
knowledge; a page decides what to do with it. `PageLayout` offers the arrows
for the frame keys, which mean the same on every page, and for a `Shortcut`
only where the page has said `with_arrow=True`.

## Middleware

A handler answers what one page says; **middleware answers what is true of every
page**. It is given the request and the rest of the chain, and may look, may
change what comes back, or may answer instead and never call it — which is what
lets a service build authentication without the framework acquiring an opinion
about how anybody logs in.

Starlette's shape, including the ordering: the first given is the outermost, so
a reader of the list sees a request entering at the top and leaving at the
bottom. The chain is built per request rather than once, which costs a closure
apiece and means an application that has already answered something can still
be added to.

One ships, and it exists because of the wire. At 1200 baud a frame takes eight
seconds to reach the reader, so *"it felt slow"* cannot tell the wire from the
page — from the far end of a telephone line the two are indistinguishable.
`log_pages` names every page and times it. It logs at the level the **duration**
deserves rather than the outcome: a page that is not there is ordinary, and one
that took four seconds to decide it was not there is not.

Nothing else is offered. What a service should say about itself is not a
question a framework can answer; that it should say something is not in doubt.

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
  typesetting would have had to be rewritten around it.
- **Attributes reset at the start of every row**, so rows are written
  independently and white text needs no attribute at all. Read from Beebium's
  `Saa5050::start_of_line()` rather than guessed.
- **Double height consumes the row below, and needs the same text on it.** Read
  from the emulation and then seen on a real screen; not what a guess would say,
  since the lower row is drawn as the bottom halves only if it carries the
  attribute too. `Canvas.double_height` writes both rows.

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
fills the row exactly, so the next key added will not fit. A prompt is composed
as items with priorities and each may offer a brief wording as well as a full
one; the renderer takes the fullest that fits, giving up long wordings before
aliases, aliases before the word beside the way out, and last words before the
keys themselves — the key last, because the key is what the reader presses and
the label only teaches it. `0` outlasts everything: a reader who cannot read
the screen still needs to leave it. See
[navigation.md](navigation.md#the-footer).

## Testing

The awkward parts are nearly all pure functions over values — transliteration,
routing, wrapping, typesetting, command parsing — and the two impure edges, the
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
- **No authentication.** The session carries a state mapping and middleware can
  refuse a page, so a service has what it needs to build one; the framework
  still has no opinion about how.
- **No differential frame update.** The cursor positioning it needs is measured
  and works, but trimming already took most of what was available.
