# Draw a chart

A how-to guide: a bar or a line chart in block graphics, from values given as
fractions of the height.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata.blocks import block_runs
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.charting import bars
from sextile.viewdata.controls import Colour

router = PageRouter()

_RAINFALL = [0.2, 0.5, 0.9, 1.0, 0.6, 0.3]


@router.page("1", name="chart", title="Rainfall")
async def chart(request: PageRequest) -> Page:
    columns = block_runs(bars(_RAINFALL, across=12, down=9))

    def draw(canvas: Canvas, row: int) -> None:
        for offset, patterns in enumerate(columns):
            canvas.row(row + offset).mosaic(patterns, Colour.CYAN)

    return PageLayout(parts=[OnOneFrame(Custom(rows=len(columns), draw=draw))]).build(request)


app = Sextile(name="Weather", pages=[*router])
```

`bars(values, across=, down=)` takes each value as a fraction of the height —
deciding what the top and bottom mean is the caller's — and returns a grid of
bits. `block_runs` turns any such grid into the six-bit mosaic patterns a row of
cells holds, which `canvas.row(n).mosaic(patterns, colour)` draws.

`curve` draws a line instead of columns: it lights one block to a column and
breaks the line at a missing value, rather than filling the blocks between two
heights, so the line reads as a line and not a wall. For a fixed picture rather
than data see {doc}`draw-icons`; for the cost of the colour attribute see
{doc}`the graphics explanation <../explanation/graphics>`.
