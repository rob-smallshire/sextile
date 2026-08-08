"""Drawing on a frame, with the cost of attributes accounted for.

A spacing attribute occupies a character cell, so a row that changes colour twice
has thirty-eight columns left for text rather than forty. Every method here works
in cells, not in characters, so a caller never has to remember that.

Attributes reset at the start of each row on the SAA5050, so a row is written
independently of its neighbours and white text needs no attribute at all. Rows
are obtained one at a time from ``Canvas.row`` for exactly that reason.
"""

from typing import Self

from sextile.viewdata.controls import Colour, Control, alpha_colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS, ROWS, Frame
from sextile.viewdata.wrapping import wrap_text

#: Every row begins displaying white alphanumerics.
DEFAULT_COLOUR = Colour.WHITE

#  Attributes that change the foreground colour, and so what a character
#  written after them will look like.
_ALPHA_COLOURS = range(0x01, 0x08)
_GRAPHICS_COLOURS = range(0x11, 0x18)
_GRAPHICS_OFFSET = 0x10


class RowWriter:
    """A cursor along one row, tracking the colour in effect."""

    def __init__(self, frame: Frame, row: int) -> None:
        self._frame = frame
        self._row = row
        self._column = 0
        self._colour = DEFAULT_COLOUR

    @property
    def column(self) -> int:
        """The next free column."""
        return self._column

    @property
    def remaining(self) -> int:
        """Cells left in the row."""
        return COLUMNS - self._column

    def text(self, text: str, colour: Colour | None = None) -> Self:
        """Append text, preceded by a colour attribute if the colour changes."""
        cells = cell_count(text)
        needs_attribute = colour is not None and colour is not self._colour
        if needs_attribute:
            cells += 1
        if cells > self.remaining:
            raise ValueError(
                f"{text!r} needs {cells} cells but only {self.remaining} remain "
                f"in row {self._row}; it overruns the frame"
            )
        if needs_attribute:
            assert colour is not None
            self._frame.set_attribute(self._row, self._column, alpha_colour(colour))
            self._column += 1
            self._colour = colour
        self._frame.write(self._row, self._column, text)
        self._column += cell_count(text)
        return self

    def skip(self, cells: int) -> Self:
        """Advance without writing, leaving the cells blank.

        Whatever colour is in force where the cursor lands becomes this
        writer's colour. Skipping is how a second writer reaches a place
        further along a row somebody else has already written, and assuming
        white there would emit no attribute and leave the text silently taking
        the earlier colour.
        """
        if cells > self.remaining:
            raise ValueError(f"skipping {cells} cells overruns row {self._row}")
        self._column += cells
        self._colour = self._colour_in_force()
        return self

    def _colour_in_force(self) -> Colour:
        """The colour a character written here would take.

        Attributes reset at the start of a row, so only this row matters, and
        only the attributes before the cursor.
        """
        colour = DEFAULT_COLOUR
        for column in range(self._column):
            code = self._frame.cell(self._row, column)
            if code in _ALPHA_COLOURS:
                colour = Colour(code)
            elif code in _GRAPHICS_COLOURS:
                colour = Colour(code - _GRAPHICS_OFFSET)
        return colour

    @property
    def colour(self) -> Colour:
        """The colour the next character would take."""
        return self._colour

    def at(self, column: int) -> Self:
        """Move to a column, which must not be behind the cursor."""
        if not (self._column <= column <= COLUMNS):
            raise ValueError(f"cannot move from column {self._column} to {column}")
        self._column = column
        return self


