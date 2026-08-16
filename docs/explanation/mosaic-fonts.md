# Mosaic fonts

Explanation: setting a line of text in outsized mosaic letters, why a font format
of Sextile's own is warranted, and why proportional spacing is required rather
than merely nicer. The API is in {py:mod}`sextile.viewdata.lettering` and
{py:mod}`sextile.viewdata.font`.

## Constraints, measured

- A cell is 2 blocks across and 3 down; a frame is 80 × 72 blocks, 78 across in
  practice, because a graphics attribute takes a cell on every row a picture
  spans. See {doc}`graphics` and {doc}`../reference/viewdata-encoding`.
- The three block rows are 3, 4 and 3 scanlines tall, so vertical spacing is
  inherently uneven and not worth correcting.
- There is no alpha-black attribute, so dark lettering is a lit field with
  letter-shaped holes — `block_runs(..., inverted=True)` — costing one attribute
  a row and no background attributes at all.

## Three ways to space

Fixed advances every glyph by the same width — what a column of figures needs and
the only spacing a page can reckon in its head. Proportional advances each glyph
by its own width. Kerned lets glyphs overlap, so the arm of a `T` may sit over
the tail of an `A`; at this resolution a block is a large fraction of a letter and
the row only 78 blocks wide, so a block recovered on each pair is worth having.

The shipped `grotesque` face, which has lower-case glyphs, sets each word three
ways, the row saying which. `AVATAR` is the kerning case: its `A`/`V` and `A`/`T`
pairs lean into one another, so kerned takes 16 cells against 18 proportional and
23 fixed.

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


def _spelled(word: str) -> Custom:
    tall = rows_needed(_FACE)

    def draw(canvas: Canvas, row: int) -> None:
        for index, (label, spacing) in enumerate(_SPACINGS):
            top = row + index * (tall + 1)
            layout = Composition()
            layout.text(top, 0, label, style=Style(colour=Colour.WHITE))
            lettering.place(layout, top, word, _FACE, Colour.YELLOW, column=13, spacing=spacing)
            layout.draw(canvas)

    return Custom(rows=3 * (tall + 1), draw=draw)


router = PageRouter()


@router.page("1", name="kerning", title="Kerning")
async def kerning(request: PageRequest) -> Page:
    return PageLayout(parts=[OnOneFrame(_spelled("AVATAR"))]).build(request)


@router.page("2", name="proportional", title="Proportional")
async def proportional(request: PageRequest) -> Page:
    return PageLayout(parts=[OnOneFrame(_spelled("million"))]).build(request)


app = Sextile(name="Fonts", pages=[*router])
```

`million` is the proportional case: the narrow `i`, `l` and `m` take 14 cells set
proportionally against 27 fixed, since a fixed face pays for its widest glyph on
every letter. There is nothing left for kerning to close, so kerned is 14 too.

```{sextile-frame}
:page: "2"

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Composition, Style
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font
from sextile.viewdata.lettering import Spacing, rows_needed

_FACE = load_font("grotesque")
_SPACINGS = [("Fixed", Spacing.FIXED), ("Proportional", Spacing.PROPORTIONAL), ("Kerned", Spacing.KERNED)]


def _spelled(word: str) -> Custom:
    tall = rows_needed(_FACE)

    def draw(canvas: Canvas, row: int) -> None:
        for index, (label, spacing) in enumerate(_SPACINGS):
            top = row + index * (tall + 1)
            layout = Composition()
            layout.text(top, 0, label, style=Style(colour=Colour.WHITE))
            lettering.place(layout, top, word, _FACE, Colour.YELLOW, column=13, spacing=spacing)
            layout.draw(canvas)

    return Custom(rows=3 * (tall + 1), draw=draw)


router = PageRouter()


@router.page("2", name="proportional", title="Proportional")
async def proportional(request: PageRequest) -> Page:
    return PageLayout(parts=[OnOneFrame(_spelled("million"))]).build(request)


app = Sextile(name="Fonts", pages=[*router])
```

Measured with the shipped `acorn` face, the same difference decides whether a
banner fits the row at all:

| | blocks | cells, with the attribute | fits on a row? |
|---|---|---|---|
| `BBC CEEFAX`, fixed | 80 | 41 | no |
| `BBC CEEFAX`, proportional | 66 | 34 | yes |
| `BBC CEEFAX`, kerned | 64 | 33 | yes |
| `STARDOT`, fixed | 55 | 29 | yes |
| `STARDOT`, proportional | 48 | 25 | yes |
| `STARDOT`, kerned | 45 | 24 | yes |

A fixed-width 8 × 8 face cannot draw the Ceefax banner — it is over by a cell —
where a proportional one draws it with five cells to spare. The advance belongs to
the font, not the renderer: trimming at render time would re-decide it on every
frame and give a space no width at all, so a font carries a fixed advance for the
face and an advance for each glyph.

## A boxed banner

`lettering.boxed` sets a word in a coloured box fitted round it, in whatever face
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


app = Sextile(name="Fonts", pages=[*router])
```

## The faces shipped

`font_names()` lists them; each is measured by how many rows of the frame it
takes.

| rows | faces |
|---|---|
| 1 | `3x3-mono` |
| 2 | `arcade`, `pixelplace` |
| 3 | `acorn`, `boldbash`, `console`, `console-bold`, and others |
| 4 | `grotesque`, `scientifica`, and their variants |
| 5 | `pixeloperator` and its variants |
| 6 | `garland` |

## A format of Sextile's own

`font.read_font`/`write_font` read and write a human-readable, dependency-free
format, because none of the importable bitmap formats carries the thing most
needed — a per-glyph advance in blocks — and a vendored font must be reviewed like
any other file. Glyphs are named by code point, not by the character, so a space,
`#` and `.` need no quoting in a file whose picture rows are drawn in `#` and `.`.

## Provenance

Every vendored font is recorded in the repository's `NOTICE.md` with its source
and terms. Three sources were checked and none was what a summary of it said: the
"MIT fonts" are MIT in their source only, each font carrying its own Creative
Commons or SIL OFL terms. Check before vendoring, not after.
