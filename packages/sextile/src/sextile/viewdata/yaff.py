"""Reading a YAFF bitmap font into a mosaic `Font`.

YAFF is the text bitmap-font format of the `monobit` toolkit, and the form the
`hoard-of-bitfonts` collection ships in (github.com/robhagemans/hoard-of-bitfonts).
A YAFF pixel is one mosaic block, so a YAFF glyph is a `Font` glyph already; this
reads the subset a `Font` needs and drops the rest, so a service can set large
lettering in a face it did not have to vendor.

What is read: `character-cell` glyphs labelled by character -- a unicode label
(``u+0041``) or a quoted character (``'A'``) -- their `.`/`@` bitmaps, and the
`cell-size`. A glyph's blank side columns are trimmed, the left becoming its
bearing and the right its advance, so a loaded face sets proportionally like a
native one; `fixed` keeps the cell width for anyone setting fixed. `copyright`,
`notice` and `author` become the font's `terms` and a `source-*` its `source`,
so a loaded font's licence travels with it.

A YAFF glyph also carries a *device* codepoint label (``0x23``) which is the
font's own character set, not ASCII -- ``0x23`` is `£` in the SAA5050 set -- so a
glyph is keyed by its unicode or character label and the bare codepoint is
ignored.

What is ignored: vertical metrics, kerning tables, `shift-up`, tag and
multi-codepoint labels, and metadata beyond the licence. Greyscale (`levels`
above two) and a glyph whose height is not the cell's are refused with
`FontError` rather than read wrongly.
"""

from collections.abc import Sequence

from sextile.viewdata.font import Font, FontError, Glyph

__all__ = ["read_yaff"]

_INK = "@"
_PAPER = "."
_EMPTY = "-"


def read_yaff(text: str) -> Font:
    """Parse a YAFF font into a `Font`. Raises `FontError`, naming what is wrong.

    Args:
        text: The contents of a YAFF file.

    Returns:
        A `Font` of the character-cell glyphs the file labels by character.

    Example:
        >>> from pathlib import Path
        >>> font = read_yaff(Path("saa5050-uk.yaff").read_text("utf-8"))  # doctest: +SKIP
    """
    return _Reader(text).read()


def _key(raw: str) -> str:
    """A property key, lowercased with dashes and underscores made the same."""
    return raw.strip().lower().replace("_", "-")


def _is_bitmap(line: str) -> bool:
    body = line.strip()
    return bool(body) and (set(body) <= {_INK, _PAPER} or body == _EMPTY)


def _character(label: str) -> str | None:
    """The single character a label names, or None for one that is not kept.

    A ``u+XXXX`` or quoted label of one character is kept; a bare codepoint, a
    tag, or a label of several code points is not.
    """
    label = label.strip()
    if label.lower().startswith("u+"):
        points = [part.strip() for part in label.split(",")]
        if len(points) != 1:
            return None
        try:
            return chr(int(points[0][2:], 16))
        except ValueError:
            return None
    if len(label) >= 2 and label[0] == label[-1] == "'":
        inner = label[1:-1]
        return inner if len(inner) == 1 else None
    return None


