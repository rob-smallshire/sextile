# Spikes

Each of these settled a question about the BBC end that could not be settled by
reading. They are kept as the record of *how* each answer was arrived at, which
matters when an answer later looks surprising.

They are **not part of the test suite**. They need a local Beebium checkout, a
Commstar ROM, and a couple of minutes each. Run one with:

```sh
BEEBIUM_ROM_DIR=~/Code/beebium/roms \
BEEBIUM_SERVER=~/Code/beebium/build-release/src/server/beebium-model-b \
uv run --no-project --python 3.12 \
    --with ~/Code/beebium/clients/beebium-python-client \
    --with . --with pytest \
    python -m pytest docs/spikes/spike_control_codes.py -s -v
```

Most drive Commstar through `rpc-serial`, which delivers bytes to the ACIA under
the test's control, and read the screen back as resolved SAA5050 cells. The
transport is interchangeable for this purpose: the questions are about what
Commstar does with bytes, not about how they arrived.

| Spike | Question | Answer |
|---|---|---|
| `spike_control_codes.py` | How must attributes be encoded? | `ESC` + code + 0x40. The SAA5050's own 0x80-0x9F codes vanish on a 7E1 line. |
| `spike_frame_geometry.py` | Where does a 24-row frame sit in a 25-row screen? | Rows 0-23. Column 40 wraps by itself; the bottom-right cell wraps to the top-left rather than scrolling. |
| `spike_page_number_buffer.py` | How long a page number will Commstar send? | At least twenty digits, untruncated. The nine-digit Prestel maximum was its database's, not a terminal's. |
| `spike_cursor_keys.py` | Do the BBC's arrow keys reach us? | Yes, as 0x08-0x0B — the viewdata cursor-control codes, the eighth bit taken by 7E1. COPY is consumed locally. |
| `spike_editing_keys.py` | What does DELETE send? | 0x7F, distinct from RETURN's 0x5F. TAB sends 0x09; CTRL-H sends 0x19. |
| `spike_cursor_output.py` | Can we redraw part of a screen? | Yes. Moving the cursor erases nothing, and cursor up from row 0 wraps to row 23 — so the footer is two bytes away. |
| `spike_cursor_visibility.py` | Can the cursor be hidden? | 0x11 and 0x14 are consumed as controls, taking no cell. Which shows and which hides was confirmed by eye, the cursor's blink defeating a read-back. |
| `spike_trimmed_frames.py` | Is a trimmed frame identical on screen? | Yes, across six frames including the one that would break it — a row filled to column 40. |
| `spike_suggestion_block.py` | Can a block of rows be repainted as a reader types? | Yes, if each row is sent trimmed: a full-width row wraps by itself, so a cursor down after one moves two rows. Three suggestions cost 121 bytes, 1.0s at 1200 baud; the common keystroke costs 40. |

What they established is written up in
[../viewdata-encoding.md](../../packages/sextile/docs/viewdata-encoding.md), which keeps what was
verified separate from what was inferred.

## Writing another

Copy the fixture and helpers from any of them; they are deliberately repetitive
rather than shared, so that a spike is a single file someone can read top to
bottom.

Two things worth knowing, both learned the hard way:

- **The cursor flashes.** One reading tells you which half of the blink you
  caught, not what the state is. `spike_cursor_visibility.py` samples across it.
- **Beebium's `teletext_screen().text` maps codes to ASCII, not to glyphs.** A
  cell holding 0x5F reads back as `_` though the screen shows `#`. Assert on
  `cell.character` when identity matters.
