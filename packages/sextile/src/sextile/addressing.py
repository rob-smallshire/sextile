"""What a page is called.

An address is the page number itself: the digits a reader keys between `*` and
`#`. The framework carries nothing richer deliberately. A page number is the one
name shared by everyone who talks about a page -- the reader, the terminal, the
application, and whoever writes it down -- and an application that wants richer
internal types keeps them to itself and routes them here.

Dealing in the page number rather than each application's own reference type
keeps history, the back key and links between services as ordinary operations on
a value that needs to know nothing about what it names.

Page numbers have no practical length limit -- measured against Commstar, which
accepted far more digits than any service would allocate -- so none is imposed
here. What limits a request is the command parser's entry limit.
"""

from dataclasses import dataclass
from typing import Final

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
