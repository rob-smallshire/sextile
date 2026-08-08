"""Placing several things on a frame and working out the attributes once.

`Canvas` writes a row left to right and inserts an attribute whenever the state
changes, which is right for a page built a phrase at a time. It is the wrong
shape for placing things *at* positions -- a heading here, a block of graphics
there -- because each call re-establishes the state it wants without knowing
what the next one will want, and because it cannot say whether the row will fit
until it has half drawn it.

A composition takes the whole row first. That buys three things:

**It answers whether the layout is possible.** Attributes occupy cells, so a row
of alternating colours may simply not fit in forty. Better to be told than to
have the last item silently truncated.

**Two runs in the same style cost one attribute, not two.** Blocks at either end
of a row need graphics entered once: the composition never returns to alpha in
between, because it can see there is no text in between. This is the case that
made the sequential writer wasteful, and it is what a mosaic font needs -- a
banner is a row of block runs that all want the same colour.

**It is exact rather than clever.** An attribute displays as a blank, and a
blank in graphics is the no-blocks mosaic, so an attribute may sit anywhere in
the gap before the run it affects. The only question at each gap is whether the
attributes fit in it, which makes a left-to-right pass optimal and leaves
nothing to search for. Placement becomes a search only if items are free to
move, which is a different feature and not this one.

Rows are independent: every row begins in alpha, white, contiguous selected,
whatever the row above ended in. So a frame composition is a row composition
done twenty-four times, and nothing here has to think about the frame at all.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.charset import mosaic_code
from sextile.viewdata.controls import Colour, Control, alpha_colour, graphics_colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS, ROWS


class DoesNotFit(ValueError):
    """A composition that cannot be drawn, and why."""


@dataclass(frozen=True)
class Style:
    """How a run is to be displayed: every attribute the SAA5050 has.

    Not every combination is reachable from every other in one cell, which is
    the whole reason this is a value handed to a compositor rather than a
    sequence of controls written by hand. A background is the worst of them: the
    hardware has no "set background" attribute, only "make the current
    foreground the background", so white on blue costs three cells -- choose
    blue, make it the background, choose white again.
    """

    colour: Colour = Colour.WHITE
    background: Colour = Colour.BLACK
    separated: bool = False
    flashing: bool = False
    double_height: bool = False
    held: bool = False
    concealed: bool = False


#: What every row starts as, whatever the row above ended in.
OPENING: Final = Style()


@dataclass(frozen=True)
class Run:
    """One thing to place: text, or a run of mosaic blocks.

    ``patterns`` is six-bit block patterns; ``words`` is characters. Exactly one
    of them says what this is.
    """

    column: int
    style: Style = Style()
    words: str = ""
    patterns: tuple[int, ...] = ()

    @property
    def graphics(self) -> bool:
        return bool(self.patterns)

    @property
    def cells(self) -> int:
        return len(self.patterns) if self.graphics else cell_count(self.words)

    @property
    def end(self) -> int:
        return self.column + self.cells


@dataclass
class Composition:
    """Things to place on a frame, and where."""

    runs: dict[int, list[Run]] = field(default_factory=dict)

    def text(
        self,
        row: int,
        column: int,
        words: str,
        colour: Colour = Colour.WHITE,
        *,
        style: Style | None = None,
    ) -> "Composition":
        """Place text at a column.

        ``colour`` is the common case said briefly; ``style`` is everything the
        hardware can do. Double height places the same text on the row below as
        well, because that is how the SAA5050 draws the bottom halves.
        """
        wanted = style if style is not None else Style(colour=colour)
        self._add(row, Run(column=column, style=wanted, words=words))
        if wanted.double_height:
            self._add(row + 1, Run(column=column, style=wanted, words=words))
        return self

    def blocks(
        self,
        row: int,
        column: int,
        patterns: Sequence[int],
        colour: Colour = Colour.WHITE,
        *,
        separated: bool = False,
        style: Style | None = None,
    ) -> "Composition":
        """Place a run of mosaic blocks at a column."""
        wanted = (
            style
            if style is not None
            else Style(colour=colour, separated=separated)
        )
        return self._add(
            row, Run(column=column, style=wanted, patterns=tuple(patterns))
        )

    def _add(self, row: int, run: Run) -> "Composition":
        if not 0 <= row < ROWS:
            raise DoesNotFit(f"row {row} is not on the frame")
        if run.column < 0 or run.end > COLUMNS:
            raise DoesNotFit(
                f"a run of {run.cells} cells at column {run.column} of row {row} "
                f"runs past the frame's {COLUMNS} columns"
            )
        self.runs.setdefault(row, []).append(run)
        return self

    # -- planning -----------------------------------------------------------

    def problems(self) -> list[str]:
        """Everything wrong with this composition, or nothing if it will draw."""
        found = []
        for row in sorted(self.runs):
            try:
                self._plan(row)
            except DoesNotFit as trouble:
                found.append(str(trouble))
        return found

    def fits(self) -> bool:
        return not self.problems()

    def draw(self, canvas: Canvas) -> None:
        """Draw it, or raise ``DoesNotFit`` having drawn nothing."""
        planned = {row: self._plan(row) for row in sorted(self.runs)}
        for row, plan in planned.items():
            for column, attribute in plan.attributes:
                canvas.frame.set_attribute(row, column, attribute)
            for run in plan.runs:
                self._write(canvas, row, run)

    def _write(self, canvas: Canvas, row: int, run: Run) -> None:
        if run.graphics:
            for offset, pattern in enumerate(run.patterns):
                canvas.frame.set_cell(row, run.column + offset, mosaic_code(pattern))
        else:
            canvas.frame.write(row, run.column, run.words)

    def _plan(self, row: int) -> "_Plan":
        """Where the attributes go on one row, or why they cannot go anywhere."""
        runs = sorted(self.runs[row], key=lambda run: run.column)
        for earlier, later in zip(runs, runs[1:], strict=False):
            if earlier.end > later.column:
                raise DoesNotFit(
                    f"row {row}: a run ending at column {earlier.end} overlaps one "
                    f"beginning at {later.column}"
                )

        state, graphics = OPENING, False
        attributes: list[tuple[int, Control]] = []
        free = 0
        for run in runs:
            wanted = _attributes_for(state, graphics, run)
            gap = run.column - free
            if len(wanted) > gap:
                raise DoesNotFit(
                    f"row {row}: the run at column {run.column} needs {len(wanted)} "
                    f"attribute cell(s) before it and only {gap} are free"
                )
            #  As late as possible, which leaves the earlier cells of the gap in
            #  the previous style -- they are blank either way, and it keeps the
            #  attributes next to what they explain.
            for offset, attribute in enumerate(wanted):
                attributes.append((run.column - len(wanted) + offset, attribute))
            state, graphics = run.style, run.graphics
            free = run.end
        return _Plan(runs=runs, attributes=attributes)


def _attributes_for(state: Style, graphics: bool, run: Run) -> list[Control]:
    """The shortest run of attributes taking one style to another.

    Order matters and is not arbitrary. The background comes first because
    setting it means setting the foreground and then saying "that one", so the
    foreground attribute that follows has to be the one that sticks. Conceal
    comes last because it hides whatever follows it, and has no off switch --
    the hardware clears it at the end of the row and nowhere else.
    """
    wanted = run.style
    if state.concealed and not wanted.concealed:
        raise DoesNotFit(
            "conceal cannot be turned off within a row: the hardware clears it "
            "only at the end of one"
        )
    needed: list[Control] = []
    colour_of = graphics_colour if run.graphics else alpha_colour
    foreground = state.colour

    if wanted.background is not state.background:
        if wanted.background is Colour.BLACK:
            needed.append(Control.BLACK_BACKGROUND)
        else:
            #  There is no "set background": the current foreground becomes it.
            needed.append(colour_of(wanted.background))
            needed.append(Control.NEW_BACKGROUND)
            foreground = wanted.background

    if run.graphics and wanted.separated is not state.separated:
        needed.append(
            Control.SEPARATED_GRAPHICS if wanted.separated else Control.CONTIGUOUS_GRAPHICS
        )

    #  The colour attribute chooses the character set as well, so it is needed
    #  whenever either changes.
    if foreground is not wanted.colour or graphics is not run.graphics:
        needed.append(colour_of(wanted.colour))

    if wanted.flashing is not state.flashing:
        needed.append(Control.FLASH if wanted.flashing else Control.STEADY)
    if wanted.double_height is not state.double_height:
        needed.append(
            Control.DOUBLE_HEIGHT if wanted.double_height else Control.NORMAL_HEIGHT
        )
    if wanted.held is not state.held:
        needed.append(Control.HOLD_GRAPHICS if wanted.held else Control.RELEASE_GRAPHICS)
    if wanted.concealed and not state.concealed:
        needed.append(Control.CONCEAL)
    return needed


@dataclass(frozen=True)
class _Plan:
    runs: list[Run]
    attributes: list[tuple[int, Control]]


