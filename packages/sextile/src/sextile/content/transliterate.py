"""Reducing arbitrary Unicode to characters the G0 set can display.

Transliteration is total: every input produces output that is displayable, with an
explicit question mark standing for anything genuinely beyond reach. The
alternative -- letting unrepresentable characters travel further down the pipeline
-- defers the failure to the moment bytes reach the wire, where it surfaces as a
corrupted frame rather than a legible substitution.

Three cases, in order of preference:

1. A deliberate substitution, listed below.
2. Compatibility decomposition with combining marks discarded, which handles most
   accented European names for free.
3. A question mark.
"""

import unicodedata
from typing import Final

from sextile.viewdata.charset import is_representable

_FALLBACK: Final = "?"

#  Characters whose obvious substitution is not simply an unaccented letter. The
#  ten ASCII characters G0 lacks are here too: their positions are occupied by
#  arrows, fractions and rules, so quoted source code needs deliberate handling.
_SUBSTITUTIONS: Final[dict[str, str]] = {
    #  ASCII characters absent from G0.
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
    #  Typographic punctuation, which web software and its writers produce
    #  freely.
    "‘": "'",  # left single quotation mark
    "’": "'",  # right single quotation mark
    "‚": ",",  # single low-9 quotation mark
    "“": '"',  # left double quotation mark
    "”": '"',  # right double quotation mark
    "„": '"',  # double low-9 quotation mark
    "–": "-",  # en dash
    "—": "-",  # em dash
    "−": "-",  # minus sign
    "…": "...",  # horizontal ellipsis
    "•": "*",  # bullet
    "·": "*",  # middle dot
    " ": " ",  # no-break space
    "​": "",  # zero width space
    "­": "",  # soft hyphen
    #  Symbols with conventional ASCII renderings.
    "×": "x",  # multiplication sign
    "°": "deg",  # degree sign
    "€": "EUR",  # euro sign
    "©": "(c)",  # copyright sign
    "®": "(R)",  # registered sign
    "™": "(tm)",  # trade mark sign
    "≤": "<=",  # less-than or equal to
    "≥": ">=",  # greater-than or equal to
    "≠": "<>",  # not equal to
    #  Ligatures and letters that decomposition leaves alone.
    "ß": "ss",  # latin small letter sharp s
    "æ": "ae",  # latin small letter ae
    "Æ": "Ae",  # latin capital letter ae
    "œ": "oe",  # latin small ligature oe
    "Œ": "Oe",  # latin capital ligature oe
    "ø": "o",  # latin small letter o with stroke
    "Ø": "O",  # latin capital letter o with stroke
    "ł": "l",  # latin small letter l with stroke
    "Ł": "L",  # latin capital letter l with stroke
    "ð": "d",  # latin small letter eth
    "Ð": "D",  # latin capital letter eth
    "þ": "th",  # latin small letter thorn
    "Þ": "Th",  # latin capital letter thorn
}


def transliterate(text: str) -> str:
    """Reduce text to characters the G0 set can display.

    Whitespace other than a plain space becomes a space: line structure belongs to
    the block model, and by the time a run of text arrives here it should already
    be a single line.
    """
    return "".join(_transliterate_character(character) for character in text)


def _transliterate_character(character: str) -> str:
    if is_representable(character):
        return character
    if character in _SUBSTITUTIONS:
        return _SUBSTITUTIONS[character]
    if character.isspace():
        return " "
    return _decompose(character)


def _decompose(character: str) -> str:
    decomposed = unicodedata.normalize("NFKD", character)
    without_marks = "".join(
        component for component in decomposed if not unicodedata.combining(component)
    )
    if without_marks == character:
        #  Decomposition achieved nothing, so there is no base letter to fall back on.
        return _FALLBACK
    reduced = transliterate(without_marks)
    return reduced if reduced else _FALLBACK
