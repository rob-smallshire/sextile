"""Driving a service the way a caller does, for a service's own tests.

A service's tests want to press keys and read the screen, which is what a
reader does and what nothing else can stand in for: a handler returns a `Page`,
but whether `*3#` reaches it, whether the field kept what was typed, and what
`0` does from three pages in are all questions about the session rather than
about any one page.

    async with calling(app) as caller:
        await caller.key("*3#")
        await caller.key("ABC")
        assert "ABC" in caller.shown

`calling` opens the service and closes it again, so a lifespan that holds a
database opens one for the test as it would for a call.

For testing a service, not the framework. The framework's own tests drive
`Session` directly, that being the thing they are testing.
"""

from collections.abc import AsyncIterator, MutableMapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from sextile.addressing import PageAddress
from sextile.application import Sextile
from sextile.requests import Arrival, PageRequest
from sextile.session.session import Session

__all__ = [
    "Caller",
    "calling",
    "request_for",
]


def request_for(
    app: Sextile,
    target: str | PageAddress = "1",
    *,
    arrival: Arrival | None = None,
    session: MutableMapping[str, object] | None = None,
    history: tuple[PageAddress, ...] = (),
) -> PageRequest:
    """A request for a page on a service, for a test that has no session.

    A handler and a layout both take the request they answer. A test that
    exercises one without ringing the service up builds the request here rather
    than by hand, so the service it belongs to is supplied in one place.

    Args:
        app: The service the page belongs to, reached as `request.app`.
        target: The page number the request is for, defaulting to `1`.
        arrival: The pages either side of this one, if the test is about a
            sequence.
        session: This caller's own state, if the test reads or writes it.
        history: Where this caller has been, if the test is about that.
    """
    address = target if isinstance(target, PageAddress) else PageAddress(target)
    return PageRequest(
        address=address,
        app=app,
        arrival=arrival or Arrival(),
        session=session if session is not None else {},
        history=history,
    )


@dataclass
class Caller:
    """A terminal at the other end of the line, driven a keypress at a time.

    Attributes:
        session: The session itself, for a test that needs something this does
            not offer.
        sent: Everything the service has sent, in the order it was sent,
            greeting first. For a test about what went down the wire rather
            than about what is on the screen.
    """

    session: Session
    sent: list[bytes] = field(default_factory=list)

    async def key(self, pressed: str | bytes) -> None:
        r"""Press one key, or several.

        Args:
            pressed: What the terminal sends. A string is the characters a
                reader keys, `"*3#"` or `"ABC"`; bytes are for the codes no
                keyboard spells, such as `b"\x5f"` for RETURN. Several keys at
                once are the same as one at a time: the session reads a byte
                at a time either way.
        """
        data = pressed.encode() if isinstance(pressed, str) else pressed
        self.sent += await self.session.receive(data)

    @property
    def address(self) -> PageAddress:
        """The page the reader is looking at."""
        return self.session.address

    @property
    def shown(self) -> str:
        """What is on the screen, as rows of text.

        The characters only. Colour and the control codes that carry it are
        left out, a test about what a page says needing no knowledge of how an
        attribute cell is spelt.
        """
        frame = self.session.current_frame()
        if frame is None:
            return ""
        characters, _ = frame.to_grid()
        return "\n".join(characters)


@asynccontextmanager
async def calling(
    application: Sextile, *, start: str | PageAddress | None = None
) -> AsyncIterator[Caller]:
    """Open the service, ring it up, and close it again afterwards.

    Args:
        application: The service to call, as its factory builds it.
        start: Where the call begins, for a test that would otherwise spend
            three keypresses getting there. The service's own opening page by
            default, which is what a real caller sees.

    Yields:
        The caller, already shown the first frame.
    """
    where = PageAddress(start) if isinstance(start, str) else start
    await application.startup()
    try:
        caller = Caller(session=Session(application, start=where))
        caller.sent.append(await caller.session.greeting())
        yield caller
    finally:
        await application.shutdown()
