"""A page: its number, and the value an application returns for it.

Each `PageFrame` carries its own key-to-destination mapping, because the
destination of a digit depends on which frame is showing: frame b of a listing
offers different choices from frame a. A page does not carry its own address;
the session holds what the reader asked for.

A `PageAddress` is the page number itself: the digits a reader keys between `*`
and `#`. The framework carries nothing richer deliberately. A page number is the
one name shared by everyone who talks about a page -- the reader, the terminal,
the application, and whoever writes it down -- and an application that wants
richer internal types keeps them to itself and routes them here. Dealing in the
page number rather than each application's own reference type keeps history, the
back key and links between services as ordinary operations on a value that needs
to know nothing about what it names.

Page numbers have no practical length limit -- measured against Commstar, which
accepted far more digits than any service would allocate -- so none is imposed
here. What limits a request is the command parser's entry limit.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from sextile.viewdata.frame import Frame

if TYPE_CHECKING:
    from sextile.forms import Form

#: Frames to a page, lettered `a` to `z`; there are no more letters.
FRAMES_PER_PAGE: Final = 26


class UnknownPageError(ValueError):
    """A request that names no page here."""


@dataclass(frozen=True)
class PageAddress:
    """A page number, as keyed.

    Frozen and hashable because addresses are used as keys throughout: what a
    digit on this frame leads to, where the reader has been, and the run of
    pages a menu offered.
    """

    digits: str

    def __post_init__(self) -> None:
        if not self.digits:
            raise UnknownPageError("a page address needs at least one digit")
        #  `str.isdigit` admits Arabic-Indic and other decimal digits, which no
        #  viewdata keypad sends and no page number is spelled with.
        if not (self.digits.isascii() and self.digits.isdigit()):
            raise UnknownPageError(f"{self.digits!r} is not a page address")

    def __str__(self) -> str:
        return self.digits

    def frame_number(self, index: int) -> str:
        """This address as one of its frames displays it, such as `82489493b`."""
        return f"{self.digits}{frame_letter(index)}"


def frame_letter(index: int) -> str:
    """The letter naming a frame within a page, counting from ``a``.

    A reader never keys this: it identifies a continuation of a page too long
    for one screen, and appears only in the page number a frame displays.
    """
    if not 0 <= index < FRAMES_PER_PAGE:
        raise ValueError(f"a page has at most {FRAMES_PER_PAGE} frames, not frame {index}")
    return chr(ord("a") + index)


def keyed(address: "PageAddress | str") -> str:
    """A page number as a reader keys it: `*91#`.

    Defined here rather than in each place that shows a page number, so a service
    does not spell `*91#` differently in different places. Takes a keyword as
    readily as a number: `*MAIN#` is keyed the same way.
    """
    return f"*{address}#"


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

    next_page: PageAddress | None = None
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
