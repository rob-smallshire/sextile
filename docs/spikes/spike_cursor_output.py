"""Spike: can we move Commstar's cursor and overwrite one row?

Commstar does not echo a `*123#` page request -- confirmed by watching a tcpser
trace while typing one -- so if a reader is to see what they are typing, Sextile
must draw it. Redrawing the whole frame per keystroke is out: even trimmed, that
is a quarter of a second of paint per digit at 9600 baud.

So the question is whether the cursor can be moved without redrawing: home, then
down to the footer row, then overwrite just that. Viewdata has no absolute
cursor addressing -- Prestel never needed it, because terminals echoed page
requests locally -- so this would be home plus relative moves.

The codes are known as *input*: the BBC's arrow keys send 0x08-0x0B. Whether
Commstar acts on them as *output* has never been measured, and everything about
a command line depends on it.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client \
        --with /Users/rjs/Code/sextile --with pytest \
        python -m pytest spike_cursor_output.py -s -v
"""

import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.frame import COLUMNS, ROWS

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"

CLEAR = 0x0C
HOME = 0x1E
LEFT, RIGHT, DOWN, UP = 0x08, 0x09, 0x0A, 0x0B


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


def numbered_frame() -> bytes:
    """Every row labelled, so any disturbance is obvious."""
    canvas = Canvas()
    for row in range(ROWS):
        canvas.row(row).text(f"ROW{row:02d}" + "." * (COLUMNS - 5))
    return canvas.frame.to_bytes()


def test_cursor_down_reaches_a_chosen_row(commstar: Beebium) -> None:
    """Home, then down: the only positioning viewdata could offer."""
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME]) + bytes([DOWN]) * 23 + b"HERE")
    lines = rows(commstar)
    print(f"\n  row 23 after home + 23 down: {lines[23][:20]!r}")
    print(f"  row  0 (should be untouched): {lines[0][:20]!r}")
    assert lines[23].startswith("HERE")
    assert lines[0].startswith("ROW00")


def test_moving_does_not_erase_what_it_passes_over(commstar: Beebium) -> None:
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME]) + bytes([DOWN]) * 5)
    lines = rows(commstar)
    untouched = [line for line in lines if line.startswith("ROW")]
    print(f"\n  rows still bearing their labels: {len(untouched)} of {ROWS}")
    assert len(untouched) == ROWS


def test_cursor_up_from_home_may_wrap_to_the_bottom(commstar: Beebium) -> None:
    """If it wraps, the footer is two bytes away rather than twenty-four."""
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME, UP]) + b"WRAP")
    lines = rows(commstar)
    print(f"\n  row 23 after home + up: {lines[23][:20]!r}")
    print(f"  row  0 after home + up: {lines[0][:20]!r}")
    print(f"  -> cursor up from row 0 wraps to the bottom: {lines[23].startswith('WRAP')}")


def test_overwriting_one_row_leaves_the_others_alone(commstar: Beebium) -> None:
    """The whole point: a command line that costs one row, not one frame."""
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME]) + bytes([DOWN]) * 23 + b"*123" + b" " * 36)
    lines = rows(commstar)
    disturbed = [
        row for row in range(ROWS - 1) if not lines[row].startswith(f"ROW{row:02d}")
    ]
    print(f"\n  row 23: {lines[23][:20]!r}")
    print(f"  rows 0-22 disturbed: {disturbed or 'none'}")
    assert not disturbed


def test_carriage_return_alone_returns_to_column_zero(commstar: Beebium) -> None:
    """So a row can be rewritten without counting backwards."""
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME]) + bytes([DOWN]) * 10 + b"XXXXX" + bytes([0x0D]) + b"YY")
    lines = rows(commstar)
    print(f"\n  row 10 after writing, CR, writing: {lines[10][:20]!r}")
    assert lines[10].startswith("YY")


def test_cursor_left_backs_over_a_character(commstar: Beebium) -> None:
    """What a delete key would need, if the reader is to correct a digit."""
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME]) + b"AB" + bytes([LEFT]) + b"C")
    lines = rows(commstar)
    print(f"\n  row 0 after A B left C: {lines[0][:20]!r}")
    print("  -> 'AC' means cursor left moved back over the B")


def test_cursor_right_skips_without_erasing(commstar: Beebium) -> None:
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME]) + b"AB" + bytes([RIGHT]) + b"D")
    lines = rows(commstar)
    print(f"\n  row 0 after A B right D: {lines[0][:20]!r}")
    print("  -> 'AB.D' means the skipped cell kept its old contents")
