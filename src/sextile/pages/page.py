"""What a page builder produces.

A page is more than a list of frames. On a menu, pressing a digit goes
somewhere, and where it goes depends on which frame is showing -- frame b of a
day's posts offers a different nine posts from frame a. So the choices belong to
the frame, not to the page.

That is the whole reason this type exists rather than the builders simply
returning frames: the session layer needs to know what `3` means right now.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from sextile.pages.numbering import PageRef, format_page_number, frame_letter
from sextile.viewdata.frame import Frame


@dataclass(frozen=True)
class PageFrame:
    """One screen of a page, and what a digit key does while it is showing."""

    frame: Frame
    choices: Mapping[str, PageRef] = field(default_factory=dict)

    def destination(self, key: str) -> PageRef | None:
        """Where a key leads, or None if it leads nowhere here.

        Keyed by character rather than by digit so that a page can offer `N`
        for next or `R` for reply without this type changing.
        """
        return self.choices.get(key)


@dataclass(frozen=True)
class Page:
    """A numbered page, in one or more frames."""

    reference: PageRef
    frames: tuple[PageFrame, ...]

    def __post_init__(self) -> None:
        if not self.frames:
            raise ValueError("a page must have at least one frame")

    @property
    def number(self) -> str:
        return format_page_number(self.reference)

    def frame_number(self, index: int) -> str:
        """The page number as displayed on a frame, such as `82489493b`."""
        return f"{self.number}{frame_letter(index)}"

    def frame(self, index: int) -> PageFrame | None:
        """A frame of this page, or None if there is no such frame."""
        if not 0 <= index < len(self.frames):
            return None
        return self.frames[index]
