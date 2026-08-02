"""Spike: where does a 24-row viewdata frame sit in Commstar's 25-row screen?

The BBC's Mode 7 display is 25 rows of 40; a viewdata frame is 24. Before the
layout engine fixes its geometry it needs to know which rows a frame occupies,
whether Commstar reserves a status line, whether the 40th column wraps of its
own accord, and what happens when the bottom right cell is written.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client --with pytest \
        python -m pytest spike_frame_geometry.py -s -v
"""

import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"

CLEAR_SCREEN = 0x0C
CURSOR_HOME = 0x1E
CARRIAGE_RETURN = 0x0D
LINE_FEED = 0x0A

COLUMNS = 40


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


def receive(bbc: Beebium, data: bytes, chunk: int = 128) -> None:
    """Deliver bytes in chunks, letting the guest keep up with the queue."""
    for start in range(0, len(data), chunk):
        piece = data[start : start + chunk]
        accepted = bbc.extensions[RpcSerial].send(piece)
        assert accepted == len(piece), f"rpc-serial accepted {accepted} of {len(piece)}"
        time.sleep(1.5)
    time.sleep(2.0)


def dump(bbc: Beebium, label: str) -> None:
    screen = bbc.video.teletext_screen()
    print(f"\n=== {label} === active={screen.active} {screen.rows}x{screen.columns}")
    for row in range(screen.rows):
        cells = [screen.cell(row, column) for column in range(screen.columns)]
        rendered = "".join(
            "." if cell.is_control_code else chr(cell.character) for cell in cells
        )
        print(f"  {row:2d} |{rendered}|")


def test_rows_written_with_cr_lf(commstar: Beebium) -> None:
    """Twenty-four marked rows, separated explicitly. Which screen rows get them?"""
    receive(commstar, bytes([CLEAR_SCREEN, CURSOR_HOME]))
    body = b"".join(
        f"R{row:02d}".encode() + bytes([CARRIAGE_RETURN, LINE_FEED]) for row in range(24)
    )
    receive(commstar, body)
    dump(commstar, "24 rows via CR LF")


def test_auto_wrap_at_the_fortieth_column(commstar: Beebium) -> None:
    """A full 40 columns with no CR or LF. Does the cursor wrap by itself?"""
    receive(commstar, bytes([CLEAR_SCREEN, CURSOR_HOME]))
    body = b"".join(
        f"R{row:02d}".encode() + b"-" * (COLUMNS - 3) for row in range(4)
    )
    receive(commstar, body)
    dump(commstar, "4 rows of exactly 40 columns, relying on wrap")


def test_filling_the_whole_screen(commstar: Beebium) -> None:
    """Fill every row. Where does content stop, and does anything scroll?"""
    receive(commstar, bytes([CLEAR_SCREEN, CURSOR_HOME]))
    body = b"".join(
        f"R{row:02d}".encode() + b"." * (COLUMNS - 3) for row in range(25)
    )
    receive(commstar, body)
    dump(commstar, "25 rows written by wrap alone")
