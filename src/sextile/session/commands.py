"""Reading what a terminal sends.

The grammar is small. A `*` begins a request, a terminator ends it, and anything
else typed on its own is an immediate keypress:

    *<payload><term>   go somewhere
    *<term>            the next frame
    *0<term>           back
    *00<term>          show this frame again
    *09<term>          fetch it afresh
    **                 abandon a part-typed request
    <term>             the next frame
    <key>              select

This module recognises syntax and nothing else. Whether `MAIN` or `82489493`
names anything is the numbering layer's business, and whether `N` does anything
is the current frame's -- which is what keeps viewdata's numeric keypad from
being baked in, so a page can offer `N` for next or `R` for reply later.

Three bytes terminate a request. Prestel's RETURN transmits 0x5F, measured
against Commstar; 0x23 is what an ordinary terminal sends for `#`; and 0x0D is
what its RETURN sends. Accepting all three costs nothing and means the service
can be driven equally from a BBC Micro and from `nc`.
"""

from dataclasses import dataclass
from typing import Final

#: Longest request we will accumulate before deciding the reader is lost.
ENTRY_LIMIT: Final = 32

_STAR: Final = "*"
_TERMINATORS: Final = frozenset({"\x5f", "#", "\r"})

_BACK: Final = "0"
_REDISPLAY: Final = "00"
_REFRESH: Final = "09"


@dataclass(frozen=True)
class GoTo:
    """Go to a named page. The name may be digits or a keyword."""

    target: str


@dataclass(frozen=True)
class Next:
    """Show the next frame."""


@dataclass(frozen=True)
class Back:
    """Return to the previous page."""


@dataclass(frozen=True)
class Redisplay:
    """Send the current frame again."""


@dataclass(frozen=True)
class Refresh:
    """Build the current page afresh."""


@dataclass(frozen=True)
class Select:
    """A key pressed on its own, which the current frame may act on."""

    key: str


@dataclass(frozen=True)
class Clear:
    """A part-typed request was abandoned."""


Command = GoTo | Next | Back | Redisplay | Refresh | Select | Clear


class CommandParser:
    """Turns a stream of bytes into commands, a few bytes at a time."""

    def __init__(self) -> None:
        self._payload: str | None = None
        #  Set after abandoning a runaway request, so the rest of it is
        #  swallowed rather than arriving as a burst of keypresses.
        self._discarding = False

    @property
    def entry(self) -> str:
        """The request typed so far, for a service that wants to echo it."""
        return "" if self._payload is None else _STAR + self._payload

    def feed(self, data: bytes) -> list[Command]:
        """Read some bytes, returning whatever commands they completed."""
        commands: list[Command] = []
        for byte in data:
            command = self._read(chr(byte & 0x7F))
            if command is not None:
                commands.append(command)
        return commands

    def _read(self, character: str) -> Command | None:
        if self._discarding:
            return self._discard(character)
        if character == _STAR:
            return self._star()
        if character in _TERMINATORS:
            return self._terminate()
        if self._payload is not None:
            return self._accumulate(character)
        if character.isalnum():
            return Select(character.upper())
        #  Line feeds, escapes and other furniture mean nothing here.
        return None

    def _star(self) -> Command | None:
        """Begin a request, or abandon one and begin again.

        `**` clears what has been typed and leaves the reader still entering a
        request, so `*824**1#` goes to page 1 rather than pressing 1.
        """
        abandoned = bool(self._payload)
        self._payload = ""
        return Clear() if abandoned else None

    def _discard(self, character: str) -> Command | None:
        if character == _STAR:
            self._discarding = False
            self._payload = ""
        elif character in _TERMINATORS:
            self._discarding = False
        return None

    def _terminate(self) -> Command | None:
        payload, self._payload = self._payload, None
        if payload is None or payload == "":
            #  A bare terminator, and `*` immediately terminated, both mean the
            #  same thing: show me the next frame.
            return Next()
        if payload == _BACK:
            return Back()
        if payload == _REDISPLAY:
            return Redisplay()
        if payload == _REFRESH:
            return Refresh()
        return GoTo(payload)

    def _accumulate(self, character: str) -> Command | None:
        assert self._payload is not None
        if not character.isalnum():
            return None
        if len(self._payload) >= ENTRY_LIMIT:
            self._payload = None
            self._discarding = True
            return Clear()
        self._payload += character.upper()
        return None
