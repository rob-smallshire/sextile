# Letter on a background

A how-to guide: set large lettering in front of a coloured panel, so the word
sits on a field rather than on the frame's black.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font

_FACE = load_font("acorn")

router = PageRouter()


@router.page("1", name="panel", title="Panel")
async def panel(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        layout = Composition()
        box = layout.panel(row, 18, width=20, colour=Colour.BLUE, rows=3)
        lettering.place(layout, Align.CENTRE, "NEWS", _FACE, Colour.CYAN, within=box)
        layout.draw(canvas)

    return PageLayout(parts=[OnOneFrame(Custom(rows=3, draw=draw))]).build(request)


app = Sextile(name="News", pages=[*router])
```

`Composition.panel(row, column, width=, colour=, rows=)` declares a coloured box
once and returns it; a run placed `within` that box inherits its background and
is centred in the box rather than on the frame. `Align.CENTRE` centres the
lettering horizontally within the panel; a column number places it instead.

For a masthead's full-width stripe, see {doc}`large-lettering`; for the panels,
alignment and the arithmetic a `Composition` checks before it draws, see
{doc}`compose-a-frame`. A coloured background costs three cells, since the
hardware has only `NEW_BACKGROUND` — {doc}`the graphics explanation
<../explanation/graphics>` gives the cost of each attribute.
