# Graphics: blocks, composition, and large lettering

Everything a teletext frame can draw that is not a letter, and the machinery for
placing it. Three of the four layers exist; the fourth — the font renderer —
is designed and not yet built, and is marked as such below.

## The block grid

A mosaic character is a 2×3 grid of blocks, so a frame of 40×24 cells is
**80×72 blocks**. In practice it is **78 across**: a graphics colour attribute
occupies a cell, attributes reset at the start of every row, so a picture pays
one cell on each row it spans.

The bit layout is read from Beebium's `TeletextFontInit::get_graphics_row`
rather than from memory of the specification:

```
bit 0  bit 1        five blocks in bits 0-4, the sixth in bit 6,
bit 2  bit 3        because bit 5 is spent saying "this is a mosaic
bit 4  bit 6        and not a control"
```

so the codes land in `0x20`–`0x3F` and `0x60`–`0x7F`, and all six blocks lit is
`0x7F` — the character the rules have always been made of.

`charset.mosaic_code(pattern)` goes one way and `charset.mosaic_pattern(code)`
the other. `ansi.sextant` maps a pattern to the Unicode block-sextant character,
so `--form ansi` shows graphics as the SAA5050 would draw them; it shares the
same bit order, and a test asserts the two agree.

**The three block rows are not equal.** The emulation puts them at scanlines
0–2, 3–6 and 7–9, so the middle band is a scanline taller than the other two. A
picture drawn on the block grid has slightly uneven vertical spacing, inherently.
Every teletext image has this; it is not worth trying to correct.

## Pictures into blocks

`viewdata/blocks.py`. A bitmap in, six-bit cell patterns out, padded to whole
cells:

```python
from sextile.viewdata.blocks import block_runs, read_bitmap

runs = block_runs(read_bitmap([
    "..##..",
    ".####.",
    "##..##",
]))                                  # -> [[patterns], ...] one list per cell row
```

### Inverted, and why it lives here

**The SAA5050 has no alpha-black attribute.** The colour codes run `0x01`–`0x07`
and there is no way to ask for a black foreground. So the Ceefax banner of black
`BBC CEEFAX` on cyan is not black lettering at all: it is a **solid cyan field
with letter-shaped holes**, the unlit blocks showing the default black
background through.

That is cheaper than the coloured background it appears to be — one graphics
attribute on each row, and no background attributes whatever.

```python
block_runs(bitmap, inverted=True)
```

It belongs in this module rather than in whatever draws the letters, because
inverting a glyph on its own would leave the space *around* it black. What has
to be inverted is the whole field the picture occupies, **padding included**, or
the field has a ragged edge exactly where a banner must not have one.

## Composition

`viewdata/composition.py`. `Canvas` writes a row left to right and inserts an
attribute whenever the state changes, which is right for a page built a phrase
at a time. It is the wrong shape for placing things *at* positions: each call
re-establishes the state it wants without knowing what the next one will want,
and it cannot say whether a row fits until it has half drawn it.

```python
from sextile.viewdata.composition import Composition, Style

layout = (
    Composition()
    .blocks(1, 1, patterns, Colour.CYAN)
    .text(8, 4, "STARDOT", style=Style(colour=Colour.WHITE, background=Colour.BLUE))
)
if layout.fits():
    layout.draw(canvas)
```

Three things that buys.

**It says whether the layout is possible**, naming the row, the column and the
arithmetic, before a cell is written — and draws nothing at all if any row
fails, so a bad layout does not leave half a frame on somebody's screen:

```
row 0: the run at column 6 needs 3 attribute cell(s) before it and only 2 are free
```

**Two runs in one style cost one attribute, not two.** Block runs at either end
of a row enter graphics once, because the composition can see there is no text
between them and so never returns to alpha. This is the case a sequential writer
cannot see, and it is what a mosaic banner is made of.

**It is exact rather than clever**, which is worth saying because it looks like
an optimisation problem and is not. An attribute displays as a blank, and a
blank in graphics is the no-blocks mosaic — visually identical. So an attribute
may sit anywhere in the gap before the run it affects, and the only question at
each gap is whether the attributes fit in it. A left-to-right pass is therefore
optimal and there is nothing to search. Placement becomes a search only if runs
are free to *move*, which is a different feature and not this one.

**Rows are independent.** Every row begins white, in alpha, with contiguous
graphics selected, whatever the row above ended in. So a frame composition is a
row composition done twenty-four times and nothing reasons across rows.

### What a style costs

`Style` carries every attribute the hardware has, because the transitions are
not uniform — which is the whole argument for handing a compositor a style
rather than writing controls by hand.

