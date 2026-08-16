"""Turn a `more-fonts` Lua bitmap font into a Sextile mosaic font.

`github.com/michielp1807/more-fonts` collects a few dozen pixel faces for
ComputerCraft, each as a Lua table. The format is not written down anywhere, so
it was read off the files:

    {
        fontname = "Dogica",
        author = "Roberto Mocci",
        license = "SIL Open Font License, Version 1.1 ...",
        data = [[...]],          one character per row of pixels
        startX = [[...]],        where the ink begins, 1-based
        lengthX = [[...]],       how wide the ink is
        charW = 8, charH = 8,    the design width and height
    }

`data` holds 256 glyphs in order, each `charH` rows, each row a run of
characters biased by a space and carrying six bits with the least significant
bit leftmost -- so a face more than six pixels wide takes two characters to a
row. Lua's long strings take a level, `[=[ ... ]=]`, and these files use it,
because a face with the right two pixels lit contains `]]` in its data.

**These are worth importing for their metrics as much as their designs.**
`startX` and `lengthX` are the ink bounds of every glyph, so the bearing and
the proportional advance come out of the file rather than being guessed at.

**Every one of these fonts carries its own licence and they are not all the
same.** Some are CC0, most of the rest are the SIL Open Font License, and the
collection's own MIT licence covers its source and not the faces. The licence
and the author travel into the converted file, and are read before anything is
vendored.

    uv run python tools/more_fonts.py BoldBash --name Bash > boldbash.font

Only codes 32-126 are converted. There are 256 glyphs in each file, in an
encoding the collection does not state, and a wrong letter is worse than a
missing one.
"""

import argparse
import re
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from sextile.viewdata.font import Font, Glyph, write_font

#: Every file holds the whole of a byte's worth of glyphs, blanks included.
_GLYPHS: Final = 256

#: Codes that mean what their Unicode code point means. Above this the files
#: are in an encoding the collection does not state.
_FIRST: Final = 0x20
_LAST: Final = 0x7E

#: A row of pixels is packed six bits to a character, biased by a space.
_BITS: Final = 6
_BIAS: Final = 0x20

#: `startX` counts from one, as Lua does.
_ORIGIN: Final = 0x21

#: Blocks left between one letter and the next when setting proportionally.
_TRACKING: Final = 1

_LIT: Final = "#"
_DARK: Final = "."


class MoreFontsError(ValueError):
    """A file that is not one of these fonts, or is not the size it says."""


@dataclass(frozen=True)
class Face:
    """One of these files, read but not yet converted."""

    fontname: str
    author: str
    source: str
    license: str
    width: int
    height: int
    data: str
    start: str
    length: str

    def picture(self, code: int) -> list[str]:
        """The glyph as it is drawn, in the face's full design box."""
        per_row = len(self.data) // (_GLYPHS * self.height)
        at = code * self.height * per_row
        rows = []
        for row in range(self.height):
            packed = self.data[at + row * per_row : at + (row + 1) * per_row]
            bits = sum(
                (ord(character) - _BIAS) << (_BITS * index)
                for index, character in enumerate(packed)
            )
            rows.append(
                "".join(
                    _LIT if bits >> column & 1 else _DARK for column in range(self.width)
                )
            )
        return rows

    def bounds(self, code: int) -> tuple[int, int]:
        """Where the glyph's ink begins and how wide it is, in pixels."""
        length = ord(self.length[code]) - _BIAS
        return (ord(self.start[code]) - _ORIGIN if length else 0, length)


