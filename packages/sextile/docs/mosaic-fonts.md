# Mosaic fonts

Large lettering drawn out of teletext block graphics — banners, title frames,
headings bigger than double height can give. **Built, and on the air: the format, one
converted face, the importer that converted it, the setting of a line and its
placement on a frame — and Stardot's title frame set in it. Not built: wrapping
in blocks, and a template for a page that is mostly banner.** The rest is written down as
requirements, so that the research behind them does not have to be done twice.

The layer beneath is built and described in [graphics.md](graphics.md): the
block grid, `blocks.block_runs`, and the `Composition` that works out where the
attributes go.

## What it is for

The first use is Stardot's title frame. It used to draw its name in
double-height text, which is two rows and one size:

```
 0 |
 1 |  ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮
 2 |
 3 |                 STARDOT          <- double height: rows 3 and 4
 4 |                 STARDOT             are the same text
 5 |
 6 |             V I E W D A T A
 7 |
 8 |  ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮
```

and now sets it in `boldbash`, three rows of blocks:

```
 0 |  ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮
 1 |
 2 |          ▛▀▘▀█▘▛▀▙▛▀▙▛▀▙▛▀▙▝█▘
 3 |          ▀▀▖ █ █▀▜█▀▘█ ██ █ █
 4 |          ▀▀  ▀ ▀ ▀▀  ▀▀ ▝▀▘  ▀
 5 |
 6 |             V I E W D A T A
 7 |
 8 |  ▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮▮
```

A mosaic font gives any height, any face, and the inverted treatment Ceefax
used — which is the look still to come.

## Constraints, measured

All of these are established; see [graphics.md](graphics.md) and
[viewdata-encoding.md](viewdata-encoding.md) for the evidence.

- A cell is **2 blocks across, 3 down**. A frame is 80×72 blocks, and **78
  across in practice** — a graphics colour attribute takes a cell on every row
  the picture spans, and attributes reset each row.
- The three block rows are **3, 4 and 3 scanlines** tall. Vertical spacing is
  inherently uneven and not worth correcting.
- **There is no alpha-black attribute.** Dark lettering is a lit field with
  letter-shaped *holes* — `block_runs(..., inverted=True)` — which costs one
  attribute per row and no background attributes at all.
- A picture that changes colour mid-row costs a cell for each change.
  `HOLD_GRAPHICS` makes that cell repeat the previous mosaic instead of
  blanking, so the gap becomes a duplicated column rather than a hole.

### Three ways to space, and all three are wanted

**Fixed** — every glyph advances by the same width. It is what the source fonts
were drawn for, it is what a column of figures needs, and it is the only one
whose arithmetic a page can do in its head.

**Proportional** — each glyph advances by its own width plus tracking. Needed,
not merely nicer, because of the measurement below.

**Kerned** — glyphs allowed to *overlap*, so the arm of a `T` may sit over the
tail of an `A`. At this resolution a block is a large fraction of a letter, and
the row is only 78 blocks wide, so a block recovered on each pair is worth
having.

Kerning needs no table: each glyph's left and right profiles are in the bitmap
already, so a pair can be closed up until the tightest row reaches the minimum
gap. A row where either letter is blank has no say, which is exactly where the
room is. Two things bound the fitting, and both stop it eating what it should
not: a pair may close up by no more than a set number of blocks, and **kerning
does not cross a blank glyph** — otherwise a narrow letter after a space slides
back into the space and the words run together.

In practice with `acorn` it is the one-block gap between letters that binds
rather than the limit, and `STARDOT` comes in three blocks narrower than
proportional setting gives.

Measured with the shipped `acorn` face, and reproducible with it:

| | blocks | cells, with the attribute | fits on a row? |
|---|---|---|---|
| `BBC CEEFAX`, fixed | 80 | 41 | **no** |
| `BBC CEEFAX`, proportional | 66 | 34 | yes |
| `BBC CEEFAX`, kerned | 64 | 33 | yes |
| `STARDOT`, fixed | 55 | 29 | yes |
| `STARDOT`, proportional | 48 | 25 | yes |
| `STARDOT`, kerned | 45 | 24 | yes |

Ten letters in the 78 blocks a row has is 7.8 blocks each. A fixed-width 8×8
face cannot draw the Ceefax banner — it is over by a cell — and a proportional
one draws it with five cells to spare.

**The advance belongs to the font, not the renderer.** Trimming at render time
would re-decide it on every frame, and would give a space no width at all. So a
font carries both: a fixed advance for the face, and an advance for each glyph.

## The format

A format of our own is warranted because none of the importable ones carries the
thing most needed — a per-glyph advance in blocks. Requirements:

