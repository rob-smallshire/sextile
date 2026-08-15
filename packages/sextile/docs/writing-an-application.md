# Writing a Sextile application

A Viewdata service answers calls from a terminal over a modem. It sends frames,
each a screen of 24 rows by 40 columns, and the caller navigates by keying a
page number such as `*821#`, or a single digit that the current frame maps to
another page. A Sextile application is the set of numbered pages, and for each
page the keys that lead from it. Sextile provides the rest: it accepts the
connection, holds one session per caller, routes a keyed number to the function
that builds the page, and encodes each frame for the wire.

The worked example is
[`calendar-viewdata`](../../calendar-viewdata/): small, dependent on nothing but
the standard library, and written to be read.

## A minimal application

```python
from sextile import Page, PageRequest, PageRoute, Sextile
from sextile.formatting import Lines
from sextile.layout import Flow, PageLayout

async def main(request: PageRequest) -> Page:
    return PageLayout(
        title="MY SERVICE",
        parts=[Flow(Lines(said=("Hello, 1981.",)))],
    ).build(request)

app = Sextile(pages=[PageRoute("1", main, name="main")])
```

`PageLayout` draws the furniture: the title bar, the page number, the two rules
and the prompt. The page supplies the text of its title, where its keys lead,
and the parts that sit between the rules. See [layout.md](layout.md).

**A page is a value; a service is a list of pages.** One `PageRoute` carries
everything about a page: its place in the numbering, the function that builds
it, the name it is listed under, and the words that reach it. Each page is
declared once, in one place.

Because everything arrives in the single `Sextile(...)` call — the converters a
pattern needs, the routes, the middleware, the lifespan — registration order
does not matter. No step has to run before another.

`@app.page(...)` declares a route as a decorator instead, which reads better for
a small service:

```python
app = Sextile()

@app.page("1", name="main")
async def main(request: PageRequest) -> Page:
    ...
```

The decorator builds the same `PageRoute`, so the two forms cannot diverge.

```sh
uv run sextile serve my_service:app
nc localhost 6850
```

A caller arrives on page 1 unless the application sets another home with
`Sextile(home="8")`. After fifteen minutes without a keypress the session hangs
up, so that one idle caller cannot hold a single-line board against everyone
else. Partway through that period the footer turns into a draining bar reading
`Press a key`, warning of the disconnection before it happens; the first key
dismisses the bar and does nothing else. Both behaviours are the framework's,
and every service has them by default. `--idle-timeout` and `--warn-after`
change the timings; `0` turns either off.

## Page numbering

A pattern is literal digits and named fields.

```python
PageRoute("82{post_id:int}", post, name="post")
PageRoute("32{day:date}", day, name="day")     # 3220260802 is 2 August 2026
```

`int` matches one or more digits and refuses a leading zero, so each value has
one spelling. `date` matches eight digits, as `YYYYMMDD`.

**`int(n)` matches exactly n digits**, zero-padded. Fixed widths are what let
fields sit next to one another, since a page number has no separators:

```python
PageRoute("32{year:int(4)}{month:int(2)}{day:int(2)}", iso, name="iso")

app.address_for("iso", year=2026, month=8, day=2)     # 3220260802
```

The leading-zero rule reverses for fixed-width fields, and for the same purpose:
one spelling per value. A variable-width field refuses a leading zero, because
`0042` and `42` would be two numbers for one page. A fixed-width field requires
the padding, because once the width is fixed each value again has one spelling.
So `708` is month 8, and `78` is not a page.

An application that needs another field shape registers a converter, either
fixed or parameterised by the argument in brackets:

```python
app = Sextile(
    converters={
        "pair": Converter(field_pattern="[0-9]{2}", width=2),
        "code": lambda width: Converter(...),          # for {x:code(3)}
    },
    pages=[PageRoute("7{n:pair}", counted, name="counted")],
)
```

Converters go to the constructor, because the router must know a field shape
before it compiles a pattern that uses it. `app.converter(...)` adds one later,
which suits a page declared later too.

Two rules keep matching predictable. **Most literal wins**: `90` beats
`9{n:int}` whatever order they were registered in, so that reordering the routes
cannot change what a number means. **Fields must be separable**: where fields
run together, all but the last must have a fixed width, or nothing marks where
one ends and the next begins. Give them widths, or put a literal digit between
them.

None of this requires prefix-free numbers. A viewdata request is terminated by
`#`, so `*8#` and `*82489493#` are distinct, and fields may vary in width.

