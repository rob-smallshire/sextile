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

Releasing a caller is not enough on its own, though: a reader who has been on
one frame for ten minutes cannot know it is about to happen. So a read is raced
against a timer rather than merely being given a deadline, which is what lets
the service speak first -- the only place it does. After a period of silence the
footer becomes a draining bar, and the next key dismisses it.
"""

import asyncio
import logging
from typing import Final

from sextile.application import Sextile
from sextile.session.session import Session
from sextile.viewdata.idle_warning import BAR_CELLS

#: After the MC6850 ACIA, which drives the BBC Micro's serial port.
DEFAULT_PORT: Final = 6850

#: How long a caller may say nothing before the line is released. None holds the
#: line indefinitely, which is right for a dedicated terminal and wrong for a
#: service anyone can dial.
DEFAULT_IDLE_TIMEOUT: Final = 15 * 60.0

#: How much of the idle timeout passes before the warning appears, when nothing
#: else is said. Half leaves as long to respond as the silence that raised it.
DEFAULT_WARN_FRACTION: Final = 0.5

#: The bar is redrawn only when a cell changes, but the clock has to be looked
#: at more often than that, and not so often as to keep a sleeping process busy.
_MIN_TICK: Final = 1.0

_READ_SIZE: Final = 256

_logger = logging.getLogger(__name__)


async def serve(
    application: Sextile,
    *,
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    idle_timeout: float | None = DEFAULT_IDLE_TIMEOUT,
    warn_after: float | None = None,
) -> asyncio.Server:
    """Start listening. Returns the server, so a caller can close it.

    ``warn_after`` is how long a caller may be silent before the warning bar
    appears, and defaults to half the idle timeout. Zero gives no warning at
    all, for a terminal that would rather not be written to unprompted; with no
    idle timeout there is nothing to warn about and none is given either way.

    Starting and stopping the application is the caller's job, not this
    function's: the server does not open or close an application's resources.
    """
    if warn_after is None and idle_timeout is not None:
        warn_after = idle_timeout * DEFAULT_WARN_FRACTION

    async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await _converse(reader, writer, application, idle_timeout, warn_after)

    server = await asyncio.start_server(handle, host, port)
    for socket in server.sockets:
        _logger.info("Sextile listening on %s", socket.getsockname())
    return server


async def _converse(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    application: Sextile,
    idle_timeout: float | None,
    warn_after: float | None,
) -> None:
    """One caller's session, from connection to ringing off."""
    caller = writer.get_extra_info("peername")
    _logger.info("Call from %s", caller)
    session = Session(application)
    clock = _Silence(idle_timeout, warn_after)
    reading: asyncio.Task[bytes] | None = None
    try:
        await _write(writer, await session.greeting())
        while not session.finished:
            if reading is None:
                reading = asyncio.create_task(reader.read(_READ_SIZE))
            #  Raced rather than merely deadlined, so the service can speak
            #  first: the warning bar is the one thing it says unprompted.
            await asyncio.wait({reading}, timeout=clock.until_something_happens())
            if not reading.done():
                if clock.expired():
                    await _write(writer, await session.time_out())
                    break
                update = session.warn(clock.warning_remaining())
                if update is not None:
                    await _write(writer, update)
                continue
            data, reading = reading.result(), None
            if not data:
                #  The caller went first. There is nobody left to say anything
                #  to, and writing to a closed line only raises.
                return
            clock.heard_something()
            for response in await session.receive(data):
                await _write(writer, response)
        #  Whoever ended it, the terminal is handed back usable: the reader has
        #  a modem to talk to next.
        await _write(writer, session.hangup())
    except (ConnectionError, asyncio.IncompleteReadError):
        #  A caller who pulls the plug is ordinary, not exceptional.
        _logger.info("Call from %s ended abruptly", caller)
    except Exception:
        #  One caller's misfortune must not take the service down with them.
        _logger.exception("Call from %s failed", caller)
    finally:
        _logger.info("Call from %s ended", caller)
        if reading is not None:
            reading.cancel()
        await _hang_up(writer)


class _Silence:
    """How long this caller has said nothing, and what that means.

    Kept apart from the conversation because it is the one piece of the server
    that is about time rather than about bytes, and because a clock is far
    easier to reason about when it cannot also send things.
    """

    def __init__(self, idle_timeout: float | None, warn_after: float | None) -> None:
        self._idle_timeout = idle_timeout
        #  Zero turns it off, as it does for the timeout itself. A warning
        #  later than the timeout could never be shown, and one at the timeout
        #  would arrive with the goodbye.
        self._warn_after = (
            None
            if not warn_after or idle_timeout is None or warn_after >= idle_timeout
            else warn_after
        )
        self._last_heard = _now()

    def heard_something(self) -> None:
        self._last_heard = _now()

    def silent_for(self) -> float:
        return _now() - self._last_heard

    def expired(self) -> bool:
        return self._idle_timeout is not None and self.silent_for() >= self._idle_timeout

    def warning_remaining(self) -> float:
        """The fraction of the warning period still to run, from 1 down to 0."""
        if self._warn_after is None or self._idle_timeout is None:
            return 1.0
        period = self._idle_timeout - self._warn_after
        left = self._idle_timeout - self.silent_for()
        return min(max(left / period, 0.0), 1.0)

    def until_something_happens(self) -> float | None:
        """How long to wait before there is anything to do, or None for ever."""
        if self._idle_timeout is None:
            return None
        remaining = self._idle_timeout - self.silent_for()
        if self._warn_after is None:
            return max(remaining, 0.0)
        until_warning = self._warn_after - self.silent_for()
        if until_warning > 0.0:
            return until_warning
        #  Warning already showing: look often enough to catch each cell of the
        #  bar draining, and no more often than that.
        period = self._idle_timeout - self._warn_after
        return max(min(remaining, period / BAR_CELLS), _MIN_TICK)


def _now() -> float:
    """A clock that does not go backwards when the machine's does."""
    return asyncio.get_running_loop().time()


async def _write(writer: asyncio.StreamWriter, data: bytes) -> None:
    writer.write(data)
    await writer.drain()


async def _hang_up(writer: asyncio.StreamWriter) -> None:
    try:
        writer.close()
        await writer.wait_closed()
    except (ConnectionError, OSError):  # pragma: no cover - the line was already gone
        pass
