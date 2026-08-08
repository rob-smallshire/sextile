"""Where this caller has been, as a menu of shortcuts.

The session keeps a history so that `*0#` can retrace it one page at a time.
Showing the whole of it costs nothing more, and turns a stack into a map: key 1
for the page before this one, 2 for the one before that, and so on.

It is a framework page rather than each service's own because there is nothing
service-specific about it. What it lists are addresses, which the framework
already understands, and what it calls them comes from the route names, which are
the *application's* words -- so the labels read in the service's own vocabulary
without the framework knowing anything about forums or calendars.

Not registered anywhere. A service maps it into its own numbering, or does not
offer it at all:

    self.page("92", name="history")(self.history)
    self.alias("HISTORY", self.address_for("history"))

The page leaves itself out of the list. Visiting it is a move like any other, so
it enters the history too, and a list of places to go back to has no business
offering the one the reader is looking at.
"""

from collections.abc import Callable, Sequence
from typing import Final

from sextile.addressing import PageAddress
from sextile.keys import CONVENTIONAL_NEXT_FRAME, NEXT_FRAME, PREVIOUS_FRAME
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS

#: A reader selects with one keypress, so nine is the most a frame can offer.
CHOICES_PER_FRAME: Final = 9

TITLE: Final = "WHERE YOU HAVE BEEN"

_NOWHERE: Final = "You have been nowhere else yet."


def history_page(
    *,
    address: PageAddress,
    been: Sequence[PageAddress],
    describe: Callable[[PageAddress], str],
    home: PageAddress,
    title: str = TITLE,
) -> Page:
    """Build the history page.

    ``been`` is oldest first, as the session keeps it; the page shows it newest
    first, so that key 1 means the same as `*0#` and the numbers count backwards
    through the call.
    """
    entries = [where for where in reversed(been) if where != address]
    if not entries:
        return _nothing_to_show(address, home, title)

    batches = [
        entries[start : start + CHOICES_PER_FRAME]
        for start in range(0, len(entries), CHOICES_PER_FRAME)
    ]
    frames = []
    for index, batch in enumerate(batches):
        canvas = Canvas()
        first, last = index > 0, index + 1 < len(batches)
        draw_chrome(
            canvas,
            title=title,
            page_number=address.frame_number(index),
            prompt=_prompt(back=first, on=last),
        )
        choices = {"0": home}
        row = CONTENT_FIRST_ROW
        for offset, where in enumerate(batch):
            #  Keys run 1-9 on every frame, as every other viewdata menu's do,
            #  so that no entry is shown which cannot be chosen. How far back it
            #  is goes in the detail line instead, since on the first frame the
            #  two coincide and after that only the label can say.
            digit = offset + 1
            steps = index * CHOICES_PER_FRAME + digit
            choices[str(digit)] = where
            canvas.row(row).text(f"{digit} ", Colour.YELLOW).text(
                _fitted(describe(where), COLUMNS - 4), Colour.WHITE
            )
            row += 1
            if row < CONTENT_FIRST_ROW + CONTENT_ROWS:
                canvas.row(row).skip(2).text(
                    _fitted(f"*{where}#  {_how_far(steps)}", COLUMNS - 4), Colour.GREEN
                )
            row += 1
        frames.append(
            PageFrame(frame=canvas.frame, choices=choices, moves=_moves(on=last, back=first))
        )
    return Page(frames=tuple(frames))


def _how_far(steps: int) -> str:
    """How many pages back this is, which the digit only says on the first frame."""
    return "one back" if steps == 1 else f"{steps} back"


def _nothing_to_show(address: PageAddress, home: PageAddress, title: str) -> Page:
    """Say so. An empty menu with no explanation looks like a fault."""
    canvas = Canvas()
    draw_chrome(
        canvas,
        title=title,
        page_number=address.frame_number(0),
        prompt=_prompt(back=False, on=False),
    )
    canvas.row(CONTENT_FIRST_ROW).text(_NOWHERE, Colour.WHITE)
    return Page(frames=(PageFrame(frame=canvas.frame, choices={"0": home}),))


def _moves(*, on: bool, back: bool) -> frozenset[str]:
    keys = set()
    if back:
        keys.add(PREVIOUS_FRAME)
    if on:
        keys.update({NEXT_FRAME, CONVENTIONAL_NEXT_FRAME})
    return frozenset(keys)


def _prompt(*, back: bool, on: bool) -> str:
    parts = ["1-9 back"]
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
