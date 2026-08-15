"""The keys that move a reader about.

Movement is two-dimensional, and there are two ways to express it::

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

__all__ = [
    "ARROW_FOR",
    "ARROW_KEYS",
    "BACK",
    "CANCEL",
    "HASH",
    "DOWN",
    "LEFT",
    "LETTER_FOR",
    "NEXT_FRAME",
    "NEXT_ITEM",
    "PREVIOUS_FRAME",
    "PREVIOUS_ITEM",
    "REDISPLAY",
    "REFRESH",
    "RIGHT",
    "RUB_OUT",
    "UP",
    "with_arrow_choices",
    "as_letter",
    "frame_moves",
    "with_arrows",
]

#: Up and down the frames of one item, because a document reads top to bottom.
PREVIOUS_FRAME: Final = "W"
NEXT_FRAME: Final = "S"

#: Back and forward through the items on either side.
PREVIOUS_ITEM: Final = "A"
NEXT_ITEM: Final = "D"

#: `#`, which moves to the next frame of a page by viewdata convention. Kept
#: working alongside `S` because it is the one key a reader will try without
#: being told.
HASH: Final = "#"

#: The payloads of the `*0#`, `*00#` and `*09#` commands: the page numbers a
#: session answers itself rather than handing to a service. Here as well as in
#: the parser, so a guide that lists them names the same ones. Not the `0` key a
#: frame offers to go home -- that is `layout.HOME_KEY`, which happens to share
#: the digit but is a keypress on a frame, not a command payload.
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
#: the session translates to WASD only where no page claims the arrow itself.
#:
#: TAB sends 0x09 too, measured against Commstar and indistinguishable from
#: cursor right. That is a gift rather than a nuisance: tabbing between the
#: fields of a form is the first thing a reader will try.
LEFT: Final = "\x08"
RIGHT: Final = "\x09"
DOWN: Final = "\x0a"
UP: Final = "\x0b"

#: Which byte is which arrow.
ARROW_KEYS: Final[dict[int, str]] = {0x08: LEFT, 0x09: RIGHT, 0x0A: DOWN, 0x0B: UP}

#: The arrow a reader would press instead of each letter, for a page that wants
#: to offer both.
#:
#: Claimed rather than applied. What an arrow means is for the page to decide:
#: on most pages it means what the letter means, and on a page with a coordinate
#: field it does not, W being West and S being South. So the arrow-to-letter
#: choice is left to each page rather than made here for every service at once.
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


#: Which letter each arrow stands for, the inverse of `ARROW_FOR`.
LETTER_FOR: Final = {arrow: letter for letter, arrow in ARROW_FOR.items()}


def as_letter(key: str) -> str:
    """The letter a key stands for: an arrow becomes the letter it points like.

    A page says which keys it answers in letters, because that is what its
    footer and its compass show the reader. `with_arrows` offers the arrows
    alongside them, and this turns a pressed arrow back into the letter it
    stands for, so a page does not offer a key it fails to act on.
    """
    return LETTER_FOR.get(key, key)


def with_arrow_choices[T](choices: Mapping[str, T]) -> dict[str, T]:
    """Those choices, with each arrow leading where its letter leads."""
    return dict(choices) | {
        ARROW_FOR[key]: where for key, where in choices.items() if key in ARROW_FOR
    }


def frame_moves(*, has_previous: bool, has_next: bool) -> frozenset[str]:
    """The keys that move between the frames of one page, arrows included.

    Args:
        has_previous: Whether there is a previous frame to go back to.
        has_next: Whether there is a further frame to go on to.

    Returns:
        The keys the frame should answer, empty for a page of one frame.

    `#` comes along wherever `S` does, so the conventional viewdata key keeps
    working for a reader who never learns the rest, and the arrows come along
    with both: a page divided into frames is a page a reader moves through in
    the ordinary way. Said by the page rather than assumed by the session,
    since what an arrow means is for the page to decide.
    """
    pressed = set()
    if has_previous:
        pressed.add(PREVIOUS_FRAME)
    if has_next:
        pressed.update({NEXT_FRAME, HASH})
    return with_arrows(pressed)
