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

from collections.abc import Iterable, Mapping
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

#: The cursor keys as themselves, once 7E1 has taken the eighth bit -- rather
#: than turned into letters, because whether an arrow means the same as a
#: letter depends on what is on the screen.
#:
#: On an ordinary page it does: a reader may press W or the up arrow and mean
#: one thing. On a page with a field in it, it does not. W is West and S is
#: South, so a reader reaching for the up arrow would silently type a letter
#: into a coordinate. The parser therefore reports which key was pressed, and
#: the session translates to WASD only where nothing wants the arrow itself.
#:
#: TAB sends 0x09 too, measured against Commstar and indistinguishable from
#: cursor right. That is a gift rather than a nuisance: tabbing between the
#: fields of a form is the first thing a reader will try.
LEFT: Final = "\x08"
RIGHT: Final = "\x09"
DOWN: Final = "\x0a"
UP: Final = "\x0b"

#: Which byte is which arrow. The framework's whole opinion on the subject.
ARROW_KEYS: Final[dict[int, str]] = {0x08: LEFT, 0x09: RIGHT, 0x0A: DOWN, 0x0B: UP}

#: The arrow a reader would press instead of each letter, for a page that wants
#: to offer both.
#:
#: Offered rather than applied. What an arrow *means* is the page's business:
#: on most of them it means what the letter means, and on a page with a
#: coordinate field it does not, W being West and S being South. A framework
#: that translated arrows to letters before any page could see them would be
#: deciding that for every service at once, which is not its to decide.
ARROW_FOR: Final[dict[str, str]] = {
    PREVIOUS_FRAME: UP,
    NEXT_FRAME: DOWN,
    PREVIOUS_ITEM: LEFT,
    NEXT_ITEM: RIGHT,
}


def with_arrows(pressed: Iterable[str]) -> frozenset[str]:
    """Those keys, and the arrows a reader might press instead.

    For a page whose keys move about in the ordinary way, which is nearly all
    of them:

        moves=with_arrows({PREVIOUS_FRAME, NEXT_FRAME})
    """
    wanted = set(pressed)
    return frozenset(wanted | {ARROW_FOR[key] for key in wanted if key in ARROW_FOR})


def arrows_lead_where[T](choices: Mapping[str, T]) -> dict[str, T]:
    """Those choices, with each arrow leading where its letter leads."""
    return dict(choices) | {
        ARROW_FOR[key]: where for key, where in choices.items() if key in ARROW_FOR
    }