- **Human-readable and diffable.** A vendored font is reviewed like any other
  file; glyphs written as the picture they are, as `yaff` does.
- **Per-glyph advance**, separate from the glyph's own width, so tracking and
  spaces are the font's business — and a fixed advance for the face beside it,
  because both ways of spacing are wanted.
- **Arbitrary height and width**, not tied to 8×8.
- **A name, and its provenance** — where it came from and on what terms — in the
  file, because a font's licence must travel with it.
- **No dependency to parse.** A reader of a hundred lines, like `robots.py`.

`viewdata/font.py`, and this is the whole of it:

```
name: Acorn
source: MDFS ArcNormal (mdfs.net/Apps/Font/Fonts1.zip)
terms: Free for public use
height: 8
fixed: 8

glyph u+0041 advance 7  A
..####..
.##..##.
...
```

`read_font` parses it and `write_font` writes it, which is how the converters
produce one; a round trip is tested, because that is what says a converter may
be trusted. Both need nothing but the standard library.

Two things about it are deliberate. **Glyphs are named by code point**, not by
the character, because a space, a `#` and a `.` would otherwise need quoting in
a file whose other lines are pictures made of `#` and `.`; the note after the
advance is for the reader and is ignored. And **a glyph with no picture is
blank but still advances**, which is what a space is.

An unknown field is an error rather than something ignored — provenance should
not be lost to a typo — and a picture whose height disagrees with the face's is
refused by code point.
## The faces shipped

Twenty-seven, by how many rows of the frame a line of them takes. `load_font`
reads one by name; the terms are in [NOTICE.md](../../../NOTICE.md) and in each
file's own header.

| rows | faces |
|---|---|
| 1 | `3x3-mono` |
| 2 | `arcade`, `pixelplace` |
| 3 | `acorn`, `boldbash`, `console`, `console-bold`, `lilliputsteps`, `pixeloperator8`, `pixeloperator8-bold`, `pixeloperator8-hb`, `publicpixel`, `roman`, `silkscreen`, `silkscreen-bold` |
| 4 | `grotesque`, `grotesque-bold`, `scientifica`, `scientifica-bold`, `scientifica-italic` |
| 5 | `pixeloperator`, `pixeloperator-bold`, `pixeloperator-hb`, `pixeloperator-sc`, `pixeloperator-sc-bold`, `pixeloperator-sc-hb` |
| 6 | `garland` |

The rows in that table are what the face needs at worst. **A line is trimmed to
its own ink**, top and bottom as well as on the right, so a line of capitals in
a face that leaves room for descenders comes out shorter — `garland` in four
rows rather than six, `pixeloperator` in three rather than five. Two lines that
must share a baseline ask for `trim=False`.

Every one of them sets `STARDOT` inside a row, from 25 blocks in `3x3-mono` to
75 in `garland`. `acorn` remains the default: it is the face a BBC Micro's own
ROM is drawn in.

`lettering.boxed` is the whole Ceefax effect in one call: a word in a field of
colour, in a box fitted round it. Lettering does not work out where the middle
is; it hands the composition an
`Align.CENTRE` and lets it. See [graphics.md](graphics.md): a picture is
centred on its ink to the nearest block, which is half a cell finer than
centring by cells and the difference between a banner that is centred and one
that is three quarters of a cell off.

To add another, see [tools/README.md](../../../tools/README.md) — including
what has to be read and recorded before a face is vendored.

## Source formats

### MDFS — `VDU 23` sequences

The intended default. **Ten bytes a glyph**: `23`, the character code, then eight
rows of eight bits, most significant bit leftmost. Verified across five files.

```python
raw = open("ArcNormal", "rb").read()
glyphs = {raw[i + 1]: raw[i + 2:i + 10] for i in range(0, len(raw), 10)}
rows = ["".join("#" if byte & (0x80 >> bit) else "." for bit in range(8))
        for byte in glyphs[ord("A")]]
```

| file | glyphs | codes |
|---|---|---|
| `ArcNormal` | 224 | 32–255 — the standard Acorn 8×8 face, and the one shipped |
| `Serif`, `Broadway`, … | 95 | 32–126 |
| `Arc7by8` | 96 | 32–127 |
| `Symbols` | — | 256 bytes, not a multiple of 10; something else |

**Codes 0x80–0x9f are dropped on conversion.** 0x20–0x7e are ASCII and
0xa0–0xff are Latin-1 — checked against ArcNormal's pound sign, e-acute,
A-diaeresis and one-half — but the range between belongs to no encoding
established here, and a wrong letter on a banner is worse than a missing one.
0x7f goes too: in these faces it is a solid block.

