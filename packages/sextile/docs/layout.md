# Laying out a page

Every page a service returns is built the same way: furniture round the edge of
each frame, and a list of parts down the middle. `PageLayout` holds both and
`build` turns them into a `Page`.

This describes what is there. [design.md](design.md#laying-out-a-page) says why
it is built this way, and what was tried and rejected.

## The shape of a frame

A frame is 24 rows of 40 cells. With the furniture a page gets unless it says
otherwise:

    row  0        header      the title, and the page number at the right
    row  1        rule
    rows 2-21     content     what the parts are drawn in
    row  22       rule
    row  23       footer      the prompt: which keys work on this frame

The content rows are not a constant. `content_rows(furniture)` returns what the
furniture leaves, so a page with no furniture has all 24 rows and a page with a
two-row prompt has 19.

## Building a page

```python
from sextile.formatting import Menu, MenuItem
from sextile.layout import Flow, PageLayout

PageLayout(
    title="LATEST POSTS",
    parts=[Flow(Menu(entries=posts))],
).build(request)
```

`PageLayout` takes:

| | |
|---|---|
| `title` | What the header calls the page. |
| `parts` | The content, in the order it appears down the frames. |
| `home` | Where `0` leads from every frame. An address, a `Shortcut` where the footer should call it something other than `index`, or None for no way home. |
| `shortcuts` | Keys offered on every frame, besides the digits and `0`. |
| `neighbours` | The pages either side of this one; given, wires `A`/`D`. Pass `request.neighbours`. |
| `item_noun` | What `A` and `D` move between, as the footer says it: `item_noun="post"` gives `previous post`. |
| `furniture` | The bands round the content. `DEFAULT_FURNITURE` unless given; `()` for a page that wants none. |
| `follows` | Where `#` leads once the frames have run out. Setting it also answers the next-frame keys. |
| `hang_up` | Whether the line drops once the page has been shown. |

`build(address)` returns the `Page`. Pass None for `address` where the page has
no number of its own, such as a notice given in reply to a number that answers
nothing: the title then has the header row to itself.

## The parts

Each part in the list is one of four kinds, and the order settles what sits
above what:

| | |
|---|---|
| `OnFirstFrame(part)` | Drawn one time, at its place in the order. |
| `OnEveryFrame(part)` | Drawn on every frame. |
| `Flow(part)` | Broken across as many frames as it takes. |
| `FrameBreak()` | Whatever follows begins on a new frame. |

```python
parts=[
    OnFirstFrame(Lines(said=("Stardot, for users of Acorn computers.", ""))),
    OnEveryFrame(Lines(said=("DAY   MAX   MIN",), colour=Colour.CYAN)),
    Flow(Menu(entries=posts)),
]
```

`OnFirstFrame` draws once, at its place in the order rather than always on
frame `a`: a fixed part before any flowing part lands on the first frame, but
one after a flowing part lands on whichever frame that flow finished on. The
name is the common case; the order is what settles it.

`OnEveryFrame` parts before the first flowing part are drawn where they stand.
Those after it have their rows reserved at the foot before the flowing part is
placed, and are then drawn under the content. A flowing part takes whatever rows
are left to it, so an `OnEveryFrame` part after one would otherwise never be
drawn.

Several flowing parts follow one another: the second begins in the row after
the first has finished, on whatever frame that is.

A `FrameBreak` that would divide nothing is ignored — one at either end of the
list, two together, or one on a frame with nothing yet drawn on it.

## The shapes ready to use

From `sextile.formatting`, each taking `entries` and an optional `empty`:

| | One entry is | Notes |
|---|---|---|
| `Menu` | a numbered line with detail beneath | nine to a frame, the reader choosing with one keypress |
| `Listing` | two columns, nothing numbered | the left column is set to the widest entry |
| `Figures` | a label and a right-aligned figure | for a page that reports rather than offers |
| `Lines` | one line, drawn as given | nothing is wrapped and nothing is moved |
| `Prose` | one row of wrapped running text | `Prose.of("First.", "Second.")` builds it from paragraphs |

`empty` is said in place of the entries where there are none. On a slow service
a frame must not come up empty and unexplained, because a reader cannot tell
that from a fault.

Two more parts are in `sextile.layout` rather than `formatting`, being drawings
rather than sequences:

| | |
|---|---|
| `Drawn(rows, draw)` | A part of a stated height, drawn cell by cell by `draw(canvas, row)`. For a picture, a grid, a masthead. |
| a `Form` | A field the reader types into. `Suggest` and `Fields` are parts, and a frame carries one. |

## The keys a frame answers

A frame's keys come from four places, and the layout gathers them:

- **the parts** — a `Menu`'s digits, which differ from frame to frame, and a
  form's suggestions, which change as the reader types;
- **`shortcuts`** — a key on every frame leading to a fixed address;
- **`home`** — `0`, unless a `Shortcut` puts it elsewhere;
- **movement** — `W` and `S` between frames, and the arrows for them, added
  where there is a frame to go to.

The prompt names all of them. `render_footer` sheds words when the row is
tight, so a `Shortcut` should put the short form of its `says` first:
`"index, or key another page"` shortens to `"index"` and then to `"0"`.

`A` and `D` step through the pages either side of this one in a sequence, and
`neighbours=request.neighbours` wires them: it offers whichever of
`previous`/`next` is not None and names them, with their cursor-key arrows, from
`viewdata.footer` so that every page describes those keys the same way.

```python
PageLayout(..., neighbours=request.neighbours, item_noun="post").build(request)
```

A page that offers some other key on `A` or `D` builds a `Shortcut` for it, and
`arrow=True` makes the matching cursor key lead there as well.

Whether an arrow should mean what its letter means is for the page to decide,
which is why `arrow` is a parameter. On a page with a coordinate field it should
not: `W` is West there, and an up arrow that typed a letter into a field would
be a defect.

## Furniture

`DEFAULT_FURNITURE` is a `Header`, a `Rule` at each end, and a `Prompt`. A
service sets its own once and a page overrides it where it has reason — red
rules on a page that does something irreversible:

```python
PageLayout(furniture=(), parts=[OnFirstFrame(Drawn(rows=ROWS, draw=masthead))])
```

Two levels, and no cascade. A reader learns where the page number sits once, so
the site-wide setting is the one to set, and a per-page override needs a reason.

## Writing a part of your own

The content inside a `OnFirstFrame`, `OnEveryFrame` or `Flow` is a `Drawable`: it draws as
much as the room allows and says what is left over.

```python
class Drawable(Protocol):
    def place(self, canvas: Canvas, room: Room) -> Placement: ...
```

`Room` carries `first_row`, `rows` and `choices` — how many of the digits `1-9`
are still unclaimed on this frame, which the whole frame shares however many
parts divide it.

`Placement` carries the `rows` used, an `Offer` of what the drawable claims, and
`rest`: what is left of the drawable for the next frame, or None when it is
finished. Returning nought rows and `self` requests a fresh frame, which is how
a drawable too tall for the room left is carried to the next frame whole rather
than split.

`Offer` carries `choices` — keys that lead somewhere — `named`, what the prompt
should say about them, and `form` where the drawable is one.

Most drawables are a sequence, and `Formatter` does the arithmetic for those. A
subclass says how tall an entry is and how to draw one:

```python
@dataclass(frozen=True, kw_only=True)
class ForecastTable(Formatter[Day]):
    rows_per_entry: ClassVar[int] = PICTURE_ROWS
    separation: ClassVar[int] = 1
    numbered: ClassVar[bool] = False

    today: date

    def draw_entry(self, canvas, row, entry, digit):
        draw_day(canvas, row, entry, self.today)
```

`separation` is blank rows between entries and not after the last of them.
`numbered` says whether entries take a digit, and `selecting_hint` what the
prompt says about choosing. A shape written along its rows subclasses
`RowFormatter` instead and writes `draw` and `draw_detail`, each given a
`RowWriter`.

A formatter that computes a column width from its entries must fix it once and
carry it into what it returns, or the columns will shift partway down the table.
`Listing` and `Figures` do this by computing the width only when they have none.

## Writing a furnishing of your own

A furnishing is a band docked to the top or the foot of every frame:

```python
class Furnishing(Protocol):
    @property
    def edge(self) -> Edge: ...
    @property
    def rows(self) -> int: ...
    def draw(self, canvas: Canvas, at: int, page: Summary) -> None: ...
```

`Summary` carries the `title`, the `address`, which frame this is (`index`),
how many there are (`frames`), and `offered` — every key that works on this
frame, assembled and in the order the prompt should try to name them.

A furnishing returns nothing and claims no keys. What it names belongs to the
layout or to the parts, and it is handed the assembled list rather than
composing one.

## When something does not fit

**A part taller than a whole frame** can never be placed, and `build` raises
`ValueError` rather than drawing nothing.

**A page past frame z** stops at `FRAMES_PER_PAGE`, twenty-six, and says
`TRUNCATION_NOTICE` on the last row of the last frame. A page's frames are
lettered `a` to `z` and there are no more letters.

**A page with nothing on it** is still one frame, with its furniture. A page
that answered with no frames could not be shown.

**Two parts carrying a form** on one frame raise `ValueError`. A frame has one
field to type into; `forms.Fields` composes several fields into one form.
