"""Spike: do the BBC's cursor keys reach the far end in Prestel mode?

The BBC's cursor keys produce MOS codes 0x88-0x8B. Prestel runs the line at
7E1, which strips the eighth bit, leaving 0x08-0x0B -- and those are precisely
the viewdata cursor-control codes. So if Commstar transmits them rather than
consuming them locally for editing, real arrow keys could drive Sextile's
navigation, which would be both more comfortable and more authentic than WASD.

Measured rather than reasoned about, because whether Commstar passes them on is
a property of Commstar, not of the encoding.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client --with pytest \
        python -m pytest spike_cursor_keys.py -s -v
"""

import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"

#  Prestel transmits at 75 baud, so a character takes about 130ms to reach the
#  wire; and Commstar samples the keyboard after taking a character, so a key
#  must stay down long enough to be seen by that scan.
KEY_HOLD_SECONDS = 0.15
TRANSMIT_SETTLE_SECONDS = 4.0

#  BBC keyboard matrix positions, from Beebium's keyboard_map.
CURSOR_KEYS = {
    "LEFT": (1, 9),
    "DOWN": (2, 9),
    "UP": (3, 9),
    "RIGHT": (7, 9),
    "COPY": (6, 9),
}

#  What each would be if it arrived as a viewdata control code, the eighth bit
#  having been stripped by the 7E1 line.
AS_VIEWDATA = {0x08: "cursor left", 0x09: "cursor right", 0x0A: "cursor down", 0x0B: "cursor up"}


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


def transmitted(bbc: Beebium) -> bytes:
    time.sleep(TRANSMIT_SETTLE_SECONDS)
    return bytes(bbc.extensions[RpcSerial].receive())


def tap(bbc: Beebium, row: int, column: int) -> None:
    bbc.keyboard.matrix_down(row, column)
    time.sleep(KEY_HOLD_SECONDS)
    bbc.keyboard.matrix_up(row, column)


def describe(sent: bytes) -> str:
    if not sent:
        return "nothing -- consumed locally"
    parts = []
    for byte in sent:
        meaning = AS_VIEWDATA.get(byte)
        parts.append(f"0x{byte:02X}" + (f" ({meaning})" if meaning else ""))
    return ", ".join(parts)


def test_an_ordinary_key_proves_the_harness(commstar: Beebium) -> None:
    #  If 'A' does not reach the wire, nothing below means anything.
    transmitted(commstar)
    commstar.keyboard.type("A")
    sent = transmitted(commstar)
    print(f"\n  'A' -> {describe(sent)}")
    assert sent, "the harness itself is not working"


@pytest.mark.parametrize("name", list(CURSOR_KEYS))
def test_what_a_cursor_key_transmits(commstar: Beebium, name: str) -> None:
    transmitted(commstar)
    tap(commstar, *CURSOR_KEYS[name])
    sent = transmitted(commstar)
    print(f"\n  {name:6} -> {describe(sent)}")


def test_all_four_arrows_in_one_pass(commstar: Beebium) -> None:
    """Together, in case Commstar treats a lone press differently."""
    transmitted(commstar)
    for name in ("LEFT", "RIGHT", "UP", "DOWN"):
        tap(commstar, *CURSOR_KEYS[name])
        time.sleep(0.3)
    sent = transmitted(commstar)
    print(f"\n  LEFT RIGHT UP DOWN -> {describe(sent)}")
