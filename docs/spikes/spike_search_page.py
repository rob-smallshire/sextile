"""Spike: does the real search page work on a real terminal?

`spike_suggestion_block.py` measured the *shape* of a suggestion block against a
mock page and hand-built bytes, and found the thing that mattered: a row written
to all forty columns wraps by itself, so a cursor down after one moves two rows.

This one asks a narrower and more useful question. Every byte here comes from
the service itself -- a real `Sextile` session, the real search page,
`weather-viewdata`'s own `Suggest` field over a real place index, and whatever
the session decides to send in reply to a keypress. Nothing is hand-built. If
the block is drawn wrongly, the fault is in code a caller would actually reach.

What that adds over the earlier spike:

1. **The page has furniture.** Chrome, a heading, a rule top and bottom, prose
   beneath the block. A repaint that overruns has something to damage, and the
   labelled rows of a mock page cannot show whether a real one survives.

2. **The bytes are the session's.** `changed_rows` decides what to send and
   `rows_bytes` walks the cursor; both are exercised as the service uses them
   rather than as a spike imagines them.

3. **The letters arrive as a terminal sends them**, through the command parser,
   so DELETE reaching a frame is tested where it actually has to work.

The place index is built from `known-places.txt`, the same eleven real GeoNames
lines the test suite pins, so this needs no downloaded dump and says the same
thing every time.

Run with:
    BEEBIUM_ROM_DIR=/Users/rjs/Code/beebium/roms \
    BEEBIUM_SERVER=/Users/rjs/Code/beebium/build-release/src/server/beebium-model-b \
    uv run --no-project --python 3.12 \
        --with /Users/rjs/Code/beebium/clients/beebium-python-client \
        --with /Users/rjs/Code/sextile \
        --with /Users/rjs/Code/sextile/packages/weather-viewdata \
        --with pytest --with pytest-asyncio \
        python -m pytest spike_search_page.py -s -v
"""

import asyncio
import time
from pathlib import Path

import pytest

from beebium.client import Beebium
from beebium.client.exceptions import ServerNotFoundError
from beebium.ext.peripheral.rpc_serial import RpcSerial
from sextile.addressing import PageAddress
from sextile.session.session import Session
from sextile.viewdata.frame import COLUMNS, ROWS
from weather_viewdata import build_application
from weather_viewdata.application import FIELD_ROW, FIRST_SUGGESTION_ROW
from weather_viewdata.dump import places_in
from weather_viewdata.forecast.source import ForecastSource
from weather_viewdata.geonames import Place
from weather_viewdata.store import Index

COMMSTAR_ROM_FILENAME = "commstar_1_40_SN882A.rom"

#: The eleven real GeoNames lines the suite already pins, so this spike needs
#: no downloaded dump and says the same thing every time it is run.
KNOWN_PLACES = (
    Path(__file__).parent.parent.parent
    / "packages/weather-viewdata/tests/data/known-places.txt"
)

#: The page the search field is on.
SEARCH = "3"

BAUD = 1200
BITS_PER_CHARACTER = 10


def seconds(data: bytes) -> float:
    return len(data) * BITS_PER_CHARACTER / BAUD


class NoForecasts(ForecastSource):
    """The service without its network end.

    Nothing here visits a forecast page, and a spike that asked met.no for one
    would be a spike that failed when the line was down.
    """

    async def forecast_for(self, place: Place) -> None:
        return None


# -- the emulator -----------------------------------------------------------


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


def show(lines: list[str], first: int, last: int) -> None:
    for row in range(first, last + 1):
        print(f"    {row:>2} |{lines[row].rstrip()}")


# -- the service ------------------------------------------------------------


@pytest.fixture
def searching(tmp_path: Path):
    """A real session on the real search page, and a way to key into it."""

    async def start() -> tuple[Session, bytes]:
        index_filepath = tmp_path / "places.sqlite"
        with Index.open(index_filepath) as index:
            index.prefer(country="GB")
            index.add_places(places_in(KNOWN_PLACES))
        application = build_application(
            source=NoForecasts(), index_filepath=index_filepath
        )
        await application.startup()
        session = Session(application, start=PageAddress(SEARCH))
        return session, await session.greeting()

    loop = asyncio.new_event_loop()
    try:
        session, greeting = loop.run_until_complete(start())

        def key(pressed: bytes) -> bytes:
            """What the service sends back when a terminal sends these bytes."""
            return b"".join(loop.run_until_complete(session.receive(pressed)))

        yield session, greeting, key
    finally:
        loop.close()


# -- what a reader does -----------------------------------------------------


