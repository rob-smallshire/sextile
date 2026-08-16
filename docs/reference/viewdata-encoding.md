# Viewdata encoding

Reference: what the BBC end actually does on the wire, and how it was measured.
Every claim is marked as measured, corroborated against the emulator, or
inferred; that separation is the document's contract, so a reader knows which
line an eye on a real Beeb could still move.

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

**Which of the two comes first is not measured.** The spike drove colour and
then separated; the compositor emits separated and then colour, because the
colour attribute is what enters graphics and it should enter the set already
chosen. Beebium's `Saa5050` reaches separated graphics either way — `0x1A`
remembers the graphics charset and switches the current one if it is already
graphics, and `0x11`–`0x17` enter graphics in whichever charset is remembered
— so this is corroborated rather than verified. Every rule on every frame now
goes out in that order, and it is the one thing here worth an eye on a real
Beeb.

## A background is set at its cell, not after it

Read from Beebium's `Saa5050`, not measured: `process_control_code` runs before
the cell's `fg` and `bg` are captured, so the cell carrying `NEW_BACKGROUND`
(`0x1D`) or `BLACK_BACKGROUND` (`0x1C`) is **already the new background**. A
foreground change on the same cell is invisible — the cell is blank — which is
why colour reads as set-after and background as set-at.

It decides where a coloured box appears to begin and end:

```
    column 17   18   19  ...  38   39
           ▁▁   ██   ██       ██   ▁▁
        choose  new background       black background
        blue    -- the box's first cell
```

so a box's own first cell is spent on the attribute that colours it, and one
black cell before that is unavoidable: a colour attribute cannot colour itself.
`Composition.panel` does this arithmetic.

**A field bar therefore begins two cells before anything can be typed into it**,
and no arrangement avoids it. `NEW_BACKGROUND` takes the *current foreground* as
the background, so the order is forced — choose blue, make it the background,
choose white back — and the last two of those three cells are already inside the
new background. Choosing white first would give a white background; a wider gap
between the label and the field makes it worse rather than better, since the
background runs on until something stops it and any padding after the attributes
is coloured too.

Two cells of a bar that nothing can be typed into is what a coloured field costs
on this hardware. Both `TypeAhead` and `FieldSet` incur it.

## Verified screen control

Only these bare C0 codes have been measured, and they are all the frame
serialiser needs:

| Byte | Effect |
|---|---|
| 0x0C | Clear screen |
| 0x1E | Cursor home |
| 0x0D | Carriage return |
| 0x0A | Line feed |

Cursor left/right/up/down (0x08–0x0B) work in both directions; see "The cursor
moves on command" below for what they do as output, and "The cursor keys reach
us" for what they mean as input.

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

The editing keys, measured by `docs/spikes/spike_editing_keys.py`:

| Keypress | Transmits |
|---|---|
| `DELETE` | 0x7F, ASCII delete — distinct from RETURN, so a digit can be rubbed out without sending the request |
| `TAB` | 0x09, the same byte as cursor right |
| `CTRL-H` | 0x19, not the ASCII backspace one might expect |
| `COPY` | nothing; consumed locally |

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

**And confirmed by eye**, which is worth saying because a partial repaint stakes
a good deal on it: a form redraws one row in the middle of a frame and sends its
attributes with it, so a background that outlived its row would spread down the
screen behind everything beneath. Watched over a good many keystrokes on the
position form, which moves a blue background between two rows on every TAB, and
nothing has ever spread. By eye rather than by read-back because the emulator's
cell API exposes no colour at all.

## Double height takes the row below, and needs the text on it too

Read from the emulation and then **confirmed on screen**: the title frame draws
its service name this way, and it renders correctly under Commstar. Worth
recording as more than an inference, because it is **not what a reasonable guess
would say** — a guess would have left the row beneath blank.

`0x0D` selects double height and `0x0C` returns to normal, both spacing
attributes occupying a cell. In `Saa5050.hpp`:

```cpp
cell.double_height_top    = (m_raster_shift == 1 && m_raster_offset == 0);
cell.double_height_bottom = (m_raster_shift == 1 && m_raster_offset != 0);
```

