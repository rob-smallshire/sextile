# Graphics

Explanation: the block mosaics, the compositor that places them, and why
placement is exact rather than a search. The API is in {py:mod}`sextile.viewdata.blocks`,
{py:mod}`sextile.viewdata.composition` and {py:mod}`sextile.viewdata.charting`.

## The block grid

A mosaic cell is a 2 × 3 grid of blocks, so a frame of 40 × 24 cells is 80 × 72
blocks — 78 across in practice, because a graphics colour attribute occupies a
cell and attributes reset at the start of every row, so a picture pays one cell
on each row it spans. `charset.mosaic_code` turns a six-bit pattern into a cell
code and `charset.mosaic_pattern` reads it back.

## An icon

`icon` reads a picture written as itself — anything that is not `#` is a block
that is off — and `Icon.cells()` gives the six-bit patterns a row of cells holds.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata.blocks import icon
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour

_ARROW = icon("""
   #
    #
######
    #
   #
""")

router = PageRouter()


@router.page("1", name="arrow", title="Icon")
async def arrow(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        for offset, patterns in enumerate(_ARROW.cells()):
            canvas.row(row + offset).mosaic(patterns, Colour.CYAN)

    return PageLayout(parts=[OnOneFrame(Custom(rows=_ARROW.rows, draw=draw))]).build(request)


app = Sextile(name="Graphics", pages=[*router])
```

`turned()` gives a quarter turn anticlockwise, which is how four arrows are one
arrow; `cells(inverted=True)` gives the Ceefax field — a solid colour with
letter-shaped holes, since the SAA5050 has no black foreground and a black-on-cyan
banner is really cyan with the black background showing through. The whole padded
field is inverted, not the glyph alone, or the field has a ragged edge.

## A composition with a panel

A `Composition` places runs at positions, where a `Canvas` writes left to right.
A `panel` is a coloured box declared once; a run drawn `within` it inherits the
background and is centred in the box rather than on the frame.

```{sextile-frame}
:page: "2"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font

_FACE = load_font("acorn")

router = PageRouter()


@router.page("2", name="panel", title="Panel")
async def panel(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        layout = Composition()
        box = layout.panel(row, 18, width=20, colour=Colour.BLUE, rows=3)
        lettering.place(layout, Align.CENTRE, "NEWS", _FACE, Colour.CYAN, within=box)
        layout.draw(canvas)

    return PageLayout(parts=[OnOneFrame(Custom(rows=3, draw=draw))]).build(request)


app = Sextile(name="Graphics", pages=[*router])
```

## A chart

`charting.bars` takes values as fractions of the height, never as data — deciding
what the top and bottom mean is the caller's — and returns a grid `block_runs`
turns into mosaic cells.

```{sextile-frame}
:page: "3"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata.blocks import block_runs
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.charting import bars
from sextile.viewdata.controls import Colour

_SERIES = [0.3, 0.6, 1.0, 0.8, 0.5, 0.2]

router = PageRouter()


@router.page("3", name="chart", title="Chart")
async def chart(request: PageRequest) -> Page:
    columns = block_runs(bars(_SERIES, across=12, down=9))

    def draw(canvas: Canvas, row: int) -> None:
        for offset, patterns in enumerate(columns):
            canvas.row(row + offset).mosaic(patterns, Colour.GREEN)

    return PageLayout(parts=[OnOneFrame(Custom(rows=len(columns), draw=draw))]).build(request)


app = Sextile(name="Graphics", pages=[*router])
```

A chart lights one block to a column and breaks the line at a missing value,
rather than filling the blocks between two heights, so the line reads as a line
and not a wall.

## What a style costs

`Style` carries every attribute the hardware has, because the transitions are not
uniform — which is the argument for handing a compositor a style rather than
writing controls by hand.

| Change | Cells | Note |
|---|---|---|
| foreground colour | 1 | also chooses the character set |
| entering or leaving graphics | 1 | the colour attribute does both |
| contiguous ↔ separated | 1 | chooses the set; a colour attribute enters it |
| flash / steady | 1 | |
| double height / normal | 1 | and takes the row below |
| hold / release graphics | 1 | |
| a background | 3 | choose the colour, promote it, choose the foreground again |
| a background matching the foreground | 2 | nothing to change back to |
| back to black | 1 | `BLACK_BACKGROUND` |
| conceal | 1 | and cannot be undone |

A background costs three cells because the hardware has no set-background, only
`NEW_BACKGROUND`, which makes the current foreground the background;
`CONCEAL` has no counterpart, so a composition asked to turn it off is refused
rather than drawn wrongly; double height places its run on the row below as well,
which is how the SAA5050 draws the bottom halves. The measured basis is in
{doc}`../reference/viewdata-encoding`.

## Exact, not clever

The compositor reports whether a layout is possible — naming the row, the column
and the arithmetic — before a cell is written, and draws nothing if any row
fails, so a bad layout never leaves half a frame on a screen. Two runs in one
style cost one attribute, not two, because it detects there is no text between
them. And placement is a single left-to-right pass rather than a search: an
attribute displays as a blank, and a blank in graphics is the no-blocks mosaic,
so an attribute may sit anywhere in the gap before its run and there is nothing
to search for. It becomes a search only if runs are free to move, which is a
different feature.