Archives: `mdfs.net/Apps/Font/Fonts1.zip` through `Fonts4.zip`, plus
`Font4px.zip`, `Font6px.zip`, `Font7px.zip` for narrower faces — which are worth
having, given the width arithmetic above. Character sets pictured at
`mdfs.net/Apps/Font/img/`.

### more-fonts — Lua tables

`github.com/michielp1807/more-fonts` collects pixel faces for ComputerCraft.
The format is written down nowhere, so it was read off the files and is written
down in `tools/more_fonts.py`: 256 glyphs, one character to a row of pixels,
six bits each biased by a space, least significant bit leftmost — so a face
wider than six pixels takes two characters to a row. Lua's long strings take a
level and these files use it, because a face with the right two pixels lit
contains `]]` in its data.

**Worth having for the metrics as much as the designs.** `startX` and
`lengthX` are the ink bounds of every glyph, so the bearing and the
proportional advance come out of the file rather than being derived.

Twenty-six of them are shipped. Their licences are not all the same one, and
the collection's own MIT covers its source rather than the faces: see
[NOTICE.md](../../../NOTICE.md).

### ZX Origins and BDF

`damieng.com/typography/zx-origins/` — 8×8, many legacy formats including a BBC
Micro one. **Not to be vendored**: the terms are *"freely available to be used in
games you create in exchange for a mention in the credits"*, which is a
permission rather than a licence. The importer is for pointing at your own
download.

**BDF** is the standard interchange format for proportional bitmap fonts of
arbitrary size — plain text, per-glyph `DWIDTH` and `BBX`, decades of tooling
and a large free corpus. Worth supporting if a new corpus appears; `monobit`
converts between it and some fifty others.

## What to build

Roughly in order, each committable on its own.

1. ~~**The format**, its reader, and one converted font.~~ Done. `acorn`, 191
   glyphs of ASCII and Latin-1, converted by `tools/mdfs_font.py`.
2. ~~**`Font`**, and the three spacings.~~ Done: `lettering.width` measures a
   line in blocks and `lettering.bitmap` sets it, `FIXED`, `PROPORTIONAL` or
   `KERNED`. A character the face has no glyph for is substituted, as
   transliteration does.
3. ~~**Rendering** — text to a bitmap, then `block_runs`, then `Composition`.~~
   Done: `lettering.cells` and `lettering.place`, which hands the composition
   an alignment rather than a column and lets it do the accounting. The inverted
   case takes a `margin`, because the field has to extend past the letters or
   they touch its edge.
4. **Wrapping** in blocks, reusing the balanced algorithm in `wrapping.py`
   (measure in blocks rather than cells; the last line is free).
5. **A template**, `Banner` or similar, on the `Template` base, so a page places
   large lettering the way it places a menu.
6. **The ZX Origins importer**, beside `tools/mdfs_font.py`. A font is
   converted once and the result vendored, so the framework carries no parser
   for a format read once in the life of a face.
7. ~~**Stardot's title frame** in it.~~ Done: `STARDOT` kerned in `boldbash`,
   yellow, on rows 2 to 4, with the rule moved to the top row so the banner has
   a blank row above and below it. Twenty-two cells of heavy strokes where
   double height gave two rows of ordinary letters.

## Decisions still open

- ~~**How many faces to ship.**~~ Settled: all of the ones whose terms allow
  it. Twenty-seven, three to seventeen blocks tall, 230K of text in total —
  small enough that choosing between them was costing more than keeping them.
- ~~**Where fonts live.**~~ Settled:
  `sextile/viewdata/fonts/`, shipped as package data, and
  `font.load_font("acorn")` reads one by name. An application with a face of
  its own reads it with `read_font` from wherever it keeps it; whether the
  library should be registrable is still open, and nothing needs it yet.
- **Whether the renderer picks a face by height.** A page asking for "a banner
  three rows tall" is a friendlier request than one naming a font. This wanted
  more than one face to be worth anything, and now there are twenty-seven of
  them, in five different heights of banner.
- **Colour within a banner.** One colour needs one attribute per row. More than
  one needs `HOLD_GRAPHICS` and an arithmetic that has not been worked out.

## Provenance

Every font vendored is recorded in [NOTICE.md](../../../NOTICE.md) with its
source and terms. Three sources have been checked and **none was what a summary
of it said** — the "MIT fonts" at `github.com/MichielP1807/more-fonts` are MIT
in their *source* only, each font carrying its own Creative Commons or SIL OFL
terms. Check before vendoring, not after.
