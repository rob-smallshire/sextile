"""The four keys that move about a page, drawn as a compass.

`W` `A` `S` `D` are the framework's keys, not any one service's, so the picture
of them belongs here rather than in a service: one copy, and it stays right if
the keys change.

**The arrows are mosaics because the character set has only three of them.**
The G0 set has `←`, `→` and `↑` at 0x5B, 0x5D and 0x5E, and no down arrow at
all -- so one of the four would have had to be drawn whatever happened, and
three drawn letters beside one drawn picture look like a mistake. All four are
drawn, on the block grid, which is 2x3 to a cell and so has the resolution for
a head and a shaft.

       page up
          W
         ###
    A <-  #  -> D
         ###
          S
      page down

    You can also use the arrow keys

`#` moves to the next frame as well, and is not here: it belongs in a list of
things a reader keys, whereas this is about which way is which.
"""

from typing import Final

from sextile import keys
from sextile.viewdata.blocks import BLOCKS_DOWN, Icon, icon
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour

#: One arrow, and the three turns of it. A long shaft and a head of two blocks
#: a side stepping back from the tip; the turn costs the head nothing, because
#: blocks laid corner to corner read as the diagonal they are.
_RIGHT: Final = icon("""
       #
        #
    ######
        #
       #
""")
_UP: Final = _RIGHT.turned()
_LEFT: Final = _UP.turned()
_DOWN: Final = _LEFT.turned()

#: The middle of the shaft, for a compass drawn without its sideways arm. The
#: two vertical arrows stop short of the middle rows, and without something on
#: them they read as two arrows rather than as one line a reader moves along.
#:
#: Taken from the bottom row of the up arrow rather than drawn again, so that
#: it is in the same column as the shaft it continues however the arrow is
#: redrawn. Two rows of cells, which is what the arrows leave between them.
_SHAFT: Final = Icon(bitmap=(_UP.bitmap[-1],) * (2 * BLOCKS_DOWN))

#: Rows the whole thing takes: a word, a key, two of arrow, the middle row and
#: its labels, two more of arrow, a key, a word, and the line about the cursor
#: keys. Every arrow is three cells across and two rows down, whichever way it
#: points.
#:
#: The down arrow starts on the row the "item" labels are on, as the up arrow
#: ends on the row above the middle one: that is what puts the two of them the
#: same distance from the horizontal pair. They do not collide -- the labels
#: are at the ends of the row and the arrow is in the middle of it.
ROWS: Final = 12

#: Where the pieces of the middle row sit, mirrored about the frame so that
#: each key stays beside its own word. Everything else is centred.
_LEFT_WORD: Final = 4
_LEFT_KEY: Final = 13
_LEFT_ARROW: Final = 15
_RIGHT_ARROW: Final = 22
_RIGHT_KEY: Final = 26
_RIGHT_WORD: Final = 28

#: "item" sits under the middle of the word above it.
_UNDER: Final = 3

#: What the vertical pair are called. A frame is what the wire calls it, but
#: the frames of a page are the pages of one document to whoever is reading
#: it -- and "page up" and "page down" say which way without borrowing
#: "previous" and "next" from the other axis, where they mean something else.
_UP_WORDS: Final = "page up"
_DOWN_WORDS: Final = "page down"

#: The BBC's cursor keys arrive as these same four; `keys.ARROWS` maps them.
_ARROW_KEYS: Final = "You can also use the arrow keys"


def compass(
    composition: Composition,
    row: int,
    *,
    items: bool = True,
    colour: Colour = Colour.CYAN,
    key: Colour = Colour.YELLOW,
    word: Colour = Colour.WHITE,
) -> Composition:
    """Draw the compass with its top row at `row`, taking `ROWS` in all.

    **`items=False` leaves the sideways arm off.** `A` and `D` step through the
    run of pages a menu offered, and the framework does not implement them: a
    service wires them to `request.arrival` or it has no such thing, and one
    that has no such thing must not draw two keys that do nothing. The up and
    down arm is always there, being frames, which every page has.
    """
    composition.text(row, Align.CENTRE, _UP_WORDS, word)
    composition.text(row + 1, Align.CENTRE, keys.PREVIOUS_FRAME, key)
    composition.picture(row + 2, Align.CENTRE, _UP.cells(), colour)
    if items:
        composition.text(row + 4, _LEFT_WORD, "previous", word)
        composition.text(row + 4, _LEFT_KEY, keys.PREVIOUS_ITEM, key)
        composition.picture(row + 4, _LEFT_ARROW, _LEFT.cells(), colour)
        composition.picture(row + 4, _RIGHT_ARROW, _RIGHT.cells(), colour)
        composition.text(row + 4, _RIGHT_KEY, keys.NEXT_ITEM, key)
        composition.text(row + 4, _RIGHT_WORD, "next", word)
        composition.text(row + 5, _LEFT_WORD + _UNDER, "item", word)
        composition.text(row + 5, _RIGHT_WORD, "item", word)
    #  The shaft of the up arrow, which the sideways arm would otherwise be
    #  drawn across. Without the arm it is the only thing on these rows.
    else:
        composition.picture(row + 4, Align.CENTRE, _SHAFT.cells(), colour)
    composition.picture(row + 6, Align.CENTRE, _DOWN.cells(), colour)
    composition.text(row + 8, Align.CENTRE, keys.NEXT_FRAME, key)
    composition.text(row + 9, Align.CENTRE, _DOWN_WORDS, word)
    return composition.text(row + 11, Align.CENTRE, _ARROW_KEYS, word)