**Build addresses; do not spell them out.** Every route has a name, taken from
the handler unless one is given, and `address_for` fills a pattern from named
values:

```python
choices = {"1": app.address_for("post", post_id=post.id)}
```

This keeps the numbering scheme in one place instead of copied across every
link.

**Keywords** belong beside the page they reach:

```python
PageRoute("1", main, name="main", keywords=("MAIN", "INDEX"))
```

`app.alias("MAIN", app.address_for("main"))` does the same for a word registered
apart from the route.

## Menus and listings

Most pages are a `PageLayout`: furniture round the edge of each frame, and a
list of parts down the middle. Most present a list of items, so the framework
formats those.

```python
from sextile import menu_page
from sextile.formatting import MenuItem

menu_page(
    request,
    title="BY USER",
    preamble=("Everyone registered.",),               # first frame only
    items=[MenuItem(text=name, detail=f"{count} entries", destination=where) ...],
    empty="NONE held yet.",                            # said instead of an empty frame
)
```

`Menu` numbers its entries 1–9, nine to a frame, each with a line of detail
beneath. `Listing` is the same mechanism for a reference page: no selectable
digits, the detail in a second column. `Figures` is a label with a
right-aligned figure, `Lines` draws lines as given, and `Prose` is running text.
The layout draws the furniture, builds the prompt from the keys the frame
offers, wires up `W`, `S` and `#`, and sends `0` home.

[layout.md](layout.md) describes all of it. What follows is what a service uses
most.

**An entry is a protocol, not a type.** Anything with `text`, `detail` and
`destination` will serve, so a service with its own richer entry type — carrying
the post, the timestamp, and anything else it needs — passes that directly:

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

For running text, leave the line breaks to the framework:

```python
from sextile import prose_page

prose_page(
    request,
    "A Viewdata service carrying posts from stardot.org.uk, for "
    "users of Acorn computers and emulators.",
    f"{held} posts held.",
    title="ABOUT STARDOT",
)
```

Each argument to `Prose.of` is a paragraph; the framework wraps and spaces them
and divides them between frames. `Prose` also accepts rendered rows in place of
plain paragraphs, which is how a notice carries a quotation or a code listing
rendered exactly as a forum post's would be:

```python
Flow(Prose(entries=rows_for(document)))
```

For a shape none of these covers, subclass `SequencePart`: give the height of one
entry and the code to draw it, and the arithmetic, the frames and the keys come
with it. A shape laid out along its rows subclasses `RowSequencePart` instead and
writes `draw` and `draw_detail`. Both are dataclasses, so a subclass that needs
something an entry does not carry — a date to mark against, a column width —
declares a field rather than writing a constructor.

For content that is not a sequence — a grid, a masthead, a picture —
`Custom(rows, draw)` is a part of a stated height that the page draws itself.

## Pages, frames and keys

A page is one or more frames, and **each frame carries what its keys do while it
is on screen**, because frame b of a listing offers a different nine choices
from frame a.

```python
PageFrame(
    frame=canvas.frame,
    choices={"0": app.address_for("main"), "1": somewhere},
    moves=frozenset({"S", "#"}),          # keys that move within this page
)
```

`choices` lead to other pages; `moves` stay on this page and step between its
frames. Keys are characters, not only digits, so a page may offer `D` for next
or `R` for reply.

Two conventions are worth keeping, because readers rely on them across services:

- **`0` returns to the index from every frame.** It is the one key a lost reader
  can always rely on.
- **A frame names only the keys that do something on it.** A key that leads
  nowhere is worse than none, and on a slow service a reader cannot tell a dead
  key from a slow one. Build the prompt and the choices from the same
  description of what the frame offers, or they will disagree.

### The footer prompt

`PageLayout` writes its own prompt from the keys the parts and the page offer. A
frame drawn some other way composes one from items rather than writing a string:

```python
from sextile.viewdata.footer import ROOM, FooterItem, Priority, movement, render_footer

items = [FooterItem("1", "month", Priority.PRIMARY)]
items += movement(choices, item="day")
items.append(FooterItem(HOME_KEY, "index", Priority.ESSENTIAL))
prompt = render_footer(items, ROOM)
```

`movement` supplies the framework's words for `W`, `S`, `A` and `D` — *page up*,
*page down*, *previous* and *next* — with the noun taken from the `item`
argument, since only the service knows what it is made of. Give the label in
full; the renderer decides how much of it a given row can hold, and a page with
cells to spare shows all of it.