class _Reader:
    """A YAFF file, read line by line into a `Font`."""

    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()
        self._globals: dict[str, str] = {}
        self._glyphs: dict[str, Glyph] = {}
        self._index = 0

    def read(self) -> Font:
        self._header()
        self._body()
        levels = self._globals.get("levels")
        if levels is not None and levels.strip() not in {"", "2"}:
            raise FontError(f"{levels!r} levels is greyscale, which has no mosaic")
        if not self._glyphs:
            raise FontError("the font has no glyph labelled by a character")
        cell = self._cell_size()
        height = cell[1] if cell else self._glyph_height()
        for character, glyph in self._glyphs.items():
            if glyph.bitmap and glyph.height != height:
                raise FontError(
                    f"u+{ord(character):04x} is {glyph.height} rows tall, "
                    f"and the cell is {height}"
                )
        return Font(
            name=self._globals.get("name") or self._globals.get("family") or "unnamed",
            height=height,
            fixed=cell[0] if cell else self._glyph_width(),
            glyphs=self._glyphs,
            source=self._source(),
            terms=self._terms(),
        )

    def _header(self) -> None:
        """Read the global ``key: value`` properties up to the first glyph."""
        while self._index < len(self._lines):
            line = self._lines[self._index]
            if not line.strip() or line.startswith("#"):
                self._index += 1
                continue
            if line[0].isspace() or _is_label(line):
                return
            key, sep, value = line.partition(":")
            if not sep:
                return
            self._globals[_key(key)] = value.strip()
            self._index += 1

    def _body(self) -> None:
        """Read the glyph blocks: labels, a bitmap, and per-glyph lines ignored."""
        while self._index < len(self._lines):
            line = self._lines[self._index]
            if not line.strip() or line.startswith("#"):
                self._index += 1
                continue
            if not _is_label(line):
                #  A per-glyph property line after a bitmap, or anything else at
                #  this depth: not part of the subset, stepped over.
                self._index += 1
                continue
            self._glyph_block()

    def _glyph_block(self) -> None:
        labels: list[str] = []
        while self._index < len(self._lines) and _is_label(self._lines[self._index]):
            labels.append(self._lines[self._index].rstrip()[:-1])
            self._index += 1
        picture: list[str] = []
        while self._index < len(self._lines) and _is_bitmap(self._lines[self._index]):
            picture.append(self._lines[self._index].strip())
            self._index += 1
        characters = {c for label in labels if (c := _character(label)) is not None}
        if not characters:
            return
        glyph = _glyph(picture)
        for character in characters:
            if character not in self._glyphs:
                self._glyphs[character] = glyph

    def _cell_size(self) -> tuple[int, int] | None:
        raw = self._globals.get("cell-size")
        if not raw or "x" not in raw:
            return None
        across, _, down = raw.partition("x")
        try:
            return int(across), int(down)
        except ValueError:
            return None

    def _glyph_height(self) -> int:
        return max((glyph.height for glyph in self._glyphs.values() if glyph.bitmap), default=0)

    def _glyph_width(self) -> int:
        return max((glyph.width for glyph in self._glyphs.values()), default=0)

    def _source(self) -> str:
        for key in ("source-url", "source-name", "source-path"):
            if self._globals.get(key):
                return self._globals[key]
        return ""

    def _terms(self) -> str:
        keys = ("copyright", "author", "notice")
        return ", ".join(self._globals[key] for key in keys if self._globals.get(key))


def _is_label(line: str) -> bool:
    """Whether a line names a glyph: unindented, ending in a colon, a label form."""
    if not line or line[0].isspace() or not line.rstrip().endswith(":"):
        return False
    head = line.rstrip()[:-1].strip()
    return bool(head) and (head[0].isdigit() or head.lower().startswith("u+") or head[0] in "'\"")


def _glyph(picture: Sequence[str]) -> Glyph:
    """A `Glyph` from a cell bitmap, trimmed of its blank side columns.

    The left blanks become the bearing and the right blanks the gap after the
    letter, so the advance carries the cell's own spacing into proportional
    setting. A bitmap that is all paper is a space of the cell's width.
    """
    rows = [row for row in picture if row != _EMPTY]
    width = max((len(row) for row in rows), default=0)
    columns = [
        any(index < len(row) and row[index] == _INK for row in rows) for index in range(width)
    ]
    if not any(columns):
        return Glyph(bitmap=(), advance=width)
    left = columns.index(True)
    right = width - 1 - columns[::-1].index(True)
    trimmed = [row[left : right + 1].replace(_INK, "#").replace(_PAPER, ".") for row in rows]
    return Glyph.of(trimmed, advance=width - (width - 1 - right), bearing=left)
