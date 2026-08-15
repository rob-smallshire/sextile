# Graphics: blocks, composition, and large lettering

Everything a teletext frame can draw that is not a letter, and the machinery for
placing it. All four layers are built, up to and including the font renderer
that sets outsized lettering from a mosaic font.

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

### An icon is written as the picture it is

Six-bit patterns typed as numbers are write-only, and a picture drawn in a
comment beside them is a copy that goes stale. So a small picture — an arrow, a
symbol, anything the character set has not got — is drawn in the source:

```python
ARROW = icon("""
       #
        #
    ######
        #
       #
""")

layout.picture(4, Align.CENTRE, ARROW.cells(), Colour.CYAN)
```

The blank lines at either end go, and so does the indentation the source needed
— the common part of it, so what one row is drawn further along than another
survives. Anything that is not `#` is a block that is off, so it reads drawn in
dots or in spaces.

`turned()` gives a quarter turn anticlockwise, which is how four arrows are one
arrow; `cells(inverted=True)` gives the Ceefax field. `across`/`down` are its
blocks and `cells_across`/`rows` what it costs a frame.

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

**It reports whether the layout is possible**, naming the row, the column and
the arithmetic, before a cell is written, and draws nothing at all if any row
fails, so a bad layout does not leave half a frame on somebody's screen:

```
row 0: the run at column 6 needs 3 attribute cell(s) before it and only 2 are free
```

**Two runs in one style cost one attribute, not two.** Block runs at either end
of a row enter graphics once, because the composition detects there is no text
between them and does not return to alpha. A sequential writer cannot detect
this case, and it is what a mosaic banner is made of.

**It is exact rather than clever**, which is worth saying because it looks like
an optimisation problem and is not. An attribute displays as a blank, and a
blank in graphics is the no-blocks mosaic — visually identical. So an attribute
may sit anywhere in the gap before the run it affects, and the only question at
each gap is whether the attributes fit in it. A left-to-right pass is therefore
optimal and there is nothing to search. Placement becomes a search only if runs
are free to *move*, which is a different feature and not this one.

**It places things by alignment.** Give `Align.CENTRE` instead of a column and
the composition computes where the middle is. It must, because what a style
costs in cells decides whether the middle is reachable at all. Text, rules and
lettering each used to compute that separately and came out a cell and a half
apart on the same frame.

```python
Composition().text(6, Align.CENTRE, "V I E W D A T A", Colour.CYAN)
```

`picture` places several rows of blocks as one thing, and centres them on their
**ink** rather than on the cells they occupy — to the nearest block, taking a
blank block before the run where that is nearer, since a blank block and an
attribute cell look the same on the screen. As one thing because a picture
centred a row at a time would have each row measure its own ink, and it would
shear.

**Rows are independent.** Every row begins white, in alpha, with contiguous
graphics selected, whatever the row above ended in. So a frame composition is a
row composition done twenty-four times, and no state carries across rows.

### Panels: a coloured box with things on it

The Ceefax pages this was built for put a word of mosaic lettering in a
coloured box — cyan on blue, red on yellow, blue on green, four boxes down the
right of a frame with plain text beside them.

```python
layout = Composition()
box = layout.panel(5, 19, width=21, colour=Colour.BLUE, rows=3)
lettering.place(layout, 5, "NEWS", face, Colour.CYAN, within=box)
```

**A background belongs to the field, not to what is written on it.** It lasts
to the end of the row unless something stops it, and it costs cells that
whatever is written on it would otherwise have to account for. So it is declared
once, and a run drawn `within` it inherits it; a run that turned the background
off inside a box would leave a black hole in it.

What the composition works out, and a caller therefore need not:

- **where the box begins.** The background is set *at* its attribute cell, so
  that cell is already coloured and is the box's first; the cell before it,
  where the colour is chosen, is not, and is unavoidably black. See
  [viewdata-encoding.md](viewdata-encoding.md).
- **where it ends** — `BLACK_BACKGROUND` on the cell after its last, unless it
  reaches the end of the row, where the row ending does the job.
- **what a run on it costs**: one cell for its own colour, rather than the
  three a background would cost from black.
- **where a run on it goes**: `Align.CENTRE` with `within=box` centres in the
  box rather than on the frame, and refuses what will not fit in it.

### Down as well as along

`picture` takes an alignment for its row too, and centres to the **block** in
that direction as well — a cell is three blocks deep, so a line of lettering
seven blocks tall sits in a three-row box with a block above it and a block
below rather than two blocks under it. `blocks.lowered` is the vertical
counterpart of `blocks.shifted`.

### A box that fits itself round its letters

```python
box = lettering.boxed(layout, 5, "NEWS", face, Colour.CYAN, Colour.BLUE, padding=2)
```

Fitted where the letters can be measured, rather than by a caller counting
them — who would then also have to know that a panel's own first cell goes on
the attribute that colours it. The letters are centred in the box both ways,
and the box is returned, so more can go in it.

A box taller than what goes in it grows upwards as well as down, so that asking
for one at row 8 leaves the letters near row 8. A box **shorter** than its
letters is refused, because it is not a box — see below.

### A stripe behind lettering is two things, not one

A band through the middle of a word — a row of colour where the word is three
rows tall — is a panel and some lettering, drawn separately:

```python
lettering.place(layout, 6, word, face, Colour.YELLOW)
layout.panel(7, colour=Colour.BLUE, around=range(6, 9), padding=3)
```

Neither knows about the other. The stripe is **fitted to what is already on
those rows**, so it needs no width and no column; the row they share comes out
coloured because the composition detects that it is — the run on that row is
covered by the panel and takes its background, while the runs above and below
are not and do not. No stripe had to be declared separately.

Fitted to the **ink** rather than to the cells the runs occupy: a picture
centred to the block often begins with a blank half-cell, and a stripe measured
from the run rather than from what is lit comes out a cell longer on one side
than the other. It is still widened to cover the runs whatever the padding,
because a panel stopping short of a run it is behind would leave that run
turning the background off in the middle of the stripe.

`lettering.cells_for` sizes a panel without the word being drawn first — the
companion of `rows_for` — for the cases where the order has to be the other
way about.

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

## A worked example: the compass

`sextile/compass.py` draws the four movement keys as arrows, and is a short
read for how these layers go together: **one** arrow drawn as an `icon`, three
`turned()` from it, and a `Composition` to place them among the letters that
label them.

It is also why the block grid earns its place. The G0 character set has `←`,
`→` and `↑` and no down arrow, so a compass drawn in letters is impossible.

Each arrow is a quarter turn of the last, which is what keeps the four looking
like one set — and is why only one of them is drawn:

```
   #                          #
    #                       # # #
######                        #
    #                         #
   #                          #

 pointing right          turned upright
```

The head is two blocks a side stepping back from the tip, and the turn costs it
nothing: blocks laid corner to corner read as the diagonal they are, which is
how every diagonal at this resolution is drawn.

## Large lettering

`viewdata/lettering.py` sets a line of text in a mosaic font: `place` and
`boxed` add it to a `Composition`, `cells_for` and `width` measure it first,
and `Spacing` chooses between fixed, proportional and kerned advance. The
requirements, the source formats and the measurements behind the font are in
[mosaic-fonts.md](mosaic-fonts.md) — including why a format of our own is
warranted, and why proportional spacing is required rather than merely nicer.
