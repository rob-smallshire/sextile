# Compose a frame

A how-to guide: place runs, panels and lettering at positions with a
`Composition`, which checks the whole layout fits before it draws a cell.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition, Style
from sextile.viewdata.controls import Colour

router = PageRouter()


@router.page("1", name="board", title="Board")
async def board(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        layout = Composition()
        box = layout.panel(row, Align.START, width=39, colour=Colour.BLUE, rows=1)
        layout.text(row, Align.CENTRE, "DEPARTURES", style=Style(colour=Colour.YELLOW), within=box)
        layout.text(row + 2, 1, "PLATFORM", style=Style(colour=Colour.CYAN))
        layout.text(row + 2, Align.END, "TIME", style=Style(colour=Colour.CYAN))
        layout.draw(canvas)

    return PageLayout(parts=[OnOneFrame(Custom(rows=3, draw=draw))]).build(request)


app = Sextile(name="Station", pages=[*router])
```

`Composition.text(row, column, text, style=)` places a run at a position, where a
`Canvas` row writes left to right; a column may be a number or an `Align`
(`START`, `CENTRE`, `END`). `panel` declares a coloured box once, and a run
placed `within` it is aligned in the box rather than on the frame.
`layout.draw(canvas)` lays the whole thing down.

## The layout is checked, not searched

`Composition.draw` reports whether the layout is possible — naming the row, the
column and the arithmetic in a `DoesNotFit` — before a cell is written, and draws
nothing if any row fails, so a bad layout never leaves half a frame on a screen.
A coloured run reserves the cell before it for its colour attribute, which is
why `PLATFORM` begins at column 1 and not column 0; two runs in one style cost
one attribute, not two. Why placement is a single
left-to-right pass rather than a search is in {doc}`the graphics explanation
<../explanation/graphics>`.

## Which to reach for

| Use | For |
|---|---|
| `Canvas.row(n)`, a `RowWriter` | text and mosaics that run left to right along one row |
| `Composition` | runs placed at positions, panels, alignment, and a checked fit |

Draw a row at a time with {doc}`draw-a-custom-frame`; set lettering on a panel
with {doc}`letter-on-a-background`. The compositor's own API is
{py:mod}`sextile.viewdata.composition`.
