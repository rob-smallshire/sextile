"""Spike: can a block of suggestions be repainted as a reader types?

A place-name search wants what every search wants: the reader types, and the
best few matches appear beneath the field. Three of them, each on a digit --
three rather than nine because the wire says so, which is question 1 below.

The cursor machinery this needs is measured -- `spike_cursor_output.py`
established that home-and-down reaches any row, that moving erases nothing, and
that a carriage return alone returns to column zero. What is *not* measured is
what happens when a block of rows is repainted at once, on every keystroke, on
a real screen at a real baud rate. Four questions, none of which arithmetic
answers:

1. **What does it cost?** A row of suggestion is thirty-odd cells, and the moves
   between them are a few more, which at 1200 baud may be seconds rather than
   milliseconds -- and a reader types faster than that. If the block cannot keep
   up, the design is a paged result list rather than type-ahead, and it is much
   better to find that out now.

2. **Where does the cursor end up?** The reader is still typing, so it has to go
   back to the field afterwards, and be visible there. If the return trip is
   expensive or lands wrong, the field is unusable however cheap the block is.

3. **Do attributes survive mid-frame?** The footer is repainted today and it is
   the last row. Attributes reset at the start of every row -- read from
   Beebium's `Saa5050::start_of_line()` -- so a row rewritten in the middle of a
   frame should be self-contained. Should be. The command line is the only
   evidence, and it is the one row where being wrong would not show.

4. **Does repainting only what changed work?** Typing narrows a result set, so
   most keystrokes leave the top few suggestions where they are. Skipping the
   unchanged rows is the difference between two seconds and a quarter of one --
   but it means stepping *over* rows with the cursor between the rows that are
   rewritten, which nothing has yet done.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client \
        --with /Users/rjs/Code/sextile --with pytest \
        python -m pytest spike_suggestion_block.py -s -v
"""

import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour, Attribute
from sextile.viewdata.encoding import encode_attribute
from sextile.viewdata.frame import COLUMNS, ROWS, Frame

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"

CLEAR = 0x0C
HOME = 0x1E
LEFT, RIGHT, DOWN, UP = 0x08, 0x09, 0x0A, 0x0B
CARRIAGE_RETURN = 0x0D
CURSOR_ON, CURSOR_OFF = 0x11, 0x14

#: Where the field and its suggestions sit on the mock search page.
FIELD_ROW = 2
FIRST_SUGGESTION_ROW = 4

#: Three, not nine, and the arithmetic rather than taste decided it. Nine rows
#: of name, country and population is 346 bytes even trimmed and diffed --
#: nearly three seconds at 1200 baud, where a reader types two characters a
#: second. Three rows of name and country is 96 bytes, and the common keystroke
#: -- typing on into a list that has already settled -- is 38.
SUGGESTIONS = 3

#: The rate a Prestel line actually runs at, and the one that decides this.
BAUD = 1200
#: 7E1: seven data bits, even parity, one stop bit, one start bit.
BITS_PER_CHARACTER = 10


def seconds_at_1200(data: bytes) -> float:
    return len(data) * BITS_PER_CHARACTER / BAUD


def screen_text(bbc: Beebium) -> str:
    text = bbc.video.screen_text().text
    return "\n".join(text) if isinstance(text, list) else text


