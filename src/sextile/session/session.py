"""What a connected terminal is doing.

A session holds where the reader is, which frame is showing, and how they got
there. It answers one command at a time with whole frames, because a terminal
that can only display what arrives has no other way of being told anything.

Pages are built when they are reached and kept until the reader leaves, so `*00`
sends what is already in hand and `*09` builds it again. That is the whole
difference between the two commands, and it is the difference a reader wants
when the board has moved on since they arrived.
"""

from dataclasses import dataclass
from typing import Final

from sextile.pages.numbering import (
    Logoff,
    MainIndex,
    PageRef,
    UnknownPageError,
    parse_page_target,
)
from sextile.pages.page import Page, PageFrame
from sextile.pages.router import (
    CONVENTIONAL_NEXT_FRAME_KEY,
    NEXT_FRAME_KEY,
    PREVIOUS_FRAME_KEY,
    Neighbours,
    resolve,
)
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
from sextile.store.repository import Repository
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, draw_chrome
from sextile.viewdata.command_line import (
    appended_character_bytes,
    command_line_bytes,
    footer_bytes,
)
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import Frame

#: How far back a reader can retrace their steps.
HISTORY_LIMIT: Final = 32


@dataclass(frozen=True)
class _Sequence:
    """The run of pages a menu offered, and where in it the reader is.

    This is what makes "next post" mean something: from a day's index it is the
    next post that day, from a forum the next in that forum. Arrive by typing a
    page number and there is no sequence, so nothing is offered.
    """

    destinations: tuple[PageRef, ...]
    position: int

    @property
    def following(self) -> PageRef | None:
        after = self.position + 1
        return self.destinations[after] if after < len(self.destinations) else None

    @property
    def preceding(self) -> PageRef | None:
        return self.destinations[self.position - 1] if self.position > 0 else None

    def neighbours(self) -> Neighbours:
        return Neighbours(following=self.following, preceding=self.preceding)

    def moved_to(self, reference: PageRef) -> "_Sequence | None":
        """The same sequence, repositioned, if it contains the destination."""
        if reference not in self.destinations:
            return None
        return _Sequence(self.destinations, self.destinations.index(reference))


@dataclass(frozen=True)
class _Place:
    """A page and the frame of it that was showing."""

    reference: PageRef
    frame_index: int


