"""Serving frames over TCP.

Sextile is a plain TCP server. tcpser is already the ip232 endpoint an emulator
connects to, so Sextile is dialled exactly as any other viewdata board is, and
needs no knowledge of ip232 at all.

These tests drive it the way a terminal does: connect, read what arrives, send a
few bytes, read again.
"""

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timedelta, timezone

import pytest

from sextile.model import Post
from sextile.server import DEFAULT_PORT, serve
from sextile.store.repository import Repository

BST = timezone(timedelta(hours=1))

from sextile.viewdata.frame import FRAME_PREAMBLE  # noqa: E402


def make_post(post_id: int, minute: int = 0) -> Post:
    when = datetime(2026, 8, 2, 9, 0, tzinfo=BST) + timedelta(minutes=minute)
    return Post(
        post_id=post_id,
        forum_id=53,
        forum_name="programming",
        author_id=10058,
        author_name="Iapetus",
        subject=f"Re: Topic {post_id}",
        published=when,
        updated=when,
        url=f"https://stardot.org.uk/forums/viewtopic.php?p={post_id}",
        content_html="<p>Some words.</p>",
    )


@pytest.fixture
async def server() -> AsyncIterator[asyncio.Server]:
    with Repository.in_memory() as repository:
        for offset in range(12):
            repository.add_post(make_post(489000 + offset, offset))
        running = await serve(repository, host="127.0.0.1", port=0)
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
        assert "SEXTILE" in text_of(greeting)
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

        assert "LATEST POSTS" in text_of(response)
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

        assert "LATEST POSTS" in text_of(await read_frame(reader))
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
        assert "LATEST POSTS" in text_of(await read_frame(first_reader))

        #  The second caller is still on the main index and unaffected.
        second_writer.write(b"*00#")
        await second_writer.drain()
        assert "SEXTILE" in text_of(await read_frame(second_reader))

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
        assert "LATEST POSTS" in text_of(await read_frame(second_reader))

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
        assert "SEXTILE" in text_of(await read_frame(other_reader))
        other_writer.close()
        await other_writer.wait_closed()


class TestIdleCallers:
    async def test_a_silent_caller_is_eventually_released(self) -> None:
        #  A single-line board held open by someone who walked away locks
        #  everyone else out.
        with Repository.in_memory() as repository:
            running = await serve(repository, host="127.0.0.1", port=0, idle_timeout=0.2)
            host, port = running.sockets[0].getsockname()[:2]
            reader, writer = await asyncio.open_connection(host, port)
            await read_frame(reader)

            assert await asyncio.wait_for(reader.read(4096), timeout=5.0)
            assert await asyncio.wait_for(reader.read(1), timeout=5.0) == b""

            writer.close()
            await writer.wait_closed()
            running.close()
            await running.wait_closed()
