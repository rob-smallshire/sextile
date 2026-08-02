"""Serving frames over TCP.

Sextile is a plain TCP server and knows nothing of ip232. tcpser is already the
ip232 endpoint an emulator connects to, so Sextile is dialled exactly as any
other viewdata board is:

    tcpser -v 25232 -s 9600 -l 4 -t sS -n 1=localhost:6850

The default port is 6850, after the Motorola ACIA in the BBC's own serial path.

Two things a real board taught us. A caller who walks away must eventually be
released, because a single-line service held open locks everyone else out. And a
caller who vanishes mid-request must not take the service with them, which is
why every connection is handled in isolation and its failures are logged rather
than raised.
"""

import asyncio
import logging
from typing import Final

from sextile.session.session import Session
from sextile.store.repository import Repository

#: The Motorola MC6850 ACIA, which drives the BBC Micro's serial port.
DEFAULT_PORT: Final = 6850

#: How long a caller may say nothing before the line is released.
DEFAULT_IDLE_TIMEOUT: Final = 15 * 60.0

_READ_SIZE: Final = 256

_logger = logging.getLogger(__name__)

_TIMED_OUT_NOTICE: Final = (
    b"\r\n\r\nNo reply for some time; ringing off.\r\n"
)


async def serve(
    repository: Repository,
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    idle_timeout: float = DEFAULT_IDLE_TIMEOUT,
) -> asyncio.Server:
    """Start listening. Returns the server, so a caller can close it."""

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _converse(reader, writer, repository, idle_timeout)

    server = await asyncio.start_server(handle, host, port)
    for socket in server.sockets:
        _logger.info("Sextile listening on %s", socket.getsockname())
    return server


async def _converse(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    repository: Repository,
    idle_timeout: float,
) -> None:
    """One caller's session, from connection to ringing off."""
    caller = writer.get_extra_info("peername")
    _logger.info("Call from %s", caller)
    session = Session(repository)
    try:
        await _write(writer, session.greeting())
        while not session.finished:
            data = await _read(reader, idle_timeout)
            if data is None:
                await _write(writer, _TIMED_OUT_NOTICE)
                break
            if not data:
                break
            #  Building a page touches SQLite, so keep it off the event loop.
            for response in await asyncio.to_thread(session.receive, data):
                await _write(writer, response)
    except (ConnectionError, asyncio.IncompleteReadError):
        #  A caller who pulls the plug is ordinary, not exceptional.
        _logger.info("Call from %s ended abruptly", caller)
    except Exception:
        #  One caller's misfortune must not take the service down with them.
        _logger.exception("Call from %s failed", caller)
    finally:
        _logger.info("Call from %s ended", caller)
        await _hang_up(writer)


async def _read(reader: asyncio.StreamReader, idle_timeout: float) -> bytes | None:
    """Bytes from the caller, or None if they have said nothing for too long."""
    try:
        return await asyncio.wait_for(reader.read(_READ_SIZE), timeout=idle_timeout)
    except TimeoutError:
        return None


async def _write(writer: asyncio.StreamWriter, data: bytes) -> None:
    writer.write(data)
    await writer.drain()


async def _hang_up(writer: asyncio.StreamWriter) -> None:
    try:
        writer.close()
        await writer.wait_closed()
    except (ConnectionError, OSError):  # pragma: no cover - the line was already gone
        pass
