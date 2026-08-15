"""Drawing on a frame, with the cost of attributes accounted for.

A spacing attribute occupies a character cell, so a row that changes colour twice
has thirty-eight columns left for text rather than forty. Every method here works
in cells, not in characters, so a caller never has to remember that.

Attributes reset at the start of each row on the SAA5050, so a row is written
independently of its neighbours and white text needs no attribute at all. Rows
are obtained one at a time from ``Canvas.row`` for exactly that reason.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, Self

from sextile.viewdata.charset import mosaic_code
from sextile.viewdata.controls import (
    GRAPHICS_COLOURS,
    Attribute,
    Colour,
    alpha_colour,
    colour_of,
    graphics_colour,
)
from sextile.viewdata.frame import COLUMNS, Frame
from sextile.viewdata.measure import cell_count, fitted

__all__ = [
    "Canvas",
    "RowWriter",
    "Span",
]

#: Every row begins displaying white alphanumerics.
DEFAULT_COLOUR = Colour.WHITE

#  What a colour attribute costs, where the cost has to be reserved before the
#  writing rather than charged during it.
_ATTRIBUTE_CELL: Final = 1


@dataclass(frozen=True)
class Span:
    """A stretch of text in one colour.

    Attributes:
        text: The characters to write.
        colour: The colour to write them in, or None to keep the one in force.

    For `RowWriter.runs`, a line whose colours carry meaning rather than
    decoration: several values side by side, told apart by colour rather than by
    a label that would cost cells to repeat what the row above already said. A
    row in one colour needs no `Span`; `RowWriter.text` takes the colour with the
    words.
    """

    text: str
    colour: Colour | None = None

class _Mode(Enum):
    """Whether the cells being written are read as letters or as blocks.

    A colour attribute chooses this as well as the colour -- `GRAPHICS_YELLOW`
    means "yellow, and read what follows as mosaics" -- so the two are tracked
    together or a row of text after a rule comes out as mosaic rubbish.
    """

    ALPHA = auto()
    GRAPHICS = auto()


class RowWriter:
    """A cursor along one row, tracking the colour and mode in effect."""

    def __init__(self, frame: Frame, row: int) -> None:
        self._frame = frame
        self._row = row
        self._column = 0
        self._colour = DEFAULT_COLOUR
        #  Every row begins in alpha with contiguous graphics selected, whatever
        #  the row above ended in. Which graphics set is *selected* is separate
        #  state from whether graphics are *in force*: the separated attribute
        #  chooses the set, and a colour attribute is what enters it.
        self._mode = _Mode.ALPHA
        self._separated = False

    @property
    def column(self) -> int:
        """The next free column."""
        return self._column

    @property
    def remaining(self) -> int:
        """Cells left in the row."""
        return COLUMNS - self._column

    def text(self, text: str, colour: Colour | None = None) -> Self:
        """Append text, preceded by a colour attribute if one is needed.

        One is needed if the colour changes, and also if the row is in graphics:
        the attribute that returns to alpha is the same attribute that sets the
        colour, so leaving a mosaic run costs a cell whether the colour changes
        or not.
        """
        cells = cell_count(text)
        wanted = colour if colour is not None else self._colour
        needs_attribute = (
            colour is not None and colour is not self._colour
        ) or self._mode is _Mode.GRAPHICS
        if needs_attribute:
            colour = wanted
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
            self._mode = _Mode.ALPHA
        self._frame.write(self._row, self._column, text)
        self._column += cell_count(text)
        return self

    def runs(self, runs: "Iterable[Span]", *, cells: int | None = None) -> Self:
        """Append several stretches of text, each in its own colour.

        What `text` does repeatedly, with the difference that this trims rather
        than raises: a line assembled from runs is usually a line assembled from
        data, and a value longer than anybody expected should cost the reader
        the end of a line rather than the whole frame.

        A cell is held back from each run for the attribute that may precede it,
        which costs nothing except in the rare case where the trimming actually
        bites -- and there one character is a cheap price for not having to ask
        `text` what it is about to charge.

        Args:
            runs: The stretches to write, in order.
            cells: A budget the runs share, giving way within it rather than at
                the row's edge. For a row that carries something further along
                it -- a clock, then a figure aligned right of it -- so the first
                does not eat the room the second needs. The row's edge still
                binds when it is the nearer of the two.
        """
        budget = cells
        for run in runs:
            width = self.remaining - _ATTRIBUTE_CELL
            if budget is not None:
                width = min(width, budget - _ATTRIBUTE_CELL)
            if width <= 0:
                break
            text = fitted(run.text, width)
            self.text(text, run.colour)
            if budget is not None:
                budget -= _ATTRIBUTE_CELL + cell_count(text)
        return self

    def mosaic(
        self,
        patterns: Sequence[int],
        colour: Colour,
        *,
        separated: bool = False,
    ) -> Self:
        """Append mosaic cells, preceded by whatever attributes they need.

        Each pattern is six bits, one per block, in the order `mosaic_code`
        names them.

        Two attributes may be wanted and they do different things. The
        separated attribute chooses *which* graphics set is selected, and takes
        effect whether or not graphics are in force; the colour attribute is
        what enters graphics, and carries the colour with it. So a contiguous
        run in a colour already in force costs one cell, a separated one costs
        two, and staying in the same run costs nothing.

        Attributes display as spaces, which is why a region drawn this way has a
        margin on its left whether it wants one or not. That cost is knowable
        and has to be planned around -- it is why the rules this service draws
        begin at column 2 -- and `HOLD_GRAPHICS` is the way out of it where a
        gap would show, since it makes an attribute cell repeat the last mosaic
        instead of blanking.
        """
        choosing = self._separated is not separated
        entering = self._mode is not _Mode.GRAPHICS or self._colour is not colour
        needed = len(patterns) + choosing + entering
        if needed > self.remaining:
            raise ValueError(
                f"{len(patterns)} mosaic cells need {needed} with their attributes, "
                f"but only {self.remaining} remain in row {self._row}"
            )
        if choosing:
            self._frame.set_attribute(
                self._row,
                self._column,
                Attribute.SEPARATED_GRAPHICS if separated else Attribute.CONTIGUOUS_GRAPHICS,
            )
            self._column += 1
            self._separated = separated
        if entering:
            self._frame.set_attribute(self._row, self._column, graphics_colour(colour))
            self._column += 1
            self._colour = colour
            self._mode = _Mode.GRAPHICS
        for pattern in patterns:
            self._frame.set_cell(self._row, self._column, mosaic_code(pattern))
            self._column += 1
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

    def background(self, colour: Colour, *, text: Colour) -> Self:
        """Colour the rest of this row's background, and what is written on it.

        Args:
            colour: The background colour, which runs to the end of the row
                unless `end_background` stops it.
            text: The colour of what is written on it.

        Three cells, the hardware's arrangement rather than a choice: a
        background can only be taken from a foreground, so the colour is chosen,
        made the background, and the text colour chosen again. The bar of colour
        a reader can see the extent of is what makes a field look like a field.
        """
        if self.remaining < _BACKGROUND_CELLS:
            raise ValueError(
                f"a background needs {_BACKGROUND_CELLS} cells and row "
                f"{self._row} has {self.remaining}"
            )
        self._frame.set_attribute(self._row, self._column, alpha_colour(colour))
        self._frame.set_attribute(self._row, self._column + 1, Attribute.NEW_BACKGROUND)
        self._frame.set_attribute(self._row, self._column + 2, alpha_colour(text))
        self._column += _BACKGROUND_CELLS
        self._colour = text
        return self

    def end_background(self) -> Self:
        """End any background, so what follows sits on black again.

        One cell. The foreground is untouched -- black is taken as a background
        directly, being the one colour that needs no foreground chosen first.

        What this is for is bounding a field. A background runs to the end of
        the row unless something stops it, which says "type as much as you
        like"; a field of known width should say how much room there is, which
        means saying where the room ends.
        """
        if self.remaining < 1:
            raise ValueError(f"row {self._row} has no cell left to end a background")
        self._frame.set_attribute(self._row, self._column, Attribute.BLACK_BACKGROUND)
        self._column += 1
        return self

    def _colour_in_force(self) -> Colour:
        """The colour a character written here would take."""
        return self._state_in_force()[0]

    def _state_in_force(self) -> tuple[Colour, "_Mode"]:
        """The colour and the mode a run written here would inherit.

        Attributes reset at the start of a row, so only this row matters, and
        only the attributes before the cursor. The last colour attribute settles
        both: a graphics colour leaves the cell in graphics, an alpha colour in
        letters.
        """
        colour, mode = DEFAULT_COLOUR, _Mode.ALPHA
        for column in range(self._column):
            code = self._frame.cell(self._row, column)
            found = colour_of(code)
            if found is not None:
                colour = found
                mode = _Mode.GRAPHICS if code in GRAPHICS_COLOURS else _Mode.ALPHA
        return colour, mode

    @property
    def colour(self) -> Colour:
        """The colour the next character would take."""
        return self._colour

    def starting_at(self, column: int) -> Self:
        """Move to a column and pick up the colour and mode in force there.

        For a second writer beginning part way along a row another has already
        drawn on -- a legend's words beside a symbol, a figure after a picture.
        Reading what is in force is what makes the next write escape it: white
        text after a mosaic emits the attribute that returns to letters, rather
        than coming out as blocks. The column must not be behind the cursor.
        """
        if not (self._column <= column <= COLUMNS):
            raise ValueError(f"cannot move from column {self._column} to {column}")
        self._column = column
        self._colour, self._mode = self._state_in_force()
        return self


#: What a background costs: the colour, making it the background, and the
#: colour of what is written on it.
_BACKGROUND_CELLS: Final = 3


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
