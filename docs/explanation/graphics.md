# Graphics

Explanation: how a colour attribute occupies a cell, what each change of style
costs, and why the compositor places runs exactly rather than searching for a
placement. The recipes that apply this are {doc}`../how-to/draw-icons`,
{doc}`../how-to/draw-charts`, {doc}`../how-to/letter-on-a-background` and
{doc}`../how-to/compose-a-frame`. The API is {py:mod}`sextile.viewdata.blocks`,
{py:mod}`sextile.viewdata.composition` and {py:mod}`sextile.viewdata.charting`.

## The block grid

A mosaic cell is a 2 × 3 grid of blocks, so a frame of 40 × 24 cells is 80 × 72
blocks — 78 across in practice, because a graphics colour attribute occupies a
cell and attributes reset at the start of every row, so a picture pays one cell
on each row it spans.

## What a style costs

`Style` carries every attribute the hardware has, because the transitions are not
uniform — which is the argument for handing a compositor a style rather than
writing controls by hand.

| Change | Cells | Note |
|---|---|---|
| foreground colour | 1 | also chooses the character set |
| entering or leaving graphics | 1 | the colour attribute does both |
| contiguous ↔ separated | 1 | chooses the set; a colour attribute enters it |
| flash / steady | 1 | |
| double height / normal | 1 | and takes the row below |
| hold / release graphics | 1 | |
| a background | 3 | choose the colour, promote it, choose the foreground again |
| a background matching the foreground | 2 | nothing to change back to |
| back to black | 1 | `BLACK_BACKGROUND` |
| conceal | 1 | and cannot be undone |

A background costs three cells because the hardware has no set-background, only
`NEW_BACKGROUND`, which makes the current foreground the background. `CONCEAL`
has no counterpart, so a composition asked to turn it off is refused rather than
drawn wrongly; double height places its run on the row below as well, which is
how the display draws the bottom halves. The measured basis is in
{doc}`../reference/viewdata-encoding`.

## Placement is exact

The compositor reports whether a layout is possible — naming the row, the column
and the arithmetic — before a cell is written, and draws nothing if any row
fails, so a bad layout never leaves half a frame on a screen. Two runs in one
style cost one attribute, not two, because there is no text between them.
Placement is a single left-to-right pass rather than a search: an attribute
displays as a blank, and a blank in graphics is the no-blocks mosaic, so an
attribute may sit anywhere in the gap before its run and there is nothing to
search for. It becomes a search only if runs are free to move, which is a
different feature.
