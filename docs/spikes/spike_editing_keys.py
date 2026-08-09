"""Spike: what do DELETE and its neighbours transmit in Prestel mode?

A reader mistyping a digit in the command line wants to rub it out. DELETE is
the obvious key, but 0x5F -- what it was thought to send -- is what RETURN
sends, measured, and that terminates a request. If both sent the same byte
there would be no telling them apart, so this settles it.

The other keys are here because they are the plausible alternatives: CTRL-H is
the ASCII backspace, and cursor left is what viewdata itself uses to back up.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client --with pytest \
        python -m pytest spike_editing_keys.py -s -v
"""

import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"

KEY_HOLD_SECONDS = 0.15
TRANSMIT_SETTLE_SECONDS = 4.0

#  BBC keyboard matrix positions, from Beebium's keyboard_map.
KEYS = {
    "DELETE": (5, 9),
    "RETURN": (4, 9),
    "COPY": (6, 9),
    "TAB": (6, 0),
    "LEFT": (1, 9),
}

CTRL_KEY = (0, 1)

MEANINGS = {
    0x08: "cursor left / backspace",
    0x09: "cursor right / tab",
    0x0A: "cursor down",
    0x0B: "cursor up",
    0x0D: "carriage return",
    0x5F: "the viewdata hash -- terminates a page request",
    0x7F: "ASCII delete",
}


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


def tap(bbc: Beebium, row: int, column: int, *, with_control: bool = False) -> None:
    if with_control:
        bbc.keyboard.matrix_down(*CTRL_KEY)
    bbc.keyboard.matrix_down(row, column)
    time.sleep(KEY_HOLD_SECONDS)
    bbc.keyboard.matrix_up(row, column)
    if with_control:
        bbc.keyboard.matrix_up(*CTRL_KEY)


def describe(sent: bytes) -> str:
    if not sent:
        return "nothing -- consumed locally"
    return ", ".join(
        f"0x{byte:02X}" + (f" ({MEANINGS[byte]})" if byte in MEANINGS else "")
        for byte in sent
    )


@pytest.mark.parametrize("name", list(KEYS))
def test_what_an_editing_key_transmits(commstar: Beebium, name: str) -> None:
    transmitted(commstar)
    tap(commstar, *KEYS[name])
    print(f"\n  {name:7} -> {describe(transmitted(commstar))}")


def test_control_h_the_ascii_backspace(commstar: Beebium) -> None:
    transmitted(commstar)
    tap(commstar, 4, 4, with_control=True)  # CTRL-H
    print(f"\n  CTRL-H  -> {describe(transmitted(commstar))}")


def test_delete_and_return_are_distinguishable(commstar: Beebium) -> None:
    """The question that matters: if they are the same, delete cannot work."""
    transmitted(commstar)
    tap(commstar, *KEYS["DELETE"])
    delete = transmitted(commstar)
    tap(commstar, *KEYS["RETURN"])
    ret = transmitted(commstar)
    print(f"\n  DELETE -> {describe(delete)}")
    print(f"  RETURN -> {describe(ret)}")
    print(f"  -> distinguishable: {delete != ret}")


def test_what_the_space_bar_transmits(commstar: Beebium) -> None:
    """Asked because a page said "no space bar" and nobody had checked.

    The search field's help told readers there was none, which would be a
    strange thing for a keyboard to lack. If it transmits 0x20 like anything
    else, then the only thing stopping NEW YORK being keyed as two words is
    Sextile's own command parser dropping it -- and the place index folds
    spaces out of what it matches against anyway, so accepting one costs
    nothing and saves a reader wondering why their space bar is dead.
    """
    transmitted(commstar)
    #  Row 6, column 2 on the BBC matrix.
    tap(commstar, 6, 2)
    sent = transmitted(commstar)
    print(f"\n  SPACE  -> {describe(sent)}")
    print(f"  -> the space bar transmits: {sent == b' '}")
