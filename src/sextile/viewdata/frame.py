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

ROWS: Final = 24
COLUMNS: Final = 40

_BLANK: Final = 0x20

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

    def to_bytes(self) -> bytes:
        """The frame as it travels: clear, home, then every cell in turn."""
        stream = bytearray([ScreenControl.CLEAR_SCREEN, ScreenControl.CURSOR_HOME])
        for code in self._cells:
            if code < _BLANK:
                stream.extend(encode_control(Control(code)))
            else:
                stream.append(code)
        return bytes(stream)

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
