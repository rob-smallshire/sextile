"""What a service is made of, from its own registrations.

A list of the pages a service advertises, each with the number a reader would
key. Where a page number carries a field, the field is shown as a placeholder
rather than enumerated:

    *5#            By contributor
    *52<user_id>#  One contributor

Nobody can list every contributor on a screen, but everybody with a contributor
number in their hand can be told where to put it. That is the whole idea, and it
is only possible because the framework knows the patterns rather than a list of
addresses somebody keeps up to date by hand.

A page appears here if it was given a title when it was registered. That is how
a title frame or a logoff page stays off the list without a flag of its own:
giving a page a title is a service saying it may be advertised.

Registered nowhere, like the history page. A service maps it into its numbering
or does without:

    self.page("93", name="contents", title="Every page")(self.contents)
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Final

from sextile.addressing import PageAddress
from sextile.keys import CONVENTIONAL_NEXT_FRAME, NEXT_FRAME, PREVIOUS_FRAME
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS

if TYPE_CHECKING:
    from sextile.application import PageInfo

TITLE: Final = "EVERY PAGE"

_NOTHING: Final = "This service advertises no pages."

#: A cell for the colour the number is in, and one for the colour after it.
_ATTRIBUTES: Final = 2


def contents_page(
    *,
    address: PageAddress,
    pages: Sequence["PageInfo"],
    home: PageAddress,
    title: str = TITLE,
) -> Page:
    """Build the contents page, one row per page, as many frames as it takes."""
    if not pages:
        return _nothing_to_show(address, home, title)

    #  Ordered by the number rather than by the order a service happens to
    #  declare its pages in. Sorting the digits as text puts each namespace root
    #  next to its members -- 5 then 52<user_id> -- which is what a scheme whose
    #  first digit names a namespace already means.
    listing = sorted(pages, key=lambda page: page.keyed)

    #  The numbers are set in a column, so the widest decides where the titles
    #  begin -- and if that leaves too little for a title, the numbers win: a
    #  number that has been truncated is a number that fetches the wrong page.
    keyed = {page.name: f"*{page.keyed}#" for page in listing}
    column = min(max(cell_count(shown) for shown in keyed.values()) + 1, COLUMNS // 2)

    per_frame = CONTENT_ROWS
    batches = [
        listing[start : start + per_frame] for start in range(0, len(listing), per_frame)
    ]
    frames = []
    for index, batch in enumerate(batches):
        canvas = Canvas()
        back, on = index > 0, index + 1 < len(batches)
        draw_chrome(
            canvas,
            title=title,
            page_number=address.frame_number(index),
            prompt=_prompt(back=back, on=on),
        )
        for offset, page in enumerate(batch):
            row = canvas.row(CONTENT_FIRST_ROW + offset)
            shown = keyed[page.name]
            row.text(_fitted(shown, column), Colour.YELLOW)
            row.skip(max(column - cell_count(shown), 0))
            row.text(
                _fitted(page.title, COLUMNS - column - _ATTRIBUTES), Colour.WHITE
            )
        frames.append(
            PageFrame(
                frame=canvas.frame,
                choices={"0": home},
                moves=_moves(back=back, on=on),
            )
        )
    return Page(frames=tuple(frames))


def _nothing_to_show(address: PageAddress, home: PageAddress, title: str) -> Page:
    canvas = Canvas()
    draw_chrome(
        canvas,
        title=title,
        page_number=address.frame_number(0),
        prompt=_prompt(back=False, on=False),
    )
    canvas.row(CONTENT_FIRST_ROW).text(_NOTHING, Colour.WHITE)
    return Page(frames=(PageFrame(frame=canvas.frame, choices={"0": home}),))


def _moves(*, back: bool, on: bool) -> frozenset[str]:
    keys = set()
    if back:
        keys.add(PREVIOUS_FRAME)
    if on:
        keys.update({NEXT_FRAME, CONVENTIONAL_NEXT_FRAME})
    return frozenset(keys)


def _prompt(*, back: bool, on: bool) -> str:
    parts = ["Key any number shown"]
    if back and on:
        parts.append(f"{PREVIOUS_FRAME}{NEXT_FRAME} frame")
    elif on:
        parts.append(f"{NEXT_FRAME} frame")
    elif back:
        parts.append(f"{PREVIOUS_FRAME} frame")
    parts.append("0 index")
    return ", ".join(parts)


def _fitted(text: str, cells: int) -> str:
    fitted = text
    while cell_count(fitted) > cells:
        fitted = fitted[:-1]
    return fitted
