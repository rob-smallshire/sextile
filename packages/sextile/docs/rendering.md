# How a document becomes bytes

Following one body of text to the wire. Each stage is a pure function over
values, which is why nearly all of it is testable without a BBC Micro.

```
Document            Paragraph(("lda &b5fe",))       what is to be said
        |  viewdata/typesetting.py
        v
rows                Row("lda &b5fe", GREEN, 2)      text, colour, indent
        |  viewdata/canvas.py, chrome.py, footer.py
        v
frame               24 x 40 cells                   what the screen shows
        |  viewdata/frame.py
        v
bytes               the wire stream
```

Where the `Document` came from is the application's business. Stardot's is
parsed out of phpBB's post HTML — see
[its design notes](../../stardot-viewdata/docs/design.md) — and a service with
prose of its own simply builds one.

## What a document is

`content/blocks.py`. Blocks are **structural, not typographic**: `Paragraph`,
`Quote` (which nests), `Code`, `ListItem`, `Image`, `Attachment`. Emphasis is
discarded, because on forty columns colour is better spent telling a quotation
from a listing from the author's own words than rendering an italic.

A `Paragraph` holds *lines* rather than one string, because a line break and a
paragraph break are different things that arrive looking the same. That is how
phpBB's HTML reads — one `<br>` is a new line, two are a new paragraph — and
spending a blank row on every break would be ruinous on twenty-four rows.

A `Document` also carries links, numbered so that the text can refer to one and
the frame can list it afterwards.

## Blocks to rows

`viewdata/typesetting.py` flattens blocks into rows and then divides them between frames.
Doing it in that order keeps two hard things apart: deciding what a quotation
four deep should look like, and deciding where a screen ends.

Colour carries structure. A quotation is cyan, a listing green, an image or
attachment magenta, the author's own words white. Someone reading in monochrome
still follows the text; someone reading in colour can tell at a glance whose
words they are.

Nesting indents two cells per level, stopping at four levels — beyond that the
indent costs more than it conveys and colour carries it alone.

A page has frames `a`-`z` and no more. A post long enough to exhaust them says
so rather than ending mid-sentence with nothing to explain it.

## Rows to a frame

`viewdata/canvas.py` exists because **a colour attribute occupies a character
cell**. A row that changes colour twice has thirty-eight columns for text, not
forty. Canvas does that accounting so nothing above it has to — and it is why
colour could not be added later: the layout engine would have had to be rewritten
around it.

Attributes reset at the start of every row on the SAA5050, so each row is
written independently and white text needs no attribute at all. That is read
from the emulation rather than guessed: `Saa5050::start_of_line()`.

`chrome.py` fixes the geometry every page shares — a header, two mosaic rules,
a footer — leaving twenty content rows. The page number goes down first and the
title takes what is left, because titles reach forty characters unaided and the
number is what a reader needs in order to come back or to quote.

## A frame to bytes

`viewdata/frame.py` is a **fixed 24 × 40 grid**, not a stream of writes, because
Commstar wraps from the bottom-right cell back to the top-left instead of
scrolling. A serialiser that emitted one cell too many would overwrite the frame
it had just drawn; with a fixed grid that cannot happen.

Serialising is: hide the cursor, clear, home, then the cells that say something.

**The wire has two namespaces sharing the C0 range**, and confusing them
produces a display wrong in ways that look like transport corruption:

| On the wire | Meaning |
|---|---|
| a bare C0 byte | screen and cursor control |
| `ESC` then byte + 0x40 | a teletext spacing attribute |

So `0x0C` alone clears the screen, while `ESC 0x4C` selects normal height —
both being 0x0C. `viewdata/encoding.py` is where that is kept straight.

## Economy on the wire

At 1200 baud a full 960-cell frame takes about eight seconds. Two measures cut
that without changing a pixel:

**Trailing blanks are not sent.** The frame clears the screen first, so a space
at the end of a row overwrites nothing — it only walks the cursor forward, and
`CR LF` does that in two bytes rather than forty. After the last row with
anything on it, nothing is sent at all. Real pages lose between a third and
three quarters of their bytes; the days index goes from 8.1 seconds to 1.9 at
1200 baud.

A row filled to all forty columns gets no terminator, because it wraps of its
own accord and a terminator there would skip the row below. That case is in
`spike_trimmed_frames.py`, which put six frames on a real screen both ways and
compared the resolved cells.

**The command line changes a byte at a time** rather than repainting. See
[navigation.md](navigation.md).

Differential update of whole frames is possible — the cursor positioning it
needs is measured and works — but the trimming already took most of what was
there, and the remaining pace was judged about right on a real screen. See
[open-questions.md](../../../docs/open-questions.md).

## Characters

`viewdata/charset.py` holds the G0 set as the SAA5050 draws it, which is not
ASCII: `£` at 0x23, `#` at 0x5F, and ten characters a modern keyboard offers
that G0 simply lacks — `[ \ ] ^ _ \` { | } ~`. Their positions hold arrows,
fractions and rules instead.

`content/transliterate.py` is **total**: whatever goes in, what comes out is
displayable. Deliberate substitutions first, then NFKD with combining marks
dropped — which handles `café`, `Müller` and `Ångström` for free — then `?`.

Two substitutions are visible in every quoted listing: `^` becomes `↑`, which is
what BBC BASIC displays for its own exponentiation operator anyway, and `|`
becomes `‖`. Braces and brackets both become parentheses.

Text arriving from somewhere that escapes it is the application's problem, and
an easy one to get wrong twice: Stardot's notes record what phpBB's CDATA does
to an ampersand.

## Seeing it without a Beeb

```sh
uv run sextile render <module>:app --page 1              # as the Beeb draws it
uv run sextile render <module>:app --page 1 --form grid  # characters and attributes
uv run sextile render <module>:app --page 1 --form bytes # the wire, as a hex dump
```

`--form grid` prints two layers: the characters as the screen shows them, with
attribute cells appearing as the spaces they are, and an attribute layer naming
those cells by the letter they travel as. That second layer lines up directly
with a `tcpser -t sS` trace.

`--form ansi` renders mosaic graphics as Unicode sextants, so a frame looks as
the SAA5050 would draw it rather than being approximated with punctuation.
