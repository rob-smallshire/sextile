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
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Final

from sextile.viewdata.blocks import BLOCKS_ACROSS, LEFT_BLOCKS, RIGHT_BLOCKS, shifted
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.charset import mosaic_code
from sextile.viewdata.controls import Colour, Control, alpha_colour, graphics_colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS, ROWS


class DoesNotFit(ValueError):
    """A composition that cannot be drawn, and why."""


class Align(Enum):
    """Where to put something, for a caller that would rather not count.

    Given instead of a column. Centring is accounting about attributes -- what
    a style costs in cells decides whether the middle is reachable at all --
    and that accounting is what a composition is for. A caller doing it has to
    know the cost before it knows the column, which is knowing this module's
    business, and three callers who did came out a cell and a half apart.
    """

    LEFT = "left"
    CENTRE = "centre"
    RIGHT = "right"


#: A column, or a request to be put somewhere.
Where = int | Align

#: What a panel costs to the left of its own first cell: one, to choose the
#: colour that the next cell then promotes to the background. That next cell is
#: the panel's own, and is already coloured -- the hardware sets a background at
#: the attribute cell rather than after it.
_PANEL_ATTRIBUTES: Final = 1


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


@dataclass(frozen=True)
class Panel:
    """A coloured rectangle, cell-aligned, with things drawn on top of it.

    `column` is its first coloured cell, which is the one carrying
    NEW_BACKGROUND: the hardware sets a background *at* the attribute cell
    rather than after it, so that cell is already the colour it asks for. The
    cell before it is not -- it is where the colour is chosen, and a colour
    attribute cannot colour itself -- so a panel always costs one black cell
    to its left, and content inside it starts at least one cell in from the
    left-hand edge.
    """

    column: int
    width: int
    colour: Colour
    rows: tuple[int, ...] = ()

    @property
    def end(self) -> int:
        """One past the last coloured cell."""
        return self.column + self.width

    def covers(self, run: Run) -> bool:
        return self.column <= run.column and run.end <= self.end