class Canvas:
    """A frame under construction, drawn on a row at a time."""

    def __init__(self, frame: Frame | None = None) -> None:
        self._frame = frame if frame is not None else Frame()

    @property
    def frame(self) -> Frame:
        return self._frame

    def row(self, row: int) -> RowWriter:
        """A writer positioned at the start of a row."""
        return RowWriter(self._frame, row)

    def double_height(
        self,
        row: int,
        text: str,
        colour: Colour | None = None,
        *,
        column: int = 0,
    ) -> None:
        """Write text at twice the height, which costs the row below as well.

        The mechanism is not what a reasonable guess would say, and is read from
        Beebium's SAA5050 rather than inferred. A row carrying the double-height
        attribute is drawn as the *top* halves of its characters, and the row
        below as the bottom halves -- but only if that row carries the attribute
        too, `double_height_bottom` requiring the shift to be set there as well.

        So both rows hold the same text, which is exactly the BBC BASIC idiom of
        printing a double-height line twice. Nothing else can be put on the row
        below: whatever is there would be drawn as the bottom of something.
        """
        if not 0 <= row < ROWS - 1:
            raise ValueError(
                f"row {row} cannot be doubled: the bottom halves need the row beneath"
            )
        cells = 1 + (1 if colour is not None else 0) + cell_count(text)
        if column + cells > COLUMNS:
            raise ValueError(
                f"{text!r} needs {cells} cells from column {column}, "
                f"which overruns the frame's {COLUMNS} columns"
            )
        for half in (row, row + 1):
            at = column
            self._frame.set_attribute(half, at, Control.DOUBLE_HEIGHT)
            at += 1
            if colour is not None:
                self._frame.set_attribute(half, at, alpha_colour(colour))
                at += 1
            self._frame.write(half, at, text)

    def centre(self, row: int, text: str, colour: Colour | None = None) -> RowWriter:
        """Write text centred in the row.

        A colour attribute sits immediately to the left of the text. When
        centring would put the text at column zero there is nowhere to put it,
        so the text gives up its centring rather than the colour being dropped.
        """
        cells = cell_count(text)
        column = max((COLUMNS - cells) // 2, 0)
        if self._needs_attribute(row, column, colour) and column == 0:
            #  There is no column to the left of zero for the attribute, so the
            #  text gives up its centring rather than the colour being dropped.
            column = 1
        return self._write_at(row, column, text, colour)

    def right(self, row: int, text: str, colour: Colour | None = None) -> RowWriter:
        """Write text ending at the right edge of the row."""
        cells = cell_count(text)
        column = COLUMNS - cells
        if column < 0:
            raise ValueError(f"{text!r} needs {cells} cells and cannot be right-aligned")
        return self._write_at(row, column, text, colour)

    def _write_at(
        self, row: int, column: int, text: str, colour: Colour | None
    ) -> RowWriter:
        """Write so that the text itself begins at a column, attribute or no.

        The attribute cell, when one is needed, is taken from in front of the
        text rather than from the text's own place, so alignment is unaffected
        by whether the colour happens to change here.
        """
        writer = self.row(row)
        writer.skip(column - (1 if self._needs_attribute(row, column, colour) else 0))
        return writer.text(text, colour)

    def _needs_attribute(self, row: int, column: int, colour: Colour | None) -> bool:
        """Whether writing this colour at this column would cost an attribute cell.

        Not simply "is it white?": a row somebody else has already coloured is
        not white at column twenty, and text written there without an attribute
        would silently take their colour.
        """
        if colour is None:
            return False
        return self.row(row).skip(column).colour is not colour

    def paragraph(
        self,
        first_row: int,
        rows: int,
        text: str,
        *,
        width: int = COLUMNS,
        colour: Colour | None = None,
    ) -> int:
        """Write wrapped text, returning the first row left free."""
        next_row, _ = self.paragraph_with_overflow(
            first_row, rows, text, width=width, colour=colour
        )
        return next_row

    def paragraph_with_overflow(
        self,
        first_row: int,
        rows: int,
        text: str,
        *,
        width: int = COLUMNS,
        colour: Colour | None = None,
    ) -> tuple[int, str]:
        """Write wrapped text, returning the next free row and whatever did not fit.

        Text that will not fit is handed back rather than dropped, so the
        paginator can carry it to a continuation frame.
        """
        attribute_cells = 1 if colour is not None and colour is not DEFAULT_COLOUR else 0
        lines = wrap_text(text, width - attribute_cells)
        for offset, line in enumerate(lines[:rows]):
            self.row(first_row + offset).text(line, colour)
        overflow = " ".join(lines[rows:])
        return first_row + min(len(lines), rows), overflow
