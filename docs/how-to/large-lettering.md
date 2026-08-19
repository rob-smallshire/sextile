# Large lettering

A how-to guide: set a word in an outsized mosaic face, on a stripe of colour,
for a masthead.

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

`load_font(name)` loads one of the faces `font_names()` lists — {doc}`the
catalogue <../reference/fonts>` sets a specimen of each, and `boldbash` has the
heavy strokes a title wants. `lettering.place` sets the text into a
`Composition`, centred within the `panel` it is given, and `layout.draw(canvas)`
lays the letters down as mosaic cells. Set the word in front of a background
instead with {doc}`letter-on-a-background`, or in a ruled box with
{doc}`boxed-banners`.

## Choose the spacing

`Spacing.FIXED` advances every glyph by the same width, `PROPORTIONAL` by each
glyph's own width, and `KERNED` lets a pair lean together. `AVATAR` is the
kerning case: its `A`/`V` and `A`/`T` pairs overlap, so kerned takes 16 cells
against 18 proportional and 23 fixed.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Composition, Style
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font
from sextile.viewdata.lettering import Spacing, rows_needed

_FACE = load_font("grotesque")
_SPACINGS = [("Fixed", Spacing.FIXED), ("Proportional", Spacing.PROPORTIONAL), ("Kerned", Spacing.KERNED)]

router = PageRouter()


@router.page("1", name="spacing", title="Spacing")
async def spacing(request: PageRequest) -> Page:
    tall = rows_needed(_FACE)

    def draw(canvas: Canvas, row: int) -> None:
        for index, (label, kind) in enumerate(_SPACINGS):
            top = row + index * (tall + 1)
            layout = Composition()
            layout.text(top, 0, label, style=Style(colour=Colour.WHITE))
            lettering.place(layout, top, "AVATAR", _FACE, Colour.YELLOW, column=13, spacing=kind)
            layout.draw(canvas)

    return PageLayout(parts=[OnOneFrame(Custom(rows=3 * (tall + 1), draw=draw))]).build(request)


app = Sextile(name="Fonts", pages=[*router])
```

`cells_needed(word, face, spacing=)` measures a word without drawing it, so a
page can pick a spacing that fits the row. Why proportional at all, and why the
face carries the advance rather than the renderer, is in {doc}`the mosaic-fonts
explanation <../explanation/mosaic-fonts>`.

## A face of your own

`read_font` and `write_font` read and write a human-readable, dependency-free
text format that carries a per-glyph advance in blocks — the measurement the
importable bitmap formats leave out. Name glyphs by code point and draw each in
`#` and `.`; see {py:mod}`sextile.viewdata.font` for the format and
{doc}`../reference/fonts` for the faces already shipped.
