"""A frame as HTML, drawn with the Bedstead font.

`render_html` turns the runs `styled_cells` yields into a `<pre>` of `ROWS` rows,
one `<span>` per run, its style carried by CSS classes rather than inline styles
so a page can restyle the lot. Each row is exactly `COLUMNS` cells, the width the
walk yields. Contiguous mosaics are the Symbols for Legacy Computing sextants, as
the terminal render uses; separated mosaics are Bedstead's Private Use glyphs,
which no terminal font has. The stylesheet is shipped beside this module.
"""

from collections.abc import Callable
from html import escape
from importlib.resources import files

from sextile.viewdata.ansi import sextant
from sextile.viewdata.charset import mosaic_code
from sextile.viewdata.display import CellStyle, StyledRun, styled_cells
from sextile.viewdata.frame import Frame

__all__ = [
    "render_html",
    "stylesheet",
]


def render_html(frame: Frame, *, css_class: str = "viewdata") -> str:
    """A frame as an HTML `<pre>`, one `<span>` a run, styled by class.

    Args:
        frame: The built frame to draw.
        css_class: The class set on the `<pre>`, which the shipped stylesheet
            styles. The default is what `stylesheet` targets.

    Returns:
        A `<pre>` of `ROWS` lines, each exactly `COLUMNS` cells wide. The classes
        on the spans -- `fg-<colour>`, `bg-<colour>`, and `flash`/`conceal`/`dh`
        where the style asks for them -- are the ones the stylesheet defines.
    """
    lines = ["".join(_span(run) for run in row) for row in styled_cells(frame)]
    return f'<pre class="{escape(css_class, quote=True)}">{chr(10).join(lines)}</pre>'


def stylesheet() -> str:
    """The viewdata stylesheet text, shipped with the package."""
    resource = files("sextile.viewdata") / "static" / "viewdata.css"
    return resource.read_text(encoding="utf-8")


def _span(run: StyledRun) -> str:
    return f'<span class="{" ".join(_classes(run.style))}">{_content(run)}</span>'


def _classes(style: CellStyle) -> list[str]:
    classes = [f"fg-{style.colour.name.lower()}", f"bg-{style.background.name.lower()}"]
    if style.flashing:
        classes.append("flash")
    if style.concealed:
        classes.append("conceal")
    if style.double_height:
        classes.append("dh")
    return classes


def _content(run: StyledRun) -> str:
    if run.patterns:
        glyph: Callable[[int], str] = _separated_mosaic if run.style.separated else sextant
        return "".join(glyph(pattern) for pattern in run.patterns)
    return escape(run.text)


#  Bedstead's separated mosaics live in the Private Use area. `mosaic_code` gives
#  the SAA5050 character-code layout -- bit0 top-left, bit1 top-right, bit2
#  middle-left, bit3 middle-right, bit4 bottom-left, bit6 bottom-right -- which is
#  the ZVBI arrangement's contiguous glyph offset from U+EE00; clearing bit 5 (the
#  -0x20) selects the separated glyph beside it. Measured from the font in the S1
#  spike and cross-checked against Beebium's get_graphics_row.
def _separated_mosaic(pattern: int) -> str:
    return chr(0xEE00 + mosaic_code(pattern) - 0x20)