@dataclass
class Composition:
    """Things to place on a frame, and where."""

    runs: dict[int, list[Run]] = field(default_factory=dict)
    panels: dict[int, list[Panel]] = field(default_factory=dict)

    def panel(
        self,
        row: int,
        where: Where,
        *,
        width: int,
        colour: Colour,
        rows: int = 1,
    ) -> Panel:
        """A coloured rectangle, `rows` deep, returned so things can go in it.

        A background is not a property of what is written on it: it belongs to
        the field, it lasts to the end of the row unless something stops it,
        and it costs cells that the things written on it would otherwise have
        to account for. So it is declared once, here, and a run drawn within it
        takes it without saying anything.
        """
        column = self._aligned(width, _PANEL_ATTRIBUTES, where)
        panel = Panel(
            column=column,
            width=width,
            colour=colour,
            rows=tuple(range(row, row + rows)),
        )
        for covered in panel.rows:
            if not 0 <= covered < ROWS:
                raise DoesNotFit(f"row {covered} is not on the frame")
            self.panels.setdefault(covered, []).append(panel)
        return panel

    def text(
        self,
        row: int,
        where: Where,
        words: str,
        colour: Colour = Colour.WHITE,
        *,
        within: Panel | None = None,
        style: Style | None = None,
    ) -> "Composition":
        """Place text at a column.

        ``colour`` is the common case said briefly; ``style`` is everything the
        hardware can do. Double height places the same text on the row below as
        well, because that is how the SAA5050 draws the bottom halves.
        """
        wanted = style if style is not None else Style(colour=colour)
        run = self._positioned(Run(column=0, style=wanted, words=words), where, within)
        self._add(row, run)
        if wanted.double_height:
            self._add(row + 1, run)
        return self

    def blocks(
        self,
        row: int,
        where: Where,
        patterns: Sequence[int],
        colour: Colour = Colour.WHITE,
        *,
        within: Panel | None = None,
        separated: bool = False,
        style: Style | None = None,
    ) -> "Composition":
        """Place a run of mosaic blocks, which is a picture one row tall."""
        return self.picture(
            row, where, [patterns], colour, within=within, separated=separated, style=style
        )

    def picture(
        self,
        row: int,
        where: Where,
        rows: Sequence[Sequence[int]],
        colour: Colour = Colour.WHITE,
        *,
        within: Panel | None = None,
        separated: bool = False,
        style: Style | None = None,
    ) -> "Composition":
        """Place several rows of mosaic blocks that belong together.

        As one thing, because they have to be positioned as one thing: a
        picture centred a row at a time would have each row measure its own ink
        and some would take the half-cell shift while others did not, and the
        picture would shear.
        """
        wanted = (
            style if style is not None else Style(colour=colour, separated=separated)
        )
        placed = [tuple(pattern for pattern in patterns) for patterns in rows]
        column, half = self._placement(placed, wanted, where, within)
        if half:
            placed = [tuple(shifted(patterns)) for patterns in placed]
        width = max((len(patterns) for patterns in placed), default=0)
        for offset, patterns in enumerate(placed):
            self._add(
                row + offset,
                Run(
                    column=column,
                    style=wanted,
                    patterns=patterns + (0,) * (width - len(patterns)),
                ),
            )
        return self

    def _placement(
        self,
        rows: Sequence[Sequence[int]],
        style: Style,
        where: Where,
        within: Panel | None = None,
    ) -> tuple[int, bool]:
        """The column a picture starts at, and whether to shift it half a cell.

        Centred on the *ink* rather than on the cells it happens to occupy. A
        cell is two blocks, so cells alone leave a picture up to a block and a
        half out -- three quarters of a cell, and plainly visible above a line
        of text. Where the nearer of the two is half way into a cell, the
        picture takes a blank block before it, which costs nothing: a blank
        block and an attribute cell look the same on the screen.
        """
        width = max((len(patterns) for patterns in rows), default=0)
        probe = Run(column=0, style=_inherited(style, within), patterns=(0,) * width)
        needed = len(_attributes_for(_opening(within), False, probe))
        if where is not Align.CENTRE:
            return self._aligned(width, needed, where, within), False
        first, last = _ink(rows)
        if first is None or last is None:
            return self._aligned(width, needed, where, within), False
        room, origin = _region(within)
        left = _centre(last - first + 1, room=room * BLOCKS_ACROSS) - first
        column, half = divmod(left + origin * BLOCKS_ACROSS, BLOCKS_ACROSS)
        least = _least(needed, within)
        return (column, bool(half)) if column >= least else (least, False)

    def _aligned(
        self, width: int, needed: int, where: Where, within: Panel | None = None
    ) -> int:
        """The column for something `width` cells wide, in cells alone."""
        if isinstance(where, int):
            return where
        room, origin = _region(within)
        least = _least(needed, within)
        if where is Align.RIGHT:
            return max(origin + room - width, least)
        if where is Align.LEFT:
            return least
        return max(origin + _centre(width, room=room), least)

    def _positioned(self, run: Run, where: Where, within: Panel | None = None) -> Run:
        """A run of text moved to where it was asked to go.

        Text has no half-cells to be positioned in, so this is cells alone.
        """
        probe = replace(run, style=_inherited(run.style, within))
        needed = len(_attributes_for(_opening(within), False, probe))
        return replace(run, column=self._aligned(run.cells, needed, where, within))

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
        for row in self._occupied():
            try:
                self._plan(row)
            except DoesNotFit as trouble:
                found.append(str(trouble))
        return found

    def fits(self) -> bool:
        return not self.problems()

    def draw(self, canvas: Canvas) -> None:
        """Draw it, or raise ``DoesNotFit`` having drawn nothing."""
        planned = {row: self._plan(row) for row in self._occupied()}
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

    def _occupied(self) -> list[int]:
        """Every row with anything on it, a panel with nothing on it included."""
        return sorted(set(self.runs) | set(self.panels))

    def _plan(self, row: int) -> "_Plan":
        """Where the attributes go on one row, or why they cannot go anywhere."""
        runs = sorted(self.runs.get(row, []), key=lambda run: run.column)
        for earlier, later in zip(runs, runs[1:], strict=False):
            if earlier.end > later.column:
                raise DoesNotFit(
                    f"row {row}: a run ending at column {earlier.end} overlaps one "
                    f"beginning at {later.column}"
                )

        panels = sorted(self.panels.get(row, []), key=lambda panel: panel.column)
        state, graphics = OPENING, False
        attributes: list[tuple[int, Control]] = []
        free = 0
        for at, kind, what in _events(runs, panels):
            marker = _marked(kind, what, state, panels)
            wanted = _attributes_for(state, graphics, marker)
            gap = at - free
            if len(wanted) > gap:
                raise DoesNotFit(
                    f"row {row}: the {kind if kind != 'run' else 'run'} at column "
                    f"{at} needs {len(wanted)} attribute cell(s) before it and "
                    f"only {gap} are free"
                )
            #  As late as possible, which leaves the earlier cells of the gap in
            #  the previous style -- they are blank either way, and it keeps the
            #  attributes next to what they explain.
            for offset, attribute in enumerate(wanted):
                attributes.append((at - len(wanted) + offset, attribute))
            state, graphics = marker.style, marker.graphics
            free = marker.end if kind == "run" else at
        return _Plan(runs=runs, attributes=attributes)


