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

from sextile.addressing import PageAddress
from sextile.page import Page
from sextile.server import DEFAULT_PORT, serve
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


async def read_frame(reader: asyncio.StreamReader) -> bytes:
    """Read until a whole frame arrives, and return it from its preamble on.

    Anything before it is discarded rather than the read being abandoned: a
    command-line update can precede a frame, and the two may well arrive in one
    chunk, so a frame has to be looked for inside what was read rather than only
    at the start of it.
    """
    buffer = b""
    while True:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        if not chunk:
            return buffer
        buffer += chunk
        found = buffer.find(FRAME_PREAMBLE)
        if found != -1:
            return buffer[found:]


def text_of(data: bytes) -> str:
    return "".join(chr(byte) for byte in data if 0x20 <= byte < 0x7F)


class TestConnecting:
    async def test_the_default_port(self) -> None:
        assert DEFAULT_PORT == 6850

    async def test_a_frame_arrives_unasked_on_connecting(self, server: asyncio.Server) -> None:
        reader, writer = await connect(server)
        greeting = await read_frame(reader)
        assert greeting.startswith(FRAME_PREAMBLE)
        assert "THE BOARD" in text_of(greeting)
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

        assert "ITEMS" in text_of(response)
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

        assert "ITEMS" in text_of(await read_frame(reader))
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
        assert "*84" in text_of(echoed)

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
        assert "GOODBYE" in text_of(goodbye)

        #  The far end closes, so a further read returns nothing.
        assert await asyncio.wait_for(reader.read(1), timeout=5.0) == b""
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
        assert "ITEMS" in text_of(await read_frame(first_reader))

        #  The second caller is still on the main index and unaffected.
        second_writer.write(b"*00#")
        await second_writer.drain()
        assert "THE BOARD" in text_of(await read_frame(second_reader))

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
        assert "ITEMS" in text_of(await read_frame(second_reader))

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
        assert "THE BOARD" in text_of(await read_frame(other_reader))
        other_writer.close()
        await other_writer.wait_closed()


class TestIdleCallers:
    async def test_a_silent_caller_is_eventually_released(self) -> None:
        #  A single-line board held open by someone who walked away locks
        #  everyone else out.
        #  No warning here: this is about the timeout alone.
        running = await serve(
            Board(), host="127.0.0.1", port=0, idle_timeout=0.2, warn_after=0
        )
        host, port = running.sockets[0].getsockname()[:2]
        reader, writer = await asyncio.open_connection(host, port)
        await read_frame(reader)

        assert await asyncio.wait_for(reader.read(4096), timeout=5.0)
        assert await asyncio.wait_for(reader.read(1), timeout=5.0) == b""

        writer.close()
        await writer.wait_closed()
        running.close()
        await running.wait_closed()


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
        assert "Press a key" in text_of(warning)
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
            assert "Press a key" in text_of(warning)
            writer.write(b" ")
            await writer.drain()
            restored = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            assert "1-9 select" in text_of(restored), "the page's own footer comes back"

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
        assert "ITEMS" in text_of(await read_frame(reader))
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
        assert "RINGING OFF" in text_of(notice)
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
        await read_frame(reader)
        parting = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        assert parting.startswith(FRAME_PREAMBLE)
        assert "RINGING OFF" in text_of(parting)
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
        assert "GOODBYE" in text_of(parting)
        assert parting.endswith(bytes([ScreenControl.CURSOR_ON]))
        await close(writer, running)

    async def test_a_service_can_word_the_timeout_itself(self) -> None:
        board = Board()

        @board.on_timed_out
        async def gone() -> Page:
            return board.menu(PageAddress("1"), "COME BACK SOON", [])

        running = await serve(
            board, host="127.0.0.1", port=0, idle_timeout=0.3, warn_after=0
        )
        reader, writer = await connect_to(running)
        await read_frame(reader)
        assert "COME BACK SOON" in text_of(await _everything_left(reader))
        await close(writer, running)


async def _everything_left(reader: asyncio.StreamReader) -> bytes:
    """Read until the far end closes."""
    buffer = b""
    while True:
        chunk = await asyncio.wait_for(reader.read(4096), timeout=5.0)
        if not chunk:
            return buffer
        buffer += chunk
