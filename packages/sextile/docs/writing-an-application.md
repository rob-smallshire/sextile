# Writing a Sextile application

A service is a set of numbered pages and the keys that lead between them.
Sextile owns everything else: the connection, the session, the routing, and the
bytes on the wire.

The worked example is
[`calendar-viewdata`](../../calendar-viewdata/), which is small, depends
on nothing but the standard library, and is meant to be read.

## The smallest thing that answers

```python
from sextile import Page, PageFrame, PageRequest, PageRoute, Sextile
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, draw_chrome

async def main(request: PageRequest) -> Page:
    canvas = Canvas()
    draw_chrome(canvas, title="MY SERVICE", page_number="1a", prompt="0 index")
    canvas.row(CONTENT_FIRST_ROW).text("Hello, 1981.")
    return Page(frames=(PageFrame(frame=canvas.frame),))

app = Sextile(pages=[PageRoute("1", main, name="main")])
```

**A page is a value and a service is a list of them.** Everything about a page
is on one line of that list — where it is in the numbering, what builds it,
what it is called where it is *listed* rather than shown, and the words that
reach it — so a page says what it is once, in one place.

That is also what makes the order things were registered in unobservable. The
converters a pattern needs, the pages themselves, what wraps them and what the
service holds all arrive in the same call, so there is no *before* and no
*after* for a service to get wrong.

`@app.page(...)` is the same thing said as a decoration, for a service small
enough that a list would be ceremony:

```python
app = Sextile()

@app.page("1", name="main")
async def main(request: PageRequest) -> Page:
    ...
```

It is defined in terms of the list, so the two cannot drift.

```sh
uv run sextile serve my_service:app
nc localhost 6850
```

A caller arrives on page 1 unless the application says otherwise —
`Sextile(home="8")` — and is released after fifteen minutes of silence, since a
single-line board held open by someone who walked away locks everyone else out.
Half way through that, the footer becomes a draining bar reading `Press a key`,
so that being disconnected is never a surprise; the first key dismisses it and
does nothing else. Both are the framework's, and every service gets them without
writing anything. `--idle-timeout` and `--warn-after` change the timings, and
`0` turns either off.

## Numbering

Patterns are literal digits and named fields.

```python
PageRoute("82{post_id:int}", post, name="post")
PageRoute("32{day:date}", day, name="day")     # 3220260802 is 2 August 2026
```

`int` takes one or more digits and refuses a leading zero, so a page cannot have
two numbers. `date` takes eight, as `YYYYMMDD`.

**`int(n)` takes exactly n digits**, zero-padded. That is what lets fields sit
next to one another, since a page number has no separators:

```python
PageRoute("32{year:int(4)}{month:int(2)}{day:int(2)}", iso, name="iso")

app.address_for("iso", year=2026, month=8, day=2)     # 3220260802
```

The leading-zero rule inverts here, for the same reason it exists. A
variable-width field refuses a leading zero because `0042` and `42` would be two
numbers for one page; a fixed-width field *requires* the padding, because with
the width settled there is again only one spelling of each value. So `708` is
month 8 and `78` is not a page.

An application that needs another field shape registers one, either fixed or
parameterised by whatever is written in the brackets:

```python
app = Sextile(
    converters={
        "pair": Converter(field_pattern="[0-9]{2}", width=2),
        "code": lambda width: Converter(...),          # for {x:code(3)}
    },
    pages=[PageRoute("7{n:pair}", counted, name="counted")],
)
```

Given to the constructor, because the router has to know a field shape before
it compiles a pattern that uses one. `app.converter(...)` adds one afterwards,
which is fine for a page declared afterwards too.

Two rules keep matching predictable. **Most literal wins**: `90` beats
`9{n:int}` however they were registered, because a table whose meaning changed
when someone tidied it would be no use. And **fields must be separable**: all
but the last field running together must have a fixed width, or nothing could
say where one ended and the next began. Give them widths, or put a literal digit
between them.

None of this needs prefix-free numbers. A viewdata request is terminated, so
`*8#` and `*82489493#` are unambiguously different and fields may vary in width.

