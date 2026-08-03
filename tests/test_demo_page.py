"""The demonstration frame, which exists to be looked at.

Its job is to exercise every part of the frame engine at once -- chrome, colour,
mosaic graphics, wrapped body text, a page number -- so that a glance at
``sextile render --demo`` shows whether anything is obviously wrong.
"""

from sextile.pages.demo import demo_frame
from sextile.viewdata.ansi import render_ansi
from sextile.viewdata.frame import COLUMNS, FRAME_PREAMBLE, ROWS


def test_the_demo_frame_fills_the_geometry() -> None:
    characters, _ = demo_frame().to_grid()
    assert len(characters) == ROWS
    assert all(len(row) == COLUMNS for row in characters)


def test_the_service_is_named() -> None:
    assert "SEXTILE" in "\n".join(demo_frame().to_grid()[0])


def test_a_page_number_is_shown() -> None:
    #  Stardot post p=489493, numbered by the scheme.
    assert "82489493" in "\n".join(demo_frame().to_grid()[0])


def test_the_frame_uses_colour() -> None:
    _, attributes = demo_frame().to_grid()
    assert any(cell != "." for row in attributes for cell in row)


def test_the_frame_uses_mosaic_graphics() -> None:
    _, attributes = demo_frame().to_grid()
    #  Graphics colours travel as Q-W; a rule drawn in mosaics uses one.
    assert any(cell in "QRSTUVW" for row in attributes for cell in row)


def test_the_untrimmed_frame_serialises_to_the_expected_length() -> None:
    #  Two bytes of preamble, 960 cells, plus one extra byte per attribute.
    frame = demo_frame()
    attributes = sum(
        1 for row in range(ROWS) for column in range(COLUMNS) if frame.is_attribute(row, column)
    )
    assert len(frame.to_bytes(trim=False)) == len(FRAME_PREAMBLE) + ROWS * COLUMNS + attributes


def test_trimming_saves_most_of_the_frame() -> None:
    frame = demo_frame()
    assert len(frame.to_bytes()) < len(frame.to_bytes(trim=False))


def test_every_byte_survives_a_seven_bit_line() -> None:
    assert all(byte < 0x80 for byte in demo_frame().to_bytes())


def test_it_renders_without_error() -> None:
    assert len(render_ansi(demo_frame()).splitlines()) == ROWS
