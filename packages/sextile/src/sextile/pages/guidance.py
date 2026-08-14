"""How to get about: a table of keys, generated from the keys we answer.

The fourth page the framework builds for a service, beside the history, the
contents and the words. It is here for the reason those are: **a guide that
drifts from the thing it describes is worse than none**, and most of what a
guide has to say is the framework's -- the digits, the way home, the syntax of
a request, the key that turns a page.

A service adds what is its own. Which keys those are is a thing only the service
knows: a search field answers letters, a forecast answers `F`, and a framework
that guessed would be describing a service it had not met.

**Two frames, and the split is by what a reader is doing.** The first is moving
about, and carries the compass under it; the second is asking for something.
That division came off Stardot's hand-written guide, which is where this whole
page came from -- it was the better of the two and the way to settle which is to
have only one.

The words are the framework's own and not taken from the routes. A description
in a table of keys is a paraphrase and cannot come to be untrue; a *number* can,
and did, which is why every number here is asked of the router instead.

**Drawn here rather than by a template**, which is the one page of the five for
which that is true. A template divides one list between as many frames as it
takes; these two frames are two different lists, split by what a reader is
doing rather than by what will fit, and the compass hangs off the foot of the
first when the words above it have left the room. Neither is something a
template could be given without becoming a second thing wearing the same name.
What it does share with them -- the keys that turn a frame -- it shares
properly, through `keys.moving`.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from sextile import keys
from sextile.addressing import PageAddress, keyed
from sextile.compass import ROWS as COMPASS_ROWS
from sextile.compass import compass
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.composition import Composition
from sextile.viewdata.drawing import key_row
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.footer import ROOM, FooterItem, Priority, movement, render_footer

TITLE: Final = "HOW TO GET ABOUT"

#: A reader selects with one keypress, so nine is the most a menu offers. Said
#: here rather than imported from the templates, which are a different subject.
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


def guide_page(
    *,
    address: PageAddress,
    title: str = TITLE,
    home: PageAddress | None = None,
    home_called: str = "index",
    moving: Sequence[GuideRow] = (),
    asking: Sequence[GuideRow] = (),
    items: bool = True,
) -> Page:
    """The guide, as two frames of keys.

    `moving` and `asking` are the service's own rows, appended to the
    framework's. `home_called` is what the service calls its first page, so
    that the row for `0` says "back to the main menu" on a service with a menu
    and "back to the main index" on one with an index -- taken from the page's
    own title rather than settled here.
    """
    first = [*_moving(home_called), *moving]
    second = [*_ASKING, GuideRow(), *asking]
    column = max(cell_count(row.key) for row in [*first, *second]) + _GAP
    frames = [
        _frame(
            address, index, rows, title, home, column,
            drawn=index == 0, items=items,
        )
        for index, rows in enumerate((first, second))
    ]
    return Page(frames=tuple(frames))


def _moving(home_called: str) -> list[GuideRow]:
    return [
        GuideRow(f"1-{_CHOICES}", "choose from a menu"),
        GuideRow(keys.BACK, f"back to the {home_called}"),
        GuideRow(keyed("<number>"), "go straight to a page"),
        GuideRow(keyed("<keyword>"), "go to a named page"),
        GuideRow(keys.CONVENTIONAL_NEXT_FRAME, "next frame of a page"),
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


def _frame(
    address: PageAddress,
    index: int,
    rows: Sequence[GuideRow],
    title: str,
    home: PageAddress | None,
    column: int,
    *,
    drawn: bool,
    items: bool,
) -> PageFrame:
    canvas = Canvas()
    back, on = index > 0, index == 0
    draw_chrome(
        canvas,
        title=title,
        page_number=address.frame_number(index),
        prompt=_prompt(back=back, on=on, home=home),
    )
    for offset, row in enumerate(rows[:CONTENT_ROWS]):
        key_row(canvas.row(CONTENT_FIRST_ROW + offset), row.key, row.does, column=column)
    #  The compass goes at the foot of the frame, under whatever it says in
    #  words -- and only where the words have left room for it. A service with
    #  a great many keys of its own gets the keys, which are what it asked for.
    if drawn and CONTENT_ROWS - len(rows) >= COMPASS_ROWS:
        compass(
            Composition(),
            CONTENT_FIRST_ROW + CONTENT_ROWS - COMPASS_ROWS,
            items=items,
        ).draw(canvas)
    return PageFrame(
        frame=canvas.frame,
        choices={keys.BACK: home} if home is not None else {},
        moves=keys.moving(back=back, on=on),
    )


def _prompt(*, back: bool, on: bool, home: PageAddress | None) -> str:
    items = movement(
        key
        for key, answered in ((keys.PREVIOUS_FRAME, back), (keys.NEXT_FRAME, on))
        if answered
    )
    if home is not None:
        items.append(FooterItem(keys.BACK, "index", Priority.ESSENTIAL))
    return render_footer(items, ROOM)