**Build addresses, do not spell them.** Every route has a name, taken from the
handler unless given, and `address_for` reads the pattern backwards:

```python
choices = {"1": app.address_for("post", post_id=post.id)}
```

That is what stops a numbering scheme existing in two places and drifting.

**Keywords** cost nothing, and belong beside the page they reach:

```python
PageRoute("1", main, name="main", keywords=("MAIN", "INDEX"))
```

`app.alias("MAIN", app.address_for("main"))` does the same for a word that
names a page some other way.

## Menus and listings

Most pages are a list of things, so the framework builds those:

```python
from sextile.templates import Listing, Menu, MenuItem

Menu(
    title="BY CONTRIBUTOR",
    entries=[MenuItem(text=name, detail=f"{count} posts", destination=where) ...],
    home=self.index,
    preamble=["Everyone who has posted."],   # first frame only
    empty="NO POSTS held yet.",              # said instead of an empty frame
).build(request.address)
```

`Menu` numbers its entries 1–9 and deals them nine to a frame, each with a line
of detail beneath. `Listing` is the same mechanism for a reference page: twenty
to a frame, nothing selectable, the detail in a second column. Both draw the
chrome, build the prompt from what the frame actually offers, wire up `W`/`S`/`#`
and send `0` home.

**Entries are a protocol, not a type.** Anything with `text`, `detail` and
`destination` will do, so a service with its own richer entry — carrying the post,
the timestamp, whatever it needs — hands that over directly:

```python
@dataclass(frozen=True)
class Line:
    post: Post

    @property
    def text(self) -> str: return self.post.subject
    @property
    def detail(self) -> str: return self.post.author_name
    @property
    def destination(self) -> PageAddress: return app.address_for("post", post_id=...)
```

For running text, don't break your own lines:

```python
Prose.of(
    "A Viewdata service carrying posts from stardot.org.uk, for users of "
    "Acorn computers and emulators.",
    f"{held} posts held.",
    title="ABOUT STARDOT",
    home=self.index,
).build(request.address)
```

Each argument is a paragraph; the framework wraps them, spaces them, and pages
them. It also takes rendered rows rather than plain paragraphs, which is how a
notice gets a quotation or a code listing rendered exactly as a forum post's
would be:

```python
Prose(title="...", entries=rows_for(document), home=self.index)
```

For a shape none of the three has, subclass `RowTemplate` and say how tall an
entry is and how to draw its rows; the pagination, chrome and keys come with
it. A shape placed by cell rather than written along its rows — a mosaic
picture several rows tall — subclasses `Template` itself and writes
`draw_entry`, which gets the canvas and the row the entry starts on. Both are
dataclasses, so a subclass adding something an entry needs — a date to mark,
a column to size — declares a field rather than writing a constructor.

## Pages, frames and keys

A page is one or more frames, and **each frame says what its keys do while it is
showing** — because frame b of a listing offers a different nine choices from
frame a.

```python
PageFrame(
    frame=canvas.frame,
    choices={"0": app.address_for("main"), "1": somewhere},
    moves=frozenset({"S", "#"}),          # keys that move within this page
)
```

`choices` lead elsewhere; `moves` stay on this page and step between its frames.
Keys are characters, not digits, so a page may offer `D` for next or `R` for
reply without anything changing.

Two conventions worth keeping, because readers rely on them across services:

- **`0` returns to the index, from every frame.** It is the one key a reader who
  has lost their bearings can rely on.
- **A frame names only the keys that do something on it.** An offer that goes
  nowhere is worse than no offer, and on a service that answers slowly a reader
  cannot tell a dead key from a slow one. Build the prompt and the choices from
  the same description of what is available, or they will disagree.

### The prompt at the foot of a frame

A template writes its own. A frame built by hand composes one from items, and
does **not** write it as a string:

```python
from sextile.viewdata.footer import ROOM, FooterItem, Priority, movement, render_footer

items = [FooterItem("1", "month", Priority.PRIMARY)]
items += movement(choices, item="day")
items.append(FooterItem(HOME_KEY, "index", Priority.ESSENTIAL))
prompt = render_footer(items, ROOM)
```

