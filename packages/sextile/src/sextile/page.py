"""The value an application returns: a page of one or more frames.

Each `PageFrame` carries its own key-to-destination mapping, because the
destination of a digit depends on which frame is showing: frame b of a listing
offers different choices from frame a. A page does not carry its own address;
the session holds what the reader asked for.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from sextile.addressing import PageAddress
from sextile.viewdata.frame import Frame

if TYPE_CHECKING:
    from sextile.forms import Form


@dataclass(frozen=True)
class PageFrame:
    """One screen of a page, and what a key does while it is showing."""

    frame: Frame

    choices: Mapping[str, PageAddress] = field(default_factory=dict)
    """Keys that lead to another page, keyed by character rather than digit so a
    page can offer `N` for next or `R` for reply."""

    moves: frozenset[str] = frozenset()
    """Keys that move to another frame of this page. Separate from `choices`
    because they name no destination; the session stays on the page already
    showing."""

    form: "Form | None" = None
    """A field on this frame that the reader types into, or None.

    A form answers a keypress by redrawing part of the frame rather than leading
    elsewhere. Its digits change as the reader types, so `destination` consults
    it before the frame's fixed `choices`; the session then treats the result as
    it treats a digit on a menu.
    """

    def destination(self, key: str) -> PageAddress | None:
        """Where a key leads, or None if it leads nowhere here.

        A form's choices are consulted first and shadow the frame's fixed
        `choices`, since they reflect what the reader has just typed. A frame
        carrying a form should not also offer a fixed digit; if it does, the
        form's choice wins while it has one.
        """
        if self.form is not None:
            found = self.form.choices().get(key)
            if found is not None:
                return found
        return self.choices.get(key)

    def offers(self, key: str) -> bool:
        """Whether this frame does anything at all with a key."""
        if self.destination(key) is not None:
            return True
        if self.form is not None and self.form.accepts(key):
            return True
        return key in self.choices or key in self.moves


@dataclass(frozen=True)
class Page:
    """One page, in one or more frames."""

    frames: tuple[PageFrame, ...]

    hang_up: bool = False
    """Whether the line should drop once this page has been shown. Which page
    ends the call is the application's choice, not the framework's."""

    follows: PageAddress | None = None
    """Where `#` leads once this page's frames have run out.

    A title frame or the last page of a guide is an invitation to press `#`;
    without this they would be dead ends under that key."""

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("a page must have at least one frame")

    @property
    def destinations(self) -> tuple[PageAddress, ...]:
        """Everything this page offers to go to, in the order it offers it.

        Across all frames, so a menu's ninth choice is followed by the first of
        its next frame. This is the sequence the next and previous keys walk.

        Only the digit keys, and not `0`: the way back to the index is on every
        page, and including it would make `next` mean something other than what
        the menu offered.
        """
        seen: list[PageAddress] = []
        for page_frame in self.frames:
            for key, destination in page_frame.choices.items():
                if key.isdigit() and key != "0" and destination not in seen:
                    seen.append(destination)
        return tuple(seen)

    def frame(self, index: int) -> PageFrame | None:
        """A frame of this page, or None if there is no such frame."""
        if not 0 <= index < len(self.frames):
            return None
        return self.frames[index]
