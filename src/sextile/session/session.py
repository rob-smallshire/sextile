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
from sextile.pages.router import resolve
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
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import Frame

#: How far back a reader can retrace their steps.
HISTORY_LIMIT: Final = 32


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
        self._reference: PageRef = start or MainIndex()
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
        return responses

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

    def _go_to(self, reference: PageRef) -> bytes | None:
        self._remember()
        self._reference = reference
        self._page = resolve(reference, self._repository)
        self._frame_index = 0
        if isinstance(reference, Logoff):
            self._finished = True
        return self._send()

    def _select(self, key: str) -> bytes | None:
        found = self._page.frame(self._frame_index)
        if found is None:
            return None
        destination = found.choices.get(key)
        #  A key the frame does not offer does nothing. Guessing would take the
        #  reader somewhere they did not ask to go.
        return None if destination is None else self._go_to(destination)

    def _next_frame(self) -> bytes | None:
        if self._frame_index + 1 >= len(self._page.frames):
            #  Wrapping round would loop a reader who cannot see that they have.
            return None
        self._frame_index += 1
        return self._send()

    def _back(self) -> bytes | None:
        if not self._history:
            return None
        place = self._history.pop()
        self._reference = place.reference
        self._page = resolve(place.reference, self._repository)
        self._frame_index = min(place.frame_index, len(self._page.frames) - 1)
        return self._send()

    def _refresh(self) -> bytes | None:
        self._page = resolve(self._reference, self._repository)
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