Anything else the frame offers is a `FooterItem` of its own:

| | |
|---|---|
| `key` | what the reader presses |
| `label` | what it does, in words |
| `brief` | a shorter label, for a crowded row |
| `priority` | `ESSENTIAL` the way out, `PRIMARY` what the page is for, `SECONDARY` moving about, `REDUNDANT` an alias for a key already shown |

The order in which items are dropped when a row is full is in
[navigation.md](navigation.md), with worked examples. The rule worth knowing
here is that **priority decides what survives, not position**, so an item can go
wherever in the list reads well.

To end the call, say so on the page:

```python
return Page(frames=(...), hang_up=True)
```

There is a second parting the service does not choose: the idle caller who is
released. It has a page of its own, told where the caller had reached:

```python
@app.on_timed_out
async def gone(request: PageRequest, parting: Parting) -> Page:
    ...   # request.address, .history, .session; parting.frame_index
```

The terminal keeps nothing, so `request.address` is worth showing: "You were
reading *82489493#" is what lets a caller dial back in and pick up. The request
is the page they were on; the `Parting` beside it says which frame. The default
page does this, and names the service if it has a name:

```python
app = Sextile(name="Stardot")     # "Thank you for calling Stardot."
```

`name` is empty unless the service sets it, and the framework does not invent
one.

Both are the last frame a reader sees, so **draw them with no footer and leave
the lower rows blank**. A key offering the index would do nothing once the line
is closing. The framework places the cursor two rows below the last line and
turns it on, giving the reader somewhere to type modem commands. `farewell_page`
in `sextile.formatting` draws exactly that frame, a page with no furniture:

```python
return farewell_page("GOODBYE", f"Thank you for calling {app.name}.", "", "Ring off.")
```

## Titles, details and keywords

```python
PageRoute("5", users, name="users", title="By user",
          detail="browse by name", keywords=("WHO", "USERS"))
```

The route takes the handler's own name unless one is given.

The title and detail are what the page is called wherever it is *listed* rather
than shown — a menu offering it, the history, the contents page. Declared once
here, they need no second copy downstream:

```python
app.page_info("users").title             # "By user"
app.title_for(PageAddress("5"))          # "By user"
app.label_for(PageAddress("5"))          # "By user", or "Post 489493" for a field page
app.pages()                              # every page that has a title
```

**A page with no title is not advertised.** A title is how a service marks a
page as listable, so a title frame or a log-off page stays off the contents page
without a separate flag. A title and a keyword are independent: a log-off page
can stay off the contents and still answer `*BYE#`.

A handler that lives in a module of its own is declared with `@router.page(...)`,
the same call as `@app.page`. A `PageRouter` gathers them in written order, and
the assembly spreads the router into the service, so each route stays on the
function that builds the page rather than in a separate list:

```python
router = PageRouter()

@router.page("5", title="By user", detail="browse by name",
             keywords=("WHO", "USERS"))
async def users(request: PageRequest) -> Page:
    ...

app = Sextile(pages=[*router, ...])
```

A route for another module's handler — the framework's own pages, say — is one
`PageRoute` line beside the spread:

```python
app = Sextile(pages=[
    *pages.router,
    PageRoute("92", handlers.history, title="Where you have been"),
])
```

## Getting page information

A page that names itself in its decorator and again in its own furniture has two
copies to keep in step, and the decorator's is the one shown in menus, on the
contents page and in the history. So the heading comes from the declaration:

```python
@router.page("3", name="days", title="By day", detail="newest first")
async def days(request: PageRequest) -> Page:
    return menu_page(request, items=items)   # headed BY DAY
```

`title_for(address)` gives the registered title as registered; the layout
shouts it into the header where a page gave no title of its own. Pages whose
heading is *not* their title — a post's forum, a day's date — pass one
explicitly, and the layout draws that one as it is.

The framework's own pages work the same way: map `contents` into the service's
numbering with a title and the page uses it, or keeps its own if none is given.

## Obtaining page addresses

`addressing.keyed` renders a page number as a reader keys it — `*91#` — and
`app.menu_item(name)` gives the words the page was registered with.
Together they let a page that tells a reader what to press avoid spelling out
either:

```python
guide = self.menu_item("help")
canvas.row(19).text("Key", Colour.WHITE).text(
    keyed(self.address_for("help")), Colour.YELLOW
).text(f"for {guide.text.lower()}.", Colour.WHITE)
```

