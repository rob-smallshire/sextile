"""Turn an MDFS `VDU 23` font file into a Sextile mosaic font.

MDFS (`mdfs.net/Apps/Font/`) publishes several dozen 8x8 faces for Acorn
machines as sequences of the `VDU 23` command that defines a character: ten
bytes each, `23`, the character code, then eight rows of eight bits with the
most significant bit leftmost. That was verified across five of the files
rather than taken from a description of the format.

A font is converted once and the result is vendored, which is why this lives
beside the framework rather than in it: `sextile` should not carry a parser for
a format that is read once in the life of each face.

    uv run python tools/mdfs_font.py ArcNormal Acorn > acorn.font

**Codes 0x80-0x9f are dropped.** 0x20-0x7e are ASCII and 0xa0-0xff are Latin-1
-- checked against ArcNormal's pound sign, e-acute, A-diaeresis and one-half --
but the range between belongs to no encoding this project has established, and
a wrong letter on a banner is worse than a missing one. 0x7f is dropped too:
in these faces it is a solid block rather than anything to set.
"""

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from sextile.viewdata.font import Font, Glyph, write_font

#: Ten bytes to a glyph, and the first of them says which command it is.
_RECORD: Final = 10
_VDU_DEFINE_CHARACTER: Final = 23
_ROWS: Final = 8
_COLUMNS: Final = 8

#: Blocks left between one letter and the next when setting proportionally.
_TRACKING: Final = 1

#: What a blank glyph advances by. Trimming a space to its ink would leave it
#: no width at all, so the width of a space is a decision made here, once.
_SPACE: Final = 3

_LIT: Final = "#"
_DARK: Final = "."


class MdfsError(ValueError):
    """A file that is not the `VDU 23` sequence it was taken for."""


def read_mdfs(data: bytes) -> dict[int, list[str]]:
    """The glyphs in an MDFS font file, as pictures, by character code."""
    if len(data) % _RECORD:
        raise MdfsError(
            f"{len(data)} bytes is not a whole number of {_RECORD}-byte glyphs"
        )
    glyphs = {}
    for start in range(0, len(data), _RECORD):
        record = data[start : start + _RECORD]
        if record[0] != _VDU_DEFINE_CHARACTER:
            raise MdfsError(
                f"the glyph at byte {start} begins {record[0]}, not "
                f"{_VDU_DEFINE_CHARACTER}"
            )
        glyphs[record[1]] = [
            "".join(
                _LIT if byte & (0x80 >> column) else _DARK for column in range(_COLUMNS)
            )
            for byte in record[2:]
        ]
    return glyphs


def wanted(code: int) -> bool:
    """Whether a character code means what its Unicode code point means."""
    return 0x20 <= code <= 0x7E or 0xA0 <= code <= 0xFF


def convert(
    glyphs: Mapping[int, Sequence[str]],
    *,
    name: str,
    source: str = "",
    terms: str = "",
    tracking: int = _TRACKING,
    space: int = _SPACE,
) -> Font:
    """A Sextile font from MDFS pictures, trimmed and given advances."""
    return Font(
        name=name,
        height=_ROWS,
        fixed=_COLUMNS,
        source=source,
        terms=terms,
        glyphs={
            chr(code): _glyph(glyphs[code], tracking, space)
            for code in sorted(glyphs)
            if wanted(code)
        },
    )


def _glyph(picture: Sequence[str], tracking: int, space: int) -> Glyph:
    lit = [column for column in range(_COLUMNS) if any(row[column] == _LIT for row in picture)]
    if not lit:
        return Glyph(bitmap=(), advance=space)
    left, right = lit[0], lit[-1]
    return Glyph.of(
        [row[left : right + 1] for row in picture],
        advance=right - left + 1 + tracking,
        bearing=left,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Turn one MDFS font file into a Sextile mosaic font.

    Args:
        argv: The arguments after the program name, or None to take them
            from `sys.argv`.

    Returns:
        The process exit status: nought where the conversion succeeded.
    """
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source_filepath", type=Path, help="an MDFS font file")
    parser.add_argument("name", help="what to call the face in the font file")
    parser.add_argument("--from", dest="source", default="", help="where it came from")
    parser.add_argument("--terms", default="", help="the terms it is available on")
    parser.add_argument("--tracking", type=int, default=_TRACKING)
    parser.add_argument("--space", type=int, default=_SPACE)
    arguments = parser.parse_args(argv)
    font = convert(
        read_mdfs(arguments.source_filepath.read_bytes()),
        name=arguments.name,
        source=arguments.source or arguments.source_filepath.name,
        terms=arguments.terms,
        tracking=arguments.tracking,
        space=arguments.space,
    )
    sys.stdout.write(write_font(font))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