`movement` gives the framework's words for `W`, `S`, `A` and `D` — *page up*,
*page down*, *previous day*, *next day* — taking the noun from you, since only
you know what your service is made of. Say it in full; the renderer decides how
much of it a given row can hold, and a page with cells to spare gets the whole
sentence.

Anything else the frame offers is a `FooterItem` of its own:

| | |
|---|---|
| `key` | what the reader presses |
| `label` | what it does, in words |
| `brief` | a shorter way of saying that, for a crowded row |
| `priority` | `ESSENTIAL` the way out, `PRIMARY` what the page is for, `SECONDARY` moving about, `REDUNDANT` an alias for a key already shown |

The order things are given up in is in
[navigation.md](navigation.md), with worked examples. The one rule worth
knowing here is that **priority decides what survives, not position** — so an
item can go anywhere in the list that reads well.

To end the call, say so on the page:

```python
return Page(frames=(...), hang_up=True)
```

There is a second parting the service does not choose — the idle caller who is
released — and it has a page of its own, told where they had got to:

```python
@app.on_timed_out
async def gone(parting: Parting) -> Page:
    ...   # parting.address, .frame_index, .history, .session
```

The terminal keeps nothing, so `parting.address` is worth showing: "You were
reading *82489493#" is what lets somebody dial back in and pick up. The default
page does this already, and names the service if it has a name:

```python
app = Sextile(name="Stardot")     # "Thank you for calling Stardot."
```

`name` is empty unless you say otherwise, and the framework will not invent one.

Both are the last thing a reader sees, so **draw them without a footer and leave
the lower rows blank**. A key offering the index would be a key that does
nothing, and the framework puts the cursor two rows below the last thing said
and turns it on, so that the reader has somewhere to type to their modem.

## Say what a page is where you write it

```python
PageRoute("5", contributors, name="contributors", title="By contributor",
          detail="browse by poster", keywords=("WHO", "USERS"))
```

The route takes the handler's own name unless given one.

The title and detail are what the page is called wherever it is *listed* rather
than shown — a menu offering it, a history naming it, the contents. Say them once
here and nothing downstream needs its own copy:

```python
app.page_info("contributors").title      # "By contributor"
app.describe(PageAddress("5"))           # "By contributor"
app.pages()                              # every page that has a title
```

**A page with no title is not advertised.** Giving one a title is how a service
says it may be listed, so a title frame or a logoff page stays off the contents
without a flag. Having no title and having no keywords are different things: a
logoff page can stay off the contents and still answer `*BYE#`.

A service whose handlers are methods may declare them beside those methods
instead, with the class-level `@page(...)`. They are collected when the
application is constructed, base classes first, in the order they are written.
It is the same registration by another road.

The same declaration works on module-level functions, gathered with
`routes_in`, so a service of ordinary functions keeps each route on the
function that builds the page rather than in a list that has to trail its
handlers:

```python
@page("5", title="By contributor", detail="browse by poster",
      keywords=("WHO", "USERS"))
async def contributors(request: PageRequest) -> Page:
    ...

app = Sextile(pages=routes_in(sys.modules[__name__]))
```

Decorate a function where it is defined, not where it is imported: the
declaration rides on the function object itself, so decorating a borrowed
handler would declare it for everyone who imports it. A route for somebody
else's handler — the framework's own pages, say — is one `PageRoute` line
beside the call:

```python
app = Sextile(pages=[
    *routes_in(pages_module),
    PageRoute("92", pages.history, title="Where you have been"),
])
```

## Say a page's name once

A page that names itself in its decorator and again in its own chrome has two
copies to keep in step, and the decorator's is the one that shows in menus, on
the contents page and in the history. So a heading comes from the declaration:

```python
@page("3", name="days", title="By day", detail="newest first")
async def _days(self, request: PageRequest) -> Page:
    return self._menu(request.address, items=items)   # headed BY DAY
```

