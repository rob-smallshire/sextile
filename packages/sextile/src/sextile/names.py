"""The words a reader can key in place of a page number.

    *ABOUT#     About this service
    *BYE#       Ring off
    *MAIN#      Main index

Prestel was almost entirely numeric, but other viewdata services took keywords
and a service that offers them has to say so somewhere. Generated from the
aliases, so it cannot drift from what the service actually answers -- which is
precisely what a list of keywords typed into a help page does, and did here.

Listed alphabetically rather than by the page they reach: somebody reading this
is looking a word up, not browsing. Several words for one page are all shown,
each on its own line, because the reader has one of them in mind and wants to
find it rather than to learn that it has synonyms.

Registered nowhere, like `history` and `contents`. A service maps it into its
numbering or does without:

    @page("94", name="names", title="Words you can key", keywords=("COMMANDS",))
    async def _names(self, request: PageRequest) -> Page:
        return await self.names(request)
"""

from collections.abc import Callable, Mapping
from typing import Final

from sextile.addressing import PageAddress
from sextile.keys import CONVENTIONAL_NEXT_FRAME, NEXT_FRAME, PREVIOUS_FRAME
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS

TITLE: Final = "WORDS YOU CAN KEY"

_NOTHING: Final = "This service has no words to key."

#: A cell for the colour the word is in, and one for the colour after it.
_ATTRIBUTES: Final = 2


def names_page(
    *,
    address: PageAddress,
    named: Mapping[str, PageAddress],
    describe: Callable[[PageAddress], str],
    home: PageAddress,
    title: str = TITLE,
) -> Page:
    """Build the page of named jumps, one row per word."""
    if not named:
        return _nothing_to_show(address, home, title)

    words = sorted(named)
    keyed = {word: f"*{word}#" for word in words}
    column = min(max(cell_count(shown) for shown in keyed.values()) + 1, COLUMNS // 2)

    batches = [
        words[start : start + CONTENT_ROWS] for start in range(0, len(words), CONTENT_ROWS)
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
        for offset, word in enumerate(batch):
            row = canvas.row(CONTENT_FIRST_ROW + offset)
            row.text(_fitted(keyed[word], column), Colour.YELLOW)
            row.skip(max(column - cell_count(keyed[word]), 0))
            row.text(
                _fitted(describe(named[word]), COLUMNS - column - _ATTRIBUTES),
                Colour.WHITE,
            )
        frames.append(
            PageFrame(
                frame=canvas.frame, choices={"0": home}, moves=_moves(back=back, on=on)
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
    parts = ["Key any word shown"]
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
