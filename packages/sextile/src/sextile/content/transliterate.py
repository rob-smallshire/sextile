r"""Reducing arbitrary Unicode to characters the G0 set can display.

Transliteration is total: every input produces output that is displayable, with
an explicit question mark standing for anything genuinely beyond reach. The
alternative -- letting unrepresentable characters travel further down the
pipeline -- defers the failure to the moment bytes reach the wire, where it
surfaces as a corrupted frame rather than a legible substitution.

**The romanisation is `anyascii`'s, not this module's.** Reducing the world's
writing systems to Latin letters is a large and specialised subject, and a table
written by hand is wrong about somebody's alphabet. The letters are not accented
Latin ones either: ø, æ, å, þ and ð are letters of their own alphabets with
their own places in them, which is why Unicode does not decompose them. That
work is `anyascii`'s.

What is left here is the part no library can know: **which ASCII characters the
G0 set has not got.** Ten of them, their code points occupied by arrows,
fractions and rules, so `[` and `\` and `~` need spelling some other way
whatever produced them -- including `anyascii` itself, whose output is therefore
put through the same table.

Three cases, in order of preference:

1. It is already displayable.
2. A deliberate substitution, listed below.
3. `anyascii`, itself reduced to what G0 can draw.
"""

from typing import Final

from anyascii import anyascii

from sextile.viewdata.charset import is_representable

_FALLBACK: Final = "?"

#  Characters that need saying something about here rather than in a library.
_SUBSTITUTIONS: Final[dict[str, str]] = {
    #  The ten ASCII characters G0 has not got. Their code points hold arrows,
    #  fractions and rules instead, so quoted source code and file paths need
    #  deliberate handling -- and no romaniser can help, because to one of
    #  those these are ASCII already and need no work doing to them.
    "[": "(",
    "]": ")",
    "{": "(",
    "}": ")",
    "\\": "/",
    "^": "↑",  # BBC BASIC displays its own exponentiation operator this way
    "_": "-",
    "`": "'",
    "|": "‖",
    "~": "-",
    #  Where a romaniser is not lossy so much as wrong. `anyascii` renders this
    #  as `=`, which does not merely drop the negation but states its opposite.
    "≠": "<>",
}


def _is_shortcode(romanised: str) -> bool:
    """Whether this is `anyascii` naming an emoji rather than romanising a letter.

    It answers `:tada:` for a party popper, which is a good answer somewhere
    with room for it. Here a row is forty cells and a line with three emoji in
    it would spend twenty of them on their names. A question mark costs one and
    says the same thing: there was something here you cannot see.
    """
    return len(romanised) > 2 and romanised.startswith(":") and romanised.endswith(":")


def transliterate(text: str) -> str:
    """Reduce text to characters the G0 set can display.

    Whitespace other than a plain space becomes a space: line structure belongs
    to the block model, and by the time a run of text arrives here it should
    already be a single line.
    """
    return "".join(_transliterate_character(character) for character in text)


def _transliterate_character(character: str) -> str:
    if is_representable(character):
        return character
    if character in _SUBSTITUTIONS:
        return _SUBSTITUTIONS[character]
    if character.isspace():
        return " "
    return _romanised(character)


def _romanised(character: str) -> str:
    """What `anyascii` makes of it, itself reduced to what G0 can draw.

    The second half is not belt and braces. A romaniser answers in ASCII, and
    ASCII holds ten characters this display has not got -- so its answer goes
    through the same table as anything else, or a name romanised into a
    backslash would reach the wire as a character the hardware cannot draw.
    """
    romanised = anyascii(character)
    if not romanised or _is_shortcode(romanised):
        return _FALLBACK
    return "".join(
        found if is_representable(found) else _SUBSTITUTIONS.get(found, _FALLBACK)
        for found in romanised
    )
