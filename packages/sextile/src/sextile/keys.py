"""The keys that move a reader about.

Movement is two-dimensional, and there are two ways to express it:

           W                          up          the frames of this item
      A    ·    D                left    right    the items either side
           S                         down

The BBC's own cursor keys reach us. Measured against Commstar in Prestel mode
(`docs/spikes/spike_cursor_keys.py`): they transmit 0x88-0x8B, and the 7E1 line
strips the eighth bit, leaving exactly the viewdata cursor-control codes. So
arrows and WASD are two spellings of the same four operations, and this module
is where they are spelled once.

WASD is deliberately anachronistic -- it postdates viewdata by a decade -- but
the arrows are as period as anything here, and a reader may use whichever comes
to hand.
"""

from typing import Final

#: Up and down the frames of one item, because a document reads top to bottom.
PREVIOUS_FRAME: Final = "W"
NEXT_FRAME: Final = "S"

#: Back and forward through the items, like shuffling sideways through a drawer.
PREVIOUS_ITEM: Final = "A"
NEXT_ITEM: Final = "D"

#: The conventional viewdata key, kept working alongside `S` because it is the
#: one key a viewdata reader will try without being told.
CONVENTIONAL_NEXT_FRAME: Final = "#"

#: The page numbers a session answers itself rather than handing to a service:
#: keyed as `*0#`, `*00#` and `*09#`. Here as well as in the parser because a
#: service that explains them in a guide has to name the same ones, and a guide
#: that has drifted from the thing it describes is worse than none.
BACK: Final = "0"
REDISPLAY: Final = "00"
REFRESH: Final = "09"

#: A bare star cancels what is being keyed; two of them begin again.
CANCEL: Final = "*"

#: What the BBC's DELETE key transmits, measured against Commstar in
#: `docs/spikes/spike_editing_keys.py`. Distinct from RETURN, which sends 0x5F
#: and terminates a request.
#:
#: Over a request being typed the command parser rubs out a character with it.
#: On a page it is an ordinary keypress like any other, which a frame may
#: answer or ignore -- a field the reader is typing into answers it, and
#: everything else does not.
RUB_OUT: Final = "\x7f"

#: What the BBC's cursor keys arrive as, once 7E1 has taken the eighth bit.
ARROWS: Final[dict[int, str]] = {
    0x08: PREVIOUS_ITEM,  # cursor left
    0x09: NEXT_ITEM,  # cursor right
    0x0A: NEXT_FRAME,  # cursor down
    0x0B: PREVIOUS_FRAME,  # cursor up
}