def _region(within: "Panel | None") -> tuple[int, int]:
    """How much room something has, and where that room starts."""
    return (COLUMNS, 0) if within is None else (within.width, within.column)


def _least(needed: int, within: "Panel | None") -> int:
    """The leftmost column a run may start at, its own attributes allowed for.

    Inside a panel that is one cell in from the edge, because the panel's own
    first cell is the attribute that colours it.
    """
    return (0 if within is None else within.column + 1) + needed


def _inherited(style: Style, within: "Panel | None") -> Style:
    """A style with the background of the panel it is going on, if it wants one.

    A run that says nothing about a background takes the panel's. It has to be
    known here as well as when the row is planned, because what a run costs in
    attributes is what decides where it can start.
    """
    if within is None or style.background is not Colour.BLACK:
        return style
    return replace(style, background=within.colour)


def _opening(within: "Panel | None") -> Style:
    """The style in force where a run is going, before the run says anything.

    Inside a panel, the colour is the panel's and so is the background -- which
    is why a run drawn on a panel pays for its own colour and nothing else.
    """
    if within is None:
        return OPENING
    return Style(colour=within.colour, background=within.colour)


def _events(
    runs: Sequence[Run], panels: Sequence["Panel"]
) -> list[tuple[int, str, "Run | Panel | None"]]:
    """Everything that happens along a row, in the order it happens.

    A panel opens one cell before the column its colour appears in, because the
    attribute that promotes the colour is set *at* its cell and that cell is the
    panel's first. It closes one cell after its last, for the same reason.
    """
    events: list[tuple[int, str, Run | Panel | None]] = []
    for panel in panels:
        events.append((panel.column + 1, "open", panel))
        if panel.end < COLUMNS:
            events.append((panel.end + 1, "close", None))
    events += [(run.column, "run", run) for run in runs]
    order = {"open": 0, "run": 1, "close": 2}
    return sorted(events, key=lambda event: (event[0], order[event[1]]))


def _centre(width: int, *, room: int = COLUMNS) -> int:
    """Where something `width` wide starts to sit in the middle of `room`.

    Left-biased where it cannot be exact -- an odd number of spare cells has to
    go somewhere -- and always the same way, so two things centred on the same
    frame are out by at most half of one and never in opposite directions.
    """
    return max((room - width) // 2, 0)


def _ink(rows: Sequence[Sequence[int]]) -> tuple[int | None, int | None]:
    """The first and last block of a picture that is lit, across all its rows."""
    lit = [
        index * BLOCKS_ACROSS + half
        for patterns in rows
        for index, pattern in enumerate(patterns)
        for half, mask in ((0, LEFT_BLOCKS), (1, RIGHT_BLOCKS))
        if pattern & mask
    ]
    return (min(lit), max(lit)) if lit else (None, None)


def _marked(
    kind: str, what: "Run | Panel | None", state: Style, panels: Sequence["Panel"]
) -> Run:
    """The style the row is to be in after this event, as a run to ask about.

    A run drawn on a panel and saying nothing about a background takes the
    panel's, which is the point of declaring the panel: a run that turned the
    background off in the middle of a box would put a black hole in it.
    """
    if kind == "close":
        return Run(column=0, style=replace(state, background=Colour.BLACK))
    if isinstance(what, Panel):
        return Run(column=0, style=Style(colour=what.colour, background=what.colour))
    run = what
    assert isinstance(run, Run)
    for panel in panels:
        if panel.covers(run):
            return replace(run, style=_inherited(run.style, panel))
    return run


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