Move the help page to another number and the instruction follows. A frame that
says `*91#` after the guide has moved is worse than no instruction: the reader
keys it and nothing happens.

## The compass

The four keys that move around a page are the framework's, and so is the picture
of them:

```python
from sextile.compass import ROWS, compass
from sextile.layout import Custom, OnOneFrame

OnOneFrame(Custom(rows=ROWS, draw=lambda canvas, row: compass(Composition(), row).draw(canvas)))
```

`ROWS` is how many rows it occupies, which is what `Custom` is given, so the
layout can leave room for it or start it on the next frame. A service that drew
its own compass would duplicate this one, and would keep drawing the old keys
after the framework's had changed.

It labels the vertical pair **page up** and **page down**. *Frame* is the wire's
term, but to a reader the frames of a page are the pages of one document, and
using *page* here keeps *previous* and *next* for the other axis, where they
mean the items. The picture also shows that the cursor keys work, which they do:
`keys.ARROW_KEYS` maps all four.

The arrows are drawn as mosaics rather than letters because the character set
has only three arrow characters — `←`, `→` and `↑`, with no down arrow — so one
of the four had to be drawn whatever else was done, and three letters beside one
drawn arrow would look like a mistake.

`#` is not on the compass. It also moves to the next frame, but the compass
shows directions, and `#` belongs in a list of keys to press.

## Built-in pages

The framework builds several of its own pages — the history, the contents, the
list of keywords, and three that read the visit log — and registers them
nowhere: a service gives each a number or does without. `standard_pages` maps
whichever it names into the service's numbering in one line, carrying the
framework's own title, detail and keywords:

```python
from sextile import standard_pages

Sextile(pages=[
    *my_pages,
    *standard_pages(history="92", contents="93", keywords="94"),
])
```

The readership pages read the visit log, so they take the `StateKey` it is held
under — the same key a service hands `record_visits`:

```python
*standard_pages(recent="96", popular="97", callers="98", visits=VISITS)
```

Each calls the application method of the same name (`history_page`,
`contents_page`, ...), so a service that wants to change what one shows
overrides the method and keeps the route.

Each is generated from what the framework already holds — where the caller has
been, which patterns are registered, which words are aliased — so none can drift
from the service it describes, whereas a hand-typed help page goes stale.

`contents` lists what the service is made of, showing pages with fields as
patterns rather than enumerating every value — `*52<user-id>#  One user`
— which a hand-written index cannot do.

Key 1 goes back one page (the same as `*0#`), 2 goes back two, and longer
histories page with `W`/`S`/`#`. The label on each entry comes from the route
by default, reading its title and fields, so `82{post_id:int}` titled "One post"
shows as "One post 489493". A route whose number carries a field says its own
words with `label=`, a template over the captured fields or a callable taking
them:

```python
@router.page("82{post_id:int}", name="post", title="One post", label="Post {post_id}")
async def post(request: PageRequest, post_id: int) -> Page:
    ...          # listed "One post", shown in history as "Post 489493"
```

## PageRequest: How pages are requested

```python
async def post(request: PageRequest, post_id: int) -> Page:
    request.address            # the page number asked for
    request.neighbours.next    # the next page in the sequence, if any
    request.session["user"]    # this caller's own state, for as long as the line is up
    request.state[CLIENT]      # what the lifespan opened, for as long as the process
    request.history            # every page visited before this one, oldest first
    request.app                # the service, for asking where another page is
```

`neighbours` gives the pages on either side of this one when the reader reached
it through a sequence such as a menu: `neighbours.previous` and
`neighbours.next`, each a `PageAddress` or `None`. Pass the whole thing to a
layout, which wires the `A` and `D` keys — *previous* and *next* — to whichever
is not None and names them:

```python
PageLayout(..., neighbours=request.neighbours, item_noun="post").build(request)
```

A page reached by keying its number directly belongs to no sequence, so both
are `None`, and it offers neither key. The session computes the neighbours from
the menu the reader used; the handler only passes them on.

`session` is a plain mutable mapping that lasts as long as the connection. The
terminal holds nothing but the frame on screen, so anything that must outlast a
single page belongs here.

`application` is what lets a handler be a plain function rather than a closure
built in a factory: a page that offers another page must look up where that page
is, and `application` is how. It is optional only because a request built by
hand in a test has no service behind it. `request.app` is the same value without
the `None`, and `Sextile.of(request)` narrows to the routing application for a
handler that queries the numbering:

