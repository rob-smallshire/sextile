"""The SAA5050 attribute model, and the plan of attributes for one row.

A style is every attribute the hardware has; a run or a panel is a thing placed
on a row in some style. Given the runs and panels of a row already positioned,
`_row_events` walks them in order and `_attributes_for` works out the shortest
run of attributes that carries one style into the next -- an attribute occupies
a cell, so the fewer the better, and some transitions the hardware cannot make
at all. `sextile.viewdata.composition` decides *where* things go and drives this
to decide *what colour* they come out.
"""

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final

from sextile.viewdata.controls import Attribute, Colour, alpha_colour, graphics_colour
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.measure import cell_count


class DoesNotFit(ValueError):
    """A composition that cannot be drawn, and why."""


@dataclass(frozen=True)
class Style:
    """How a run is to be displayed: every attribute the SAA5050 has.

    Not every combination is reachable from every other in one cell, which is
    why this is a value handed to a compositor rather than a sequence of
    attributes written by hand. A background is the worst of them: the
    hardware has no "set background" attribute, only "make the current
    foreground the background", so white on blue costs three cells -- choose
    blue, make it the background, choose white again.
    """

    colour: Colour = Colour.WHITE
    background: Colour = Colour.BLACK
    separated: bool = False
    flashing: bool = False
    double_height: bool = False
    hold_graphics: bool = False
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


@dataclass(frozen=True)
class _Plan:
    runs: list[Run]
    attributes: list[tuple[int, Attribute]]


def _opening_style(within: "Panel | None") -> Style:
    """The style in force where a run is going, before the run says anything.

    Inside a panel, the colour is the panel's and so is the background -- which
    is why a run drawn on a panel pays for its own colour and nothing else.
    """
    if within is None:
        return OPENING
    return Style(colour=within.colour, background=within.colour)


def _with_panel_background(style: Style, within: "Panel | None") -> Style:
    """A style with the background of the panel it is going on, if it wants one.

    A run that says nothing about a background takes the panel's. It has to be
    known where a run is placed as well as where the row is planned, because what
    a run costs in attributes is what decides where it can start.
    """
    if within is None or style.background is not Colour.BLACK:
        return style
    return replace(style, background=within.colour)


def _row_events(
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


def _style_after(
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
            return replace(run, style=_with_panel_background(run.style, panel))
    return run


def _attributes_for(state: Style, graphics: bool, run: Run) -> list[Attribute]:
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
    needed: list[Attribute] = []
    colour_of = graphics_colour if run.graphics else alpha_colour
    foreground = state.colour

    if wanted.background is not state.background:
        if wanted.background is Colour.BLACK:
            needed.append(Attribute.BLACK_BACKGROUND)
        else:
            #  There is no "set background": the current foreground becomes it.
            needed.append(colour_of(wanted.background))
            needed.append(Attribute.NEW_BACKGROUND)
            foreground = wanted.background

    if run.graphics and wanted.separated is not state.separated:
        needed.append(
            Attribute.SEPARATED_GRAPHICS if wanted.separated else Attribute.CONTIGUOUS_GRAPHICS
        )

    #  The colour attribute chooses the character set as well, so it is needed
    #  whenever either changes.
    if foreground is not wanted.colour or graphics is not run.graphics:
        needed.append(colour_of(wanted.colour))

    if wanted.flashing is not state.flashing:
        needed.append(Attribute.FLASH if wanted.flashing else Attribute.STEADY)
    if wanted.double_height is not state.double_height:
        needed.append(
            Attribute.DOUBLE_HEIGHT if wanted.double_height else Attribute.NORMAL_HEIGHT
        )
    if wanted.hold_graphics is not state.hold_graphics:
        needed.append(
            Attribute.HOLD_GRAPHICS if wanted.hold_graphics else Attribute.RELEASE_GRAPHICS
        )
    if wanted.concealed and not state.concealed:
        needed.append(Attribute.CONCEAL)
    return needed
