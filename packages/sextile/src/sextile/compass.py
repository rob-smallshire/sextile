"""The four keys that move about a page, drawn as a compass.

`W` `A` `S` `D` are the framework's keys, not any one service's, so the picture
of them belongs here: a service that drew its own would be drawing the same
thing, and would keep drawing it after the keys had moved.

**The arrows are mosaics because the character set has only three of them.**
The G0 set has `←`, `→` and `↑` at 0x5B, 0x5D and 0x5E, and no down arrow at
all -- so one of the four would have had to be drawn whatever happened, and
three drawn letters beside one drawn picture look like a mistake. All four are
drawn, on the block grid, which is 2x3 to a cell and so has the resolution for
a head and a shaft.

    previous frame
          W
         ###
    A <-  #  -> D
         ###
          S
     next frame

`#` moves to the next frame as well, and is not here: it belongs in a list of
things a reader keys, whereas this is about which way is which.
"""

from typing import Final

from sextile import keys
from sextile.viewdata.blocks import block_runs, read_bitmap
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour

#: A long shaft and a head of two blocks a side, stepping diagonally back from
#: the tip. Each arrow is a quarter turn of the last, which is what keeps the
#: four looking like one set -- and the turn costs the head nothing, because
#: blocks laid corner to corner read as the diagonal they are.
_RIGHT: Final = ("...#..", "....#.", "######", "....#.", "...#..")
_UP: Final = ("..#..", ".###.", "#.#.#", "..#..", "..#..", "..#..")
_LEFT: Final = ("..#...", ".#....", "######", ".#....", "..#...")
_DOWN: Final = ("..#..", "..#..", "..#..", "#.#.#", ".###.", "..#..")

#: Rows the whole thing takes: a word, a key, two of arrow, the middle row and
#: its labels, two more of arrow, a key and a word. Every arrow is three cells
#: across and two rows down, whichever way it points.
ROWS: Final = 11

#: Where the pieces of the middle row sit, mirrored about the frame so that
#: each key stays beside its own word. Everything else is centred.
_LEFT_WORD: Final = 1
_LEFT_KEY: Final = 10
_LEFT_ARROW: Final = 12
_RIGHT_ARROW: Final = 25
_RIGHT_KEY: Final = 29
_RIGHT_WORD: Final = 31

#: "item" sits under the middle of the word above it.
_UNDER: Final = 3


def compass(
    composition: Composition,
    row: int,
    *,
    colour: Colour = Colour.CYAN,
    key: Colour = Colour.YELLOW,
    word: Colour = Colour.WHITE,
) -> Composition:
    """Draw the compass with its top row at `row`, taking `ROWS` in all."""
    composition.text(row, Align.CENTRE, "previous frame", word)
    composition.text(row + 1, Align.CENTRE, keys.PREVIOUS_FRAME, key)
    composition.picture(row + 2, Align.CENTRE, _blocks(_UP), colour)
    composition.text(row + 4, _LEFT_WORD, "previous", word)
    composition.text(row + 4, _LEFT_KEY, keys.PREVIOUS_ITEM, key)
    composition.picture(row + 4, _LEFT_ARROW, _blocks(_LEFT), colour)
    composition.picture(row + 4, _RIGHT_ARROW, _blocks(_RIGHT), colour)
    composition.text(row + 4, _RIGHT_KEY, keys.NEXT_ITEM, key)
    composition.text(row + 4, _RIGHT_WORD, "next", word)
    composition.text(row + 6, _LEFT_WORD + _UNDER, "item", word)
    composition.text(row + 6, _RIGHT_WORD, "item", word)
    composition.picture(row + 7, Align.CENTRE, _blocks(_DOWN), colour)
    composition.text(row + 9, Align.CENTRE, keys.NEXT_FRAME, key)
    return composition.text(row + 10, Align.CENTRE, "next frame", word)


def _blocks(arrow: tuple[str, ...]) -> list[list[int]]:
    return block_runs(read_bitmap(arrow))
