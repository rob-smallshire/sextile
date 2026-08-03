"""Fitting the navigation prompt into one row.

Forty cells is not many, and the prompt has to say what every available key
does. At its longest it already fills the row exactly, so the next thing added
will not fit -- and what gives should be decided by what the reader can least
afford to lose, not by which item happens to sit at the end of the string.

Each item therefore carries a priority, and the renderer sheds in a fixed order:

1. labels, from the least important upward;
2. whole items, from the least important upward;
3. and finally, if even one key will not fit, what is left is cut.

The key is the last thing to go, because the key is what the reader presses.
The label only teaches it, and a reader who has already learned `0` does not
need to be told it means the menu.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum

from sextile.viewdata.encoding import cell_count

_SEPARATOR = ", "


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

    def rendered(self, *, with_label: bool) -> str:
        return f"{self.key} {self.label}" if with_label and self.label else self.key


def render_footer(items: Sequence[FooterItem], width: int) -> str:
    """Compose the prompt, shedding what will not fit in priority order."""
    if width <= 0:
        return ""

    for labelled in _labelling_orders(items):
        line = _joined(items, labelled)
        if cell_count(line) <= width:
            return line

    #  Every label has gone and the keys alone are still too wide, so items go
    #  too -- the least important first, and never the last one standing.
    kept = list(items)
    while len(kept) > 1:
        kept.remove(_least_important(kept))
        line = _joined(kept, labelled=set())
        if cell_count(line) <= width:
            return line

    return _cut(_joined(kept, labelled=set()), width)


def _labelling_orders(items: Sequence[FooterItem]) -> list[set[int]]:
    """Which items keep their labels, as fewer and fewer of them do.

    Begins with all of them and sheds one at a time, least important first.
    """
    shedding = sorted(
        range(len(items)),
        key=lambda index: (items[index].priority, -index),
    )
    orders = [set(range(len(items)))]
    for index in shedding:
        orders.append(orders[-1] - {index})
    return orders


def _least_important(items: list[FooterItem]) -> FooterItem:
    return min(items, key=lambda item: (item.priority, -items.index(item)))


def _joined(items: Sequence[FooterItem], labelled: set[int]) -> str:
    return _SEPARATOR.join(
        item.rendered(with_label=index in labelled) for index, item in enumerate(items)
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