`describe(address)` gives the registered title, so `describe(address).upper()`
is a heading. Pages whose heading is *not* their name — a post's forum, a day's
date — pass one, and passing one now means something.

The framework's own pages work the same way from the other side: map `contents`
into your numbering with a title and the page takes it, and keeps its own if
you give none.

## Saying where a page is, once

`addressing.keyed` gives a page number as a reader keys it — `*91#` — and
`MenuItem.for_page(app, name)` gives the words the page was registered with.
Between them, a page that tells a reader to press something need not spell out
either:

```python
guide = MenuItem.for_page(self, "help")
canvas.row(19).text("Key", Colour.WHITE).text(
    keyed(self.address_for("help")), Colour.YELLOW
).text(f"for {guide.text.lower()}.", Colour.WHITE)
```

Move the help page to another number and the instruction moves with it. A frame
that says `*91#` when the guide has moved is worse than no instruction at all:
the reader does as they are told and it does not work.

## The compass

The four keys that move about a page are the framework's, so the picture of
them is too:

```python
from sextile.compass import ROWS, compass

compass(Composition(), CONTENT_FIRST_ROW).draw(canvas)
```

`ROWS` says how many rows it takes, so it can be centred in what is left of a
frame. A service that drew its own would be drawing the same thing, and would
go on drawing it after the keys had moved.

It calls the vertical pair **page up** and **page down**. A frame is what the
wire calls it, but the frames of a page are the pages of one document to
whoever is reading — and saying so keeps *previous* and *next* for the other
axis, where they mean the items. It also says that the cursor keys work, which
they do: `keys.ARROWS` maps all four.

The arrows are mosaics rather than letters because the character set has only
three of them — `←`, `→` and `↑`, and no down arrow at all — so one of the four
had to be drawn whatever happened, and three letters beside one picture look
like a mistake.

`#` is not on it. It moves to the next frame as well, but a compass is about
which way is which, and `#` belongs in a list of things to key.

## Pages that come with the framework

Three pages are built for you and registered nowhere, so that a service maps
them into its own numbering or does without. They are handlers already, so
the mapping is one line apiece:

```python
from sextile import pages

PageRoute("92", pages.history, title="Where you have been", keywords=("HISTORY",))
PageRoute("93", pages.contents, title="Every page", keywords=("PAGES",))
PageRoute("94", pages.names, title="Words you can key", keywords=("KEYWORDS",))
```

Each answers by calling the application's method of the same name, so a
service wanting to change what one shows overrides the method and keeps the
route.

Each is generated from what the framework already knows — where a caller has
been, which patterns are registered, which words are aliased — so none can drift
from the service it describes. Anything you would otherwise type into a help
page by hand is a list that goes stale.

`contents` lists what the service is made of, taking pages with fields as
patterns rather than enumerating them — `*52<user-id>#  One contributor` — which
is the one thing a hand-written index cannot do.

Key 1 goes back one page — the same as `*0#` — 2 goes back two, and longer
histories page with `W`/`S`/`#`. The entries are labelled by
`Application.describe`, which by default reads the route's own name and fields,
so `82{post_id:int}` named `post` shows as "post 489493". Override it to say
what a reader would say:

```python
def describe(self, address: PageAddress) -> str:
    found = self.route(address)          # the numbering, read backwards
    ...
```

## The request

```python
async def post(request: PageRequest, post_id: int) -> Page:
    request.address            # the page number asked for
    request.arrival.following  # the next page in the sequence, if any
    request.session["user"]    # this caller's own state, for as long as the line is up
    request.service["client"]  # what the lifespan opened, for as long as the process
    request.history            # every page visited before this one, oldest first
    request.application        # the service, for asking where another page is
```

`arrival` is what makes "next" mean something: a page reached through one menu
has that menu's pages either side of it, and one reached by keying its number
has neither, and should offer neither. The session works this out from the
choices the menu offered; the handler only has to decide whether to use it.

`session` is a plain mutable mapping that lives as long as the connection. The
terminal holds nothing but the frame on screen, so anything outlasting a single
page belongs here.