| Change | Cells | Note |
|---|---|---|
| foreground colour | 1 | also chooses the character set |
| entering or leaving graphics | 1 | the colour attribute does both |
| contiguous ↔ separated | 1 | chooses the *set*; a colour attribute enters it |
| flash / steady | 1 | |
| double height / normal | 1 | and takes the row below — see below |
| hold / release graphics | 1 | |
| **a background** | **3** | choose the colour, promote it, choose the foreground again |
| a background matching the foreground | 2 | nothing to change back to |
| back to black | 1 | `BLACK_BACKGROUND` |
| conceal | 1 | **and cannot be undone** |

The background is three cells because the hardware has no "set background", only
`NEW_BACKGROUND`, which makes the *current foreground* the background. That is
the dance `command_line.py` has been doing by hand since the beginning.

`CONCEAL` has no counterpart: the hardware clears it at the end of a row and
nowhere else, so a composition that asks to turn it off is refused rather than
drawn wrongly.

**Double height places its run on the row below as well**, because that is how
the SAA5050 draws the bottom halves — the lower row is drawn as the bottom of
the glyphs only if it carries the attribute *and* the same text. Leaving that
row blank is the mistake everyone makes; see
[viewdata-encoding.md](viewdata-encoding.md).

### Which to use

`Canvas`/`RowWriter` for a page written left to right — a heading, a menu line,
prose. `Composition` for a page placed at coordinates, for anything mixing text
and blocks on one row, and for anything whose feasibility is in doubt.
`RowWriter.mosaic` exists for the sequential case and pays the same costs, one
run at a time.

## The font renderer — designed, not built

What follows is the plan, recorded so the findings behind it are not lost. None
of it is written yet.

### Why a format of our own

The corpus worth importing is in several formats and none of them suits a 2×3
block grid:

- **MDFS** (`mdfs.net/Apps/Font/`) — streams of `VDU 23,ch,r1..r8`: ten bytes a
  glyph, the standard Acorn user-defined-character command. Verified across five
  files. `ArcNormal` is 224 glyphs covering 32–255; most others are 95 or 96
  covering printable ASCII. This is where the intended default comes from.
- **ZX Origins** (`damieng.com/typography/zx-origins/`) — 8×8, distributed in a
  dozen legacy formats including a BBC Micro one.
- **BDF** — the standard interchange format for proportional bitmap fonts of
  arbitrary size: plain text, per-glyph `DWIDTH` and `BBX`, decades of tooling.
  The right *import* format, and the one to reach for if a new corpus appears.

What none of them carries is the thing this renderer most needs: a per-glyph
**advance** measured in blocks. Hence a format of our own, human-readable so
that a vendored font diffs and reviews, with glyphs written as the picture they
are.

### Proportional spacing is not a nicety

At eight blocks a glyph, `BBC CEEFAX` is 47 cells and there are **39**. Trimmed
to each glyph's own width it is 35 and fits comfortably. Ten letters in 78
blocks is 7.8 blocks each, so a fixed-width 8×8 face cannot draw that banner and
a proportional one can. The advance belongs to the font — trimming at render
time would mean re-deciding it on every frame.

### Writing an importer

A converter has one job: produce our format from somebody else's. The shape:

1. **Read the glyphs.** For a fixed-width format this is arithmetic — MDFS is
   `data[i+1]` for the character code and `data[i+2:i+10]` for eight rows of
   eight bits, most significant bit leftmost.
2. **Turn each row of bits into blocks**, most significant bit leftmost, which
   is what `read_bitmap` expects.
3. **Decide the advance.** Trim leading and trailing blank columns and add the
   tracking the font wants; a space has no lit columns and needs its width
   stated rather than measured.
4. **Write our format**, one glyph per stanza, and record where the font came
   from and on what terms.

Converters live beside the framework as scripts rather than inside it: a font is
converted once and vendored, and the framework should not carry a parser for a
format nobody will use again.

### Provenance

Fonts are somebody's work and their terms differ. Record every one in
[NOTICE.md](../../../NOTICE.md) with its source and licence.

Two already checked, and neither is what a summary suggested:

- **MDFS** — the site states no licence; the author is J.G.Harston. Confirmed by
  the maintainer of this repository as available for public use.
- **ZX Origins** — *"freely available to be used in games you create in exchange
  for a mention in the credits section"*. A permission rather than a licence, no
  SPDX identifier, and phrased around games. Not vendored here; the importer is
  for pointing at your own download.
- **More Fonts** (`github.com/MichielP1807/more-fonts`) — the **source** is MIT;
  the **fonts are not**, each carrying its own terms, usually Creative Commons
  or SIL OFL. Worth stating because the repository reads as MIT at a glance.
