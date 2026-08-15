"""Reading a frame the way the SAA5050 does, into styled runs.

The display rules -- set-at backgrounds, separated graphics, hold, the reset each
row -- are the interesting part, and are verified against the semantics written up
from Beebium in docs/reference/display-semantics.md.
"""

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Attribute, Colour
from sextile.viewdata.display import CellStyle, StyledRun, styled_cells
from sextile.viewdata.frame import COLUMNS, ROWS, Frame


def rows(frame: Frame) -> list[list[StyledRun]]:
    return list(styled_cells(frame))


def cells(runs: list[StyledRun]) -> list[tuple[str | int, CellStyle]]:
    """A row's runs expanded back to one (glyph, style) per column."""
    out: list[tuple[str | int, CellStyle]] = []
    for run in runs:
        if run.patterns:
            out += [(p, run.style) for p in run.patterns]
        else:
            out += [(c, run.style) for c in run.text]
    return out


class TestTheShapeOfIt:
    def test_a_blank_frame_is_rows_of_spaces(self) -> None:
        result = rows(Frame())
        assert len(result) == ROWS
        for row in result:
            assert "".join(r.text for r in row) == " " * COLUMNS

    def test_text_becomes_a_run(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("HELLO")
        first = rows(canvas.frame)[0]
        assert first[0].text.startswith("HELLO")
        assert first[0].style == CellStyle()


class TestAttributes:
    def test_an_attribute_shows_as_a_space(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("RED", Colour.RED)
        line = cells(rows(canvas.frame)[0])
        assert line[0][0] == " "  # the colour attribute's own cell

    def test_a_foreground_colour_applies_from_the_next_cell(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("RED", Colour.RED)
        line = cells(rows(canvas.frame)[0])
        assert line[0][1].colour == Colour.WHITE  # the attribute cell, still white
        assert line[1][1].colour == Colour.RED  # the R of RED

    def test_a_new_background_is_set_at_its_own_cell(self) -> None:
        #  The chip sets a background at the attribute cell, not after it.
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.ALPHA_RED)
        frame.set_attribute(0, 1, Attribute.NEW_BACKGROUND)
        line = cells(rows(frame)[0])
        assert line[1][1].background == Colour.RED
        assert line[0][1].background == Colour.BLACK

    def test_black_background_is_set_at_its_own_cell(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.ALPHA_RED)
        frame.set_attribute(0, 1, Attribute.NEW_BACKGROUND)
        frame.set_attribute(0, 2, Attribute.BLACK_BACKGROUND)
        line = cells(rows(frame)[0])
        assert line[2][1].background == Colour.BLACK


class TestGraphics:
    def test_graphics_cells_become_patterns(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.GRAPHICS_WHITE)
        frame.write(0, 1, "▮")  # 0x7F, solid mosaic
        line = cells(rows(frame)[0])
        assert line[1][0] == 0b111111
        assert line[1][1].graphics is True

    def test_separated_is_carried_on_the_style(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.SEPARATED_GRAPHICS)
        frame.set_attribute(0, 1, Attribute.GRAPHICS_WHITE)
        frame.write(0, 2, "▮")
        line = cells(rows(frame)[0])
        assert line[2][1].separated is True

    def test_a_letter_in_graphics_mode_stays_a_letter(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.GRAPHICS_WHITE)
        frame.write(0, 1, "A")  # 0x41, in the alpha island of graphics mode
        line = cells(rows(frame)[0])
        assert line[1][0] == "A"


class TestHoldGraphics:
    def test_a_held_control_cell_repeats_the_last_mosaic(self) -> None:
        #  Nothing the framework builds uses hold, but the walk implements it.
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.GRAPHICS_WHITE)
        frame.write(0, 1, "▮")  # solid mosaic; becomes the held pattern
        frame.set_attribute(0, 2, Attribute.HOLD_GRAPHICS)
        frame.set_attribute(0, 3, Attribute.ALPHA_YELLOW)  # a control cell under hold
        line = cells(rows(frame)[0])
        assert line[3][0] == 0b111111  # repeats the held mosaic, not a space
        assert line[3][1].graphics is True


class TestRowsAreIndependent:
    def test_graphics_does_not_leak_to_the_next_row(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.GRAPHICS_WHITE)
        frame.write(1, 0, "▮")
        line = cells(rows(frame)[1])
        assert isinstance(line[0][0], str)  # row 1 is alpha again: a character