`application` is what lets a handler be an ordinary function rather than a
closure built inside a factory: a page that offers another page has to ask the
numbering where that one is, and this is how it asks. It is optional only
because a request built by hand in a test has no service behind it;
`request.app` is the same thing without the `None`, and `Sextile.of(request)`
narrows to the routing application for a handler that asks the numbering
something:

```python
app = Sextile.of(request)
choices = {"1": app.address_for("post", post_id=post.id)}
```

## Saying that a page is not there

Return `None`. The session then shows a notice and leaves the reader where they
were, which is not the same as taking them somewhere empty.

```python
async def post(request: PageRequest, post_id: int) -> Page | None:
    found = await lookup(post_id)
    return None if found is None else _page_for(found)
```

The framework's notice is deliberately plain. A service with furniture of its
own should say it in that:

```python
@app.on_not_found
async def missing(target: str) -> Page:
    ...
```

**A handler that raises is a different thing**, and gets a different page: the
viewdata equivalent of a 500. The session catches it, logs the traceback and
shows `failed` without moving the reader, so a bug in one page costs that page
rather than the call.

```python
@app.on_failed
async def broke(address: PageAddress) -> Page:
    ...
```

There is a difference worth keeping between a page that does not exist and a
page that exists but has nothing to show. The second should be a real page that
says why — an empty menu with no explanation looks like a fault, and on a
service that answers slowly a reader cannot tell the difference.

## A page a reader types into

```python
from sextile import Suggest, draw_form

form = Suggest(look_up=..., field_row=4, first_row=6, label="PLACE:")
draw_form(canvas.frame, form)
return Page(frames=(PageFrame(frame=canvas.frame, form=form),))
```

A form answers a keypress by changing part of the frame rather than by going
anywhere. `Suggest` is a field with the best few matches beneath it, each on a
digit; `Fields` is several fields moved between with TAB and the arrows. Both
are `Form`s, and a service wanting a fourth shape subclasses that.

**Put the form in the session**, not in the handler: it is one caller's typing
and lasts exactly as long as their line.

```python
form = request.session.get(SEARCH)
if not isinstance(form, Suggest):
    form = Suggest(...)
    request.session[SEARCH] = form
```

Three things the wire decided, so that a service does not have to rediscover
them:

- **Offer three suggestions, not nine.** Nine rows repainted per keystroke is
  three seconds at 1200 baud; three is one, and a keystroke that changes nothing
  but the field is a single byte.
- **Digits are data or they are choices.** A form whose fields hold numbers
  cannot offer `0` for the index — say `*1#` in the footer instead, rather than
  offering a key that would eat a digit.
- **Say what RETURN will do where it does it**, and only while it would do
  something. `Suggest` marks the suggestion it would take; `Fields` marks the
  last field once the form is whole.

If a page's keys should also answer the cursor keys, say so — the framework
knows which byte is which arrow and deliberately does not decide what one means:

```python
moves=with_arrows({PREVIOUS_FRAME, NEXT_FRAME})
choices=arrows_lead_where({"A": before, "D": after})
```

`Template` already does this for every page it builds. A form receives the
arrows as themselves, which is what lets TAB move between fields without
typing a `D`.

## What is true of every page

A handler answers what one page says. **Middleware answers what is true of every
page** — who is asking, how long it took, whether they may:

```python
async def timing(request: PageRequest, build: Next) -> Page | None:
    began = time.monotonic()
    page = await build(request)
    log.info("*%s# in %.3fs", request.address, time.monotonic() - began)
    return page

app = Sextile(middleware=[timing], pages=[...])
```

It is given the request and the rest of the chain, and may look, may change
what comes back, or may answer instead and never call it at all — which is how
a service builds authentication without the framework having an opinion about
how anybody logs in. The first given is the outermost, so a reader of the list
sees a request entering at the top and leaving at the bottom.

One comes with the framework, and it exists because of the wire:

```python
from sextile.middleware import log_pages

app = Sextile(middleware=[log_pages()], pages=[...])
```

