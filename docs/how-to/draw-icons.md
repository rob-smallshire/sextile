# Draw an icon

A how-to guide: a small picture in block graphics — two blocks across a cell and
three down — drawn from a shape written as itself.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata.blocks import icon
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour

router = PageRouter()

_ARROW = icon("""
   #
    #
######
    #
   #
""")


@router.page("1", name="arrow", title="Arrow")
async def arrow(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        for offset, patterns in enumerate(_ARROW.cells()):
            canvas.row(row + offset).mosaic(patterns, Colour.CYAN)

    return PageLayout(parts=[OnOneFrame(Custom(rows=_ARROW.rows, draw=draw))]).build(request)


app = Sextile(name="Graphics", pages=[*router])
```

`icon` reads a picture written as itself — anything that is not `#` is a block
that is off — and `Icon.cells()` gives the six-bit patterns a row of cells
holds. Draw a row of patterns with `canvas.row(n).mosaic(patterns,
Colour.CYAN)`, spending one cell of the row on the graphics colour attribute.

`turned()` gives a quarter turn anticlockwise, so four arrows are one icon drawn
four ways. `cells(inverted=True)` gives the Ceefax field — a solid colour with
letter-shaped holes — because the display has no black foreground, so a
black-on-cyan banner is cyan with the black background showing through; see
{doc}`../reference/display-semantics`. `read_bitmap` reads a monochrome bitmap
file into the same cells, for a picture too large to write by hand.

For laying several pictures out relative to one another use
{doc}`compose-a-frame`; for a bar or a line chart use {doc}`draw-charts`. The
cost of the colour attribute, and why a picture pays one cell on each row it
spans, is in {doc}`the graphics explanation <../explanation/graphics>`.
