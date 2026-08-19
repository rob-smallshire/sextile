# Draw a custom frame

A how-to guide: when no layout has the shape you want, draw the content yourself,
cell by cell.

```{sextile-frame}
:page: "5"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour

router = PageRouter()

_SWATCHES = [Colour.RED, Colour.GREEN, Colour.YELLOW, Colour.CYAN, Colour.WHITE]


@router.page("5", name="palette", title="Colours")
async def palette(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        for offset, colour in enumerate(_SWATCHES):
            canvas.row(row + offset).text(colour.name, colour)

    return PageLayout(
        parts=[OnOneFrame(Custom(rows=len(_SWATCHES), draw=draw))],
    ).build(request)


app = Sextile(name="Palette", pages=[*router])
```

A `Custom` part owns a stated number of rows and is handed the `Canvas` and the
row it begins on. `canvas.row(n)` gives a writer for that row; `.text(string,
Colour.RED)` appends text, spending a cell on a colour attribute where the colour
changes. Reach for `Custom` only for a picture no layout has a shape for — a
chart, a masthead, a grid — and prefer a layout otherwise.

For runs placed at positions with a checked fit, rather than a row at a time, use
{doc}`compose-a-frame`; for a sequence drawn its own way, a
{doc}`a-custom-part`. The parts model is {doc}`../reference/layout`, and the cost
of the colour attribute a row spends is in {doc}`../explanation/graphics`.
