# Draw mosaics

A how-to guide: a picture and a chart, drawn in the block graphics a viewdata
frame affords — two blocks across a cell and three down.

```{sextile-frame}
:page: "6"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata.blocks import block_runs, icon
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.charting import bars
from sextile.viewdata.controls import Colour

router = PageRouter()

_ARROW = icon(
    """
    ..#..
    .###.
    #####
    ..#..
    ..#..
    ..#..
    """
)

_RAINFALL = [0.2, 0.5, 0.9, 1.0, 0.6, 0.3]


@router.page("6", name="chart", title="Rainfall")
async def chart(request: PageRequest) -> Page:
    picture = _ARROW.cells()
    columns = block_runs(bars(_RAINFALL, across=12, down=9))

    def draw(canvas: Canvas, row: int) -> None:
        for offset, patterns in enumerate(picture):
            canvas.row(row + offset).mosaic(patterns, Colour.GREEN)
        for offset, patterns in enumerate(columns):
            canvas.row(row + len(picture) + 1 + offset).mosaic(patterns, Colour.CYAN)

    height = len(picture) + 1 + len(columns)
    return PageLayout(parts=[OnOneFrame(Custom(rows=height, draw=draw))]).build(request)


app = Sextile(name="Weather", pages=[*router])
```

`icon` reads a picture written as itself — anything that is not `#` is a block
that is off — and `Icon.cells()` turns it into the six-bit patterns a row of cells
holds. `block_runs` does the same for any grid of bits, so `bars(fractions,
across=, down=)` becomes a chart. Draw a row of patterns with `canvas.row(n).mosaic(
patterns, Colour.CYAN)`. For laying several pictures out relative to one another
use `Composition` and `Panel`; for a line instead of columns use `curve`.
