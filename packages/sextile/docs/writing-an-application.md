# Writing a Sextile application

A service is a set of numbered pages and the keys that lead between them.
Sextile owns everything else: the connection, the session, the routing, and the
bytes on the wire.

The worked example is
[`calendar-viewdata`](../../calendar-viewdata/), which is small, depends
on nothing but the standard library, and is meant to be read.

## The smallest thing that answers

```python
from sextile import Page, PageFrame, PageRequest, Sextile
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, draw_chrome

app = Sextile()

@app.page("1", name="main")
async def main(request: PageRequest) -> Page:
    canvas = Canvas()
    draw_chrome(canvas, title="MY SERVICE", page_number="1a", prompt="0 menu")
    canvas.row(CONTENT_FIRST_ROW).text("Hello, 1981.")
    return Page(frames=(PageFrame(frame=canvas.frame),))
```

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
@app.page("82{post_id:int}", name="post")
async def post(request: PageRequest, post_id: int) -> Page:
    ...

@app.page("32{day:date}", name="day")          # 3220260802 is 2 August 2026
async def day(request: PageRequest, day: date) -> Page:
    ...
```

`int` takes one or more digits and refuses a leading zero, so a page cannot have
two numbers. `date` takes eight, as `YYYYMMDD`.

**`int(n)` takes exactly n digits**, zero-padded. That is what lets fields sit
next to one another, since a page number has no separators:

```python
@app.page("32{year:int(4)}{month:int(2)}{day:int(2)}", name="iso")
async def iso(request: PageRequest, year: int, month: int, day: int) -> Page:
    ...

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
app.converter("pair", Converter(field_pattern="[0-9]{2}", width=2))
app.converter("code", lambda width: Converter(...))    # for {x:code(3)}
```

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

**Keywords** cost nothing to offer beside numbers:

```python
app.alias("MAIN", app.address_for("main"))
```

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

## Say what a page is where you register it

```python
@app.page("5", name="contributors", title="By contributor", detail="browse by poster")
async def contributors(request: PageRequest) -> Page:
    ...
```

Those words are what the page is called wherever it is *listed* rather than
shown — a menu offering it, a history naming it, the contents. Say them once
here and nothing downstream needs its own copy:

```python
app.page_info("contributors").title      # "By contributor"
app.describe(PageAddress("5"))           # "By contributor"
app.pages()                              # every page that has a title
```

**A page with no title is not advertised.** Giving one a title is how a service
says it may be listed, so a title frame or a logoff page stays off the contents
without a flag.

## Pages that come with the framework

Two pages are built for you and registered nowhere, so that a service maps them
into its own numbering or does without:

```python
self.page("92", name="history", title="Where you have been")(self.history)
self.page("93", name="contents", title="Every page")(self.contents)
self.alias("HISTORY", self.address_for("history"))
```

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
    request.history            # every page visited before this one, oldest first
```

`arrival` is what makes "next" mean something: a page reached through one menu
has that menu's pages either side of it, and one reached by keying its number
has neither, and should offer neither. The session works this out from the
choices the menu offered; the handler only has to decide whether to use it.

`session` is a plain mutable mapping that lives as long as the connection. The
terminal holds nothing but the frame on screen, so anything outlasting a single
page belongs here.

## Saying that a page is not there

Return `None`. The session then shows a notice and leaves the reader where they
were, which is not the same as taking them somewhere empty.

```python
@app.page("82{post_id:int}")
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

There is a difference worth keeping between a page that does not exist and a
page that exists but has nothing to show. The second should be a real page that
says why — an empty menu with no explanation looks like a fault, and on a
service that answers slowly a reader cannot tell the difference.

## Anything that has to be opened

```python
class MyApplication(Sextile):
    async def startup(self) -> None:
        self._client = httpx.AsyncClient()

    async def shutdown(self) -> None:
        await self._client.aclose()
```

Called once before the first call and once after the last, so a handler never
has to wonder.

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
