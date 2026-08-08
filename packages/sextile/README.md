# Sextile

A framework for Viewdata services, in Python. Sextile is to a Prestel-style
service what Flask or Starlette is to a web application: it owns the connection,
the session, the page numbering and the frames on the wire, and you write what
the pages say.

```python
from sextile import Page, PageFrame, PageRequest, Sextile
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, draw_chrome

app = Sextile()

@app.page("1", name="main")
async def main(request: PageRequest) -> Page:
    canvas = Canvas()
    draw_chrome(canvas, title="MY SERVICE", page_number="1a", prompt="0 menu")
    canvas.row(CONTENT_FIRST_ROW).text("Hello, 1981.")
    return Page(frames=(PageFrame(frame=canvas.frame),))

app.alias("MAIN", "1")
```

```sh
uv run sextile serve my_service:app     # answer calls on port 6850
nc localhost 6850                       # and call it
uv run sextile render --demo            # a frame, in colour, without a Beeb
```

## What it gives you

**Routing by page number.** Patterns of literal digits and named fields, so
`82{post_id:int}` answers every page beginning 82 and hands the rest to the
handler already read as an integer. `app.address_for("post", post_id=...)` reads
the same pattern backwards, so a page linking to another does not respell the
numbering. Keywords — `*MAIN#` for `*1#` — are `app.alias`.

**Sessions that last as long as the line.** A Viewdata terminal is a display and
nothing more: it holds the frame on screen and not one thing else. So the server
holds where the reader is, what they have seen, and the menu they came through,
and a handler is a function of a request rather than of a number.

**The wire, measured rather than assumed.** Attributes travel as `ESC` + code +
0x40, a frame is 24 rows of 40 that wraps at the bottom-right back to the top
left, `RETURN` transmits 0x5F. Those were settled by driving real Commstar under
an emulator, and are written up in
[docs/viewdata-encoding.md](docs/viewdata-encoding.md).

**Nobody is cut off without warning.** After half the idle timeout a silent
caller's footer becomes a bar that drains, reading `Press a key`. The first key
dismisses it and does nothing else, so it is safe to press whatever comes to
hand. Every service gets this without writing anything.

**Forty columns, accounted for.** A colour attribute occupies a character cell,
so a row that changes colour twice has thirty-eight columns for text. `Canvas`
does that arithmetic so nothing above it has to.

## Documentation

| | |
|---|---|
| [design.md](docs/design.md) | the framework as built, and which decisions are load-bearing |
| [writing-an-application.md](docs/writing-an-application.md) | how to write a service |
| [rendering.md](docs/rendering.md) | how a document becomes bytes, stage by stage |
| [navigation.md](docs/navigation.md) | how a reader moves about, and why the controls are what they are |
| [graphics.md](docs/graphics.md) | blocks, and the compositor that places them |
| [mosaic-fonts.md](docs/mosaic-fonts.md) | large lettering: requirements, not yet built |
| [viewdata-encoding.md](docs/viewdata-encoding.md) | what the BBC end actually does, and how we know |

## Status

Young, and extracted from a working service rather than designed in the
abstract. Two applications use it: `stardot-viewdata` in the same repository is
a real one, and `calendar-viewdata` is a small one written to be read.

MIT licensed.
