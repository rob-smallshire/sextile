# A page layout: its furniture, and the parts between

A design note. Nothing here is built.

It proposes splitting `Template` into two pieces — the furniture around a
frame, and the parts drawn between the rules — and works the proposal against
every page in the three services to find out whether it holds.

## The frame, and what each part is called

A frame is 24 rows of 40 cells. `viewdata/chrome.py` fixes the geometry today:

    row  0        header        the page title, and the page number at the right
    row  1        rule
    rows 2-21     content       CONTENT_FIRST_ROW, CONTENT_ROWS = 20
    row  22       rule
    row  23       footer        FOOTER_ROW

**The bottom row is the footer.** Usage has already settled that: "footer"
appears 89 times in the framework against 24 for "prompt" and 19 for "command
line", and it names the constant, the module (`viewdata/footer.py`) and the two
types that compose it. Three different things occupy that row at different
moments, and they are three things rather than three names for one:

- the **prompt** — which keys work on this frame and what they do, composed
  from `FooterItem` values and shed in priority order when the row is tight;
- the **command line** — what the reader has keyed so far, while a request is
  being typed;
- the **countdown** — a draining bar warning that a silent line is about to be
  released, which covers whatever else wanted the row.

**Furniture** is the collective term for the header, the rules and the footer.
**Content** is what lies between the rules. **A part** is one item of content.

## The two jobs

`Template` does both, and only one of them is available on its own.

**The furniture**: title and page number, the rules, the prompt, the way home,
the shortcuts, the keys that move between frames, assembling the `Page`.

**The content**: everything between the rules, and how much of it fits.

Today the only way to obtain the first is to be a formatter of a homogeneous
sequence, so content that is not a sequence has no route to the furniture at
all.

### The evidence

**Five pages draw their own furniture** rather than accept that:
`stardot_viewdata/post_page.py`, the two frames a reader types into in
`weather_viewdata/handlers.py`, and the title frames of Stardot and weather,
which want no furniture rather than a different sort. The first three are the
remaining crossings in [public-surface.md](public-surface.md).

**One page pretends to be a sequence to get the furniture.** The calendar's
month page is `Lines(entries=[], preamble=[Block(...)])`. A month grid is not a
collection of items; the furniture and the keys were what it wanted, and being
a formatter of nothing was the price.

**The optional fields divide along the same line.** Of the nine on `Template`:

    furniture   title, home, shortcuts, item
    content     entries, preamble, headings, footnote, empty

Every field that has raised a question about knob growth is on the content
side, attached to a class that is mostly about furniture. `Figures` grew
`footnote` because a table of figures wants a note beneath it, which has
nothing to do with titles, rules or keys.

## The shape of it

A **page layout** is a title, a way home, the shortcuts, the furniture, and a
list of parts. `build(address)` returns a `Page`.

```python
PageLayout(
    title=SERVICE_NAME,
    home=app.index,
    parts=[Flowing(Menu(entries=items, empty="Nothing yet."))],
).build(address)
```

### Filled, then furnished

The prompt of a frame names `S page down` only where there is a frame to page
down to, so the prompt of frame *i* depends on whether frame *i+1* exists. That
looks as though frames cannot be produced one at a time. The geometry says
otherwise: content occupies rows 2 to 21, furniture rows 0, 1, 22 and 23, and
they never touch.

**Fill.** Walk the parts, drawing content onto canvases and starting a new one
whenever a frame runs out of rows or a `Break()` says so. Nothing in this pass
needs to know how many frames there will be.

**Furnish.** Once the count is known, draw the header, the rules and the prompt
on each, and assemble the `Page`. This is the only pass that needs the total.

`Template` does the reverse — divide first, then draw content and furniture
together — which is why it must know the count before it draws anything.

## Parts

Four kinds, and list order settles what sits above what:

    Once(part)      drawn one time, at its place in the order
    Every(part)     drawn on every frame, at its place in the order
    Flowing(part)   broken across as many frames as it takes
    Break()         whatever follows begins on a new frame

### This removes fields rather than adding them

`preamble`, `headings` and `footnote` are one idea spelled three times: rows
around the entries, differing in whether they sit above or below and whether
they appear once or always. As parts the difference is position in the list and
one word:

    [ Once(preamble), Every(headings), Flowing(Menu(items)), Every(footnote) ]

Above-versus-below falls out of the ordering. Once-versus-always falls out of
the kind.

### Several flowing parts follow one another

A flowing part takes the rows left to it and continues on the next frame. Where
a second follows, it begins in the row after the first has finished, on
whatever frame that is. Concatenation, and nothing more.

That is the decision `typesetting.rows_for` already made: a post's body and its
list of links are two streams, and it joins them into one before anything is
divided between frames.

