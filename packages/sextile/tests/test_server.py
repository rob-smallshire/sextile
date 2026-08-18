"""Serving frames over TCP.

Sextile is a plain TCP server. tcpser is already the ip232 endpoint an emulator
connects to, so Sextile is dialled exactly as any other viewdata board is, and
needs no knowledge of ip232 at all.

These tests drive it the way a terminal does: connect, read what arrives, send a
few bytes, read again. The service on the other end is a made-up one, because
the server should not be able to tell what it is serving.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress

import pytest
from exemplar import Board

from sextile.application import PageRequest
from sextile.page import Page, PageAddress
from sextile.server import DEFAULT_MAX_CONNECTIONS, DEFAULT_PORT, serve
from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import FRAME_PREAMBLE


@pytest.fixture
async def server() -> AsyncIterator[asyncio.Server]:
    running = await serve(Board(), host="127.0.0.1", port=0)
    yield running
    running.close()
    await running.wait_closed()


def address(server: asyncio.Server) -> tuple[str, int]:
    host, port = server.sockets[0].getsockname()[:2]
    return host, port


async def connect(server: asyncio.Server) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    host, port = address(server)
    return await asyncio.open_connection(host, port)


#: How long the line must be quiet for a frame to be judged complete. A frame
#: has no terminator -- trailing blanks are not sent, so its length is not
#: known in advance -- and each one is written in a single burst, so a pause
#: means it is over.
#:
#: Bounded from both ends. It must outlast the gap between one frame's own
#: segments -- under a kilobyte written in a single call over loopback, so
#: microseconds, and fifty milliseconds is three orders of magnitude of margin.
#: And it must be shorter than the shortest deliberate pause before the service
#: says anything else, or a frame read would swallow what came next: the
#: briefest here is a `warn_after` of 0.25.
#:
#: It is also paid once per frame read, so it is the suite's own tax. At 0.15
#: it cost three seconds of a six-second run; at 0.05 it costs one.
SETTLE = 0.05


async def read_frame(reader: asyncio.StreamReader) -> bytes:
    """Read a whole frame, and return it from its preamble on.

    Anything before it is discarded rather than the read being abandoned: a
    command-line update can precede a frame, and the two may well arrive in one
    chunk, so a frame has to be looked for inside what was read rather than only
    at the start of it.

    **Read until the line goes quiet, not until the preamble appears.** This
    used to return the moment it saw a preamble, which on an unloaded machine
    is the whole frame in one chunk and on a busy one is the first few bytes of
    it. The rest then turned up in whatever the next test line happened to
    read, which is why the idle-caller test failed about one run in three and
    only ever under the full suite.
    """
    buffer = b""
    while FRAME_PREAMBLE not in buffer:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        if not chunk:
            return buffer
        buffer += chunk
    while True:
        try:
            chunk = await asyncio.wait_for(reader.read(4096), timeout=SETTLE)
        except TimeoutError:
            break
        if not chunk:
            break
        buffer += chunk
    return buffer[buffer.find(FRAME_PREAMBLE) :]


def printable(data: bytes) -> str:
    return "".join(chr(byte) for byte in data if 0x20 <= byte < 0x7F)


class TestConnecting:
    async def test_the_default_port(self) -> None:
        assert DEFAULT_PORT == 16650

    async def test_a_frame_arrives_unasked_on_connecting(self, server: asyncio.Server) -> None:
        reader, writer = await connect(server)
        greeting = await read_frame(reader)
        assert greeting.startswith(FRAME_PREAMBLE)
        assert "THE BOARD" in printable(greeting)
        writer.close()
        await writer.wait_closed()

    async def test_every_byte_sent_survives_a_seven_bit_line(
        self, server: asyncio.Server
    ) -> None:
        reader, writer = await connect(server)
        greeting = await read_frame(reader)
        assert all(byte < 0x80 for byte in greeting)
        writer.close()
        await writer.wait_closed()


class TestNavigating:
    async def test_a_page_request_is_answered_with_that_page(
        self, server: asyncio.Server
    ) -> None:
        reader, writer = await connect(server)
        await read_frame(reader)

        writer.write(b"*8#")
        await writer.drain()
        response = await read_frame(reader)

        assert "ITEMS" in printable(response)
        writer.close()
        await writer.wait_closed()

    async def test_a_request_split_across_packets_is_still_answered(
        self, server: asyncio.Server
    ) -> None:
        #  At 75 baud a request arrives a character at a time.
        reader, writer = await connect(server)
        await read_frame(reader)

        for byte in b"*8#":
            writer.write(bytes([byte]))
            await writer.drain()
            await asyncio.sleep(0.01)

        assert "ITEMS" in printable(await read_frame(reader))
        writer.close()
        await writer.wait_closed()

    async def test_a_part_typed_request_is_echoed_on_the_footer_row(
        self, server: asyncio.Server
    ) -> None:
        #  Commstar does not echo a page request, so Sextile draws it -- over
        #  the footer row alone, leaving the page beneath it intact.
        reader, writer = await connect(server)
        await read_frame(reader)

        writer.write(b"*84")
        await writer.drain()
        echoed = await asyncio.wait_for(reader.read(4096), timeout=5.0)

        assert not echoed.startswith(FRAME_PREAMBLE)
        assert "*84" in printable(echoed)

        writer.close()
        await writer.wait_closed()


class TestLoggingOff:
    async def test_the_service_says_goodbye_and_drops_the_line(
        self, server: asyncio.Server
    ) -> None:
        reader, writer = await connect(server)
        await read_frame(reader)

        writer.write(b"*90#")
        await writer.drain()
        goodbye = await read_frame(reader)
        assert "GOODBYE" in printable(goodbye)

        #  The far end closes, so reading runs out. Not the very next byte:
        #  the cursor is handed back after the frame, and whether that arrives
        #  in the same chunk is the network's business rather than ours.
        assert await _everything_left(reader) is not None
        writer.close()
        await writer.wait_closed()


class TestSeveralCallers:
    async def test_two_terminals_hold_separate_places(self, server: asyncio.Server) -> None:
        first_reader, first_writer = await connect(server)
        second_reader, second_writer = await connect(server)
        await read_frame(first_reader)
        await read_frame(second_reader)

        first_writer.write(b"*8#")
        await first_writer.drain()
        assert "ITEMS" in printable(await read_frame(first_reader))

        #  The second caller is still on the main index and unaffected.
        second_writer.write(b"*00#")
        await second_writer.drain()
        assert "THE BOARD" in printable(await read_frame(second_reader))

        for writer in (first_writer, second_writer):
            writer.close()
            await writer.wait_closed()

    async def test_one_caller_ringing_off_does_not_disturb_another(
        self, server: asyncio.Server
    ) -> None:
        first_reader, first_writer = await connect(server)
        second_reader, second_writer = await connect(server)
        await read_frame(first_reader)
        await read_frame(second_reader)

        first_writer.close()
        await first_writer.wait_closed()

        second_writer.write(b"*8#")
        await second_writer.drain()
        assert "ITEMS" in printable(await read_frame(second_reader))

        second_writer.close()
        await second_writer.wait_closed()

    async def test_a_caller_who_vanishes_mid_request_is_survivable(
        self, server: asyncio.Server
    ) -> None:
        reader, writer = await connect(server)
        await read_frame(reader)
        writer.write(b"*8")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

        #  The service is still answering.
        other_reader, other_writer = await connect(server)
        assert "THE BOARD" in printable(await read_frame(other_reader))
        other_writer.close()
        await other_writer.wait_closed()


class TestIdleCallers:
    async def test_a_silent_caller_is_eventually_released(self) -> None:
        #  A single-line board held open by someone who walked away locks
        #  everyone else out.
        #  No warning here: this is about the timeout alone.
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=0.5, warn_after=0
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)

        #  Everything said between here and the end of the call, however the
        #  network chose to divide it. Reading to EOF rather than counting
        #  chunks is the point: a frame split across two packets used to
        #  satisfy "something arrived" with its first half and then fail
        #  "the line dropped" with its second.
        tail = await asyncio.wait_for(reader.read(), timeout=5.0)
        assert FRAME_PREAMBLE in tail, "being cut off is worth a frame of its own"
        assert "RINGING OFF" in printable(tail)

        await close(writer, running)


class TestWarningBeforeRingingOff:
    """The one thing the service says unprompted.

    A reader who has been on one frame for ten minutes cannot know the line is
    about to be released, and a service that answers slowly gives them no way to
    tell a dropped call from a slow one.
    """

    async def test_a_warning_arrives_before_the_line_goes(self) -> None:
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=1.5, warn_after=0.3
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)

        warning = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        assert "Press a key" in printable(warning)
        assert not warning.startswith(FRAME_PREAMBLE), "the page beneath must survive"

        await close(writer, running)

    async def test_a_key_after_the_warning_holds_the_line(self) -> None:
        #  A caller who keeps answering the bar is never released: five rounds
        #  take longer than the idle timeout, and the line is still up.
        idle_timeout = 1.0
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=idle_timeout, warn_after=0.25
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)

        began = asyncio.get_running_loop().time()
        for _ in range(5):
            warning = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            assert "Press a key" in printable(warning)
            writer.write(b" ")
            await writer.drain()
            restored = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            assert "1-9 select" in printable(restored), "the page's own footer comes back"

        assert asyncio.get_running_loop().time() - began > idle_timeout
        await close(writer, running)

    async def test_a_request_keyed_while_the_bar_is_up_is_not_half_obeyed(self) -> None:
        #  `*8#` arriving in one packet wakes the line and is dropped entire.
        #  Dropping only its first byte would leave `8#` to be read as a
        #  selection and a page turn, which is worse than keying it again.
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=1.5, warn_after=0.2
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)
        await asyncio.wait_for(reader.read(4096), timeout=5.0)

        writer.write(b"*8#")
        await writer.drain()
        woken = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        assert not woken.startswith(FRAME_PREAMBLE), "no page was sent"

        #  And keying it again works.
        writer.write(b"*8#")
        await writer.drain()
        assert "ITEMS" in printable(await read_frame(reader))
        await close(writer, running)

    async def test_the_key_that_resumes_does_not_navigate(self) -> None:
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=1.5, warn_after=0.3
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)
        await asyncio.wait_for(reader.read(4096), timeout=5.0)

        #  `1` would ordinarily select the first item of the front page.
        writer.write(b"1")
        await writer.drain()
        restored = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        assert not restored.startswith(FRAME_PREAMBLE), "no new page was sent"

        await close(writer, running)

    async def test_no_warning_where_the_line_is_never_released(self) -> None:
        running = await serve(Board(), host="127.0.0.1", port=0, idle_timeout=None)
        reader, writer = await connect_to(running)
        await read_frame(reader)
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(reader.read(4096), timeout=0.5)
        await close(writer, running)

    async def test_a_warning_can_be_turned_off_on_its_own(self) -> None:
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=0.5, warn_after=0
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)
        #  Straight to the parting frame, with no bar in between.
        notice = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        assert "RINGING OFF" in printable(notice)
        await close(writer, running)


async def connect_to(
    running: asyncio.Server,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    host, port = running.sockets[0].getsockname()[:2]
    return await asyncio.open_connection(host, port)


async def close(writer: asyncio.StreamWriter, running: asyncio.Server) -> None:
    writer.close()
    with suppress(ConnectionError):
        await writer.wait_closed()
    running.close()
    await running.wait_closed()


class TestTheBoardHasAFiniteNumberOfLines:
    """A ceiling on live callers, so no one can lock every line.

    A caller over it is turned away with a whole frame, not a silent line, the
    way the timeout says goodbye rather than just dropping.
    """

    async def test_the_ceiling_is_sixty_four_by_default(self) -> None:
        assert DEFAULT_MAX_CONNECTIONS == 64

    async def test_a_caller_over_the_ceiling_is_turned_away(self) -> None:
        running = await serve(Board(), host="127.0.0.1", port=0, max_connections=1)
        held_reader, held_writer = await connect_to(running)
        await read_frame(held_reader)  # the one line is taken
        turned_reader, turned_writer = await connect_to(running)
        #  A whole frame, then the far end closes: read to the close.
        turned_away = await _everything_left(turned_reader)
        assert turned_away.startswith(FRAME_PREAMBLE)
        assert "BUSY" in printable(turned_away)
        turned_writer.close()
        await close(held_writer, running)

    async def test_a_line_frees_when_a_caller_rings_off(self) -> None:
        running = await serve(Board(), host="127.0.0.1", port=0, max_connections=1)
        first_reader, first_writer = await connect_to(running)
        await read_frame(first_reader)
        first_writer.close()
        await first_writer.wait_closed()
        await asyncio.sleep(SETTLE)  # let the server notice the far end has gone
        second_reader, second_writer = await connect_to(running)
        served = await read_frame(second_reader)
        assert "BUSY" not in printable(served)
        await close(second_writer, running)

    async def test_a_service_can_word_the_busy_frame_itself(self) -> None:
        board = Board()

        @board.on_busy
        async def full(request: PageRequest) -> Page:
            return board.menu(PageAddress("1"), "COME BACK SOON", [])

        running = await serve(board, host="127.0.0.1", port=0, max_connections=1)
        held_reader, held_writer = await connect_to(running)
        await read_frame(held_reader)
        turned_reader, turned_writer = await connect_to(running)
        assert "COME BACK SOON" in printable(await _everything_left(turned_reader))
        turned_writer.close()
        await close(held_writer, running)


class TestHandingTheTerminalBack:
    """What the reader is left with once the line has gone.

    They are talking to their modem again by then, so the last thing sent is
    the cursor, somewhere there is room to type.
    """

    async def test_the_timeout_sends_a_whole_frame(self) -> None:
        #  Not a line of text over whatever was showing, which is hard to pick
        #  out from the frame it lands on.
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=0.3, warn_after=0
        )
        reader, writer = await connect_to(running)
        #  Read to the far end closing rather than a fixed number of bytes: the
        #  greeting and the parting may each arrive in several chunks, and a
        #  `read(n)` after the greeting would race the chunking and pick up a
        #  remainder. The parting is the last frame, and being a whole frame it
        #  opens with the preamble that clears the screen and homes the cursor,
        #  so a second preamble is present.
        everything = await _everything_left(reader)
        assert everything.count(FRAME_PREAMBLE) >= 2
        parting = everything[everything.rfind(FRAME_PREAMBLE) :]
        assert parting.startswith(FRAME_PREAMBLE)
        assert "RINGING OFF" in printable(parting)
        await close(writer, running)

    async def test_the_cursor_is_left_on_after_a_timeout(self) -> None:
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=0.3, warn_after=0
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)
        parting = await _everything_left(reader)
        assert parting.endswith(bytes([ScreenControl.CURSOR_ON]))
        await close(writer, running)

    async def test_the_cursor_is_left_on_after_a_deliberate_goodbye(self) -> None:
        running = await serve(Board(), host="127.0.0.1", port=0)
        reader, writer = await connect_to(running)
        await read_frame(reader)
        writer.write(b"*90#")
        await writer.drain()
        parting = await _everything_left(reader)
        assert "GOODBYE" in printable(parting)
        assert parting.endswith(bytes([ScreenControl.CURSOR_ON]))
        await close(writer, running)

    async def test_a_service_can_word_the_timeout_itself(self) -> None:
        board = Board()

        @board.on_timed_out
        async def gone(request: PageRequest, frame_index: int) -> Page:
            return board.menu(
                PageAddress("1"), f"COME BACK TO *{request.address}#", []
            )

        running = await serve(
            board, host="127.0.0.1", port=0, idle_timeout=0.3, warn_after=0
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)
        #  Without the terminator: `#` travels as 0x5F, which the SAA5050 draws
        #  as `#` and this helper, decoding as ASCII, shows as `_`.
        assert "COME BACK TO *1" in printable(await _everything_left(reader))
        await close(writer, running)


async def _everything_left(reader: asyncio.StreamReader) -> bytes:
    """Read until the far end closes."""
    buffer = b""
    while True:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        if not chunk:
            return buffer
        buffer += chunk
