"""Fitting the navigation prompt into one row.

Forty cells is not many, and the prompt has to say what every available key
does. At its longest it already fills the row exactly, so the next thing added
will not fit -- and what gives should be decided by what the reader can least
afford to lose, not by which item happens to sit at the end of the string.

Each item therefore carries a priority, and the renderer sheds in a fixed order:

1. the long way of saying it, where there is a short way -- a band of keys at
   a time, since a pair that reads alike should not stop doing so;
2. keys that are only another key said differently;
3. the word beside the way out, which is the one key every reader knows;
4. the last word off everything else, then the items themselves, and finally,
   if even one key will not fit, what is left is cut.

The key is the last thing to go, because the key is what the reader presses.
The label only teaches it, and a reader who has already learned `0` does not
need to be told it means the index.

**A label sheds by steps rather than all at once**, which is the difference
between a prompt that says what it means and one that does not. An item may
offer a brief form as well as a full one -- "page down", then "down", then
nothing -- so a crowded row loses a word where it used to lose the sentence.
Without that, a page with room to spare was written for the page that has
none, and the reader of both got the terse version.
"""

from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from enum import IntEnum
from typing import Final

from sextile import keys
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS

_SEPARATOR = ", "

#: The row less the cell the colour attribute takes.
ROOM: Final = COLUMNS - 1


class Priority(IntEnum):
    """What a reader can least afford to lose, in descending order."""

    ESSENTIAL = 3
    """The way out. A reader who cannot read the screen still needs to leave it."""

    PRIMARY = 2
    """What this page is chiefly for."""

    SECONDARY = 1
    """Moving about."""

    REDUNDANT = 0
    """An alias for something already shown, such as `#` beside `S`."""


@dataclass(frozen=True)
class FooterItem:
    """One key the reader may press, and what it does."""

    key: str
    label: str = ""
    priority: Priority = Priority.SECONDARY
    brief: str = ""
    """A shorter way of saying the same thing, for when the row is tight."""

    def wordings(self) -> list[str]:
        """Every way of writing this item, the fullest first."""
        said = [word for word in (self.label, self.brief) if word]
        return [f"{self.key} {word}" for word in said] + [self.key]


def render_footer(items: Sequence[FooterItem], width: int) -> str:
    """Compose the prompt, shedding what will not fit in priority order."""
    if width <= 0:
        return ""
    line = ""
    for said, kept in _wordings(items):
        line = _joined([items[index] for index in kept], [said[index] for index in kept])
        if cell_count(line) <= width:
            return line
    return _cut(line, width)


def _wordings(
    items: Sequence[FooterItem],
) -> "Iterator[tuple[dict[int, int], list[int]]]":
    """Every way of writing the row, the fullest first.

    Four things are given up, in this order, and each is a whole band at a
    time so that a row never shows one key of a pair with a word beside it and
    the other without -- they are the same sort of thing and should read alike.

    1. the long way of saying it, where there is a short way;
    2. keys that are only another key said differently;
    3. the word beside the way out, which is the one key every reader knows;
    4. the last word off everything else, and then the keys themselves.

    Two and three are in that order because a row that shows an alias and does
    not say where the way out goes has kept the wrong thing.
    """
    bands = sorted({item.priority for item in items})
    moving: list[Priority] = [
        band for band in bands if band is not Priority.ESSENTIAL
    ]
    said = {index: 0 for index in range(len(items))}
    kept = list(range(len(items)))

    def shorten(band: Priority, level: int) -> None:
        for index in kept:
            if items[index].priority == band:
                said[index] = min(level, len(items[index].wordings()) - 1)

    yield dict(said), list(kept)
    for band in moving:
        shorten(band, 1)
        yield dict(said), list(kept)
    for index in _shedding(items, kept):
        if items[index].priority is Priority.REDUNDANT and len(kept) > 1:
            kept.remove(index)
            yield dict(said), list(kept)
    last: list[Priority] = [Priority.ESSENTIAL, *reversed(moving)]
    for band in last:
        shorten(band, len(items))
        yield dict(said), list(kept)
    for index in _shedding(items, kept):
        if len(kept) > 1:
            kept.remove(index)
            yield dict(said), list(kept)


def _shedding(items: Sequence[FooterItem], kept: Sequence[int]) -> list[int]:
    """Which to give up first: least important, and later before earlier."""
    return sorted(kept, key=lambda index: (items[index].priority, -index))


def _least_important(items: list[FooterItem]) -> FooterItem:
    return min(items, key=lambda item: (item.priority, -items.index(item)))


def _joined(items: Sequence[FooterItem], said: Sequence[int]) -> str:
    return _SEPARATOR.join(
        item.wordings()[step] for item, step in zip(items, said, strict=True)
    )


def _cut(line: str, width: int) -> str:
    """Shorten to fit, measured in cells rather than characters.

    Transliteration can lengthen a string -- an ellipsis becomes three
    characters -- so counting characters would overflow the row. The text is
    left untransliterated: the canvas does that when it writes.
    """
    while line and cell_count(line) > width:
        line = line[:-1]
    return line


#: What each of the movement keys does, said fully and briefly. The item axis
#: takes its noun from whoever is drawing the page: a service moves between
#: posts, or days, or whatever it is made of.
_MOVEMENT: Final = {
    keys.PREVIOUS_FRAME: ("page up", "up"),
    keys.NEXT_FRAME: ("page down", "down"),
    keys.PREVIOUS_ITEM: ("previous {item}", "prev"),
    keys.NEXT_ITEM: ("next {item}", "next"),
}


def movement(available: Iterable[str], *, item: str = "item") -> list[FooterItem]:
    """Footer items for the movement keys a frame answers, in order.

    Here because both the templates and a service drawing a frame by hand have
    to name these, and naming them twice is how two pages of one service come
    to describe the same key differently -- which is what happened: a page
    built by a template said one thing and a page built by hand said another.
    """
    answered = set(available)
    return [
        FooterItem(key, label.format(item=item), Priority.SECONDARY, brief=brief)
        for key, (label, brief) in _MOVEMENT.items()
        if key in answered
    ]
