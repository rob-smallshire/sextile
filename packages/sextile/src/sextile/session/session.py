"""What a connected terminal is doing.

A session holds where the reader is, which frame is showing, and how they got
there. It answers one command at a time with whole frames, because a terminal
that can only display what arrives has no other way of being told anything.

The connection *is* the session. A viewdata terminal keeps nothing but the frame
on screen -- not the page it came from, not the menu that led there, not who is
logged in -- so everything of that kind is held here, for as long as the line is
up. That is the opposite of the web, where the client carries a cookie and the
server may forget; and it is why a page request is a request from a *session*
rather than merely for a number.

Pages are built when they are reached and kept until the reader leaves, so `*00`
sends what is already in hand and `*09` builds it again. That is the whole
difference between the two commands, and it is the difference a reader wants
when the board has moved on since they arrived.
"""

from dataclasses import dataclass
from typing import Final

from sextile.addressing import PageAddress, UnknownPageError
from sextile.application import Application, Arrival, PageRequest, Parting
from sextile.keys import (
    CONVENTIONAL_NEXT_FRAME,
    NEXT_FRAME,
    PREVIOUS_FRAME,
)
from sextile.page import Page, PageFrame
from sextile.session.commands import (
    Back,
    Clear,
    Command,
    CommandParser,
    GoTo,
    Next,
    Redisplay,
    Refresh,
    Select,
)
from sextile.viewdata.command_line import (
    command_line_bytes,
    footer_bytes,
    incremental_bytes,
)
from sextile.viewdata.countdown import countdown_bytes, lit_cells
from sextile.viewdata.frame import Frame
from sextile.viewdata.parting import parting_bytes

#: How far back a reader can retrace their steps.
HISTORY_LIMIT: Final = 32


@dataclass(frozen=True)
class _Sequence:
    """The run of pages a menu offered, and where in it the reader is.

    This is what makes "next" mean something: it is the next of whatever the
    menu the reader came through was listing. Arrive by keying a page number and
    there is no sequence, so nothing is offered.
    """

    destinations: tuple[PageAddress, ...]
    position: int

    @property
    def following(self) -> PageAddress | None:
        after = self.position + 1
        return self.destinations[after] if after < len(self.destinations) else None

    @property
    def preceding(self) -> PageAddress | None:
        return self.destinations[self.position - 1] if self.position > 0 else None

    def arrival(self) -> Arrival:
        return Arrival(following=self.following, preceding=self.preceding)

    def moved_to(self, address: PageAddress) -> "_Sequence | None":
        """The same sequence, repositioned, if it contains the destination."""
        if address not in self.destinations:
            return None
        return _Sequence(self.destinations, self.destinations.index(address))


@dataclass(frozen=True)
class _Place:
    """A page and the frame of it that was showing."""

    address: PageAddress
    frame_index: int


