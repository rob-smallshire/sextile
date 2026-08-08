"""Serving frames over TCP.

Sextile is a plain TCP server and knows nothing of ip232. tcpser is already the
ip232 endpoint an emulator connects to, so Sextile is dialled exactly as any
other viewdata board is:

    tcpser -v 25232 -s 9600 -l 4 -t sS -n 1=localhost:6850

Two things a real board taught us. A caller who walks away must eventually be
released, because a single-line service held open locks everyone else out. And a
caller who vanishes mid-request must not take the service with them, which is
why every connection is handled in isolation and its failures are logged rather
than raised.
"""

import asyncio
import logging
from typing import Final

from sextile.application import Application
from sextile.session.session import Session

#: After the MC6850 ACIA, which drives the BBC Micro's serial port.
DEFAULT_PORT: Final = 6850

#: How long a caller may say nothing before the line is released. None holds the
#: line indefinitely, which is right for a dedicated terminal and wrong for a
#: service anyone can dial.
DEFAULT_IDLE_TIMEOUT: Final = 15 * 60.0

_READ_SIZE: Final = 256

_logger = logging.getLogger(__name__)

_TIMED_OUT_NOTICE: Final = (
    b"\r\n\r\nNo reply for some time; ringing off.\r\n"
)


async def serve(
    application: Application,
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    idle_timeout: float | None = DEFAULT_IDLE_TIMEOUT,
) -> asyncio.Server:
    """Start listening. Returns the server, so a caller can close it.

    Starting and stopping the application is the caller's, not this function's:
    a server that opened an application's database would be a server with an
    opinion about what an application is.
    """

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _converse(reader, writer, application, idle_timeout)

    server = await asyncio.start_server(handle, host, port)
    for socket in server.sockets:
        _logger.info("Sextile listening on %s", socket.getsockname())
    return server


async def _converse(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    application: Application,
    idle_timeout: float | None,
) -> None:
    """One caller's session, from connection to ringing off."""
    caller = writer.get_extra_info("peername")
    _logger.info("Call from %s", caller)
    session = Session(application)
    try:
        await _write(writer, await session.greeting())
        while not session.finished:
            data = await _read(reader, idle_timeout)
            if data is None:
                await _write(writer, _TIMED_OUT_NOTICE)
                break
            if not data:
                break
            for response in await session.receive(data):
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


async def _read(reader: asyncio.StreamReader, idle_timeout: float | None) -> bytes | None:
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
