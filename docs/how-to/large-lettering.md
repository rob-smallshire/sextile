# Large lettering

A how-to guide: set a word in an outsized face, on a stripe of colour, for a
masthead.

```{sextile-frame}
:page: "7"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.lettering import Spacing

router = PageRouter()

_FACE = load_font("boldbash")


@router.page("7", name="masthead", title="Weather")
async def masthead(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        layout = Composition()
        stripe = layout.panel(
            row, Align.START, colour=Colour.BLUE, width=COLUMNS - 1, rows=lettering.rows_needed(_FACE)
        )
        lettering.place(
            layout, Align.CENTRE, "WEATHER", _FACE, Colour.YELLOW, within=stripe, spacing=Spacing.KERNED
        )
        layout.draw(canvas)

    return PageLayout(
        parts=[OnOneFrame(Custom(rows=lettering.rows_needed(_FACE), draw=draw))],
    ).build(request)


app = Sextile(name="Weather", pages=[*router])
```

`load_font(name)` loads one of the faces `font_names()` lists; `boldbash` has the
heavy strokes a title wants. `lettering.place` sets the text into a `Composition`,
centred within the `panel` it is given, and `layout.draw(canvas)` lays the letters
down as mosaic cells. Use `boxed` to draw the same word in a ruled box, and
`Spacing.KERNED` to let the letters lean together where the row is narrow.
