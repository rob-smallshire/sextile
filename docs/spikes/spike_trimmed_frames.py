"""Spike: does a trimmed frame draw the same screen as an untrimmed one?

Sextile stops each row at its last non-blank cell and walks to the next with
CR LF, sending nothing at all after the last row that has anything on it. That
saves between a third and three quarters of a frame, which at 1200 baud is
several seconds -- but only if the screen is identical afterwards.

The reasoning is sound: the frame clears the screen first, so trailing spaces
overwrite nothing; CR LF was measured putting 24 rows on rows 0-23; and column
40 wraps by itself, so a row that fills it needs no terminator. Reasoning is not
measurement, and every frame the service sends depends on this, so it is
measured: the same frame is sent both ways and the resolved SAA5050 cells are
compared.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client \
        --with /Users/rjs/Code/sextile --with pytest \
        python -m pytest spike_trimmed_frames.py -s -v
"""

import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial
from sextile.pages.demo import demo_frame
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour, Control
from sextile.viewdata.frame import COLUMNS, ROWS, Frame

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"


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
        accepted = bbc.extensions[RpcSerial].send(piece)
        assert accepted == len(piece), f"rpc-serial accepted {accepted} of {len(piece)}"
        time.sleep(1.5)
    time.sleep(2.0)


def cells(bbc: Beebium) -> list[tuple[int, int, int, int]]:
    """The resolved SAA5050 cells of the 24 rows a viewdata frame occupies."""
    screen = bbc.video.teletext_screen()
    return [
        (
            screen.cell(row, column).character,
            screen.cell(row, column).fg,
            screen.cell(row, column).bg,
            screen.cell(row, column).charset,
        )
        for row in range(ROWS)
        for column in range(COLUMNS)
    ]


def show_difference(full: list, trimmed: list) -> str:
    for index, (a, b) in enumerate(zip(full, trimmed, strict=True)):
        if a != b:
            return f"first difference at row {index // COLUMNS}, column {index % COLUMNS}: {a} vs {b}"
    return "none"


def compare(bbc: Beebium, frame: Frame, label: str) -> None:
    send(bbc, frame.to_bytes(trim=False))
    full = cells(bbc)
    send(bbc, frame.to_bytes())
    trimmed = cells(bbc)
    saved = len(frame.to_bytes(trim=False)) - len(frame.to_bytes())
    print(f"\n  {label}: {saved} bytes saved; difference: {show_difference(full, trimmed)}")
    assert full == trimmed, label


def test_the_demonstration_frame(commstar: Beebium) -> None:
    """Colour, mosaic rules, wrapped body text and a page number."""
    compare(commstar, demo_frame(), "the demonstration frame")


def test_a_frame_with_blank_rows_between_content(commstar: Beebium) -> None:
    canvas = Canvas()
    canvas.row(0).text("TOP")
    canvas.row(11).text("MIDDLE", Colour.CYAN)
    canvas.row(23).text("BOTTOM", Colour.YELLOW)
    compare(commstar, canvas.frame, "blank rows between content")


def test_a_row_filled_to_the_last_column(commstar: Beebium) -> None:
    """The case a terminator would break, by skipping the row after it."""
    canvas = Canvas()
    canvas.row(0).text("X" * COLUMNS)
    canvas.row(1).text("SHOULD BE ROW ONE")
    canvas.row(2).text("Y" * COLUMNS)
    canvas.row(3).text("SHOULD BE ROW THREE")
    compare(commstar, canvas.frame, "a row filled to column 40")


def test_a_frame_whose_last_rows_are_blank(commstar: Beebium) -> None:
    canvas = Canvas()
    canvas.row(0).text("ONLY THIS ROW")
    compare(commstar, canvas.frame, "nothing after the first row")


def test_a_frame_ending_in_an_attribute(commstar: Beebium) -> None:
    """An attribute is not a blank, even with nothing after it."""
    canvas = Canvas()
    canvas.row(0).text("BEFORE")
    canvas.frame.set_attribute(0, 10, Control.ALPHA_MAGENTA)
    canvas.row(1).text("AFTER")
    compare(commstar, canvas.frame, "a trailing attribute")


def test_a_wholly_full_frame(commstar: Beebium) -> None:
    """Nothing to trim, so the two forms should be byte-identical."""
    canvas = Canvas()
    for row in range(ROWS):
        canvas.row(row).text("*" * COLUMNS)
    assert canvas.frame.to_bytes() == canvas.frame.to_bytes(trim=False)
    compare(commstar, canvas.frame, "a wholly full frame")
