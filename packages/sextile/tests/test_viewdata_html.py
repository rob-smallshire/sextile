"""A frame as HTML, drawn with Bedstead.

Every row must be exactly the frame's width however the runs fall, and the
mosaics must be the sextants for contiguous graphics and the Private Use glyphs
for separated -- the two things a wrong render gets wrong.
"""

import html
import re
from pathlib import Path

from sextile.viewdata.ansi import sextant
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.charset import mosaic_code
from sextile.viewdata.controls import Attribute, Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.frame import COLUMNS, ROWS, Frame
from sextile.viewdata.html import render_html, stylesheet

_TAG = re.compile(r"<[^>]+>")
_GOLDEN = Path(__file__).parent / "data" / "viewdata_fixture.html"


def displayed_rows(rendered: str) -> list[str]:
    """Each row's displayed characters, with the spans and escaping removed."""
    body = rendered[rendered.index(">") + 1 : rendered.rindex("</pre>")]
    return [html.unescape(_TAG.sub("", line)) for line in body.split("\n")]


def fixture() -> Frame:
    """A frame exercising text, colour, a rule and stacked mosaic cells."""
    canvas = Canvas()
    canvas.row(0).text("SEXTILE", Colour.CYAN)
    canvas.row(1).text("the weather <today>", Colour.YELLOW)
    rule(canvas, 3, Colour.GREEN)
    #  Two vertically stacked full-block cells, contiguous and separated, so the
    #  rendered page proves the row-to-row join: the contiguous pair butts with no
    #  seam, the separated pair keeps its gap.
    solid = (0b111111, 0b111111)
    for row in (5, 6):
        canvas.row(row).starting_at(1).mosaic(solid, Colour.WHITE)
        canvas.row(row).starting_at(6).mosaic(solid, Colour.WHITE, separated=True)
    return canvas.frame


class TestShape:
    def test_it_is_a_pre_of_the_right_height(self) -> None:
        rendered = render_html(Frame())
        assert rendered.startswith('<pre class="viewdata">')
        assert rendered.rstrip().endswith("</pre>")
        assert len(displayed_rows(rendered)) == ROWS

    def test_every_row_is_exactly_the_frame_width(self) -> None:
        #  However the runs fall, and whatever a run does, a row is 40 cells.
        for line in displayed_rows(render_html(fixture())):
            assert len(line) == COLUMNS

    def test_the_class_can_be_changed(self) -> None:
        assert render_html(Frame(), css_class="v2").startswith('<pre class="v2">')


class TestSpans:
    def test_text_is_escaped(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("a<b>&c")
        assert "a&lt;b&gt;&amp;c" in render_html(canvas.frame)

    def test_a_colour_becomes_a_class(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("X", Colour.RED)
        assert 'class="fg-red bg-black"' in render_html(canvas.frame)

    def test_a_contiguous_mosaic_is_a_sextant(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.GRAPHICS_WHITE)
        frame.write(0, 1, "▮")  # solid
        assert sextant(0b111111) in render_html(frame)

    def test_a_separated_mosaic_is_a_private_use_glyph(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.SEPARATED_GRAPHICS)
        frame.set_attribute(0, 1, Attribute.GRAPHICS_WHITE)
        frame.write(0, 2, "▮")  # solid, separated
        separated = chr(0xEE00 + mosaic_code(0b111111) - 0x20)  # U+EE5F
        assert separated in render_html(frame)
        assert sextant(0b111111) not in render_html(frame)


class TestStylesheet:
    def test_it_ships_and_names_bedstead(self) -> None:
        css = stylesheet()
        assert '"Bedstead"' in css
        assert "line-height: 1" in css


class TestSnapshot:
    def test_a_fixture_frame_renders_as_recorded(self) -> None:
        rendered = render_html(fixture())
        assert rendered == _GOLDEN.read_text(encoding="utf-8")
