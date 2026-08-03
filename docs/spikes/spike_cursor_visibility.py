"""Spike: can the cursor be turned on and off?

Sextile now draws a command line for a reader entering a page request, and a
visible cursor in it would show where the next digit lands. Elsewhere a cursor
would be a distraction, blinking in the middle of a frame nobody is typing into.

Viewdata convention puts cursor on at 0x11 (DC1) and cursor off at 0x14 (DC4),
as bare C0 bytes -- which does not clash with the graphics colours at the same
values, those travelling escaped. Whether Commstar implements it is another
matter, and the SAA5050 cells Beebium exposes carry a `cursor` flag, so it can
be seen rather than guessed at.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client \
        --with /Users/rjs/Code/sextile --with pytest \
        python -m pytest spike_cursor_visibility.py -s -v
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

HOME = 0x1E
CURSOR_ON = 0x11  # DC1, by viewdata convention
CURSOR_OFF = 0x14  # DC4, by viewdata convention


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


def cursors(bbc: Beebium) -> list[tuple[int, int]]:
    """Where the SAA5050 says a cursor is being drawn, right now."""
    screen = bbc.video.teletext_screen()
    return [
        (row, column)
        for row in range(ROWS)
        for column in range(COLUMNS)
        if screen.cell(row, column).cursor
    ]


def cursor_ever_seen(bbc: Beebium, samples: int = 24) -> list[tuple[int, int]]:
    """Where a cursor appears over a couple of seconds.

    The cursor flashes, so one look tells you only which half of the blink you
    caught. Sampling across it is the difference between a measurement and a
    coin toss -- as two contradictory readings in an earlier run of this spike
    demonstrated.
    """
    seen: set[tuple[int, int]] = set()
    for _ in range(samples):
        seen.update(cursors(bbc))
        time.sleep(0.1)
    return sorted(seen)


def rows(bbc: Beebium) -> list[str]:
    screen = bbc.video.teletext_screen()
    return [
        "".join(chr(screen.cell(row, column).character) for column in range(COLUMNS))
        for row in range(ROWS)
    ]


def numbered_frame() -> bytes:
    canvas = Canvas()
    for row in range(ROWS):
        canvas.row(row).text(f"ROW{row:02d}" + "." * (COLUMNS - 5))
    return canvas.frame.to_bytes()


def test_a_cursor_shows_by_default(commstar: Beebium) -> None:
    send(commstar, numbered_frame())
    found = cursor_ever_seen(commstar)
    print(f"\n  after drawing a frame: cursor at {found or 'nowhere'}")
    assert found, "expected a cursor: Commstar shows one unless told otherwise"


def test_whether_dc4_turns_it_off(commstar: Beebium) -> None:
    send(commstar, numbered_frame())
    before = cursor_ever_seen(commstar)
    send(commstar, bytes([CURSOR_OFF]))
    after = cursor_ever_seen(commstar)
    print(f"\n  before 0x14: {before or 'nowhere'}")
    print(f"  after  0x14: {after or 'nowhere'}")
    print(f"  -> 0x14 turns the cursor off: {bool(before) and not after}")


def test_whether_dc1_turns_it_on_again(commstar: Beebium) -> None:
    send(commstar, numbered_frame())
    send(commstar, bytes([CURSOR_OFF]))
    off = cursor_ever_seen(commstar)
    send(commstar, bytes([HOME, CURSOR_ON]))
    on = cursor_ever_seen(commstar)
    print(f"\n  with 0x14: {off or 'nowhere'}")
    print(f"  then 0x11: {on or 'nowhere'}")
    print(f"  -> 0x11 turns the cursor on: {not off and bool(on)}")


def test_where_the_cursor_sits_after_a_partial_redraw(commstar: Beebium) -> None:
    """Which is where a command line would want it: after the typed text."""
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME, 0x0B]) + b"*123" + bytes([CURSOR_ON]))
    found = cursor_ever_seen(commstar)
    print(f"\n  after writing *123 on row 23: cursor at {found or 'nowhere'}")


def test_whether_the_codes_disturb_the_display(commstar: Beebium) -> None:
    """They must not be taken as the graphics colours at the same values."""
    send(commstar, numbered_frame())
    send(commstar, bytes([HOME, CURSOR_ON]) + b"AB" + bytes([CURSOR_OFF]) + b"CD")
    line = rows(commstar)[0]
    print(f"\n  row 0 after 0x11 A B 0x14 C D: {line[:16]!r}")
    print("  -> 'ABCD' means the codes took no cell; anything else means they did")
