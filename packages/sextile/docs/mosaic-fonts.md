# Mosaic fonts: requirements

Large lettering drawn out of teletext block graphics — banners, title frames,
headings bigger than double height can give. **None of this is built.** What
follows is what is known before starting, so that the research behind it does
not have to be done twice.

The layer beneath is built and described in [graphics.md](graphics.md): the
block grid, `blocks.block_runs`, and the `Composition` that works out where the
attributes go.

## What it is for

The immediate use is Stardot's title frame, which today draws its name in
double-height text:

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

Double height is two rows and one size. A mosaic font gives any height, any
face, and the inverted treatment Ceefax used — which is the look worth having.

Rows 2–7 are free on that frame if the rules move, so a banner of three or four
cell-rows fits without redesigning the page.

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

### Proportional spacing is required, not optional

Measured with real ArcNormal glyphs:

| | cells | fits in 39? |
|---|---|---|
| `BBC CEEFAX`, fixed 8 blocks a glyph | 47 | no |
| `BBC CEEFAX`, trimmed to each glyph | 35 | yes |
| `STARDOT`, fixed 8 blocks a glyph | 56 blocks ≈ 28 | yes |

Ten letters in 78 blocks is 7.8 blocks each. A fixed-width 8×8 face cannot draw
the Ceefax banner and a proportional one draws it comfortably.

**The advance belongs to the font, not the renderer.** Trimming at render time
would re-decide it on every frame, and would give a space no width at all.

## The format

A format of our own is warranted because none of the importable ones carries the
thing most needed — a per-glyph advance in blocks. Requirements:

- **Human-readable and diffable.** A vendored font is reviewed like any other
  file; glyphs written as the picture they are, as `yaff` does.
- **Per-glyph advance**, separate from the glyph's own width, so tracking and
  spaces are the font's business.
- **Arbitrary height and width**, not tied to 8×8.
- **A name, and its provenance** — where it came from and on what terms — in the
  file, because a font's licence must travel with it.
- **No dependency to parse.** A reader of a hundred lines, like `robots.py`.

Sketch, not yet decided:

```
name: Acorn
from: MDFS ArcNormal, mdfs.net/Apps/Font/Fonts1.zip
terms: public use, per its author J.G.Harston
height: 8

A  advance 7
   ..####..
   .##..##.
   ...
```

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
| `ArcNormal` | 224 | 32–255 — the standard Acorn 8×8 face, and the intended default |
| `Serif`, `Broadway`, … | 95 | 32–126 |
| `Arc7by8` | 96 | 32–127 |
| `Symbols` | — | 256 bytes, not a multiple of 10; something else |

Archives: `mdfs.net/Apps/Font/Fonts1.zip` through `Fonts4.zip`, plus
`Font4px.zip`, `Font6px.zip`, `Font7px.zip` for narrower faces — which are worth
having, given the width arithmetic above. Character sets pictured at
`mdfs.net/Apps/Font/img/`.

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

1. **The format**, its reader, and one converted font. A reader and a golden
   file are testable without any rendering.
2. **`Font`** — glyphs by character, advance, height; `measure(text)` in blocks;
   a missing glyph substituted rather than raising, as transliteration does.
3. **Rendering** — text to a bitmap, then `block_runs`, then `Composition`. The
   inverted case needs the *field*, not the glyphs, so the renderer decides the
   band's extent.
4. **Wrapping** in blocks, reusing the balanced algorithm in `wrapping.py`
   (measure in blocks rather than cells; the last line is free).
5. **A template**, `Banner` or similar, on the `Template` base, so a page places
   large lettering the way it places a menu.
6. **The converters**, as scripts beside the framework rather than inside it: a
   font is converted once and vendored, and the framework should not carry a
   parser for a format nobody will use again. See "Writing an importer" in
   [graphics.md](graphics.md).
7. **Stardot's title frame** in it, which is the point of the exercise.

## Decisions still open

- **Where fonts live.** A `fonts/` directory in the framework package, shipped
  as package data, is the obvious answer; whether applications can register
  their own from a path or must import them is not decided.
- **How many faces to ship.** One default and no more, probably: each is
  provenance to track, and an application wanting another can convert it.
- **Whether the renderer picks a face by height.** A page asking for "a banner
  three cell-rows tall" is a friendlier request than one naming a font, but it
  needs more than one face to be worth anything.
- **Colour within a banner.** One colour needs one attribute per row. More than
  one needs `HOLD_GRAPHICS` and an arithmetic that has not been worked out.

## Provenance

Every font vendored is recorded in [NOTICE.md](../../../NOTICE.md) with its
source and terms. Three sources have been checked and **none was what a summary
of it said** — the "MIT fonts" at `github.com/MichielP1807/more-fonts` are MIT
in their *source* only, each font carrying its own Creative Commons or SIL OFL
terms. Check before vendoring, not after.