`m_raster_shift` is set by `0x0D` and, like every other attribute, resets at the
start of each row. `m_raster_offset` is the row-level state that steps 0 → 20 →
0 as character rows complete while any double height is in force. So:

- the row carrying the attribute is drawn as the **top halves** of its
  characters;
- the row below is drawn as the **bottom halves** — but only if it carries the
  attribute as well, since `double_height_bottom` requires the shift on that row
  too;
- so **both rows hold the same text**, which is exactly the old BBC BASIC idiom
  of printing a double-height line twice, both prefixed with `CHR$(141)`.

Nothing else can go on the lower row: whatever were there would be drawn as the
bottom of something. `drawing.centred_double` writes both rows and refuses the
last row of the frame, there being no row beneath it.

Confirmed by eye rather than by a spike script, so what is pinned is the bytes
Sextile emits — `ESC M` then the colour, twice, with the same text — and not the
pixels. That is the right division: the emulation and the hardware agree about
those pixels, and the suite cannot see a screen.

## The character set is corroborated

`docs/discussion/teletext-repertoire-choice.md` in the Beebium tree tabulates
the eleven positions where the SAA5050's UK repertoire departs from ASCII, and
`teletext_alpha_codepoint` in `src/core/src/TeletextText.cpp` implements them.
Both agree with `sextile.viewdata.charset` exactly, including 0x60 as U+2015
HORIZONTAL BAR — the one glyph the spike could not confirm.

**0x60 is the long dash, and the underscore is not.** The font in
`TeletextFont.hpp` settles a thing that is easy to get one position wrong: 0x60
draws a bar the full width of the cell, 0x2D draws a three-pixel hyphen, and
0x5F — where ASCII keeps its low line — draws the **hash**, the viewdata command
key. So a range wanting a long dash is written with U+2015 and not with `_`,
whatever a teletext editor's keyboard suggests; and a literal `_` in source is
transliterated to a hyphen and comes out short.

```
0x5F  .#.#..     0x60  ......      0x2D  ......
      .#.#..           ......            ......
      #####.           ......            ......
      .#.#..           #####.            .###..
      #####.           ......            ......
       hash          long dash          hyphen
```

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

## The cursor keys reach us

Commstar passes the BBC's cursor keys straight through in Prestel chat mode,
measured by `docs/spikes/spike_cursor_keys.py`:

| Key | Transmits | As viewdata |
|---|---|---|
| LEFT | 0x08 | cursor left |
| RIGHT | 0x09 | cursor right |
| DOWN | 0x0A | cursor down |
| UP | 0x0B | cursor up |
| COPY | nothing | consumed locally |

They are the MOS codes 0x88-0x8B with the eighth bit taken by the 7E1 line,
which lands them exactly on the viewdata cursor-control codes. So a reader has
real arrow keys, and Sextile reads them as the same four movements as WASD.

One consequence worth knowing: 0x0A is both the cursor-down key and the second
half of a terminal's CR LF. The parser tells them apart by position -- a line
feed directly after a carriage return is the rest of that terminator, and on its
own it is the key.

## Trailing blanks need not be sent

A frame clears the screen before drawing, so a space at the end of a row
overwrites nothing: it exists only to walk the cursor forward. `CR LF` does that
in two bytes instead of up to forty, and after the last row with anything on it
nothing need be sent at all.

Measured by `docs/spikes/spike_trimmed_frames.py`, which sends the same frame
both ways and compares the resolved SAA5050 cells:

| Frame | Saved | Difference |
|---|---|---|
| the demonstration frame | 462 bytes | none |
| blank rows between content | 897 bytes | none |
| a row filled to column 40 | 842 bytes | none |
| nothing after the first row | 947 bytes | none |
| a trailing attribute | 942 bytes | none |
| a wholly full frame | 0 bytes | none |

Real pages save between a third and three quarters, which at 1200 baud is eight
seconds down to two or three.

The one case that would break it is a row filled to all forty columns: that
wraps of its own accord, so a terminator after it would skip the row below. It
is in the table above for that reason.

