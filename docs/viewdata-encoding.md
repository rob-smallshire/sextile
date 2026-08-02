# How Sextile must encode bytes for a viewdata terminal

Measured against Pace Commstar 1.40 in Prestel mode, running on an emulated BBC
Model B under Beebium, with bytes delivered to the ACIA through `rpc-serial` and
the resulting cells read back from the SAA5050 after it had resolved them.

The spike script is at `docs/spikes/spike_control_codes.py`. It needs a local
Beebium checkout, so it is not part of the test suite; the conclusions below are
what the suite pins instead.

## The wire has two separate namespaces

This is the thing to understand before writing any serialiser. A byte in the C0
range means one of two entirely different things depending on how it arrives:

| On the wire | Meaning |
|---|---|
| A bare C0 byte | Screen and cursor control — clear, home, carriage return, line feed |
| `ESC` (0x1B) then byte + 0x40 | A teletext spacing attribute — colour, graphics, height, flash |

So 0x0C on its own clears the screen, whereas `ESC 0x4C` selects normal height.
0x1E on its own homes the cursor, whereas `ESC 0x5E` holds graphics. Conflating
the two produces a display that is wrong in ways that look like transport
corruption.

## Attributes must be escape-encoded

`ESC 0x41` followed by `RED` was read back as:

```
[ 0, 0] 0x01 fg=red   control=True     <- the attribute, occupying a cell
[ 0, 1] 0x52 fg=red   control=False    <- 'R'
```

The attribute lands in a character cell of its own and takes effect from the
following cell. Both facts matter to layout: a colour change costs one of the
forty columns.

Sending the SAA5050's own codes directly does **not** work. `0x81` followed by
`RED` produced white text with no control cell at all — the byte vanished.
Prestel mode runs the line at 7E1, which has no eighth bit to carry, so this is
the expected outcome and not a Commstar quirk. Sextile therefore has one
encoding, not a choice of two.

## Graphics select the same way

`ESC 0x57` (graphics white) then `ESC 0x5A` (separated graphics) put following
cells into `charset=separated`; `ESC 0x59` returned them to `contiguous`. The
separated/contiguous attribute is set-at — the control cell itself already
reports the new character set — whereas colour is set-after.

## Verified screen control

Only these bare C0 codes have been measured, and they are all the frame
serialiser needs:

| Byte | Effect |
|---|---|
| 0x0C | Clear screen |
| 0x1E | Cursor home |
| 0x0D | Carriage return |
| 0x0A | Line feed |

Cursor left/right/up/down (0x08–0x0B) are conventional viewdata but have not
been measured here, so nothing depends on them.

## The keyboard transposition

Commstar in Prestel mode transmits, per `docs/serial-ip232.md` in the Beebium
tree and confirmed by its own test suite:

| Keypress | Transmits | Displays as |
|---|---|---|
| `SHIFT-3` | 0x23 | `£` |
| `RETURN` | **0x5F** | `#` |
| `CTRL-M` | 0x0D | carriage return |

The viewdata `#` command key therefore arrives as **0x5F**, not 0x23. The
Prestel command parser must accept it.

## Attributes reset at the start of every row

Not measured but read directly from the emulation, which is a better oracle:
`Saa5050::start_of_line()` in `src/core/include/beebium/Saa5050.hpp` sets

| State | Value at the start of each row |
|---|---|
| Foreground | white (7) |
| Background | black (0) |
| Character set | alpha |
| Graphics set | contiguous |
| Conceal | off |
| Hold graphics | off |

So a row never inherits anything from the row above, white text needs no
attribute at all, and `Canvas` writes each row independently.

## The character set is corroborated

`docs/discussion/teletext-repertoire-choice.md` in the Beebium tree tabulates
the eleven positions where the SAA5050's UK repertoire departs from ASCII, and
`teletext_alpha_codepoint` in `src/core/src/TeletextText.cpp` implements them.
Both agree with `sextile.viewdata.charset` exactly, including 0x60 as U+2015
HORIZONTAL BAR — the one glyph the spike could not confirm.

0x7F is a twelfth departure: the font at `TeletextFont.hpp` has a glyph there
labelled "Block", which Sextile maps to U+25AE. Beebium's text conversion
deliberately returns nothing for it, since a block does not copy usefully as
text — a rendering decision, not a claim that the cell is blank.

## Page numbers have no practical length limit

Commstar collects a `*nnn` request and transmits it with the terminating
`RETURN`. Measured by `docs/spikes/spike_page_number_buffer.py`, it truncates
nothing:

| Typed | Reached the wire |
|---|---|
| `*100#` | `*100_` |
| `*123456789#` | `*123456789_` |
| `*123456789012#` | `*123456789012_` |
| `*12345678901234567890#` | `*12345678901234567890_` |

The nine-digit Prestel maximum was a property of Prestel's database, not of the
terminal. The real costs of a long page number are typing time — about 130ms per
character at 75 baud — and the header space needed to display it.

The trailing `_` is 0x5F, the viewdata `#`, confirming that a page request
terminates with 0x5F and not 0x23.

## A testing gotcha

Beebium's `teletext_screen().text` maps cell codes to ASCII, not to the glyph the
SAA5050 draws. A cell holding 0x5F reads back as `_` in that string even though
the screen shows `#`. Assert on `cell.character` when the identity of a character
matters; `.text` is for locating things, not for confirming them.

One consequence: the glyph at 0x60 could not be confirmed this way, so nothing in
Sextile depends on it. Em and en dashes transliterate to `-`.

## Frame geometry

Measured by `docs/spikes/spike_frame_geometry.py`, and simpler than expected.

- **Home is row 0**, and twenty-four rows written with CR/LF land on rows 0–23.
  Commstar reserves no status line at the top.
- **Column 40 wraps by itself.** Forty characters with no CR or LF advance to the
  start of the next row, so a frame needs no line terminators at all.
- **The bottom wraps to the top; nothing scrolls.** Writing a twenty-fifth row
  overwrote row 0 rather than scrolling the display. Row 24 of the BBC's 25-row
  Mode 7 screen is never used.

So a frame is exactly **24 rows of 40 cells**, and serialising one is: clear
screen, home, then precisely 960 cells. Emitting even one cell more corrupts the
top of the frame it just drew, which is why `Frame` is a fixed-size grid rather
than a stream of writes.

## What this does not yet cover

- Whether ip232 framing behaves as documented end to end — measured only as a
  codec so far, never with Commstar attached. Not on the critical path: tcpser
  is already the ip232 endpoint, so Sextile is a plain TCP server that tcpser
  dials into, exactly as it dials any other board.
