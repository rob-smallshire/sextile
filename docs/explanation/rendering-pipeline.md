# The rendering pipeline

Explanation: how a page becomes bytes on the wire, one stage at a time. Each
stage is a pure function over values, which is why nearly all of it runs without
a BBC Micro.

```text
Document                                 what is to be said
   │  sextile.content.blocks
   │  sextile.viewdata.typesetting
   ▼
Row  (text, colour, indent)
   │  sextile.formatting, sextile.layout
   │  sextile.viewdata.canvas
   ▼
Frame  (24 × 40 cells)                    what the screen shows
   │  sextile.viewdata.frame
   ▼
bytes                                     the wire stream
   │  sextile.viewdata.encoding
```

A `Document` is structural, not typographic: `Paragraph`, `Quote`, `Code` and the
rest say what a thing is, and colour is spent telling a quotation from a listing
rather than on an italic. `typesetting.rows_for` flattens it into `Row`s — a
quotation cyan, a listing green, nesting indented — and leaves where a frame ends
to the layer that draws them.

## A document, drawn

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.content.blocks import Code, Document, Paragraph
from sextile.formatting import Prose
from sextile.viewdata.typesetting import rows_for

_DOC = Document(blocks=(
    Paragraph(("A page begins as a document.",)),
    Code(("PRINT CHR$(141)",)),
))

router = PageRouter()


@router.page("1", name="page", title="Pipeline")
async def page(request: PageRequest) -> Page:
    return PageLayout(title="PIPELINE", parts=[Prose(entries=rows_for(_DOC))]).build(request)


app = Sextile(name="Demo", pages=[*router])
```

## The same frame, on the wire

`viewdata.frame` is a fixed grid, not a stream of writes, and serialising it is:
hide the cursor, clear, home, then the cells that say something. The C0 range
holds two namespaces — a bare byte is screen or cursor control, `ESC` then byte
+ `0x40` a teletext attribute — kept straight in `viewdata.encoding` and measured
in {doc}`../reference/viewdata-encoding`. The frame above goes down the wire as:

```{sextile-frame}
:page: "1"
:form: bytes

from sextile import Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.content.blocks import Code, Document, Paragraph
from sextile.formatting import Prose
from sextile.viewdata.typesetting import rows_for

_DOC = Document(blocks=(
    Paragraph(("A page begins as a document.",)),
    Code(("PRINT CHR$(141)",)),
))

router = PageRouter()


@router.page("1", name="page", title="Pipeline")
async def page(request: PageRequest) -> Page:
    return PageLayout(title="PIPELINE", parts=[Prose(entries=rows_for(_DOC))]).build(request)


app = Sextile(name="Demo", pages=[*router])
```

## Economy on the wire

Two measures cut a frame's bytes without changing a pixel, both settled on a real
screen and written up in {doc}`../reference/viewdata-encoding`:

- A colour attribute occupies a cell, and `canvas` counts it, so a row that
  changes colour twice has thirty-eight columns for text and no layer above has
  to know. It is why colour could not have been added later.
- Trailing blanks are not sent. The frame clears the screen first, so a space at
  the end of a row overwrites nothing; after the last row with anything on it,
  nothing is sent at all. Real pages lose between a third and three quarters of
  their bytes.