The alternative is to let two streams compete for the room on a frame.
InDesign threads a story through a chain of frames a person has drawn and
linked, so the placement question is answered by whoever draws the rectangles.
LaTeX has three streams competing for every page — running text, floats,
footnotes — and a parameter set to referee them: `\topfraction`,
`\bottomfraction`, `\textfraction`, `\floatpagefraction`, `\topnumber`,
`\bottomnumber`, `\totalnumber`. The familiar failures follow from allowing it
at all: a footnote that will not fit moves its reference to the next page,
which moves the footnote; floats deferred often enough drift to the end of the
chapter. CSS Regions offered the same for the web, shipped in Blink, and was
removed.

A viewdata frame is twenty rows of forty cells with no floats, no columns and
nothing to place around. Concatenation answers every case here, and it means
there is no rule about how many parts may flow.

### What concatenation settles

**A part that does not flow is drawn whole or moved on.** Where a fixed part
will not fit in the rows left, it begins the next frame rather than being
split. A part taller than a whole frame can never be placed, and that is an
error at build time rather than a silent truncation.

**Choices are a frame's budget, not a part's.** A reader chooses with one
keypress, so nine is the most a frame can offer however it is divided. Two
flowing menus on one frame might show five entries and four. `CHOICES_PER_FRAME`
therefore stops being a fact about a template and becomes part of what the
layout hands down.

**`once` means once, not first.** A fixed part before any flowing part lands on
the first frame, which is what `preamble` does today. A fixed part after a
flowing part lands on whichever frame that flow finished on. One rule, and the
second case falls out of concatenation.

**`every` parts are placed against the frame, not the stream.** Those before
the flowing parts reserve rows at the top of every frame; those after reserve
rows at the foot. What lies between is what the flowing parts divide.

### A break divides where a page means to

    [ Flowing(moving_keys), Break(), Flowing(asking_keys) ]

That is the guide, whose two frames are two different lists — the keys for
moving about, and the keys for asking for something — split by what a reader is
doing rather than by what fits. Its docstring gives exactly that as the reason
it cannot be a template.

A break also removes a silent cap: the guide draws `rows[:CONTENT_ROWS]`, so a
service with more than twenty keys of its own loses the surplus without being
told, where flowing parts would go on to a third frame.

**A break that would divide nothing is not a break.** One at either end of the
list, two together, or one on a frame with nothing yet drawn on it: each is
ignored, or a stray break produces a frame carrying furniture and no content.

## The two protocols

Content and furniture are drawn in different passes and are told different
things, so they are two protocols rather than one. The distinction is short:
**a content part claims, and a furniture part reports.** A part between the
rules says which keys lead where; the furniture names what the whole page
offers, and can only be drawn once every part has spoken.

### What a part is given, and what it gives back

```python
@dataclass(frozen=True)
class Room:
    """What is left of a frame when a part is asked to draw on it."""

    first_row: int
    rows: int
    choices: int


@dataclass(frozen=True)
class Offer:
    """What a part gives the frame it has drawn on."""

    choices: Mapping[str, PageAddress] = ...
    named: Sequence[FooterItem] = ()
    form: Form | None = None
```

`Offer` rather than anything more inventive, because that is the verb the
framework already uses: *keys offered on every frame*, *a page cannot offer a
key silently*.

A part is a description and may be built into several pages, so placing one
must not change it. A part is to its placing as an iterable is to an iterator:

```python
class Part(Protocol):
    def placing(self) -> "Placing":
        """Begin placing this part. The result carries the position."""


class Placing(Protocol):
    def fits(self, room: Room) -> int:
        """Rows this will take of `room`, or nought where it cannot begin here."""

    def draw(self, canvas: Canvas, room: Room) -> Offer:
        """Draw what `fits` said would fit, and advance past it."""

    @property
    def finished(self) -> bool:
        """Whether there is nothing left of this part to draw."""
```

`fits` returning nought is how a fixed part too tall for what is left asks to
begin the next frame. A flowing part answers with as much as the rows *and* the
choices allow, which is where a menu's nine-to-a-frame now comes from.

### What the furniture is given

```python
class Edge(Enum):
    TOP = auto()
    FOOT = auto()


@dataclass(frozen=True)
class Summary:
    """What a furnishing is told about the frame it is drawing on."""

    title: str
    address: PageAddress | None
    index: int
    frames: int
    offered: Sequence[FooterItem]


class Furnishing(Protocol):
    edge: Edge
    rows: int

    def draw(self, canvas: Canvas, at: int, page: Summary) -> None:
        """Draw this band, at the row the layout has reserved for it."""
```

`offered` is assembled by the layout: what the parts named, then the shortcuts,
the movement keys and the way home. A prompt furnishing hands that to
`render_footer` and nothing else has to know the order.

A furnishing returns nothing. It claims no keys, because the keys it names
belong to the layout or to the parts.

