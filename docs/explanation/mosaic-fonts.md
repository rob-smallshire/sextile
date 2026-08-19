# Mosaic fonts

Explanation: the measured constraints that shape outsized mosaic lettering, and
why a font format of Sextile's own is warranted. The recipes that apply this are
{doc}`../how-to/large-lettering` and {doc}`../how-to/boxed-banners`; the
catalogue of faces is {doc}`../reference/fonts`. The API is
{py:mod}`sextile.viewdata.lettering` and {py:mod}`sextile.viewdata.font`.

## Constraints, measured

- A cell is 2 blocks across and 3 down; a frame is 80 × 72 blocks, 78 across in
  practice, because a graphics attribute takes a cell on every row a picture
  spans. See {doc}`graphics` and {doc}`../reference/viewdata-encoding`.
- The three block rows are 3, 4 and 3 scanlines tall, so vertical spacing is
  inherently uneven and not worth correcting.
- There is no alpha-black attribute, so dark lettering is a lit field with
  letter-shaped holes — `block_runs(..., inverted=True)` — costing one attribute
  a row and no background attributes at all.

Proportional and kerned spacing are required, not merely nicer: the row is only
78 blocks wide and a block is a large fraction of a letter at this resolution, so
a block recovered on each glyph, or each leaning pair, is worth having. Set
kerned, `AVATAR` takes 16 cells against 18 proportional and 23 fixed, because its
`A`/`V` and `A`/`T` pairs overlap.

## A font format of its own

`font.read_font`/`write_font` read and write a human-readable, dependency-free
format, because none of the importable bitmap formats carries the thing most
needed — a per-glyph advance in blocks — and a vendored font must be reviewed
like any other file. Glyphs are named by code point, not by the character, so a
space, `#` and `.` need no quoting in a file whose picture rows are drawn in `#`
and `.`. The advance belongs to the font, not the renderer: trimming at render
time would re-decide it on every frame and give a space no width at all, so a
font carries a fixed advance for the face and an advance for each glyph.