def test_the_search_page_arrives_whole(commstar: Beebium, searching) -> None:
    """Before any typing: the page as the service first sends it."""
    _, greeting, _ = searching
    send(commstar, greeting)
    lines = rows(commstar)
    print(f"\n  the page is {len(greeting)} bytes, {seconds(greeting):.1f}s at 1200 baud")
    show(lines, 0, 14)
    assert "FIND A PLACE" in lines[0]
    assert "PLACE:" in lines[FIELD_ROW]


def test_typing_puts_suggestions_under_the_field(commstar: Beebium, searching) -> None:
    """The whole point. Every byte from the session, none built here."""
    _, greeting, key = searching
    send(commstar, greeting)
    for letter in b"TRO":
        send(commstar, key(bytes([letter])))
    lines = rows(commstar)
    show(lines, FIELD_ROW, FIRST_SUGGESTION_ROW + 3)
    assert "TRO" in lines[FIELD_ROW]
    offered = " ".join(lines[FIRST_SUGGESTION_ROW : FIRST_SUGGESTION_ROW + 3])
    assert "Trondheim" in offered
    assert "Troms" in offered, "Tromso is in the eleven and starts with TRO"


def test_the_furniture_around_the_block_survives(commstar: Beebium, searching) -> None:
    """A real page has something to damage, which a labelled mock has not.

    The heading, the two rules and the prose beneath the block are all drawn by
    the service and none of them is the form's to touch.
    """
    _, greeting, key = searching
    send(commstar, greeting)
    before = rows(commstar)
    for letter in b"TROND":
        send(commstar, key(bytes([letter])))
    after = rows(commstar)
    untouched = [
        row
        for row in range(ROWS)
        if row not in range(FIELD_ROW, FIRST_SUGGESTION_ROW + 3)
    ]
    disturbed = [row for row in untouched if before[row] != after[row]]
    print(f"\n  rows outside the form disturbed: {disturbed or 'none'}")
    show(after, 0, ROWS - 1)
    assert not disturbed


def test_narrowing_removes_what_no_longer_matches(commstar: Beebium, searching) -> None:
    """The failure this is really watching for.

    A suggestion that has grown shorter must cover what the longer one said, or
    a place the reader has typed past goes on offering itself under a digit
    that now means something else.
    """
    _, greeting, key = searching
    send(commstar, greeting)
    for letter in b"TRO":
        send(commstar, key(bytes([letter])))
    wide = rows(commstar)
    for letter in b"NDH":
        send(commstar, key(bytes([letter])))
    narrow = rows(commstar)
    print("\n  with TRO:")
    show(wide, FIRST_SUGGESTION_ROW, FIRST_SUGGESTION_ROW + 2)
    print("  with TRONDH:")
    show(narrow, FIRST_SUGGESTION_ROW, FIRST_SUGGESTION_ROW + 2)
    offered = " ".join(narrow[FIRST_SUGGESTION_ROW : FIRST_SUGGESTION_ROW + 3])
    assert "Trondheim" in offered
    assert "Troms" not in offered, "Tromso was typed past and must be gone"


def test_rubbing_out_brings_them_back(commstar: Beebium, searching) -> None:
    """DELETE off a request, through the parser, to the form. 0x7F, measured."""
    _, greeting, key = searching
    send(commstar, greeting)
    for letter in b"TROND":
        send(commstar, key(bytes([letter])))
    #  Two of the five letters back, leaving TRO.
    for _ in range(2):
        send(commstar, key(b"\x7f"))
    lines = rows(commstar)
    show(lines, FIELD_ROW, FIRST_SUGGESTION_ROW + 2)
    assert "TRO" in lines[FIELD_ROW]
    assert "Troms" in " ".join(lines[FIRST_SUGGESTION_ROW : FIRST_SUGGESTION_ROW + 3])


def test_what_a_keystroke_costs_in_practice(commstar: Beebium, searching) -> None:
    """Not a measurement of the emulator, but of the service's own decisions.

    `changed_rows` decides how much to send, so this is what a reader on a real
    line would actually wait for between letters.
    """
    _, greeting, key = searching
    send(commstar, greeting)
    costs = []
    for letter in b"TRONDHEIM":
        sent = key(bytes([letter]))
        costs.append(len(sent))
        send(commstar, sent)
    print("\n  bytes per keystroke, T-R-O-N-D-H-E-I-M:")
    for letter, cost in zip("TRONDHEIM", costs, strict=True):
        print(f"    {letter}  {cost:>4} bytes   {cost * BITS_PER_CHARACTER / BAUD:.2f}s")
    lines = rows(commstar)
    show(lines, FIELD_ROW, FIRST_SUGGESTION_ROW + 2)
    assert "Trondheim" in " ".join(lines[FIRST_SUGGESTION_ROW : FIRST_SUGGESTION_ROW + 3])
