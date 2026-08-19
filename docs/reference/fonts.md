# Fonts

Reference: the built-in mosaic font faces, one specimen to a face. The
catalogue is drawn from `font_names()`; each specimen sets upper case, lower
case and digits, with the face's name, height in rows, whether it carries lower
case, and its provenance beneath. The API is {py:mod}`sextile.viewdata.font`
and {py:mod}`sextile.viewdata.lettering`; the lettering recipe is
{doc}`../how-to/large-lettering`.

```{sextile-frame}
:catalogue:

from sextile import Custom, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font, font_names
from sextile.viewdata.lettering import Spacing, cells_needed, rows_needed

_LINES = ("HAMBURGERS", "hamburgers", "0123456789")


def _fit(word: str, face: object) -> str:
    while word and cells_needed(word, face, spacing=Spacing.PROPORTIONAL) > 38:
        word = word[:-1]
    return word


def _specimen(face: object) -> Custom:
    tall = rows_needed(face)

    def draw(canvas: Canvas, row: int) -> None:
        for index, line in enumerate(_LINES):
            layout = Composition()
            lettering.place(
                layout, row + index * (tall + 1), _fit(line, face), face,
                Colour.WHITE, column=1, spacing=Spacing.PROPORTIONAL,
            )
            layout.draw(canvas)

    return Custom(rows=3 * tall + 2, draw=draw)


def _handler(face: object):
    async def handler(request: PageRequest) -> Page:
        return PageLayout(parts=[OnOneFrame(_specimen(face))], numbered=False).build(request)

    return handler


def _brief(text: str) -> str:
    return text.split(",")[0].split(" http")[0].split(" (")[0].strip()


router = PageRouter()
captions: dict[str, str] = {}
for _number, _name in enumerate(sorted(font_names()), start=1):
    _face = load_font(_name)
    _rows = rows_needed(_face)
    _low = "lower case" if all(c in _face for c in "abcdefghijklmnopqrstuvwxyz") else "caps only"
    captions[str(_number)] = (
        f"{_name} — {_rows} row{'s' if _rows != 1 else ''}, {_low}, "
        f"{_brief(_face.source)}, {_brief(_face.terms)}"
    )
    router.page(str(_number), name=_name, title=_name)(_handler(_face))

app = Sextile(name="Fonts", pages=[*router])
```

`load_font(name)` loads a face by name and `font_names()` lists them all. Each
face is vendored and recorded in `NOTICE.md` with its source and licence; check
those before vendoring another, since a summary is not the licence — the "MIT
fonts" are MIT in their repository only, each font carrying its own Creative
Commons or SIL Open Font Licence terms.