class Session:
    """One terminal's conversation with the service."""

    def __init__(self, repository: Repository, *, start: PageRef | None = None) -> None:
        self._repository = repository
        self._parser = CommandParser()
        self._history: list[_Place] = []
        self._finished = False
        #  What the footer row is currently showing of a request being typed,
        #  or "" when it is showing the page's own prompt. Kept so that a
        #  keystroke which merely extends it can be sent as one byte.
        self._displayed = ""
        self._reference: PageRef = start or MainIndex()
        self._sequence: _Sequence | None = None
        self._page = resolve(self._reference, repository)
        self._frame_index = 0

    # -- where we are -------------------------------------------------------

    @property
    def reference(self) -> PageRef:
        return self._reference

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def finished(self) -> bool:
        """Whether the service has said goodbye and the line should drop."""
        return self._finished

    def current_frame(self) -> Frame | None:
        found = self._page.frame(self._frame_index)
        return found.frame if found else None

    def greeting(self) -> bytes:
        """The first frame, sent when a terminal connects."""
        return self._send()

    # -- being spoken to ----------------------------------------------------

    def receive(self, data: bytes) -> list[bytes]:
        """Read bytes from the terminal and return whatever should be sent back."""
        responses: list[bytes] = []
        for command in self._parser.feed(data):
            reply = self._act(command)
            if reply is not None:
                responses.append(reply)
            if self._finished:
                break
        self._show_entry(responses)
        return responses

    def _show_entry(self, responses: list[bytes]) -> None:
        """Keep the footer row showing whatever the reader is doing.

        A request being typed replaces the footer; finishing or cancelling one
        puts it back. A whole frame going out has the page's own footer in it
        already, so nothing more is needed then.

        A keystroke that merely extends what is showing sends that one
        character and lets the cursor advance itself. Repainting the row for
        every digit is visible as a flicker once the cursor is on.
        """
        entry = self._parser.entry
        if entry:
            appended = appended_character_bytes(entry, self._displayed)
            responses.append(appended or command_line_bytes(entry))
        elif self._displayed and not responses:
            frame = self.current_frame()
            if frame is not None:
                responses.append(footer_bytes(frame))
        self._displayed = entry

    def _act(self, command: Command) -> bytes | None:
        match command:
            case GoTo(target):
                return self._go_to_target(target)
            case Select(key):
                return self._select(key)
            case Next():
                return self._next_frame()
            case Back():
                return self._back()
            case Redisplay():
                return self._send()
            case Refresh():
                return self._refresh()
            case Clear():
                #  Abandoning a part-typed request changes nothing on screen.
                return None

    # -- movement -----------------------------------------------------------

    def _go_to_target(self, target: str) -> bytes | None:
        try:
            reference = parse_page_target(target)
        except UnknownPageError:
            #  Say so, and leave the reader where they were. Silence would be
            #  indistinguishable from a line fault.
            return self._unknown(target)
        return self._go_to(reference)

    def _go_to(self, reference: PageRef, sequence: "_Sequence | None" = None) -> bytes | None:
        self._remember()
        self._reference = reference
        self._sequence = sequence
        self._page = resolve(
            reference,
            self._repository,
            neighbours=sequence.neighbours() if sequence else Neighbours(),
        )
        self._frame_index = 0
        if isinstance(reference, Logoff):
            self._finished = True
        return self._send()

    def _select(self, key: str) -> bytes | None:
        found = self._page.frame(self._frame_index)
        if found is None:
            return None
        if key in found.moves:
            return self._move(key)
        destination = found.choices.get(key)
        #  A key the frame does not offer does nothing. Guessing would take the
        #  reader somewhere they did not ask to go.
        if destination is None:
            return None
        return self._go_to(destination, self._sequence_towards(destination))

    def _sequence_towards(self, destination: PageRef) -> "_Sequence | None":
        """The run of pages the reader is walking, once they step into it."""
        if self._sequence is not None:
            moved = self._sequence.moved_to(destination)
            if moved is not None:
                return moved
        offered = self._page.destinations
        return _Sequence(offered, offered.index(destination)) if destination in offered else None

    def _move(self, key: str) -> bytes | None:
        if key in (NEXT_FRAME_KEY, CONVENTIONAL_NEXT_FRAME_KEY):
            return self._next_frame()
        if key == PREVIOUS_FRAME_KEY:
            return self._previous_frame()
        return None

    def _next_frame(self) -> bytes | None:
        if self._frame_index + 1 >= len(self._page.frames):
            #  Wrapping round would loop a reader who cannot see that they have.
            return None
        self._frame_index += 1
        return self._send()

    def _previous_frame(self) -> bytes | None:
        if self._frame_index == 0:
            return None
        self._frame_index -= 1
        return self._send()

    def _back(self) -> bytes | None:
        if not self._history:
            return None
        place = self._history.pop()
        self._reference = place.reference
        self._sequence = None
        self._page = resolve(place.reference, self._repository)
        self._frame_index = min(place.frame_index, len(self._page.frames) - 1)
        return self._send()

    def _refresh(self) -> bytes | None:
        self._page = resolve(
            self._reference,
            self._repository,
            neighbours=self._sequence.neighbours() if self._sequence else Neighbours(),
        )
        self._frame_index = min(self._frame_index, len(self._page.frames) - 1)
        return self._send()

    def _remember(self) -> None:
        self._history.append(_Place(self._reference, self._frame_index))
        del self._history[:-HISTORY_LIMIT]

    # -- sending ------------------------------------------------------------

    def _send(self) -> bytes:
        found: PageFrame | None = self._page.frame(self._frame_index)
        assert found is not None, "a page always has the frame it is showing"
        return found.frame.to_bytes()

    def _unknown(self, target: str) -> bytes:
        canvas = Canvas()
        draw_chrome(
            canvas,
            title="UNKNOWN PAGE",
            page_number=_displayed_number(self._page, self._frame_index),
            prompt="0 index, or key another page",
        )
        canvas.row(CONTENT_FIRST_ROW).text(f"*{target[:30]}# is NOT a page here.", Colour.WHITE)
        canvas.row(CONTENT_FIRST_ROW + 2).text("Try *1# for the main index.", Colour.WHITE)
        return canvas.frame.to_bytes()


def _displayed_number(page: Page, frame_index: int) -> str:
    return page.frame_number(frame_index)
