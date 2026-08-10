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

TITLE: Final = "How to get about"

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
class Key:
    """One key a reader may press, and what pressing it does.

    An empty key is a continuation: a second line of words for the row above,
    which is how a meaning too long for the column gets said. An empty pair is
    a blank row, for grouping.
    """

    key: str = ""
    does: str = ""


def guide_page(
    *,
    address: PageAddress,
    title: str = TITLE,
    home: PageAddress | None = None,
    home_called: str = "index",
    moving: Sequence[Key] = (),
    asking: Sequence[Key] = (),
) -> Page:
    """The guide, as two frames of keys.

    `moving` and `asking` are the service's own rows, appended to the
    framework's. `home_called` is what the service calls its first page, so
    that the row for `0` says "back to the main menu" on a service with a menu
    and "back to the main index" on one with an index -- taken from the page's
    own title rather than settled here.
    """
    first = [*_moving(home_called), *moving]
    second = [*_ASKING, Key(), *asking]
    column = max(cell_count(row.key) for row in [*first, *second]) + _GAP
    frames = [
        _frame(address, index, rows, title, home, column, drawn=index == 0)
        for index, rows in enumerate((first, second))
    ]
    return Page(frames=tuple(frames))


def _moving(home_called: str) -> list[Key]:
    return [
        Key(f"1-{_CHOICES}", "choose from a menu"),
        Key(keys.BACK, f"back to the {home_called}"),
        Key(keyed("<number>"), "go straight to a page"),
        Key(keyed("<keyword>"), "go to a named page"),
        Key(keys.CONVENTIONAL_NEXT_FRAME, "next frame of a page"),
        Key(_RUB_OUT, "rub out a character"),
    ]


_ASKING: Final = (
    #  A meaning too long for the column, said on two rows rather than
    #  shortened into something that reads like a different instruction.
    Key(keyed(keys.BACK), "back, through where you"),
    Key("", "have been"),
    Key(keyed(keys.REDISPLAY), "show this frame again"),
    Key(keyed(keys.REFRESH), "fetch it afresh"),
)


def _frame(
    address: PageAddress,
    index: int,
    rows: Sequence[Key],
    title: str,
    home: PageAddress | None,
    column: int,
    *,
    drawn: bool,
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
            Composition(), CONTENT_FIRST_ROW + CONTENT_ROWS - COMPASS_ROWS
        ).draw(canvas)
    return PageFrame(
        frame=canvas.frame,
        choices={keys.BACK: home} if home is not None else {},
        moves=keys.with_arrows(_pressed(back=back, on=on)),
    )


def _pressed(*, back: bool, on: bool) -> set[str]:
    pressed = set()
    if back:
        pressed.add(keys.PREVIOUS_FRAME)
    if on:
        pressed.update({keys.NEXT_FRAME, keys.CONVENTIONAL_NEXT_FRAME})
    return pressed


def _prompt(*, back: bool, on: bool, home: PageAddress | None) -> str:
    items = movement(
        key
        for key, answered in ((keys.PREVIOUS_FRAME, back), (keys.NEXT_FRAME, on))
        if answered
    )
    if home is not None:
        items.append(FooterItem(keys.BACK, "index", Priority.ESSENTIAL))
    return render_footer(items, ROOM)
