"""The semantic shape of a post, between HTML and a screen.

Deliberately structural rather than typographic. On forty columns, colour earns
its keep telling a quotation from a code listing from the author's own words; it
earns nothing rendering an italic, so emphasis is dropped and structure is kept.

A paragraph holds lines rather than one string because phpBB uses `<br>` for
both purposes: a single break is a new line, a double break a new paragraph.
Spending a blank row on every `<br>` would be ruinous on a twenty-four row
screen.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Paragraph:
    """Running text, already broken at the author's own line breaks."""

    lines: tuple[str, ...]


@dataclass(frozen=True)
class Quote:
    """Words quoted from another post, which may themselves quote."""

    blocks: tuple["Block", ...]


@dataclass(frozen=True)
class Code:
    """A listing, whose spacing is significant and must not be reflowed."""

    lines: tuple[str, ...]


@dataclass(frozen=True)
class ListItem:
    text: str


@dataclass(frozen=True)
class Image:
    """A picture, which a viewdata terminal can only announce."""

    description: str


@dataclass(frozen=True)
class Attachment:
    """A file attached to the post, named but not retrievable."""

    name: str


Block = Paragraph | Quote | Code | ListItem | Image | Attachment


@dataclass(frozen=True)
class Link:
    """A link, numbered so the text can refer to it and the frame can list it."""

    number: int
    text: str
    url: str


@dataclass(frozen=True)
class PostContent:
    """A post's body, ready to be laid out."""

    blocks: tuple[Block, ...]
    links: tuple[Link, ...] = ()
