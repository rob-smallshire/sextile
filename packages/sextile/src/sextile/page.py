"""What an application hands back.

A page is more than a list of frames. On a menu, pressing a digit goes
somewhere, and where it goes depends on which frame is showing -- frame b of a
listing offers a different nine choices from frame a. So the choices belong
to the frame, not to the page. That is the whole reason this type exists rather
than an application simply returning frames: the session needs to know what `3`
means right now.

A page does not carry its own number. The address is what the reader asked for
and the session is already holding it; a page that named itself as well would be
one more thing that could disagree.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from sextile.addressing import PageAddress
from sextile.viewdata.frame import Frame


@dataclass(frozen=True)
class PageFrame:
    """One screen of a page, and what a key does while it is showing."""

    frame: Frame

    choices: Mapping[str, PageAddress] = field(default_factory=dict)
    """Keys that go to another page. Keyed by character rather than by digit so
    that a page can offer `N` for next or `R` for reply without this type
    changing."""

    moves: frozenset[str] = frozenset()
    """Keys that move within this page, to another of its frames. Kept apart
    from the choices because they name no destination: the session moves within
    the page it is already showing."""

    def destination(self, key: str) -> PageAddress | None:
        """Where a key leads, or None if it leads nowhere here."""
        return self.choices.get(key)

    def offers(self, key: str) -> bool:
        """Whether this frame does anything at all with a key."""
        return key in self.choices or key in self.moves


@dataclass(frozen=True)
class Page:
    """One page, in one or more frames."""

    frames: tuple[PageFrame, ...]

    hang_up: bool = False
    """Whether the line should drop once this page has been shown. A framework
    that knew which number meant goodbye would be a framework with an opinion
    about numbering, so the page says so instead."""

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("a page must have at least one frame")

    @property
    def destinations(self) -> tuple[PageAddress, ...]:
        """Everything this page offers to go to, in the order it offers it.

        Across all frames, so a menu's ninth choice is followed by the first of
        its next frame. This is the sequence the next and previous keys walk.

        Only the digits, and not 0: the way back to the index is on every page,
        and counting it would make `next` mean something other than what the
        menu appeared to offer.
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
