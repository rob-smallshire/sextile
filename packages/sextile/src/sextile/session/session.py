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

import copy
import logging
from dataclasses import dataclass
from typing import Final

from sextile.addressing import PageAddress, UnknownPageError
from sextile.application import Neighbours, PageRequest, Parting, Sextile
from sextile.forms import draw_form
from sextile.keys import (
    CONVENTIONAL_NEXT_FRAME,
    NEXT_FRAME,
    PREVIOUS_FRAME,
    as_letter,
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
from sextile.viewdata.repaint import (
    NOTHING,
    caret_bytes,
    changed_rows,
    rows_bytes,
    typed_bytes,
)

_logger = logging.getLogger(__name__)

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
    def next(self) -> PageAddress | None:
        after = self.position + 1
        return self.destinations[after] if after < len(self.destinations) else None

    @property
    def previous(self) -> PageAddress | None:
        return self.destinations[self.position - 1] if self.position > 0 else None

    def neighbours(self) -> Neighbours:
        return Neighbours(previous=self.previous, next=self.next)

    def moved_to(self, address: PageAddress) -> "_Sequence | None":
        """The same sequence, repositioned, if it contains the destination."""
        if address not in self.destinations:
            return None
        return _Sequence(self.destinations, self.destinations.index(address))


class _PageFailed(Exception):
    """A handler raised while building a page that exists.

    Carried as an exception rather than folded into "no such page", because the
    two are different things to say and only one of them is the reader's doing.
    """

    def __init__(self, address: PageAddress) -> None:
        super().__init__(f"*{address}# could not be built")
        self.address = address


@dataclass(frozen=True)
class _Place:
    """A page and the frame of it that was showing."""

    address: PageAddress
    frame_index: int


class Session:
    """One terminal's conversation with a service."""

    def __init__(self, application: Sextile, *, start: PageAddress | None = None) -> None:
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
                history=self._been(),
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
                #  Putting the footer back begins by hiding the cursor, which
                #  is right -- something is about to be drawn over the row it
                #  was on. On a page with a field, it has to come back: a
                #  reader who thought better of a page number is otherwise left
                #  in a field with no cursor in it and nothing to say where
                #  their next letter would go.
                showing = self._showing()
                if showing is not None and showing.form is not None:
                    responses.append(caret_bytes(*showing.form.caret))
        self._displayed = entry

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
            return await self._show(await self._application.failed(broke.address))
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
            return await self._type(found, key)
        #  A key the frame does not offer does nothing. Guessing would take the
        #  reader somewhere they did not ask to go.
        return None

    async def _type(self, showing: PageFrame, key: str) -> bytes | None:
        """Let a form take a keypress, and send back only what it changed.

        The frame is redrawn **in place**, so what the terminal is showing and
        what the session holds stay the same thing: `*00#` sends the frame in
        hand, and it has to be the frame with the reader's typing on it.

        Only the form's own rows are compared, so a form cannot disturb the
        page around it however wrong it is about its own contents. And only the
        rows that differ are sent -- typing narrows a list of suggestions, so
        the common keystroke leaves the top of it alone and costs forty bytes
        rather than a hundred and twenty.
        """
        form = showing.form
        assert form is not None, "only asked of a frame that has one"
        was = copy.deepcopy(showing.frame)
        caret = form.caret
        await form.typed(key)
        draw_form(showing.frame, form)
        moved = changed_rows(was, showing.frame, form.rows)
        #  The cursor is still where the last repaint left it, which is where
        #  the next character goes. So if the only thing that changed is the
        #  cell under it -- which is every keystroke that does not change what
        #  is on offer, and most of them do not -- the whole repaint is that
        #  one character, and the cursor need not even be moved back.
        field = caret[0]
        if moved == [field]:
            typed = typed_bytes(was, showing.frame, field, at=caret[1])
            if typed is not None:
                return typed
        if not moved:
            #  A keystroke that draws nothing and still moves the cursor: a
            #  space is a blank cell over a blank cell, so the frame comes out
            #  identical and there are no rows to send. Sending nothing leaves
            #  the cursor a cell behind where the form now thinks it is, and
            #  every keystroke after it lands one cell out -- which is how
            #  `ULAN BATOR` came to be typed with its space in the wrong place
            #  and rubbed out leaving characters behind.
            return caret_bytes(*form.caret) if form.caret != caret else NOTHING
        return rows_bytes(showing.frame, moved, was=was, caret=form.caret)

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
        if key in (NEXT_FRAME, CONVENTIONAL_NEXT_FRAME):
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
            was = copy.deepcopy(showing.frame)
            sending = showing.form.submit()
            if sending is not None:
                return await self._go_to(sending, self._sequence_towards(sending))
            #  It kept the reader here and may have moved the caret -- a form
            #  of several fields finishes one and starts the next. So the frame
            #  is redrawn and the cursor put where it now belongs, which
            #  nothing else would do: the rows may not have changed at all.
            draw_form(showing.frame, showing.form)
            moved = changed_rows(was, showing.frame, showing.form.rows)
            return rows_bytes(
                showing.frame, moved, was=was, caret=showing.form.caret
            ) or caret_bytes(*showing.form.caret)
        if self._frame_index + 1 < len(self._page.frames):
            self._frame_index += 1
            return self._send()
        if self._page.follows is not None:
            #  Out of frames, but the page says what comes after it. Treated as
            #  going there, history and all: it is a move between pages.
            return await self._go_to(self._page.follows)
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
        place = self._history[-1]
        #  Without the place being returned to: it is about to be popped.
        try:
            page = await self._build(place.address, None, self._been()[:-1])
        except _PageFailed as broke:
            return await self._show(await self._application.failed(broke.address))
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
            return await self._show(await self._application.failed(broke.address))
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
            self._page = await self._application.failed(broke.address)
            return
        self._page = page if page is not None else await self._application.not_found(str(address))

    async def _build(
        self,
        address: PageAddress,
        sequence: "_Sequence | None",
        been: tuple[PageAddress, ...],
    ) -> Page | None:
        try:
            return await self._application.respond(
                PageRequest(
                    address=address,
                    neighbours=sequence.neighbours() if sequence else Neighbours(),
                    session=self._state,
                    history=been,
                    state=self._application.state,
                    app=self._application,
                )
            )
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
            raise _PageFailed(address) from error

    def _been(self) -> tuple[PageAddress, ...]:
        """Where the reader has been, oldest first, as the history stands."""
        return tuple(place.address for place in self._history)

    def _remember(self) -> None:
        self._history.append(_Place(self._address, self._frame_index))
        del self._history[:-HISTORY_LIMIT]

    # -- sending ------------------------------------------------------------

    def _showing(self) -> PageFrame | None:
        return self._page.frame(self._frame_index) if self._page else None

    def _send(self) -> bytes:
        found = self._showing()
        assert found is not None, "a page always has the frame it is showing"
        frame = found.frame.to_bytes()
        if found.form is None:
            return frame
        #  A frame begins by hiding the cursor, which is right everywhere but
        #  here: a reader who has arrived at a field needs to see where their
        #  typing will go before they have typed anything. Without this the
        #  caret appears only on the first repaint, which is to say only after
        #  the reader has guessed correctly.
        return frame + caret_bytes(*found.form.caret)

    async def _unknown(self, target: str) -> bytes:
        return await self._show(await self._application.not_found(target))

    async def _show(self, page: Page) -> bytes:
        """Send a page without going to it: something said, not somewhere gone."""
        first = page.frame(0)
        assert first is not None, "a page must have at least one frame"
        return first.frame.to_bytes()