```python
app = Sextile.of(request)
choices = {"1": app.address_for("post", post_id=post.id)}
```

## Error handling

Return `None`. The session shows a notice and leaves the reader on the current
page, rather than moving them to an empty one.

```python
async def post(request: PageRequest, post_id: int) -> Page | None:
    found = await lookup(post_id)
    return None if found is None else _page_for(found)
```

The framework's notice is deliberately plain. A service with its own furniture
should render the notice in that:

```python
@app.on_not_found
async def missing(request: PageRequest, target: str) -> Page:
    ...          # notice_page(request, ...) in the service's own furniture
```

**A handler that raises is different**, and gets a different page: the viewdata
equivalent of a 500. The session catches the exception, logs the traceback and
shows `failed` without moving the reader, so a bug in one page costs that page
and not the call. The hook is handed the request and the exception, so a service
can log or classify it its own way:

```python
@app.on_failed
async def broke(request: PageRequest, error: Exception) -> Page:
    ...
```

Keep the difference between a page that does not exist and a page that exists but
has nothing to show. The second should be a real page that says why: an empty
menu with no explanation looks like a fault, and on a slow service a reader
cannot tell the two apart.

## Forms: Accepting typed input

```python
from sextile import Suggest
from sextile.layout import OnOneFrame, PageLayout

return PageLayout(
    title="FIND A PLACE",
    parts=[
        OnOneFrame(Lines(said=("Key a place name.", ""))),
        OnOneFrame(Suggest(look_up=places.matching, label="PLACE:")),
    ],
).build(request)
```

A form answers a keypress by redrawing part of the frame rather than by moving
to another page. `Suggest` is a field with the best few matches beneath it, each
on a digit; `Fields` is several fields moved between with TAB and the arrows.
Both are `Form`s, and a service that wants a third shape subclasses `Form`.

**A form is a part**, so it is given the row it begins on and counts its own rows
from zero. `Suggest` puts its field on its first row and its suggestions two rows
below unless told otherwise, and a page that moves the form up or down moves the
part, not the offsets inside it. The form also supplies the prompt's words for
the keys it answers — `A-Z type a name` and `1-9 choose one` — so a page carrying
one need not name them itself.

**Keep the form in the session**, not in the handler: it holds one caller's
typing and lasts as long as their line.

```python
form = request.session.get(SEARCH)
if not isinstance(form, Suggest):
    form = Suggest(...)
    request.session[SEARCH] = form
```

Three constraints the wire imposes, so a service need not rediscover them:

- **Offer three suggestions, not nine.** Repainting nine rows per keystroke takes
  three seconds at 1200 baud; three rows take one, and a keystroke that changes
  only the field is a single byte.
- **Digits are either data or choices.** A form whose fields hold numbers cannot
  offer `0` for the index; put `*1#` in the footer instead, rather than a key
  that would swallow a digit.
- **Say what RETURN will do where it does it**, and only while it would do
  something. `Suggest` marks the suggestion it would take; `Fields` marks the
  last field once every field is filled.

If a page's keys should also answer the cursor keys, say so. The framework knows
which byte is which arrow and deliberately does not fix what an arrow means:

```python
moves=with_arrows({PREVIOUS_FRAME, NEXT_FRAME})
choices=arrows_lead_where({"A": before, "D": after})
```

`PageLayout` does the first for every page it builds, and the second for any
shortcut given `with_arrow=True`. A form receives the arrows unmapped, which is what
lets TAB move between fields without registering a `D`.

## Middleware: Intercepting every request and response

A handler decides what one page says. **Middleware handles what is true of every
page** — who is calling, how long a page took, whether the caller is allowed:

```python
async def timing(request: PageRequest, build: Next) -> Page | None:
    began = time.monotonic()
    page = await build(request)
    log.info("*%s# in %.3fs", request.address, time.monotonic() - began)
    return page

app = Sextile(middleware=[timing], pages=[...])
```

Each middleware is given the request and the rest of the chain. It may inspect
the request, change the page that comes back, or answer itself and never call
the chain, which is how a service adds authentication without the framework
prescribing how anyone logs in. The first in the list is the outermost, so the
list reads top-to-bottom as a request enters and the page leaves.

One middleware comes with the framework, and it exists because of the wire:

```python
from sextile.middleware import log_pages

app = Sextile(middleware=[log_pages()], pages=[...])
```