def parse(text: str) -> Face:
    """Read one of these files. Raises `MoreFontsError` on anything else."""
    numbers = {"charW": 0, "charH": 0}
    for key in numbers:
        found = re.search(rf"\b{key}\s*=\s*(\d+)", text)
        if found is None:
            raise MoreFontsError(f"no {key}: this is not one of these fonts")
        numbers[key] = int(found.group(1))
    strings = {
        match.group(1): match.group(3)
        #  Lua's long strings take a level, and these files use it.
        for match in re.finditer(r"(\w+)\s*=\s*\[(=*)\[(.*?)\]\2\]", text, re.S)
    }
    for key in ("data", "startX", "lengthX"):
        if key not in strings:
            raise MoreFontsError(f"no {key}: this is not one of these fonts")
    height, width = numbers["charH"], numbers["charW"]
    if len(strings["data"]) % (_GLYPHS * height):
        raise MoreFontsError(
            f"{len(strings['data'])} characters of data is not {_GLYPHS} glyphs "
            f"of {height} rows"
        )
    for key in ("startX", "lengthX"):
        if len(strings[key]) != _GLYPHS:
            raise MoreFontsError(f"{key} has {len(strings[key])} of {_GLYPHS} glyphs")
    return Face(
        fontname=_quoted(text, "fontname"),
        author=_quoted(text, "author"),
        source=_quoted(text, "source"),
        license=_quoted(text, "license"),
        width=width,
        height=height,
        data=strings["data"],
        start=strings["startX"],
        length=strings["lengthX"],
    )


def _quoted(text: str, key: str) -> str:
    found = re.search(rf'\b{key}\s*=\s*"(.*?)",', text, re.S)
    return found.group(1) if found else ""


def convert(
    face: Face,
    *,
    name: str | None = None,
    tracking: int = _TRACKING,
    space: int | None = None,
    trim: bool = True,
) -> Font:
    """A Sextile font from one of these faces, trimmed and given advances.

    `trim` drops the rows that are blank in every glyph. Several of these are
    drawn in a box taller than their letters, and three blank block-rows is a
    whole row of the screen, which a frame of twenty-four cannot spare.
    """
    pictures = {
        code: _cropped(face.picture(code), *face.bounds(code))
        for code in range(_FIRST, _LAST + 1)
    }
    keep = _rows_to_keep(list(pictures.values()), face.height) if trim else range(face.height)
    gap = space if space is not None else max(2, face.width // 3)
    return Font(
        name=name or face.fontname,
        height=len(keep),
        fixed=face.width,
        source=f"{face.fontname} by {face.author}, {face.source}".rstrip(", "),
        terms=face.license,
        glyphs={
            chr(code): _glyph(picture, face.bounds(code), keep, tracking, gap)
            for code, picture in pictures.items()
        },
    )


def _cropped(picture: Sequence[str], start: int, length: int) -> list[str]:
    return [row[start : start + length] for row in picture] if length else []


def _rows_to_keep(pictures: Iterable[Sequence[str]], height: int) -> list[int]:
    """The rows any glyph puts ink on, which all glyphs then keep.

    Any glyph's, and not each glyph's own: trimming a glyph vertically would
    stop the letters sitting on the same line as each other.
    """
    inked = {
        row
        for picture in pictures
        for row, line in enumerate(picture)
        if _LIT in line
    }
    return [row for row in range(height) if row in inked] or list(range(height))


def _glyph(
    picture: Sequence[str],
    bounds: tuple[int, int],
    keep: Sequence[int],
    tracking: int,
    space: int,
) -> Glyph:
    start, length = bounds
    if not length:
        return Glyph(bitmap=(), advance=space)
    return Glyph.of(
        [picture[row] for row in keep],
        advance=length + tracking,
        bearing=start,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Turn one `more-fonts` Lua font into a Sextile mosaic font.

    Args:
        argv: The arguments after the program name, or None to take them
            from `sys.argv`.

    Returns:
        The process exit status: nought where the conversion succeeded.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source_filepath", type=Path, help="a more-fonts Lua font")
    parser.add_argument("--name", default=None, help="what to call the converted face")
    parser.add_argument("--tracking", type=int, default=_TRACKING)
    parser.add_argument("--space", type=int, default=None)
    parser.add_argument(
        "--keep-blank-rows",
        action="store_true",
        help="keep rows no glyph puts ink on, rather than dropping them",
    )
    arguments = parser.parse_args(argv)
    font = convert(
        parse(arguments.source_filepath.read_text(encoding="utf-8", errors="replace")),
        name=arguments.name,
        tracking=arguments.tracking,
        space=arguments.space,
        trim=not arguments.keep_blank_rows,
    )
    sys.stdout.write(write_font(font))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
