"""How to get about: a table of keys, generated from the keys we answer.

The fourth page the framework builds for a service, beside the history, the
contents and the words. It is here for the reason those are: **a guide that
drifts from the thing it describes is worse than none**, and most of what a
guide has to say is the framework's -- the digits, the way home, the syntax of
a request, the key that turns a page.

A service adds what is its own. Which keys those are is something only the
service knows: one page may answer letters typed into a field, another a single
key such as `F`.

**Two frames, and the split is by what a reader is doing.** The first is moving
about, and carries the compass under it; the second is asking for something.

The words are the framework's own and not taken from the routes. A description
in a table of keys is a paraphrase and cannot come to be untrue; a *number* can,
which is why every number here is asked of the router instead.

**The division is a `FrameBreak`, not a shortage of rows.** These two frames are two
different lists, split by what a reader is doing rather than by what will fit,
and that is what a break says. The compass follows the first list as an
ordinary part, drawn under the words rather than held to the foot of the frame:
a rule about where one particular thing sits is the beginning of a layout
language, and a compass is a few rows of graphics like any other few.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from sextile import keys
from sextile.formatting import RowSequencePart
from sextile.layout import HOME_KEY, Custom, Flow, FrameBreak, OnOneFrame, PageLayout
from sextile.page import Page, keyed
from sextile.viewdata.canvas import RowWriter
from sextile.viewdata.compass import ROWS as COMPASS_ROWS
from sextile.viewdata.compass import compass
from sextile.viewdata.composition import Composition
from sextile.viewdata.drawing import key_row
from sextile.viewdata.measure import cell_count

if TYPE_CHECKING:
    from sextile.requests import PageRequest

TITLE: Final = "HOW TO GET ABOUT"

#: A reader selects with one keypress, so nine is the most a menu offers. Kept
#: here rather than imported from the layout layer, a different subject.
_CHOICES: Final = 9

#: What the rub-out key is called on a keyboard. The byte it sends has no
#: printable name, and `DEL` is what is written on the key a reader is looking
#: for.
_RUB_OUT: Final = "DEL"

#: A cell between the key and what it does.
_GAP: Final = 1


@dataclass(frozen=True)
class GuideRow:
    """One row of the guide: a key a reader may press, and what it does.

    Attributes:
        key: What the reader presses, as the guide writes it: `1-9`, `*95#`,
            `A-Z`. Empty continues the row above, which is how a meaning too
            long for the column is carried on to a second line.
        does: What pressing it does, in the framework's own words. Empty
            alongside an empty `key` leaves a blank row, for grouping.

    A row rather than a key, because a service passing these to
    `Sextile.guide` is describing its own additions to a table and not naming
    a keypress the session will answer.
    """

    key: str = ""
    does: str = ""


@dataclass(frozen=True, kw_only=True)
class _Keys(RowSequencePart[GuideRow]):
    """The rows of the guide: a key on the left, what it does on the right.

    The column is given rather than worked out, because both frames of the
    guide share it: a table whose two halves set their own would step sideways
    at the division.
    """

    column: int

    def draw(self, row: RowWriter, entry: GuideRow) -> None:
        key_row(row, entry.key, entry.does, column=self.column)


def guide_page(
    *,
    request: "PageRequest",
    title: str = TITLE,
    home_label: str = "index",
    moving_rows: Sequence[GuideRow] = (),
    asking_rows: Sequence[GuideRow] = (),
    show_item_keys: bool = True,
) -> Page:
    """Build the guide, as two frames of the keys this service answers.

    Args:
        request: The request this page answers.
        title: What the header calls it.
        home_label: What the service calls its first page, so that the row for
            `0` says "back to the main menu" on a service with a menu and
            "back to the main index" on one with an index.
        moving_rows: The service's own rows about moving about, appended to the
            framework's.
        asking_rows: The service's own rows about asking for something.
        show_item_keys: Whether the compass shows the keys that move between items.

    Returns:
        Two frames, divided where the guide means to divide rather than where
        the rows run out: the first is about moving about and carries the
        compass, the second about asking for something.
    """
    first = [*_moving(home_label), *moving_rows]
    second = [*_ASKING, GuideRow(), *asking_rows]
    column = max(cell_count(row.key) for row in [*first, *second]) + _GAP
    return PageLayout(
        title=title,
        parts=[
            Flow(_Keys(entries=first, column=column)),
            #  Under the words rather than at the foot of the frame. A rule
            #  about where one particular part sits is the beginning of a
            #  layout language, and this is a few rows of graphics like any
            #  other few rows of graphics.
            OnOneFrame(
                Custom(
                    rows=COMPASS_ROWS,
                    draw=lambda canvas, row: compass(
                        Composition(), row, items=show_item_keys
                    ).draw(canvas),
                )
            ),
            FrameBreak(),
            Flow(_Keys(entries=second, column=column)),
        ],
    ).build(request)


def _moving(home_label: str) -> list[GuideRow]:
    return [
        GuideRow(f"1-{_CHOICES}", "choose from a menu"),
        GuideRow(HOME_KEY, f"back to the {home_label}"),
        GuideRow(keyed("<number>"), "go straight to a page"),
        GuideRow(keyed("<keyword>"), "go to a named page"),
        GuideRow(keys.HASH, "next frame of a page"),
        GuideRow(_RUB_OUT, "rub out a character"),
    ]


_ASKING: Final = (
    #  A meaning too long for the column, said on two rows rather than
    #  shortened into something that reads like a different instruction.
    GuideRow(keyed(keys.BACK), "back, through where you"),
    GuideRow("", "have been"),
    GuideRow(keyed(keys.REDISPLAY), "show this frame again"),
    GuideRow(keyed(keys.REFRESH), "fetch it afresh"),
)
