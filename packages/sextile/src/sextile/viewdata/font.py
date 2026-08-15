"""Fonts for lettering drawn out of block graphics, and the file they live in.

A mosaic font is a bitmap font measured in *blocks* rather than pixels: a letter
eight blocks tall is two and two-thirds cells tall on the screen, and a banner
made of them is drawn with `blocks.block_runs` like any other picture.

**The format is this project's own, and a text file, for two reasons.** A vendored font
is third-party material that has to be reviewed and whose terms have to travel
with it, which a binary blob makes nobody do; and none of the formats these
faces arrive in carries the one thing most needed here, an advance for each
glyph. A row is 78 blocks wide and ten letters at a fixed eight blocks do not
fit in it, so proportional spacing is a requirement rather than a refinement --
and the width to advance by is a decision about the face, made once by whoever
converts it, not something to re-derive on every frame. Deriving it would also
give a space no width at all.

The file is its own documentation:

    name: Acorn
    source: MDFS ArcNormal (mdfs.net/Apps/Font/Fonts1.zip)
    terms: Free for public use
    height: 8
    fixed: 8

    glyph u+0041 advance 7 bearing 1  A
    ..##..
    .####.
    ##..##
    ...

Glyphs are named by code point rather than by the character itself, so that a
space, a `#` and a `.` need no quoting in a file whose other lines are pictures
made of `#` and `.`. The note at the end is for the reader and is ignored. A
glyph with no picture is blank -- which is what a space is.

The picture is the letter and nothing else: the blank columns either side of it
are trimmed away, because a proportional setting wants the letter and the gap
after it is what the advance is for. **The bearing is what makes fixed-width
setting still possible** -- it says how far in from the left the ink sat in the
face's own design width, so a fixed setting can put it back where the designer
had it rather than jamming every letter against the left of its cell.

Reading it needs nothing but the standard library, deliberately: a font is
loaded when a page is drawn.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from typing import Final

__all__ = [
    "Font",
    "FontError",
    "Glyph",
    "font_names",
    "load_font",
    "read_font",
]

#: What is drawn in place of a character the font has no glyph for -- the same
#: substitution `content.transliterate` makes, for the same reason: a banner
#: with one wrong letter is a better answer to a caller than no page at all.
_FALLBACK: Final = "?"

_LIT: Final = "#"
_DARK: Final = "."

_TEXT_FIELDS: Final = ("name", "source", "terms")
_NUMERIC_FIELDS: Final = ("height", "fixed")
_REQUIRED_FIELDS: Final = ("name", "height", "fixed")


class FontError(ValueError):
    """A font file that cannot be read, said as precisely as the file allows."""


@dataclass(frozen=True)
class Glyph:
    """One letter: the blocks it lights, and how far the next one starts along.

    The advance is not the width. It is the width plus whatever gap the face
    wants after this letter, and for a space it is a gap and nothing else. The
    bearing is where the ink sat within the face's design width, kept so that a
    fixed-width setting can put a trimmed glyph back where it belongs.
    """

    bitmap: tuple[tuple[bool, ...], ...]
    advance: int
    bearing: int = 0

    @classmethod
    def of(cls, rows: Sequence[str], advance: int, bearing: int = 0) -> "Glyph":
        """A glyph from a picture, `#` for a lit block; short rows end in blanks."""
        width = max((len(row) for row in rows), default=0)
        return cls(
            bitmap=tuple(
                tuple(index < len(row) and row[index] == _LIT for index in range(width))
                for row in rows
            ),
            advance=advance,
            bearing=bearing,
        )

    @property
    def width(self) -> int:
        return len(self.bitmap[0]) if self.bitmap else 0

    @property
    def height(self) -> int:
        return len(self.bitmap)


@dataclass(frozen=True)
class Font:
    """A face: its glyphs, its height, and where it came from.

    `fixed` is the advance a fixed-width setting uses -- the face's own design
    width, before any trimming. Proportional and kerned settings use the
    glyphs' own advances instead.
    """

    name: str
    height: int
    fixed: int
    glyphs: Mapping[str, Glyph]
    source: str = ""
    terms: str = ""

    def __contains__(self, character: str) -> bool:
        return character in self.glyphs

    def __getitem__(self, character: str) -> Glyph:
        return self.glyphs[character]

    def glyph(self, character: str) -> Glyph:
        """The glyph for a character, substituting rather than raising.

        A font with no question mark of its own leaves a gap of the fixed
        width, which is at least the shape of a missing letter.
        """
        if character in self.glyphs:
            return self.glyphs[character]
        if _FALLBACK in self.glyphs:
            return self.glyphs[_FALLBACK]
        return Glyph(bitmap=(), advance=self.fixed)


#: Where the faces shipped with the framework live. An application may read a
#: font from anywhere with `read_font`; this is only the library.
_LIBRARY: Final = "sextile.viewdata.fonts"

_SUFFIX: Final = ".font"


def font_names() -> tuple[str, ...]:
    """The faces the framework ships, in a fit state to be offered to a caller."""
    return tuple(
        sorted(
            entry.name.removesuffix(_SUFFIX)
            for entry in resources.files(_LIBRARY).iterdir()
            if entry.name.endswith(_SUFFIX)
        )
    )


@lru_cache
def load_font(name: str) -> Font:
    """A face shipped with the framework, by name.

    Cached: a font is some thousands of lines of picture, and a page that draws
    a banner should not pay for parsing it twice.
    """
    file = resources.files(_LIBRARY).joinpath(name + _SUFFIX)
    if not file.is_file():
        raise FontError(
            f"there is no font called {name!r}; there is {', '.join(font_names())}"
        )
    return read_font(file.read_text(encoding="utf-8"))


def read_font(text: str) -> Font:
    """Parse a font file. Raises `FontError`, naming the line, on anything odd."""
    return _Reader(text).read()


def write_font(font: Font) -> str:
    """The font as a file, which `read_font` reads back to the same thing."""
    lines = [f"name: {font.name}"]
    if font.source:
        lines.append(f"source: {font.source}")
    if font.terms:
        lines.append(f"terms: {font.terms}")
    lines += [f"height: {font.height}", f"fixed: {font.fixed}"]
    for character, glyph in sorted(font.glyphs.items(), key=lambda item: ord(item[0])):
        lines += ["", _glyph_line(character, glyph)]
        lines += [
            "".join(_LIT if block else _DARK for block in row) for row in glyph.bitmap
        ]
    return "\n".join(lines) + "\n"


def _glyph_line(character: str, glyph: Glyph) -> str:
    line = f"glyph u+{ord(character):04x} advance {glyph.advance}"
    if glyph.bearing:
        line += f" bearing {glyph.bearing}"
    #  The note is there to be read by eye; a character that would not survive
    #  the trip through a text file, or is invisible in one, does not get one.
    if character.isprintable() and not character.isspace():
        line += f"  {character}"
    return line


class _Reader:
    """A font file, line by line.

    Written as a small state machine rather than with regular expressions
    because what makes a good error message here is the line number, and every
    line has to be classified anyway: a picture row is a line made only of `#`
    and `.`, which is not a shape a regex over the whole file can localise.
    """

    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()
        self._fields: dict[str, str] = {}
        self._glyphs: dict[str, Glyph] = {}
        self._character: str | None = None
        self._picture: list[str] = []
        self._advance = 0
        self._bearing = 0
        self._number = 0

    def read(self) -> Font:
        for number, line in enumerate(self._lines, start=1):
            self._number = number
            self._line(line.rstrip())
        self._close()
        for field in _REQUIRED_FIELDS:
            if field not in self._fields:
                raise FontError(f"the font gives no {field}")
        #  The header is checked through before the glyphs, so that a
        #  mistyped field is reported as itself rather than as its consequence.
        height, fixed = self._numeric("height"), self._numeric("fixed")
        if not self._glyphs:
            raise FontError(f"{self._fields['name']} has no glyphs")
        for character, glyph in self._glyphs.items():
            if glyph.bitmap and glyph.height != height:
                raise FontError(
                    f"u+{ord(character):04x} is {glyph.height} rows tall, "
                    f"and the font says {height}"
                )
        return Font(
            name=self._fields["name"],
            height=height,
            fixed=fixed,
            glyphs=self._glyphs,
            source=self._fields.get("source", ""),
            terms=self._fields.get("terms", ""),
        )

    def _line(self, line: str) -> None:
        if not line:
            return
        if line.startswith("glyph"):
            self._close()
            self._open(line)
        elif set(line) <= {_LIT, _DARK}:
            if self._character is None:
                raise FontError(f"line {self._number}: a picture before any glyph line")
            self._picture.append(line)
        elif ":" in line and self._character is None:
            self._field(line)
        else:
            raise FontError(
                f"line {self._number}: expected a field, a glyph or a picture"
            )

    def _field(self, line: str) -> None:
        key, _, value = line.partition(":")
        key = key.strip()
        if key not in _TEXT_FIELDS + _NUMERIC_FIELDS:
            raise FontError(f"line {self._number}: {key} is not a field of a font")
        self._fields[key] = value.strip()

    def _numeric(self, key: str) -> int:
        try:
            return int(self._fields[key])
        except ValueError:
            raise FontError(
                f"{key} is {self._fields[key]!r}, which is not a number"
            ) from None

    def _open(self, line: str) -> None:
        words = line.split()
        if len(words) < 4 or words[2] != "advance":
            raise FontError(
                f"line {self._number}: a glyph line reads "
                f"'glyph u+XXXX advance N', optionally 'bearing N', "
                f"then an optional note"
            )
        bearing = 0
        if len(words) > 5 and words[4] == "bearing":
            try:
                bearing = int(words[5])
            except ValueError:
                raise FontError(
                    f"line {self._number}: {words[5]!r} is not a bearing"
                ) from None
        self._bearing = bearing
        self._character = _code_point(words[1], self._number)
        if self._character in self._glyphs:
            raise FontError(
                f"line {self._number}: u+{ord(self._character):04x} a second time"
            )
        try:
            self._advance = int(words[3])
        except ValueError:
            raise FontError(
                f"line {self._number}: {words[3]!r} is not an advance"
            ) from None
        self._picture = []

    def _close(self) -> None:
        if self._character is not None:
            self._glyphs[self._character] = Glyph.of(
                self._picture, self._advance, self._bearing
            )
        self._character = None


def _code_point(word: str, number: int) -> str:
    if not word.lower().startswith("u+"):
        raise FontError(
            f"line {number}: {word!r} is not a code point, like u+0041"
        ) from None
    try:
        return chr(int(word[2:], 16))
    except ValueError:
        raise FontError(
            f"line {number}: {word!r} is not a code point, like u+0041"
        ) from None
