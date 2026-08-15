"""Where a reader has been, and the run of pages they are stepping through.

Two pieces of a session's state, each its own value. `History` is the stack
`*0#` retraces, oldest first and bounded. A `_Sequence` is the run of pages a
menu offered and where in it the reader is, which is what makes "next" and
"previous" mean something -- the next of what that menu was listing. Arrive by
keying a page number and there is no sequence, so neither is offered.
"""

from dataclasses import dataclass, field
from typing import Final

from sextile.page import PageAddress
from sextile.requests import Neighbours

#: How far back a reader can retrace their steps.
HISTORY_LIMIT: Final = 32


@dataclass(frozen=True)
class _Place:
    """A page and the frame of it that was showing."""

    address: PageAddress
    frame_index: int


@dataclass
class History:
    """The pages a reader has left, oldest first, bounded to the last few.

    `*0#` pops the most recent; a new page pushes where the reader was. The
    bound keeps a long call from accumulating without limit -- a terminal
    holds nothing, so the session holds everything, and everything has to end
    somewhere.
    """

    _places: list[_Place] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self._places)

    def been(self) -> tuple[PageAddress, ...]:
        """Where the reader has been, oldest first, as the history stands."""
        return tuple(place.address for place in self._places)

    def remember(self, address: PageAddress, frame_index: int) -> None:
        """Push the page the reader is leaving, dropping the oldest past the bound."""
        self._places.append(_Place(address, frame_index))
        del self._places[:-HISTORY_LIMIT]

    def last(self) -> _Place:
        """The most recent place, which `*0#` returns to."""
        return self._places[-1]

    def pop(self) -> None:
        """Drop the most recent place, once the reader has gone back to it."""
        self._places.pop()


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
