"""Spike: how must Sextile encode teletext attributes for Commstar?

Two candidate encodings, and the whole visual layer rests on the answer:

  (a) the viewdata convention -- ESC (0x1B) followed by the attribute + 0x40
  (b) the SAA5050's own codes -- 0x80-0x9F sent directly

Prestel mode runs the line at 7E1, which cannot carry an eighth bit, so (a) is
the strong prediction. This measures it rather than assuming it, and settles
three smaller questions at the same time: what 0x23, 0x5F and 0x60 actually
display, and whether separated graphics can be selected the same way.

Driven over rpc-serial rather than ip232: the question is what Commstar does
with bytes, and rpc-serial delivers them to the ACIA deterministically under
test control. The transport is interchangeable for this purpose.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --project /Users/rjs/Code/beebium/clients/beebium-python-client \
        pytest spike_control_codes.py -s -v
"""

import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"

COLOUR_NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"]
CHARSET_NAMES = {0: "alpha", 1: "contiguous", 2: "separated"}

ESC = 0x1B
CLEAR_SCREEN = 0x0C
CURSOR_HOME = 0x1E
CARRIAGE_RETURN = 0x0D
LINE_FEED = 0x0A


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
    """Boot -> *COMMSTAR -> Prestel emulation -> chat mode."""
    wait_for_screen(bbc, "BASIC")
    bbc.keyboard.type("*COMMSTAR\r")
    wait_for_screen(bbc, "Select ?")
    #  The Comms/Prestel toggle, typed as '#' but displayed as '_'.
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


def receive(bbc: Beebium, data: bytes, settle: float = 3.0) -> None:
    """Deliver bytes to the BBC's serial port and let the guest paint them."""
    accepted = bbc.extensions[RpcSerial].send(data)
    assert accepted == len(data), f"rpc-serial accepted {accepted} of {len(data)}"
    time.sleep(settle)


def report(bbc: Beebium, rows: int = 8) -> None:
    """Print the top of the screen, cell by cell, with resolved attributes."""
    screen = bbc.video.teletext_screen()
    print(f"\n  active={screen.active} {screen.rows}x{screen.columns}")
    for row in range(min(rows, screen.rows)):
        cells = [screen.cell(row, column) for column in range(screen.columns)]
        if all(cell.character == 0x20 for cell in cells):
            continue
        rendered = "".join(
            "." if cell.is_control_code else chr(cell.character) for cell in cells
        )
        print(f"  row {row:2d}: {rendered!r}")
        for column, cell in enumerate(cells[:24]):
            if cell.character == 0x20 and not cell.is_control_code:
                continue
            print(
                f"      [{row:2d},{column:2d}] 0x{cell.character:02X} "
                f"fg={COLOUR_NAMES[cell.fg]:<7} bg={COLOUR_NAMES[cell.bg]:<7} "
                f"charset={CHARSET_NAMES.get(cell.charset, cell.charset):<10} "
                f"control={cell.is_control_code}"
            )


def test_escape_encoded_attribute(commstar: Beebium) -> None:
    """Candidate (a): ESC + 0x40 + n, the viewdata convention."""
    receive(commstar, bytes([CLEAR_SCREEN, CURSOR_HOME]))
    receive(commstar, bytes([ESC, 0x41]) + b"RED" + bytes([ESC, 0x42]) + b"GREEN")
    print("\n=== (a) ESC 0x41 'RED' ESC 0x42 'GREEN' ===")
    report(commstar)


def test_direct_saa5050_codes(commstar: Beebium) -> None:
    """Candidate (b): 0x80-0x9F sent directly, which 7E1 should not carry."""
    receive(commstar, bytes([CLEAR_SCREEN, CURSOR_HOME]))
    receive(commstar, bytes([0x81]) + b"RED" + bytes([0x82]) + b"GREEN")
    print("\n=== (b) 0x81 'RED' 0x82 'GREEN' ===")
    report(commstar)


def test_national_option_glyphs(commstar: Beebium) -> None:
    """What 0x23, 0x5F and 0x60 actually display."""
    receive(commstar, bytes([CLEAR_SCREEN, CURSOR_HOME]))
    receive(commstar, b"[" + bytes([0x23, 0x5F, 0x60]) + b"]")
    print("\n=== 0x23 0x5F 0x60, expecting pound, hash, bar ===")
    report(commstar)


def test_separated_graphics(commstar: Beebium) -> None:
    """Whether graphics colour and separated mosaics select via the same escape."""
    receive(commstar, bytes([CLEAR_SCREEN, CURSOR_HOME]))
    receive(
        commstar,
        bytes([ESC, 0x57])  # graphics white (0x17)
        + bytes([ESC, 0x5A])  # separated graphics (0x1A)
        + bytes([0x35, 0x3F, 0x7F, 0x2A])
        + bytes([ESC, 0x59])  # contiguous graphics (0x19)
        + bytes([0x35, 0x3F, 0x7F, 0x2A]),
    )
    print("\n=== separated then contiguous mosaics ===")
    report(commstar)


def test_cursor_and_clear_controls(commstar: Beebium) -> None:
    """Whether the C0 codes behave as viewdata cursor control."""
    receive(commstar, bytes([CLEAR_SCREEN, CURSOR_HOME]))
    receive(commstar, b"FIRST" + bytes([CARRIAGE_RETURN, LINE_FEED]) + b"SECOND")
    print("\n=== CR LF between two words ===")
    report(commstar)
