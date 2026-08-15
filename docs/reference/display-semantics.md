# Display semantics

Reference: what a SAA5050 does with the control codes in a row, beyond the colour
and the mosaic bits `viewdata/ansi.py` already walks. Measured against Beebium's
`Saa5050` (`~/Code/beebium/src/core/include/beebium/Saa5050.hpp`), the in-repo
oracle, and marked **verified** against it or **inferred** where the source does
not settle a point or where a modern HTML render departs from the chip.

## Control codes, and when each takes effect

A control code occupies a character cell, which shows as a space (or as held
graphics, below). The distinction that matters is whether the code changes the
display **at** its own cell or only **after** it.

| Code | Meaning | Effect |
|---|---|---|
| `0x00`–`0x07` | alpha colour (fg) | set-after |
| `0x08` | flash | set-after |
| `0x09` | steady | set-after |
| `0x0C` | normal height | set-after |
| `0x0D` | double height | set-after |
| `0x11`–`0x17` | graphics colour (fg) | set-after |
| `0x18` | conceal | set-after |
| `0x19` | contiguous graphics | set-after |
| `0x1A` | separated graphics | set-after |
| `0x1C` | black background | **set-at** |
| `0x1D` | new background | **set-at** |
| `0x1E` | hold graphics | **set-at** |
| `0x1F` | release graphics | set-after |

**Verified.** In `Saa5050::byte`, a control code is processed before the cell's
output is written, so a code that changes the background (`0x1C`, `0x1D`) colours
its own cell; a foreground or attribute code writes a space in the prevailing
state and applies from the next cell. `0x1E` shows the held mosaic in its own
cell; `0x1F` still shows it and releases from the next.

**Every attribute resets at the start of each row**: white on black, alpha,
steady, contiguous, no hold, no conceal (`Saa5050::start_of_line`). A row is read
left to right and nothing carries from the row above.

## Double height

`0x0D` makes the row twice as tall: this character row shows the top halves of
its glyphs, and the row below shows the bottom halves.

**Verified** (`set_raster`, `process_control_code` `0x0D`/`0x0C`, `byte`): a
`0x0D` sets a raster shift so each source font row is drawn on two scanlines, and
sets a flag that persists to the next character row, which is displayed at a
raster offset of 20 — its lower half. The flag then clears, so double height
spans exactly two physical rows. On the lower row the chip reads that row's own
memory and shows its glyphs' bottom halves; a page that wants a clean
double-height line therefore leaves the row below it blank, or repeats the text.
A `0x0C` (or `0x0D`) that changes the height blanks its own cell.

**Inferred (render departure).** A browser cannot show a font's lower half from a
raster offset. The HTML renderer instead draws the whole glyph at the row it
appears on, scaled 2× from the top (`transform: scaleY(2)`), and leaves the same
columns on the row below blank so the descending half has room. The result reads
the same; the mechanism is not the chip's.

## Hold graphics

Between `0x1E` (hold) and `0x1F` (release), a control cell shows the **last
mosaic drawn on the row** instead of a space, in the graphics charset in force
when it was held.

**Verified** (`byte`, `capture_cell`, `m_last_graphics_data`/`m_last_graphics_char`):
the last displayed graphics character (a code with bit 5 set, in a graphics
charset, not concealed) is remembered; while hold is on, a control code's cell
repeats it rather than blanking. An alpha colour code clears the remembered
mosaic (so the held cell after it is blank). Hold is cleared at the start of each
row.

## Conceal

`0x18` hides every following character on the row until a colour code or the row
ends.

**Verified** (`process_control_code` `0x18`; the colour cases clear `m_conceal`):
concealed characters are output as blank. Any alpha or graphics colour code
(`0x00`–`0x07`, `0x11`–`0x17`) reveals the rest of the row. Conceal is cleared at
the start of each row.

## Flash

`0x08` flashes the following characters; `0x09` stops it.

**Verified** (`0x08`/`0x09`, `m_frame_flash_visible`, `vsync`): flashing text is
shown or hidden by a frame counter that cycles roughly once a second (hidden for
16 of every 64 fields, shown for the other 48). A static render shows a flashing
run steady; an HTML render animates it and honours `prefers-reduced-motion`.

## Separated graphics

`0x1A` selects separated mosaics, `0x19` contiguous. A separated mosaic is the
same 2×3 block pattern with a gap on the left and bottom of each block.

**Verified** (`get_graphics_row`): separated graphics blank the left column of
each half (columns 0 and 3 of the six) and the bottom row of each block (font
rows 2, 6 and 9), leaving the blocks unjoined. Contiguous mosaics fill the cell.
The mosaic bit layout is `bit0`=top-left, `bit1`=top-right, `bit2`=middle-left,
`bit3`=middle-right, `bit4`=bottom-left, **`bit6`=bottom-right** — `bit5` is
skipped, being the bit that distinguishes the alphanumeric range `0x40`–`0x5F`
from the mosaics. This is the same layout Bedstead's Private Use mosaics use (see
the spike report).

## What `viewdata/ansi.py` does not yet implement

The current walk tracks foreground colour, background (as set-after, not set-at),
the graphics-on flag and contiguous mosaics. It does not implement: double height
(`0x0D`), hold graphics (`0x1E`/`0x1F`), conceal (`0x18`), flash (`0x08`), the
separated charset (`0x1A`, drawn as contiguous), or set-at backgrounds. These are
the semantics the display walk gains when it moves to `viewdata/display.py`.
