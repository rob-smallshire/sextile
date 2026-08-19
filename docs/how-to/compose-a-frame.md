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

_BOARD = [
    ("Aberdeen", "4", "10:15"), ("Bristol", "9", "10:22"), ("Carlisle", "1", "10:40"),
    ("Dover", "6", "10:51"), ("Edinburgh", "3", "11:05"), ("Falmouth", "7", "11:18"),
    ("Glasgow", "2", "11:30"),
]


@router.page("1", name="board", title="Departures")
async def board(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        layout = Composition()
        head = layout.panel(row, Align.START, width=39, colour=Colour.BLUE, rows=1)
        layout.text(row, Align.CENTRE, "KINGS CROSS", style=Style(colour=Colour.YELLOW), within=head)
        for column, heading in ((1, "TO"), (Align.CENTRE, "PLAT"), (Align.END, "TIME")):
            layout.text(row + 2, column, heading, style=Style(colour=Colour.CYAN))
        for offset, (place, plat, time) in enumerate(_BOARD):
            line = row + 4 + offset * 2
            layout.text(line, 1, place, style=Style(colour=Colour.WHITE))
            layout.text(line, Align.CENTRE, plat, style=Style(colour=Colour.WHITE))
            layout.text(line, Align.END, time, style=Style(colour=Colour.GREEN))
        foot = layout.panel(row + 18, Align.START, width=39, colour=Colour.MAGENTA, rows=1)
        layout.text(row + 18, Align.CENTRE, "Times are provisional", style=Style(colour=Colour.WHITE), within=foot)
        layout.draw(canvas)

    return PageLayout(parts=[OnOneFrame(Custom(rows=19, draw=draw))]).build(request)


app = Sextile(name="Station", pages=[*router])
```

`Composition.text(row, column, text, style=)` places a run at a position, where a
`Canvas` row writes only left to right; a column may be a number or an `Align`
(`START`, `CENTRE`, `END`). Each row's destination, platform and time are placed
at `START`, `CENTRE` and `END`, so the three columns line up however long the
names are. `panel` declares a coloured box once — the blue masthead and the
magenta footer — and a run placed `within` it is aligned in the box rather than on
the frame.

## The layout is checked, not searched

`Composition.draw` reports whether the layout is possible — naming the row, the
column and the arithmetic in a `DoesNotFit` — before a cell is written, and draws
nothing if any row fails, so a bad layout never leaves half a frame on a screen.
A coloured run reserves the cell before it for its colour attribute, which is why
the destinations begin at column 1 and not column 0; two runs in one style cost
one attribute, not two. Why placement is a single left-to-right pass rather than a
search is in {doc}`the graphics explanation <../explanation/graphics>`.

## Which to reach for

| Use | For |
|---|---|
| `Canvas.row(n)`, a `RowWriter` | text and mosaics that run left to right along one row |
| `Composition` | runs placed at positions, panels, alignment, and a checked fit |

Draw a row at a time with {doc}`draw-a-custom-frame`; set lettering on a panel
with {doc}`letter-on-a-background`. The compositor's own API is
{py:mod}`sextile.viewdata.composition`.