At 1200 baud a frame takes eight seconds to reach the reader, so "it felt slow"
cannot tell the wire from the page. `log_pages` names every page and times it,
warning on anything past a second — by *duration* rather than by outcome, since
a missing page is ordinary and taking four seconds to decide it was missing is
not.

## Anything that has to be opened

```python
CLIENT = Held("client", httpx.AsyncClient)

@asynccontextmanager
async def lifespan(app: Sextile) -> AsyncIterator[Mapping[str, object]]:
    client = httpx.AsyncClient()
    try:
        yield CLIENT.holding(client)
    finally:
        await client.aclose()

app = Sextile(lifespan=lifespan, pages=[...])
```

Entered once before the first call and left once after the last, so a handler
never has to wonder. **What it yields is what the service holds**, and every
page is handed it:

```python
async def post(request: PageRequest, post_id: int) -> Page:
    client = CLIENT.of(request.service)
```

What a service holds is typed as objects, because the framework cannot know
what any service puts in it. A `Held` key is the narrowing said once: the name
and the type travel together, `of` raises by name when the service has not
started, and `found_in` answers `None` for a thing a service may run without.
Yield several with `|`: `CLIENT.holding(client) | VISITS.holding(log)`. For a
kind that is a protocol or an abstract class, `Held.checking(name, kind)` makes
the same key — the type checker refuses those where a type is expected, and
the assignment's annotation says what the key holds:

```python
VISITS: Final[Held[Visits]] = Held.checking("visits", Visits)
```

`service` is the counterpart of `session`, and the contrast is why there are
two: `session` is this caller's and lasts as long as the line, `service` is
everybody's and lasts as long as the process. A page cannot write to `service`,
because a page that changed what the service holds would change it for every
other caller at once.

One function rather than a pair of handlers, because setup and teardown as two
functions have to be kept in step by hand and must hoist whatever they open
somewhere both can see. As two halves of one function they cannot drift, and
the thing opened is an ordinary local held across the `yield`.

The lifespan is given the application, which matters for a service assembled by
a factory: there is no name for the application until its constructor has
returned.

Handlers are `async`. Anything synchronous and slow — SQLite, a file — belongs
in `asyncio.to_thread`, or the one caller waiting on it is every caller waiting
on it.

## Forty columns, and what they cost

A colour attribute **occupies a character cell**. A row that changes colour
twice has thirty-eight columns for text, not forty. `Canvas` does that
arithmetic, which is why you write to it rather than to a `Frame`:

```python
canvas.row(row).text("1 ", Colour.YELLOW).text(title, Colour.WHITE)
canvas.right(row, page_number, Colour.WHITE)
canvas.paragraph(first_row, rows, prose, colour=Colour.WHITE)
```

`sextile.viewdata.drawing` has the small operations every page wants — free
functions, so your own sit beside them:

```python
from sextile.viewdata.drawing import bar, centred, centred_double, rule
from sextile.viewdata.encoding import cell_count, fitted

rule(canvas, 1)                                    # a mosaic rule across the row
centred(canvas, 3, "STARDOT", Colour.YELLOW)       # across the middle of a row
centred_double(canvas, 5, "STARDOT", Colour.CYAN)  # and at twice the height
bar(canvas, 20, colour=Colour.GREEN, cells=20, lit=13)   # a gauge
fitted(title, COLUMNS - 4)                         # shortened to the cells free
```

`draw_chrome` gives you a header with the page number, two rules and a footer,
leaving twenty rows. It is a convenience, not a requirement; a service that
wants the whole screen simply does not call it.

For long text, hand `sextile.viewdata.layout` a `Document` of blocks and it will
wrap it, colour quotations and listings distinctly, and deal the result into
frame-sized pages of rows.

## Seeing it

```sh
uv run sextile render my_service:app --page 1              # in colour
uv run sextile render my_service:app --page 1 --form grid  # characters and attributes
uv run sextile render my_service:app --page 1 --form bytes # the wire, as a hex dump
```

`render` also prints where each key on that frame leads, which is the quickest
way to check a menu is wired up correctly.

For a real terminal, see the dialling instructions in
[stardot-viewdata's README](../../stardot-viewdata/README.md).
