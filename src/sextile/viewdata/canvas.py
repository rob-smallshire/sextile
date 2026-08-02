"""Drawing on a frame, with the cost of attributes accounted for.

A spacing attribute occupies a character cell, so a row that changes colour twice
has thirty-eight columns left for text rather than forty. Every method here works
in cells, not in characters, so a caller never has to remember that.

Attributes reset at the start of each row on the SAA5050, so a row is written
independently of its neighbours and white text needs no attribute at all. Rows
are obtained one at a time from ``Canvas.row`` for exactly that reason.
"""

from typing import Self

from sextile.viewdata.controls import Colour, alpha_colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS, Frame
from sextile.viewdata.wrapping import wrap_text

#: Every row begins displaying white alphanumerics.
DEFAULT_COLOUR = Colour.WHITE


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
        """Advance without writing, leaving the cells blank."""
        if cells > self.remaining:
            raise ValueError(f"skipping {cells} cells overruns row {self._row}")
        self._column += cells
        return self

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

    def centre(self, row: int, text: str, colour: Colour | None = None) -> RowWriter:
        """Write text centred in the row.

        A colour attribute sits immediately to the left of the text. When
        centring would put the text at column zero there is nowhere to put it,
        so the text gives up its centring rather than the colour being dropped.
        """
        cells = cell_count(text)
        column = max((COLUMNS - cells) // 2, 0)
        needs_attribute = colour is not None and colour is not DEFAULT_COLOUR
        if needs_attribute and column == 0:
            column = 1
        writer = self.row(row)
        writer.skip(column - 1 if needs_attribute else column)
        return writer.text(text, colour)

    def right(self, row: int, text: str, colour: Colour | None = None) -> RowWriter:
        """Write text ending at the right edge of the row."""
        cells = cell_count(text)
        needs_attribute = colour is not None and colour is not DEFAULT_COLOUR
        start = COLUMNS - cells - (1 if needs_attribute else 0)
        if start < 0:
            raise ValueError(f"{text!r} needs {cells} cells and cannot be right-aligned")
        writer = self.row(row)
        writer.skip(start)
        return writer.text(text, colour)

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