### The geometry stops being constant

Furniture as bands docked to the top and foot means the content gets what they
leave. `CONTENT_FIRST_ROW` and `CONTENT_ROWS` become derived rather than fixed,
which settles whether the footer may be more than one row — it may, at the cost
of a content row, and the arithmetic says so rather than a constant needing to
be edited.

It also removes a reason to reach into the framework:
`weather_viewdata/search.py` imports `CONTENT_FIRST_ROW` to say which row its
field sits on, and a part is told where it begins.

### Two levels of furniture

A service sets its furniture once, which is what gives a site its character; a
page overrides it where it has reason — red rules on a page that does something
irreversible. The application holds what a service settles once, so the default
belongs there and the override on `PageLayout`.

Two levels and no cascade. Several would make "why is this page that colour"
hard to answer, and that answer matters more than the flexibility.

**A caution.** A reader learns where the page number sits and what the rules
mean, and learns it once. The page number at the top right is where Prestel put
it, and a service that moves it makes its readers wrong about every other
service they have used. The framework should make the site-wide setting easy,
the per-page override deliberate, and the defaults worth keeping.

## Every page in the three services

The test of the design is not the four pages that prompted it but all of them.

| Shape | Where it is used | As parts |
|---|---|---|
| Menu, with a lead-in | Stardot's indexes, weather's menu, the calendar's | `[Once(preamble), Flowing(Menu(items))]` |
| Two columns, nothing chosen | contents, the words | `[Flowing(Listing(items))]` |
| Label and figure | who has called | `[Flowing(Figures(counts)), Every(footnote)]` |
| Lines said as given | Stardot's notices, the time now | `[Flowing(Lines(said))]` |
| Wrapped prose | the about page of all three | `[Flowing(Prose(document))]` |
| Entries several rows tall | forecast days, the symbol legend | `[Once(preamble), Every(headings), Flowing(days)]` |
| A grid drawn by cell | the calendar's month | `[Once(grid)]` |
| A heading on every frame | one post | `[Every(heading), Flowing(document)]` |
| A field typed into | search by name, search by position | `[Once(instructions), Once(form)]` |
| Two lists divided on purpose | the guide | `[Flowing(moving), Once(compass), Break(), Flowing(asking)]` |
| A masthead and nothing else | the title frames of Stardot and weather | `furniture=(), [Once(masthead), Once(words)]` |
| A farewell | all three | stays `farewell_page` |

Ten of the twelve are the model exactly as described. The title frames needed
something settled and the farewell stays a helper, both below; the guide is the
model too, at the cost of a deliberate change to where its compass sits.

### The compass is a part, and is never split

The guide draws a compass at the *foot* of its first frame, where the rows
above leave room. As a part it is drawn where it lands, immediately under the
keys above it:

    [ Flowing(moving_keys), Once(compass), Break(), Flowing(asking_keys) ]

That changes what the page looks like, and the change is meant. A compass held
to the foot of the frame is a rule about where a thing sits, and a rule about
where one particular thing sits is the beginning of a layout language. The
compass is a few rows of graphics; it can be included in content like any other
few rows of graphics.

What the compass does need is already there. **A part that does not flow is
drawn whole or moved on**, so four rows of compass either fit where they land
or begin the next frame, and are never divided between two. That rule was
stated for parts too tall for what is left; the compass is what makes it worth
stating, because a compass split across a frame boundary would be four rows of
meaningless blocks.

**Keeping a part with the one after it is a different thing, and is not
wanted.** A heading drawn at the foot of a frame with its list beginning
overleaf is the case that would need it, and the framework already prefers the
opposite: `_capacity` lets a lead-in have a frame to itself and starts the
entries on the next, deliberately, rather than squeezing one entry in beneath
it. Nothing in the workspace asks for keep-with-next, so it is not here.

### A masthead is a page with no furniture

The title frames of Stardot and weather draw no header, no rules and no footer.
Under this design that is `furniture=()`, which is a value rather than a
special case — where today it means not calling `draw_chrome`, and building the
`Page` by hand.

### `follows`, and the key that reaches it

`Page.follows` says where `#` leads once a page's frames have run out, which is
what makes a title frame an invitation rather than a dead end. The session
tries the next frame first and falls through to `follows`, so the key must be
in `PageFrame.moves` for that to be reached at all. Today the title frame knows
this and builds `moves` by hand:

```python
moves = frozenset({NEXT_FRAME_KEY, CONVENTIONAL_NEXT_FRAME_KEY})
```

`follows` belongs on `PageLayout`, and setting it should add those keys: there
is somewhere to go on to, which is the only question `moves` answers. A service
would then say where a title frame leads without knowing how the session
reaches it.

`Page.hang_up` belongs on `PageLayout` for the same reason, and asks nothing
further.

