"""The SAA5050 display walk: a built frame read as the chip reads it.

A control code occupies a cell and changes the style of the cells after it -- or,
for a background, of its own cell (`viewdata.display` calls this set-at, against
the set-after of the rest). This walks a frame row by row, left to right, the way
the chip does, and yields the runs a renderer draws, so `render_ansi` and
`render_html` share one implementation of the display rules rather than each
re-deriving them.

The rules it implements, verified against Beebium's `Saa5050`, are written up in
`docs/reference/display-semantics.md`: set-at backgrounds, hold graphics,
conceal, flash, separated graphics, double height, and the reset at the start of
every row.
"""

from collections.abc import Iterator
from dataclasses import dataclass, replace

from sextile.viewdata.charset import decode_g0, mosaic_pattern
from sextile.viewdata.controls import GRAPHICS_COLOURS, Attribute, Colour, colour_of
from sextile.viewdata.frame import COLUMNS, ROWS, Frame

__all__ = [
    "CellStyle",
    "StyledRun",
    "styled_cells",
]

#  Codes that still show a letter while graphics are selected, rather than a
#  mosaic: the alphanumeric island the sixth mosaic bit is displaced to skip.
_ALPHA_IN_GRAPHICS = range(0x40, 0x60)


@dataclass(frozen=True)
class CellStyle:
    """Every attribute the SAA5050 carries, as it stands at one cell.

    Attributes:
        colour: The foreground colour.
        background: The background colour.
        graphics: Whether mosaics are selected rather than letters.
        separated: Whether mosaics are drawn separated (gaps between blocks).
        double_height: Whether the row is drawn twice as tall.
        flashing: Whether the run flashes.
        concealed: Whether the run is hidden until revealed.
    """

    colour: Colour = Colour.WHITE
    background: Colour = Colour.BLACK
    graphics: bool = False
    separated: bool = False
    double_height: bool = False
    flashing: bool = False
    concealed: bool = False


@dataclass(frozen=True)
class StyledRun:
    """A run of cells sharing a style: text, or mosaic patterns.

    Exactly one of `text` and `patterns` is non-empty. `text` is decoded
    characters, ready to show; `patterns` is six-bit mosaic patterns, which a
    renderer maps to whichever characters its font draws mosaics with.

    Attributes:
        style: The style every cell of the run is in.
        text: The characters, for a run of letters, digits or spaces.
        patterns: The mosaic patterns, for a run of graphics.
    """

    style: CellStyle
    text: str = ""
    patterns: tuple[int, ...] = ()


def styled_cells(frame: Frame) -> Iterator[list[StyledRun]]:
    """The frame as `ROWS` lists of runs, each row read left to right.

    Args:
        frame: The built frame to read.

    Yields:
        One list of `StyledRun` per row, in top-to-bottom order. Every row
        starts white on black in alpha, whatever the row above ended in.
    """
    for row in range(ROWS):
        yield _row_runs(frame, row)


def _apply(code: int, style: CellStyle) -> CellStyle:
    """The style after a spacing attribute, before the cost of its own cell."""
    colour = colour_of(code)
    if colour is not None:
        #  A colour code chooses the character set too, and reveals concealed
        #  text from here to the end of the row.
        return replace(
            style, colour=colour, graphics=code in GRAPHICS_COLOURS, concealed=False
        )
    match code:
        case Attribute.FLASH:
            return replace(style, flashing=True)
        case Attribute.STEADY:
            return replace(style, flashing=False)
        case Attribute.DOUBLE_HEIGHT:
            return replace(style, double_height=True)
        case Attribute.NORMAL_HEIGHT:
            return replace(style, double_height=False)
        case Attribute.CONTIGUOUS_GRAPHICS:
            return replace(style, separated=False)
        case Attribute.SEPARATED_GRAPHICS:
            return replace(style, separated=True)
        case Attribute.BLACK_BACKGROUND:
            return replace(style, background=Colour.BLACK)
        case Attribute.NEW_BACKGROUND:
            return replace(style, background=style.colour)
        case Attribute.CONCEAL:
            return replace(style, concealed=True)
        case _:
            return style


def _row_runs(frame: Frame, row: int) -> list[StyledRun]:
    runs: list[StyledRun] = []
    style = CellStyle()
    hold = False
    held: int | None = None
    pending: list[str] | list[int] = []
    run_style: CellStyle | None = None
    graphics_run = False

    def flush() -> None:
        nonlocal pending, run_style
        if run_style is None:
            return
        if graphics_run:
            runs.append(StyledRun(style=run_style, patterns=tuple(pending)))  # type: ignore[arg-type]
        else:
            runs.append(StyledRun(style=run_style, text="".join(pending)))  # type: ignore[arg-type]
        pending = []
        run_style = None

    def emit(cell_style: CellStyle, *, graphics: bool, char: str = "", pattern: int = 0) -> None:
        nonlocal run_style, graphics_run
        if cell_style != run_style or graphics != graphics_run:
            flush()
            run_style, graphics_run = cell_style, graphics
        if graphics:
            pending.append(pattern)  # type: ignore[arg-type]
        else:
            pending.append(char)  # type: ignore[arg-type]

    for column in range(COLUMNS):
        code = frame.cell(row, column)
        if frame.is_attribute(row, column):
            new = _apply(code, style)
            holding = hold or code == Attribute.HOLD_GRAPHICS
            #  A background is set at its own cell; every other attribute is set
            #  after it, so the attribute cell shows the old style but the new
            #  background.
            set_at = code in (Attribute.BLACK_BACKGROUND, Attribute.NEW_BACKGROUND)
            cell_style = new if set_at else style
            if holding and held is not None:
                #  A held control cell repeats the last mosaic instead of blanking.
                emit(replace(cell_style, graphics=True), graphics=True, pattern=held)
            else:
                emit(cell_style, graphics=False, char=" ")
            if code == Attribute.HOLD_GRAPHICS:
                hold = True
            elif code == Attribute.RELEASE_GRAPHICS:
                hold = False
            if colour_of(code) is not None and code not in GRAPHICS_COLOURS:
                held = None  # an alpha colour forgets the held mosaic
            style = new
        elif style.graphics and code not in _ALPHA_IN_GRAPHICS:
            pattern = mosaic_pattern(code)
            held = pattern
            emit(style, graphics=True, pattern=pattern)
        else:
            emit(style, graphics=False, char=decode_g0(code))
    flush()
    return runs