At 1200 baud a frame takes eight seconds to reach the reader, so "it felt slow"
cannot separate the wire from the page. `log_pages` names and times every page,
warning on anything over a second, by *duration* rather than by outcome: a
missing page is ordinary, but taking four seconds to decide it is missing is not.

## Application lifecycle

```python
CLIENT = StateKey[httpx.AsyncClient]("client")

@asynccontextmanager
async def lifespan(app: Sextile) -> AsyncIterator[None]:
    client = httpx.AsyncClient()
    app.state[CLIENT] = client
    try:
        yield
    finally:
        await client.aclose()

app = Sextile(lifespan=lifespan, pages=[...])
```

The lifespan is entered once before the first call and left once after the last.
It writes what the service holds into `app.state` under `StateKey` keys and
yields nothing; every page is given the same values as `request.state`:

```python
async def post(request: PageRequest, post_id: int) -> Page:
    client = request.state[CLIENT]
```

A `StateKey[T]("name")` states the narrowing once: the key carries the type
`T`, so `app.state[CLIENT] = client` type-checks the write and
`request.state[CLIENT]` reads it back as an `httpx.AsyncClient`.
`request.state[KEY]` raises `KeyError` naming the key when the service has not
started; `request.state.get(KEY)` returns `None` for a value a service may run
without. Identity is the key, not the name: two keys spelt the same are
distinct, and the name is only for the repr and the error text. A key holding a
protocol or an abstract class needs no special form — `StateKey[Visits]("visits")`
narrows to `Visits` like any other:

```python
VISITS: Final = StateKey[Visits]("visits")
```

`state` is the counterpart of `session`, and the contrast is the reason for
having both: `session` is one caller's and lasts as long as the line, `state`
is shared and lasts as long as the process. `request.state` is a read-only
view, because a page writing there would reach every other caller at once; only
the lifespan writes, through `app.state`.

It is one function rather than a setup/teardown pair, because two functions must
be kept in step by hand and must store whatever they open where both can reach
it. As two halves of one function they cannot drift, and the opened resource is
an ordinary local held across the `yield`.

The lifespan is given the application, which matters for a service assembled by a
factory: the application has no name until its constructor has returned.

Handlers are `async`. Anything synchronous and slow — SQLite, a file read —
belongs in `asyncio.to_thread`, or every caller waits while one caller's page is
built.

## Text and Graphics

A colour attribute **occupies a character cell**. A row that changes colour twice
has thirty-eight columns left for text, not forty. `Canvas` does this arithmetic,
which is why a page writes to it rather than to a `Frame`:

```python
canvas.row(row).text("1 ", Colour.YELLOW).text(title, Colour.WHITE)
canvas.right(row, page_number, Colour.WHITE)
canvas.paragraph(first_row, rows, prose, colour=Colour.WHITE)
```

`sextile.viewdata.drawing` has the small operations most pages need, as free
functions, so a service's own sit beside them:

```python
from sextile.viewdata.drawing import bar, centred, centred_double, rule
from sextile.viewdata.encoding import cell_count, fitted

rule(canvas, 1)                                    # a mosaic rule across the row
centred(canvas, 3, "STARDOT", Colour.YELLOW)       # across the middle of a row
centred_double(canvas, 5, "STARDOT", Colour.CYAN)  # and at twice the height
bar(canvas, 20, colour=Colour.GREEN, cells=20, lit=13)   # a gauge
fitted(title, COLUMNS - 4)                         # shortened to the cells free
```

To get the standard header, two rules and footer, build the page with
`PageLayout` and its `DEFAULT_FURNITURE` rather than drawing the frame by hand.
A frame drawn entirely by hand draws its own: `rule(canvas, 1)` for each rule,
and `canvas` for the header and footer. Neither is required; a page that wants
the whole screen draws only what it wants.

For long text, give `sextile.viewdata.typesetting` a `Document` of blocks; it
wraps the text, colours quotations and listings distinctly, and divides the
result into frame-sized pages of rows.

## Previewing a page

```sh
uv run sextile render my_service:app --page 1              # in colour
uv run sextile render my_service:app --page 1 --form grid  # characters and attributes
uv run sextile render my_service:app --page 1 --form bytes # the wire, as a hex dump
```

`render` also prints where each key on the frame leads, which is the quickest way
to check a menu is wired correctly.

For a real terminal, see the dialling instructions in
[stardot-viewdata's README](../../stardot-viewdata/README.md).