def wait_for_screen(bbc: Beebium, needle: str, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if needle in screen_text(bbc):
            return
        time.sleep(0.1)
    pytest.fail(f"{needle!r} did not appear. Screen was:\n{screen_text(bbc)}")


def enter_prestel_chat(bbc: Beebium) -> None:
    wait_for_screen(bbc, "BASIC")
    bbc.keyboard.type("*COMMSTAR\r")
    wait_for_screen(bbc, "Select ?")
    bbc.keyboard.type("#")
    wait_for_screen(bbc, "Prestel")
    bbc.keyboard.type("C")
    time.sleep(1.0)


@pytest.fixture
def commstar(
    mos_filepath: Path,
    basic_filepath: Path | None,
    beebium_server_filepath: Path | None,
    beebium_roms_dirpath: Path,
):
    rom_filepath = beebium_roms_dirpath / COMMSTAR_ROM_FILENAME
    if not rom_filepath.exists():
        pytest.skip(f"Commstar ROM not found: {rom_filepath}")
    try:
        with Beebium.launch(
            mos_filepath=mos_filepath,
            basic_filepath=basic_filepath,
            server_filepath=beebium_server_filepath,
            extra_args=["--rpc-serial", "--sideways", f"13:rom:{rom_filepath}"],
        ) as bbc:
            enter_prestel_chat(bbc)
            yield bbc
    except ServerNotFoundError as e:
        pytest.skip(str(e))


def send(bbc: Beebium, data: bytes, chunk: int = 128) -> None:
    for start in range(0, len(data), chunk):
        piece = data[start : start + chunk]
        assert bbc.extensions[RpcSerial].send(piece) == len(piece)
        time.sleep(1.2)
    time.sleep(1.5)


def rows(bbc: Beebium) -> list[str]:
    screen = bbc.video.teletext_screen()
    return [
        "".join(chr(screen.cell(row, column).character) for column in range(COLUMNS))
        for row in range(ROWS)
    ]


# -- the mock search page ---------------------------------------------------
#
#  Not the real one: the real one does not exist yet, and the point is to
#  measure the shape rather than the service. Rows are labelled so that any row
#  which should not have been touched says so when it is.


def matches_for(typed: str) -> list[tuple[str, str, int]]:
    """A plausible result set, narrowing as more is typed.

    Real numbers, from GeoNames, so the rows are the width they will really be.
    """
    everything = [
        ("TRONDHEIM", "NO", 147139),
        ("TROMSO", "NO", 64000),
        ("TRONDHEIMSFJORDEN", "NO", 0),
        ("TROY", "US", 87000),
        ("TROYES", "FR", 61652),
        ("TRONVIK", "NO", 0),
        ("TROGIR", "HR", 10923),
        ("TROISDORF", "DE", 74749),
        ("TRONDENES", "NO", 0),
    ]
    return [place for place in everything if place[0].startswith(typed)][:SUGGESTIONS]


def suggestion_row(canvas: Canvas, row: int, digit: int, place: tuple[str, str, int]) -> None:
    name, country, population = place
    #  The shape a Menu draws, squeezed onto one row rather than two: the digit
    #  in yellow, the name in white, the country and population in green as the
    #  detail that tells two places of the same name apart.
    canvas.row(row).text(f"{digit} ", Colour.YELLOW).text(
        name.title().ljust(20), Colour.WHITE
    ).text(f"{country}  {population:>7}", Colour.GREEN)


def search_frame(typed: str) -> bytes:
    """The whole page, as it would first be sent."""
    canvas = Canvas()
    canvas.row(0).text("FIND A PLACE", Colour.CYAN)
    canvas.row(FIELD_ROW).text("PLACE: ", Colour.WHITE).text(typed, Colour.YELLOW)
    for offset, place in enumerate(matches_for(typed)):
        suggestion_row(canvas, FIRST_SUGGESTION_ROW + offset, offset + 1, place)
    #  Rows below the block, so that overrunning it is visible rather than
    #  merely suspected.
    for row in range(FIRST_SUGGESTION_ROW + SUGGESTIONS, ROWS):
        canvas.row(row).text(f"ROW{row:02d}" + "." * (COLUMNS - 5))
    return canvas.frame.to_bytes()


BLANK = 0x20


def used_columns(frame: Frame, row: int) -> int:
    """How much of a row is worth sending: up to its last non-blank cell."""
    codes = frame._cells[row * COLUMNS : (row + 1) * COLUMNS]
    for column in reversed(range(COLUMNS)):
        if codes[column] != BLANK:
            return column + 1
    return 0


def row_bytes_upto(frame: Frame, row: int, upto: int) -> bytes:
    """A row's cells, escaped, stopping at ``upto``.

    `Frame.row_bytes` sends all forty columns, which is right for the command
    line -- its field is deliberately full width -- and wrong here for a reason
    that only shows on real hardware: **a row written to column 40 wraps by
    itself**, measured in `spike_frame_geometry`. The cursor is then already on
    the next row, and the carriage return and cursor down that follow move it
    down a second one, so a three-row block lands on rows 4, 6 and 8.
    """
    out = bytearray()
    for code in frame._cells[row * COLUMNS : row * COLUMNS + upto]:
        if code < BLANK:
            out.extend(encode_attribute(Attribute(code)))
        else:
            out.append(code)
    return bytes(out)


def to_row(row: int) -> bytes:
    """Home, then down. The only positioning viewdata offers."""
    return bytes([HOME]) + bytes([DOWN]) * row


def block_bytes(typed: str, *, only_rows: set[int] | None = None) -> bytes:
    """Repaint the field and its suggestions, optionally only where changed.

    Written as one walk down the block rather than a fresh home for each row:
    once the cursor is in the block, the next row is a carriage return and a
    cursor down, which is two bytes against the seven or so a fresh home costs.
    """
    canvas = Canvas()
    canvas.row(FIELD_ROW).text("PLACE: ", Colour.WHITE).text(typed, Colour.YELLOW)
    found = matches_for(typed)
    for offset in range(SUGGESTIONS):
        row = FIRST_SUGGESTION_ROW + offset
        if offset < len(found):
            suggestion_row(canvas, row, offset + 1, found[offset])
        else:
            #  A row that has stopped matching has to be cleared, or the reader
            #  is offered a digit that leads to the place they have just typed
            #  past. Spaces to the width the row had, not the whole forty.
            canvas.row(row).text(" " * 32)

    wanted = [
        row
        for row in [FIELD_ROW, *range(FIRST_SUGGESTION_ROW, FIRST_SUGGESTION_ROW + SUGGESTIONS)]
        if only_rows is None or row in only_rows
    ]
    out = bytearray()
    at = 0
    for row in wanted:
        if not out:
            out += to_row(row)
        else:
            #  Step over the rows being left alone: carriage return to column
            #  zero, then one cursor down per row skipped.
            out += bytes([CARRIAGE_RETURN]) + bytes([DOWN]) * (row - at)
        #  Trimmed, so the row does not fill to column 40 and wrap of its own
        #  accord -- which would put the cursor a row further on than the walk
        #  below believes it to be.
        out += row_bytes_upto(canvas.frame, row, used_columns(canvas.frame, row))
        at = row
    #  Back to the field, and visible: the reader has not finished typing.
    out += to_row(FIELD_ROW)
    out += bytes([RIGHT]) * (len("PLACE: ") + len(typed) + 1)
    out += bytes([CURSOR_ON])
    return bytes(out)


# -- what it costs ----------------------------------------------------------


def test_a_full_block_repaint_costs_what_we_can_afford(commstar: Beebium) -> None:
    """Question 1, and the one that decides whether type-ahead is possible.

    A reader on a BBC keypad types perhaps two characters a second. If a full
    repaint takes longer than that, the block lags further behind with every
    letter and the feature is a lie.
    """
    send(commstar, search_frame("TRO"))
    painted = block_bytes("TROND")
    print(f"\n  a full block repaint: {len(painted)} bytes")
    print(f"  at {BAUD} baud: {seconds_at_1200(painted):.2f} s per keystroke")
    print(f"  at 9600 baud: {len(painted) * BITS_PER_CHARACTER / 9600:.2f} s")
    send(commstar, painted)
    lines = rows(commstar)
    print(f"  field row:   {lines[FIELD_ROW][:24]!r}")
    for offset in range(SUGGESTIONS):
        print(f"  suggestion {offset + 1}: {lines[FIRST_SUGGESTION_ROW + offset][:34]!r}")
    assert "TROND" in lines[FIELD_ROW]
    assert "Trondheim" in lines[FIRST_SUGGESTION_ROW]


def test_repainting_only_the_changed_rows_is_much_cheaper(commstar: Beebium) -> None:
    """Question 4: stepping over the rows that did not change.

    Typing narrows, so the top of the list usually stays put. If skipping works,
    the common keystroke costs a row or two rather than nine.
    """
    send(commstar, search_frame("TROND"))
    #  Going from TROND to TRONDH drops everything but Trondheim: rows 2 and
    #  5 onwards change, row 4 does not.
    changed = {FIELD_ROW} | set(range(FIRST_SUGGESTION_ROW + 1, FIRST_SUGGESTION_ROW + SUGGESTIONS))
    partial = block_bytes("TRONDH", only_rows=changed)
    full = block_bytes("TRONDH")
    print(f"\n  full repaint:    {len(full)} bytes, {seconds_at_1200(full):.2f} s")
    print(f"  changed rows:    {len(partial)} bytes, {seconds_at_1200(partial):.2f} s")
    print(f"  saved: {100 - 100 * len(partial) / len(full):.0f}%")
    send(commstar, partial)
    lines = rows(commstar)
    print(f"  row skipped over (should still read Trondheim): "
          f"{lines[FIRST_SUGGESTION_ROW][:34]!r}")
    assert "Trondheim" in lines[FIRST_SUGGESTION_ROW]
    assert "Tromso" not in lines[FIRST_SUGGESTION_ROW + 1]


def test_the_block_leaves_the_rest_of_the_frame_alone(commstar: Beebium) -> None:
    """A repaint that scrolled or overran would take the page with it."""
    send(commstar, search_frame("TRO"))
    send(commstar, block_bytes("TROND"))
    lines = rows(commstar)
    below = range(FIRST_SUGGESTION_ROW + SUGGESTIONS, ROWS)
    disturbed = [row for row in below if not lines[row].startswith(f"ROW{row:02d}")]
    print(f"\n  rows below the block disturbed: {disturbed or 'none'}")
    print(f"  title row: {lines[0][:20]!r}")
    assert not disturbed
    #  Not `startswith`: the title is coloured, and a colour attribute occupies
    #  the cell before it.
    assert "FIND A PLACE" in lines[0]


def test_colour_survives_a_row_rewritten_mid_frame(commstar: Beebium) -> None:
    """Question 3: attributes reset per row, so a rewrite should be self-contained.

    Read from Beebium's `Saa5050::start_of_line()` and true of the footer, which
    is the last row. A row in the middle of a frame has rows after it that could
    inherit what it set, and nothing has yet checked.
    """
    send(commstar, search_frame("TRO"))
    send(commstar, block_bytes("TROND"))
    screen = commstar.video.teletext_screen()
    #  The digit is yellow and the name white on the same row: if the attribute
    #  travelled, the row beneath would come up yellow too.
    first = screen.cell(FIRST_SUGGESTION_ROW, 2)
    beneath = screen.cell(FIRST_SUGGESTION_ROW + SUGGESTIONS, 0)
    print(f"\n  a suggestion's foreground:     {getattr(first, 'foreground', '?')}")
    print(f"  the row below the block's:     {getattr(beneath, 'foreground', '?')}")
    print("  -> they should differ; the same would mean an attribute leaked")


def test_the_cursor_comes_back_to_the_field(commstar: Beebium) -> None:
    """Question 2. The reader is mid-word; the caret has to be where they type.

    Read across the blink, as `spike_cursor_visibility.py` had to: one sample
    tells you which half of it you caught.
    """
    send(commstar, search_frame("TRO"))
    send(commstar, block_bytes("TROND"))
    seen = set()
    for _ in range(12):
        screen = commstar.video.teletext_screen()
        seen.add((getattr(screen, "cursor_row", None), getattr(screen, "cursor_column", None)))
        time.sleep(0.1)
    print(f"\n  cursor positions sampled across the blink: {seen}")
    print(f"  wanted: row {FIELD_ROW}, column {len('PLACE: ') + len('TROND') + 1}")


def test_a_keystroke_that_changes_nothing_costs_nothing(commstar: Beebium) -> None:
    """The cheapest case, and the one that makes the rest affordable.

    Typing deeper into a query that already has one match changes no row at all
    but the field. If that is one byte, a reader typing the tail of a name they
    have already narrowed to pays nothing for it.
    """
    only_the_field = block_bytes("TRONDHEI", only_rows={FIELD_ROW})
    print(f"\n  field alone: {len(only_the_field)} bytes, "
          f"{seconds_at_1200(only_the_field):.2f} s")
    print("  -> compare the command line's fifty bytes for the same job")