## The cursor moves on command

Measured by `docs/spikes/spike_cursor_output.py`. Commstar acts on the cursor
codes sent *to* it, which makes it possible to redraw part of a screen instead
of all of it:

| Sent | Effect |
|---|---|
| `0x1E` then `0x0B` | Home, then up — **wraps to row 23** |
| `0x1E` then n × `0x0A` | Home, then down to row n |
| `0x0D` | Back to column 0 of the current row |
| `0x08` | Back one cell, over what is there |
| `0x09` | Forward one cell, leaving it as it was |

Two findings matter more than the rest. **Moving the cursor erases nothing** —
after home and five downs, all twenty-four rows still bore their labels. And
**cursor up from row 0 wraps to row 23**, so the footer row is two bytes away
rather than twenty-four.

Overwriting row 23 alone left rows 0 to 22 untouched. So a command line, or any
other partial redraw, costs about `2 + len(text)` bytes: a few milliseconds at
9600 baud, and under a third of a second at 1200.

Smaller edits are cheaper still, and are what the command line actually uses.
Because the cursor is left where the next character goes, typing one costs that
character alone, and rubbing one out costs three bytes — cursor left, a space,
cursor left. The space keeps the row's background, the attributes that set it
sitting earlier in the row and going untouched.

This is also what differential update would need, should the whole-frame repaint
ever become the thing worth optimising.

## A block of rows can be repainted, if each row is trimmed

Measured by `docs/spikes/spike_suggestion_block.py`, which asks whether a
type-ahead search is possible at all: the reader types, and the best three
matching places are repainted beneath the field.

**A row written to all forty columns must not be followed by a cursor down.**
It wraps by itself — `spike_frame_geometry` established that — so the cursor is
already on the next row, and the carriage return and cursor down that walk to
the next row of the block move it down a second one. A three-row block written
that way lands on rows 4, 6 and 8, overruns what is beneath it, and leaves the
rows between showing whatever they showed before. This is what the spike found
first, and nothing but a real screen would have found it: the arithmetic is
identical either way.

So each row of a multi-row repaint is sent **trimmed to its last non-blank
cell**, which fixes the walk and costs a third fewer bytes into the bargain.

What it costs, on real Commstar, for three suggestions of a name and a country:

| Repainted | Bytes | At 1200 baud |
|---|---|---|
| The field alone — the common keystroke | 40 | 0.33 s |
| The rows that changed | 81 | 0.68 s |
| The whole block | 121 | 1.01 s |

A reader on a BBC keypad types perhaps two characters a second, so the block
keeps up when the list is settling and lags a little while it churns. Nine
suggestions would not: the same measurement scaled is nearly three seconds a
keystroke, which is why the design is three.

Nothing below the block was disturbed, and the title row survived — so a
repaint neither scrolls nor overruns once the trimming is right.

**Two things this did not establish.** Whether an attribute can leak out of a
row rewritten mid-frame is only inferred: the rows beneath kept their own text,
and attributes are known to reset at the start of every row, but the emulator's
cell API did not expose a foreground colour to read back. And where the cursor
ends up after the walk could not be read at all — `cursor_row` and
`cursor_column` are not exposed — so, as with cursor visibility, that one needs
an eye on a real screen.

## The cursor

Commstar shows a cursor by default, which is a distraction on a page nobody is
typing into. Every frame therefore begins by hiding it, and the command line
turns it back on where the next character will land — the one place in the
service a cursor tells a reader anything.

`0x11` (DC1) shows the cursor and `0x14` (DC4) hides it, following viewdata
convention and confirmed on a real screen. Both are consumed as controls rather
than displayed: `0x11 A B 0x14 C D` renders as `ABCD` with no gap, so neither
takes a cell and neither is mistaken for the graphics colour at the same value.

Confirmed by looking rather than by reading the screen back, because the cursor
flashes — which defeated a first attempt to measure it, two readings of the same
state disagreeing because they caught opposite halves of the blink. A sample of
a flashing thing is a coin toss.

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
