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

The session coordinates. Where the reader has been and the run of pages a menu
offered are `sextile.session.navigation`; the bytes that bring the terminal's
display up to date, and the little display state they depend on, are
`sextile.session.screen`. What is left here is deciding, per command, which of
those to reach for.
"""

import logging

from sextile.application import Neighbours, PageRequest, Sextile
from sextile.keys import (
    HASH,
    NEXT_FRAME,
    PREVIOUS_FRAME,
    as_letter,
)
from sextile.page import Page, PageAddress, PageFrame, UnknownPageError
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
from sextile.session.navigation import History, _Sequence
from sextile.session.screen import Screen
from sextile.state import State
from sextile.viewdata.frame import Frame

_logger = logging.getLogger(__name__)


class _PageFailed(Exception):
    """A handler raised while building a page that exists.

    Carried as an exception rather than folded into "no such page", because the
    two are different things to say and only one of them is the reader's doing.
    """

    def __init__(self, request: PageRequest, error: Exception) -> None:
        super().__init__(f"*{request.address}# could not be built")
        self.request = request
        self.error = error


class Session:
    """One terminal's conversation with a service."""

    def __init__(self, application: Sextile, *, start: PageAddress | None = None) -> None:
        self._application = application
        self._parser = CommandParser()
        self._history = History()
        self._screen = Screen()
        self._finished = False
        self._address: PageAddress = start or application.home
        self._sequence: _Sequence | None = None
        self._state = State()
        #  Built on greeting rather than here: an application answers when it is
        #  asked, and asking is something that has to be awaited.
        self._page: Page | None = None
        self._frame_index = 0

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
    def state(self) -> State:
        """What this caller has accumulated, which handlers may add to."""
        return self._state

    def current_frame(self) -> Frame | None:
        if self._page is None:
            return None
        found = self._page.frame(self._frame_index)
        return found.frame if found else None

    def displayed_frame(self) -> Frame | None:
        """The last whole frame the terminal was sent.

        Not always the frame the reader is on: a not-found or failed notice is
        sent over the page they were left on, so this shows the notice while
        `current_frame` still names their page.
        """
        return self._screen.painted

    async def greeting(self) -> bytes:
        """The first frame, sent when a terminal connects."""
        await self._arrive(self._address)
        return self._send()

    # -- ringing off --------------------------------------------------------

    async def busy(self) -> bytes:
        """The frame shown to a caller the board has no room for, then hang up.

        Built and drawn like the greeting, so a turned-away caller sees a whole
        frame in the service's own furniture rather than a line that dies silent.
        """
        self._page = await self._application.busy(self._request(self._address))
        self._frame_index = 0
        self._finished = True
        return self._send()

    async def time_out(self) -> bytes:
        """The frame shown as the line is released for want of a reply.

        The application's, so that a service can say it in its own furniture.
        A whole frame rather than a line of text over whatever was showing:
        being cut off is worth a screen of its own, and a message overprinting
        a frame is hard to pick out from the frame.
        """
        self._page = await self._application.timed_out(
            self._request(self._address),
            self._frame_index,
        )
        self._frame_index = 0
        self._finished = True
        return self._send()

    def hangup(self) -> bytes:
        """Hand the terminal back, after the last frame has gone."""
        return self._screen.handback(self.current_frame())

    # -- the idle warning ---------------------------------------------------
    #
    #  A caller who has read one frame for ten minutes cannot know the line is
    #  about to be released, and being disconnected without warning looks like a
    #  fault. So the footer becomes a draining bar, which the next key dismisses.
    #
    #  Three things want that row: the page's own prompt, a request being typed,
    #  and this. The bar wins while it is up, and whichever of the other two
    #  belongs there is put back when it goes. The bar itself is the screen's;
    #  the session only says when it should go up and come down.

    @property
    def warning_showing(self) -> bool:
        return self._screen.warning_showing

    def warn(self, remaining: float) -> bytes | None:
        """Draw or update the warning bar, or None if the row would not change.

        ``remaining`` is the fraction of the warning period left.
        """
        return self._screen.warn(remaining)

    def dismiss(self) -> bytes | None:
        """Put back whatever the row should show, or None if no bar was up."""
        return self._screen.dismiss(self._parser.entry, self.current_frame())

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
        swallowing = self._screen.warning_showing and not self._parser.entry
        for command in self._parser.feed(data):
            if swallowing:
                swallowing = False
                continue
            reply = await self._act(command)
            if reply is not None:
                responses.append(reply)
            if self._finished:
                break
        self._screen.echo(self._parser.entry, self._showing(), responses)
        return responses

    async def _act(self, command: Command) -> bytes | None:
        match command:
            case GoTo(target):
                return await self._go_to_target(target)
            case Select(key):
                return await self._select(key)
            case Next():
                return await self._next_frame()
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
        #  Plus the page being left: from where the reader is going, that is
        #  where they have just been, and is what `*0#` would return to.
        try:
            page = await self._build(address, sequence, self._been() + (self._address,))
        except _PageFailed as broke:
            #  It exists and we could not draw it, which is a different thing to
            #  say and not the reader's doing. They stay where they are either
            #  way.
            return self._screen.first_frame(
                await self._application.failed(broke.request, broke.error)
            )
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
            return await self._move(key)
        #  Before the form is asked anything: a digit that leads somewhere is a
        #  selection, never a character. `destination` consults the form's own
        #  choices first, so what a digit means is whatever the reader has just
        #  typed it into meaning.
        destination = found.destination(key)
        if destination is not None:
            return await self._go_to(destination, self._sequence_towards(destination))
        if found.form is not None and found.form.accepts(key):
            return await self._screen.type_into(found, key)
        #  A key the frame does not offer does nothing. Guessing would take the
        #  reader somewhere they did not ask to go.
        return None

    def _sequence_towards(self, destination: PageAddress) -> "_Sequence | None":
        """The run of pages the reader is walking, once they step into it."""
        if self._sequence is not None:
            moved = self._sequence.moved_to(destination)
            if moved is not None:
                return moved
        offered = self._page.destinations if self._page else ()
        return _Sequence(offered, offered.index(destination)) if destination in offered else None

    async def _move(self, key: str) -> bytes | None:
        #  An arrow stands for the letter it points like. A page names its keys
        #  in letters, because that is what its footer and its compass say, and
        #  `with_arrows` offers the arrows beside them -- so the arrow has to be
        #  read back as its letter here or the page offers a key it never acts
        #  on.
        key = as_letter(key)
        if key in (NEXT_FRAME, HASH):
            return await self._next_frame()
        if key == PREVIOUS_FRAME:
            return self._previous_frame()
        return None

    async def _next_frame(self) -> bytes | None:
        if self._page is None:
            return None
        showing = self._showing()
        if showing is not None and showing.form is not None:
            #  A reader who has typed something presses RETURN without being
            #  told to. Before the frames, because a page with a field on it is
            #  a page they are typing into rather than reading through.
            sending = showing.form.submit()
            if sending is not None:
                return await self._go_to(sending, self._sequence_towards(sending))
            #  It kept the reader here and may have moved the caret -- a form of
            #  several fields finishes one and starts the next. The screen
            #  redraws the form's rows and puts the cursor where it now belongs.
            return self._screen.repaint_form(showing)
        if self._frame_index + 1 < len(self._page.frames):
            self._frame_index += 1
            return self._send()
        if self._page.next_page is not None:
            #  Out of frames, but the page says what comes after it. Treated as
            #  going there, history and all: it is a move between pages.
            return await self._go_to(self._page.next_page)
        #  Wrapping round would loop a reader who cannot see that they have.
        return None

    def _previous_frame(self) -> bytes | None:
        if self._frame_index == 0:
            return None
        self._frame_index -= 1
        return self._send()

    async def _back(self) -> bytes | None:
        if not self._history:
            return None
        place = self._history.last()
        #  Without the place being returned to: it is about to be popped.
        try:
            page = await self._build(place.address, None, self._been()[:-1])
        except _PageFailed as broke:
            return self._screen.first_frame(
                await self._application.failed(broke.request, broke.error)
            )
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
        #  Unchanged: the reader is on this page, not arriving at it.
        try:
            page = await self._build(self._address, self._sequence, self._been())
        except _PageFailed as broke:
            return self._screen.first_frame(
                await self._application.failed(broke.request, broke.error)
            )
        if page is None:
            return None
        self._page = page
        self._frame_index = min(self._frame_index, len(page.frames) - 1)
        return self._send()

    async def _arrive(self, address: PageAddress) -> None:
        """Put the reader somewhere on connecting, come what may."""
        try:
            page = await self._build(address, None, ())
        except _PageFailed as broke:
            #  On connecting there is nowhere to stay, so the error becomes the
            #  page: a caller must be given a frame.
            self._page = await self._application.failed(broke.request, broke.error)
            return
        if page is not None:
            self._page = page
        else:
            self._page = await self._application.not_found(
                self._request(address), str(address)
            )

    def _request(
        self,
        address: PageAddress,
        sequence: "_Sequence | None" = None,
        been: tuple[PageAddress, ...] | None = None,
    ) -> PageRequest:
        """The request for a page at ``address``, as a handler is given it.

        The one place a request is built: a page's, and the one an error or
        timeout hook is handed, so the two cannot come to carry different things.
        """
        return PageRequest(
            address=address,
            neighbours=sequence.neighbours() if sequence else Neighbours(),
            session=self._state,
            history=self._been() if been is None else been,
            state=self._application.state,
            app=self._application,
        )

    async def _build(
        self,
        address: PageAddress,
        sequence: "_Sequence | None",
        been: tuple[PageAddress, ...],
    ) -> Page | None:
        request = self._request(address, sequence, been)
        try:
            return await self._application.respond(request)
        except Exception as error:
            #  A page that will not build costs its page, not the call. A
            #  session here is a telephone call, so ending it over one page's
            #  exception would make the caller dial back in and find their way
            #  to where they were -- minutes of a slow line for a fault that
            #  was ours.
            #
            #  Logged with its traceback rather than swallowed, so a bug in a
            #  page the service has is found rather than hidden behind a
            #  "not here".
            _logger.exception("Page *%s# could not be built", address)
            raise _PageFailed(request, error) from error

    def _been(self) -> tuple[PageAddress, ...]:
        """Where the reader has been, oldest first, as the history stands."""
        return self._history.been()

    def _remember(self) -> None:
        self._history.remember(self._address, self._frame_index)

    # -- sending ------------------------------------------------------------

    def _showing(self) -> PageFrame | None:
        return self._page.frame(self._frame_index) if self._page else None

    def _send(self) -> bytes:
        found = self._showing()
        assert found is not None, "a page always has the frame it is showing"
        return self._screen.full_frame(found)

    async def _unknown(self, target: str) -> bytes:
        #  The reader stays where they are; the notice is shown over the way, so
        #  the request is theirs -- the page they are on -- and the target is
        #  what they keyed that led nowhere.
        request = self._request(self._address)
        return self._screen.first_frame(await self._application.not_found(request, target))
