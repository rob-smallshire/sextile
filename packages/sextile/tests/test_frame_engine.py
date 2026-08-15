"""A whole-frame smoke test of the drawing engine.

The unit tests each cover one piece -- the canvas, the frame, the drawing
helpers, the serialiser. This builds one representative frame that uses all of
them at once -- a header with a page number, mosaic rules, colour, wrapped body
text, a footer -- and checks the geometry, the colour, the serialised length,
the trimming and the rendering, so an obvious break shows up in one place.
"""

from sextile.addressing import PageAddress, keyed
from sextile.viewdata.ansi import render_ansi
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.frame import COLUMNS, FRAME_PREAMBLE, ROWS, Frame

_NAME = "SEXTILE"
_PAGE_NUMBER = PageAddress("82489493")
_INDEX_NUMBER = PageAddress("1")
_BODY = (
    "I've been investigating the cycle timing of the Acorn NS32016 second "
    "processor. The board runs at 8MHz nominally, but the Tube interface "
    "introduces wait states that nobody seems to have documented. Has anyone "
    "measured this properly?"
)


def _frame() -> Frame:
    """A representative frame that exercises every part of the engine."""
    canvas = Canvas()
    canvas.row(0).text(_NAME, Colour.CYAN)
    canvas.right(0, str(_PAGE_NUMBER), Colour.WHITE)
    rule(canvas, 1)
    canvas.row(3).text("NS32016 TIMING INVESTIGATION", Colour.YELLOW)
    canvas.row(5).text("RobertS", Colour.GREEN).at(30).text("21:20", Colour.GREEN)
    canvas.paragraph(7, 12, _BODY, colour=Colour.WHITE)
    rule(canvas, 21)
    canvas.row(22).text("Key ", Colour.WHITE).text("#", Colour.YELLOW).text(
        " for next frame", Colour.WHITE
    )
    canvas.row(23).text("Key ", Colour.WHITE).text(
        keyed(_INDEX_NUMBER), Colour.YELLOW
    ).text(" for the main index", Colour.WHITE)
    return canvas.frame


def test_the_frame_fills_the_geometry() -> None:
    characters, _ = _frame().to_grid()
    assert len(characters) == ROWS
    assert all(len(row) == COLUMNS for row in characters)


def test_the_header_shows_the_name_and_page_number() -> None:
    top = "\n".join(_frame().to_grid()[0])
    assert "SEXTILE" in top
    assert "82489493" in top


def test_the_frame_uses_colour() -> None:
    _, attributes = _frame().to_grid()
    assert any(cell != "." for row in attributes for cell in row)


def test_the_frame_uses_mosaic_graphics() -> None:
    _, attributes = _frame().to_grid()
    #  Graphics colours travel as Q-W; a rule drawn in mosaics uses one.
    assert any(cell in "QRSTUVW" for row in attributes for cell in row)


def test_the_untrimmed_frame_serialises_to_the_expected_length() -> None:
    #  Two bytes of preamble, 960 cells, plus one extra byte per attribute.
    frame = _frame()
    attributes = sum(
        1 for row in range(ROWS) for column in range(COLUMNS) if frame.is_attribute(row, column)
    )
    assert len(frame.to_bytes(trim=False)) == len(FRAME_PREAMBLE) + ROWS * COLUMNS + attributes


def test_trimming_saves_most_of_the_frame() -> None:
    frame = _frame()
    assert len(frame.to_bytes()) < len(frame.to_bytes(trim=False))


def test_every_byte_survives_a_seven_bit_line() -> None:
    assert all(byte < 0x80 for byte in _frame().to_bytes())


def test_it_renders_without_error() -> None:
    assert len(render_ansi(_frame()).splitlines()) == ROWS
