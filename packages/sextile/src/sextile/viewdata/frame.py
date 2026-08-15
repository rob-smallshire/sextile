"""A viewdata frame: a fixed grid of 24 rows by 40 cells.

Each cell holds one byte, exactly as the SAA5050 sees it: a G0 character position
in 0x20-0x7F, or a spacing attribute below 0x20 which the display renders as a
space in the prevailing background.

The grid is fixed rather than a stream of writes because Commstar wraps from the
bottom right cell straight back to the top left instead of scrolling. A
serialiser that emitted one cell too many would overwrite the top of the frame it
had just drawn. With a fixed grid that cannot happen: the frame always occupies
exactly 960 cells.

Attributes cost a byte more on the wire than on screen, since they travel escaped
as two bytes but still occupy a single cell. The grid, never the byte count, is
the authority on layout.
"""

from typing import Final

from sextile.viewdata.charset import decode_g0
from sextile.viewdata.controls import Control
from sextile.viewdata.encoding import ScreenControl, encode_control, encode_text

__all__ = [
    "COLUMNS",
    "FOOTER_ROW",
    "Frame",
    "ROWS",
]

ROWS: Final = 24
COLUMNS: Final = 40

#: The last row, which the session draws on directly: the command line while a
#: request is being keyed, and the countdown before a silent line is released.
#: A page reaches it through its furniture rather than through this.
FOOTER_ROW: Final = ROWS - 1

_BLANK: Final = 0x20

#: What every frame begins with: hide the cursor so it does not trail across the
#: screen as the frame paints, clear, and home. The command line turns the
#: cursor back on, that being the one place it tells a reader anything.
FRAME_PREAMBLE: Final = bytes(
    [ScreenControl.CURSOR_OFF, ScreenControl.CLEAR_SCREEN, ScreenControl.CURSOR_HOME]
)

#  In the readable dump, an attribute shows as the letter it travels as on the
#  wire, which keeps a golden frame directly comparable with a byte trace.
_NOT_AN_ATTRIBUTE: Final = "."


