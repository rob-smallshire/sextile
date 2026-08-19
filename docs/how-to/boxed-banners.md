# Boxed banners

A how-to guide: set a word in a coloured box fitted round it, in whatever face
it is given.

```{sextile-frame}
:page: "2"
:show-code:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font

router = PageRouter()


@router.page("2", name="banner", title="Banner")
async def banner(request: PageRequest) -> Page:
    def draw(canvas: Canvas, row: int) -> None:
        layout = Composition()
        lettering.boxed(layout, row, "NEWS", load_font("boldbash"), Colour.YELLOW, Colour.BLUE)
        lettering.boxed(layout, row + 6, "NEWS", load_font("acorn"), Colour.CYAN, Colour.MAGENTA)
        layout.draw(canvas)

    return PageLayout(parts=[OnOneFrame(Custom(rows=11, draw=draw))]).build(request)


app = Sextile(name="News", pages=[*router])
```

`lettering.boxed(layout, row, word, face, text_colour, box_colour)` measures the
word, draws the box to fit, and sets the word inside it. The two faces above
draw the same word to different widths, because a face carries its own advances;
{doc}`the catalogue <../reference/fonts>` sets a specimen of each.

## Fit a banner to the row

The spacing decides whether a banner fits the forty columns at all. Measured
with the shipped `acorn` face:

| | blocks | cells, with the attribute | fits on a row? |
|---|---|---|---|
| `BBC CEEFAX`, fixed | 80 | 41 | no |
| `BBC CEEFAX`, proportional | 66 | 34 | yes |
| `BBC CEEFAX`, kerned | 64 | 33 | yes |
| `STARDOT`, fixed | 55 | 29 | yes |
| `STARDOT`, proportional | 48 | 25 | yes |
| `STARDOT`, kerned | 45 | 24 | yes |

A fixed-width face cannot draw the Ceefax banner — it is over by a cell — where
a proportional one draws it with five cells to spare. Measure a word with
`cells_needed(word, face, spacing=)` before drawing it, and set the spacing with
`Spacing`; {doc}`large-lettering` shows the three spacings side by side, and
{doc}`the mosaic-fonts explanation <../explanation/mosaic-fonts>` says why the
advance belongs to the font.
