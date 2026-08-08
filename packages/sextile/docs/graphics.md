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

**Centring is by the block.** `drawing.centre` gives the column an item of a
given width starts at, left-biased where it cannot be exact and always the same
way, so text, rules and lettering agree where the middle of a frame is. Blocks
go one better: `lettering.place` centres to the nearest block and takes a blank
block before the run where that is nearer, since a blank block and an attribute
cell look the same on the screen.

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

## Large lettering

Not built. The requirements, the source formats and the measurements behind
them are in [mosaic-fonts.md](mosaic-fonts.md) — including why a format of our
own is warranted, and why proportional spacing is required rather than merely
nicer.