class Frame:
    """A frame under construction."""

    def __init__(self) -> None:
        self._cells = bytearray([_BLANK] * (ROWS * COLUMNS))

    def cell(self, row: int, column: int) -> int:
        """The byte held at a position."""
        return self._cells[self._offset(row, column)]

    def is_attribute(self, row: int, column: int) -> bool:
        """Whether a position holds a spacing attribute rather than a character."""
        return self.cell(row, column) < _BLANK

    def set_attribute(self, row: int, column: int, control: Control) -> None:
        """Place a spacing attribute, which occupies the cell and displays as a space."""
        self._cells[self._offset(row, column)] = control

    def set_cell(self, row: int, column: int, code: int) -> None:
        """Put a displayable code in a cell, as the SAA5050 will read it.

        What it draws depends on the character set in force where it lands,
        which is the caller's business: the same byte is a letter in alpha and
        a pattern of blocks in graphics. `Canvas` tracks that; this does not.
        """
        if not 0x20 <= code <= 0x7F:
            raise ValueError(f"0x{code:02X} is not a displayable character code")
        self._cells[self._offset(row, column)] = code

    def write(self, row: int, column: int, text: str) -> None:
        """Place text, transliterating and encoding it into G0 positions."""
        encoded = encode_text(text)
        if column + len(encoded) > COLUMNS:
            raise ValueError(
                f"{text!r} needs {len(encoded)} cells from column {column}, "
                f"which overruns the frame's {COLUMNS} columns"
            )
        offset = self._offset(row, column)
        self._cells[offset : offset + len(encoded)] = encoded

    def text_at(self, row: int, column: int, length: int) -> str:
        """The characters held in a run of cells, with attributes reading as spaces."""
        offset = self._offset(row, column)
        if column + length > COLUMNS:
            raise ValueError(f"{length} cells from column {column} overruns the frame")
        return "".join(
            " " if code < _BLANK else decode_g0(code)
            for code in self._cells[offset : offset + length]
        )

    def to_bytes(self, *, trim: bool = True) -> bytes:
        """The frame as it travels: clear, home, then the cells that say something.

        Trailing blanks are not sent. The frame begins by clearing the screen,
        so a space at the end of a row overwrites nothing -- it exists only to
        walk the cursor forward, and a carriage return and line feed do that in
        two bytes rather than up to forty. A row that fills all forty columns
        gets no terminator, because column 40 wraps of its own accord and a
        terminator there would skip a row. After the last row with anything on
        it, nothing is sent at all.

        ``trim=False`` gives the older form, every cell in turn, so the two can
        be compared on real hardware.
        """
        stream = bytearray(FRAME_PREAMBLE)
        last_row = self.last_written_row() if trim else ROWS - 1
        for row in range(last_row + 1):
            used = self.used_columns(row) if trim else COLUMNS
            offset = row * COLUMNS
            for code in self._cells[offset : offset + used]:
                if code < _BLANK:
                    stream.extend(encode_control(Control(code)))
                else:
                    stream.append(code)
            if row < last_row and used < COLUMNS:
                stream.extend((ScreenControl.CARRIAGE_RETURN, ScreenControl.LINE_FEED))
        return bytes(stream)

    def row_bytes(self, row: int, *, upto: int | None = None) -> bytes:
        """One row's cells, escaped, with no preamble and no terminator.

        For drawing over a row of a screen that is already showing something,
        which is what the command line does.

        ``upto`` stops short of the row's end, and a repaint of *several* rows
        must use it. Measured on real Commstar: a row written to all forty
        columns wraps of its own accord, so the cursor is already on the next
        row and the carriage return and cursor down that walk to the next row
        of the block move it down a second one. A three-row block written full
        width lands on rows 4, 6 and 8 and overruns what is beneath it.

        The command line does not need it, its field being deliberately full
        width and nothing following it.
        """
        offset = self._offset(row, 0)
        stream = bytearray()
        width = COLUMNS if upto is None else max(0, min(upto, COLUMNS))
        for code in self._cells[offset : offset + width]:
            if code < _BLANK:
                stream.extend(encode_control(Control(code)))
            else:
                stream.append(code)
        return bytes(stream)

    def last_written_row(self) -> int:
        """The last row with anything on it, or -1 if the frame is blank.

        Where the cursor is left once the frame has been sent, trailing blanks
        not being sent, which is what lets anything drawn afterwards find its
        way from there.
        """
        for row in reversed(range(ROWS)):
            if self.used_columns(row):
                return row
        return -1

    def used_columns(self, row: int) -> int:
        """How much of a row is worth sending: up to its last non-blank cell."""
        offset = row * COLUMNS
        codes = self._cells[offset : offset + COLUMNS]
        for column in reversed(range(COLUMNS)):
            if codes[column] != _BLANK:
                return column + 1
        return 0

    def to_grid(self) -> tuple[list[str], list[str]]:
        """A readable dump as two layers, so golden-frame failures diff legibly.

        The character layer shows what the screen shows, with attribute cells
        appearing as the spaces they are. The attribute layer names those cells
        by the letter they travel as, and marks every other cell with a dot.
        """
        characters: list[str] = []
        attributes: list[str] = []
        for row in range(ROWS):
            offset = row * COLUMNS
            codes = self._cells[offset : offset + COLUMNS]
            characters.append(
                "".join(" " if code < _BLANK else decode_g0(code) for code in codes)
            )
            attributes.append(
                "".join(
                    chr(code + 0x40) if code < _BLANK else _NOT_AN_ATTRIBUTE for code in codes
                )
            )
        return characters, attributes

    @staticmethod
    def _offset(row: int, column: int) -> int:
        if not (0 <= row < ROWS and 0 <= column < COLUMNS):
            raise IndexError(f"({row}, {column}) is outside a {ROWS}x{COLUMNS} frame")
        return row * COLUMNS + column