### A page where every part is empty

One frame, with furniture and nothing between the rules. `Template` guarantees
this today with `batches or [()]`; the layout has to say so too, since a page
that answered with no frames at all could not be shown.

## What it would cost

23 construction sites change shape. A menu today:

```python
Menu(title=SERVICE_NAME, entries=items, home=app.index, empty="Nothing yet.").build(address)
```

and as a layout of parts:

```python
PageLayout(
    title=SERVICE_NAME,
    home=app.index,
    parts=[Flowing(Menu(entries=items, empty="Nothing yet."))],
).build(address)
```

One line longer, and it says which half is which. `Menu` keeps only what it
needs to format a sequence.

Nothing about the division changes. Sixteen items are still nine on the first
frame and seven on the second, the digits still restart at 1 so that no entry
is shown which cannot be chosen, and nine is still the limit because a reader
chooses with one keypress rather than because ten rows of two will not fit.

The alternative is to keep `Menu(title=..., entries=..., home=...)` as it is and
have it construct both halves. That leaves the call sites alone and hides the
split, which defeats the purpose for anyone whose content is not a sequence.

## What it replaces

`viewdata/typesetting.py` divides rendered rows between frames; `Template`
divides entries between frames. Both are the flowing rule written twice, and
they had diverged: one stopped at twenty-six frames and said so, the other
built a twenty-seventh and raised `ValueError` out of `frame_letter`. That is
fixed, but two implementations of one idea will diverge again. Under
fill-and-furnish exactly one pass counts frames, so the limit can only be
written once.

`Form` is already most of the part protocol. It has `rows`, `draw(canvas)`,
`choices()` and `accepts(key)`: it occupies a row range, draws itself,
contributes keys that lead somewhere, and answers keypresses. It reached that
shape independently, for a page that types rather than a page that lists, which
is the strongest evidence the seam is real — and it shows the join in the wrong
place today, a form hanging off `PageFrame` as a special case when it is one
kind of part among several.

## What this is not

**Not a widget toolkit.** A frame is a still picture plus a mapping from keys
to addresses, computed once and sent down a 1200-baud line. There is nothing
for per-widget event handling to attach to, and the session already owns what
happens when a key arrives.

**Not a second placement engine.** `viewdata/composition.py` places things
within a frame and knows what attributes cost in cells. Parts are stacked down
the frame, and nothing here arranges anything side by side.

**Not borrowed from terminal UI frameworks.** Textual and its relatives lay out
into one continuous viewport and scroll it; the problem here is to break into
discrete frames, each carrying its own furniture and keys, with no scrolling
anywhere. What does transfer is docking a header and a footer and giving the
rest to content, which is the furniture-and-content split itself.

## Risks

**A protocol got wrong is worse than a class with too many knobs.** `Offer`
carries three things because twelve shapes wanted three; a thirteenth may want
a fourth, and each addition is a change to every implementation rather than a
default on one class.

**Capacity becomes shared knowledge.** `_capacity` and `_divide` hold the
arithmetic in one place today. Split across parts, an off-by-one writes over
the rule at the foot of the frame.

**A layout engine is a large thing to build for twenty-five pages.** The
version worth having is the smallest the evidence demands: four kinds of part,
concatenation where they flow, furniture docked at two edges, no side-by-side
arrangement, no styling language, no units. Three things would say it had gone
wrong: a second axis, a way of expressing proportions, or a rule about where
one particular part must sit. The last of those was nearly added for the
guide's compass and was refused; the first two are where LaTeX's float
parameters came from.

**Names.** `Part`, `Placing`, `Room`, `Offer`, `Summary`, `Furnishing`, `Edge`,
and the four kinds of part are all proposals.

## What is settled and what is not

Settled: the bottom row is the footer, and the prompt, the command line and the
countdown are three things that appear on it. Furniture and content are
separable, and the evidence is six pages: five that draw their own furniture,
and one that pretends to be a sequence to obtain it. Frames are filled and then furnished, in that order,
because only the furniture needs to know how many there turned out to be.
Content is a list of parts of four kinds; where several flow they follow one
another and nothing arbitrates between them. Furniture is bands docked at two
edges, set once for a service and overridden by a page, which makes the
content's row range derived rather than constant. Content parts claim and
furniture parts report, which is why they are two protocols.

Every shape in the three services is expressible. A masthead is a page with no
furniture, `follows` belongs on the layout and brings the next-frame keys with
it, and the guide's compass is an ordinary part, drawn where it lands rather
than held to the foot of the frame -- a change to that page's appearance,
accepted so that no rule about where one particular thing sits has to exist.

Not settled: the names above; whether the 23 call sites change or keep a
convenience form; and whether `Placing` should be an iterator in fact as well
as in shape, which is a question about how a part that has been half drawn is
represented rather than about what the design does.
