"""Spike: how long a page number will Commstar accept and transmit?

Commstar buffers a `*nnn` page request locally and sends it when `#` is pressed,
so its buffer -- not the protocol, and not our server -- caps how long a page
number can be. Every numbering scheme depends on the answer, so it is measured
before one is chosen.

Typed at the keyboard, read off the wire.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client --with pytest \
        python -m pytest spike_page_number_buffer.py -s -v
"""

import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"

#  Prestel transmits at 75 baud: roughly 130ms per character, so a long page
#  number takes a couple of seconds to reach the wire.
TRANSMIT_SETTLE_SECONDS = 6.0


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


def request_page(bbc: Beebium, digits: str) -> bytes:
    """Type a page request and return what reached the wire."""
    transmitted(bbc)  # drain
    bbc.keyboard.type(f"*{digits}")
    time.sleep(1.0)
    #  RETURN transmits 0x5F, the viewdata hash, which is what terminates a
    #  page request. Typing '#' would send 0x23, which displays as a pound.
    bbc.keyboard.type("\r")
    sent = transmitted(bbc)
    print(f"\n  typed *{digits}#  ({len(digits)} digits)")
    print(f"  wire: {sent!r}")
    rows = screen_text(bbc).splitlines()
    print(f"  screen row 0: {(rows[0] if rows else '')!r}")
    return sent


def test_a_short_page_number(commstar: Beebium) -> None:
    print("\n=== 3 digits ===")
    request_page(commstar, "100")


def test_nine_digits(commstar: Beebium) -> None:
    print("\n=== 9 digits, the classic Prestel maximum ===")
    request_page(commstar, "123456789")


def test_twelve_digits(commstar: Beebium) -> None:
    print("\n=== 12 digits, beyond any Prestel scheme ===")
    request_page(commstar, "123456789012")


def test_twenty_digits(commstar: Beebium) -> None:
    print("\n=== 20 digits, to find the ceiling ===")
    request_page(commstar, "12345678901234567890")