class Session:
    """One terminal's conversation with a service."""

    def __init__(self, application: Application, *, start: PageAddress | None = None) -> None:
        self._application = application
        self._parser = CommandParser()
        self._history: list[_Place] = []
        self._finished = False
        #  What the footer row is currently showing of a request being typed,
        #  or "" when it is showing the page's own prompt. Kept so that a
        #  keystroke which merely extends it can be sent as one byte.
        self._displayed = ""
        self._address: PageAddress = start or application.home
        self._sequence: _Sequence | None = None
        self._state: dict[str, object] = {}
        #  Built on greeting rather than here: an application answers when it is
        #  asked, and asking is something that has to be awaited.
        self._page: Page | None = None
        self._frame_index = 0
        #  How much of the idle-warning bar is lit, or None when it is not
        #  showing. Kept so an unchanged bar costs nothing on the wire.
        self._warning_cells: int | None = None

    # -- where we are -------------------------------------------------------

    @property
    def address(self) -> PageAddress:
        return self._address

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def finished(self) -> bool:
        """Whether the service has said goodbye and the line should drop."""
        return self._finished

    @property
    def state(self) -> dict[str, object]:
        """What this caller has accumulated, which handlers may add to."""
        return self._state

    def current_frame(self) -> Frame | None:
        if self._page is None:
            return None
        found = self._page.frame(self._frame_index)
        return found.frame if found else None

    async def greeting(self) -> bytes:
        """The first frame, sent when a terminal connects."""
        await self._arrive(self._address)
        return self._send()

    # -- ringing off --------------------------------------------------------

    async def time_out(self) -> bytes:
        """The frame shown as the line is released for want of a reply.

        The application's, so that a service can say it in its own furniture.
        A whole frame rather than a line of text over whatever was showing:
        being cut off is worth a screen of its own, and a message overprinting
        a frame is hard to pick out from the frame.
        """
        self._page = await self._application.timed_out(
            Parting(
                address=self._address,
                frame_index=self._frame_index,
                history=tuple(place.address for place in self._history),
                session=dict(self._state),
            )
        )
        self._frame_index = 0
        self._finished = True
        return self._send()

    def parting(self) -> bytes:
        """Hand the terminal back, after the last frame has gone.

        The reader is about to be talking to their modem again, and a terminal
        with the cursor hidden under a full screen of somebody else's frame
        gives them nothing to type at.
        """
        frame = self.current_frame()
        return parting_bytes(frame) if frame is not None else b""

    # -- the idle warning ---------------------------------------------------
    #
    #  A caller who has read one frame for ten minutes cannot know the line is
    #  about to be released, and being disconnected without warning looks like a
    #  fault. So the footer becomes a draining bar, which the next key dismisses.
    #
    #  Three things want that row: the page's own prompt, a request being typed,
    #  and this. The bar wins while it is up, and whichever of the other two
    #  belongs there is put back when it goes.

    @property
    def warning_showing(self) -> bool:
        return self._warning_cells is not None

    def warn(self, remaining: float) -> bytes | None:
        """Draw or update the warning bar, or None if the row would not change.

        ``remaining`` is the fraction of the warning period left.

        The bar covers a request being typed, which shares the row. Nothing is
        lost by that: what was keyed is held in the parser rather than on the
        screen, and comes back the moment the reader touches anything. Leaving
        them unwarned and then cutting them off mid-request would be the rudest
        thing this service could do.
        """
        cells = lit_cells(remaining)
        if cells == self._warning_cells:
            return None
        self._warning_cells = cells
        return countdown_bytes(remaining)

    def dismiss(self) -> bytes | None:
        """Put back whatever the row should show, or None if no bar was up."""
        if self._warning_cells is None:
            return None
        self._warning_cells = None
        entry = self._parser.entry
        if entry:
            self._displayed = entry
            return command_line_bytes(entry)
        frame = self.current_frame()
        return footer_bytes(frame) if frame is not None else None

    # -- being spoken to ----------------------------------------------------

    async def receive(self, data: bytes) -> list[bytes]:
        """Read bytes from the terminal and return whatever should be sent back."""
        if self._page is None:
            await self._arrive(self._address)
        responses: list[bytes] = []
        #  The bar said "press a key", so a key has to be safe to press: on a
        #  page, the first thing the reader does wakes the line and does nothing
        #  else.
        #
        #  A whole *command* is suppressed rather than a byte, which matters for
        #  a request arriving all at once. Dropping the first byte of `*8#`
        #  would leave `8#` to be read as a selection and a page turn -- two
        #  things the reader never asked for -- where dropping the request
        #  entire merely means keying it again. A `*` on its own produces no
        #  command at all, so a reader who wakes the line by starting a request
        #  can simply carry on typing it.
        #
        #  Nothing is swallowed over a request already being typed. No key
        #  navigates there -- digits accumulate, `*` cancels, DELETE rubs out --
        #  so every key can safely go on meaning what it always means, and the
        #  reader picks up where they left off.
        swallowing = self._warning_cells is not None and not self._parser.entry
        for command in self._parser.feed(data):
            if swallowing:
                swallowing = False
                continue
            reply = await self._act(command)
            if reply is not None:
                responses.append(reply)
            if self._finished:
                break
        self._show_entry(responses)
        return responses

    def _show_entry(self, responses: list[bytes]) -> None:
        """Keep the footer row showing whatever the reader is doing.

        A request being typed replaces the footer; finishing or cancelling one
        puts it back, and so does dismissing the idle warning. A whole frame
        going out has the page's own footer in it already, so nothing more is
        needed then.

        A keystroke that only adds or removes a character changes the row by
        a byte or three rather than repainting it, which is visible as a
        flicker once the cursor is on.
        """
        entry = self._parser.entry
        warned, self._warning_cells = self._warning_cells is not None, None
        if entry:
            #  A bar covering the command line makes the byte-at-a-time trick a
            #  lie: what is on the row is not what was displayed before.
            change = None if warned else incremental_bytes(entry, self._displayed)
            responses.append(change or command_line_bytes(entry))
        elif responses:
            #  A whole frame went out, and it carries the page's own footer.
            pass
        elif self._displayed or warned:
            frame = self.current_frame()
            if frame is not None:
                responses.append(footer_bytes(frame))
        self._displayed = entry

    async def _act(self, command: Command) -> bytes | None:
        match command:
            case GoTo(target):
                return await self._go_to_target(target)
            case Select(key):
                return await self._select(key)
            case Next():
                return self._next_frame()
            case Back():
                return await self._back()
            case Redisplay():
                return self._send()
            case Refresh():
                return await self._refresh()
            case Clear():
                #  Abandoning a part-typed request changes nothing on screen.
                return None

    # -- movement -----------------------------------------------------------

    async def _go_to_target(self, target: str) -> bytes | None:
        try:
            address = self._application.resolve(target)
        except UnknownPageError:
            return await self._unknown(target)
        return await self._go_to(address, told=target)

    async def _go_to(
        self,
        address: PageAddress,
        sequence: "_Sequence | None" = None,
        *,
        told: str | None = None,
    ) -> bytes | None:
        page = await self._build(address, sequence)
        if page is None:
            #  Say so, and leave the reader where they were. Silence would be
            #  indistinguishable from a line fault, and moving them to a page
            #  that is not there would be worse.
            return await self._unknown(told or str(address))
        self._remember()
        self._address = address
        self._sequence = sequence
        self._page = page
        self._frame_index = 0
        if page.hang_up:
            self._finished = True
        return self._send()

    async def _select(self, key: str) -> bytes | None:
        found = self._showing()
        if found is None:
            return None
        if key in found.moves:
            return self._move(key)
        destination = found.destination(key)
        #  A key the frame does not offer does nothing. Guessing would take the
        #  reader somewhere they did not ask to go.
        if destination is None:
            return None
        return await self._go_to(destination, self._sequence_towards(destination))

    def _sequence_towards(self, destination: PageAddress) -> "_Sequence | None":
        """The run of pages the reader is walking, once they step into it."""
        if self._sequence is not None:
            moved = self._sequence.moved_to(destination)
            if moved is not None:
                return moved
        offered = self._page.destinations if self._page else ()
        return _Sequence(offered, offered.index(destination)) if destination in offered else None

    def _move(self, key: str) -> bytes | None:
        if key in (NEXT_FRAME, CONVENTIONAL_NEXT_FRAME):
            return self._next_frame()
        if key == PREVIOUS_FRAME:
            return self._previous_frame()
        return None

    def _next_frame(self) -> bytes | None:
        if self._page is None or self._frame_index + 1 >= len(self._page.frames):
            #  Wrapping round would loop a reader who cannot see that they have.
            return None
        self._frame_index += 1
        return self._send()

    def _previous_frame(self) -> bytes | None:
        if self._frame_index == 0:
            return None
        self._frame_index -= 1
        return self._send()

    async def _back(self) -> bytes | None:
        if not self._history:
            return None
        place = self._history[-1]
        page = await self._build(place.address, None)
        if page is None:
            #  The page has gone since the reader was on it. Staying put is
            #  better than unwinding to somewhere they did not ask for.
            return None
        self._history.pop()
        self._address = place.address
        self._sequence = None
        self._page = page
        self._frame_index = min(place.frame_index, len(page.frames) - 1)
        return self._send()

    async def _refresh(self) -> bytes | None:
        page = await self._build(self._address, self._sequence)
        if page is None:
            return None
        self._page = page
        self._frame_index = min(self._frame_index, len(page.frames) - 1)
        return self._send()

    async def _arrive(self, address: PageAddress) -> None:
        """Put the reader somewhere on connecting, come what may."""
        page = await self._build(address, None)
        self._page = page if page is not None else await self._application.not_found(str(address))

    async def _build(self, address: PageAddress, sequence: "_Sequence | None") -> Page | None:
        return await self._application.respond(
            PageRequest(
                address=address,
                arrival=sequence.arrival() if sequence else Arrival(),
                session=self._state,
            )
        )

    def _remember(self) -> None:
        self._history.append(_Place(self._address, self._frame_index))
        del self._history[:-HISTORY_LIMIT]

    # -- sending ------------------------------------------------------------

    def _showing(self) -> PageFrame | None:
        return self._page.frame(self._frame_index) if self._page else None

    def _send(self) -> bytes:
        found = self._showing()
        assert found is not None, "a page always has the frame it is showing"
        return found.frame.to_bytes()

    async def _unknown(self, target: str) -> bytes:
        page = await self._application.not_found(target)
        first = page.frame(0)
        assert first is not None, "a page must have at least one frame"
        return first.frame.to_bytes()
