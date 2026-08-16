# Content

Reference: the document vocabulary in {py:mod}`sextile.content.blocks`, for a
service turning something richer than strings into frames.

| Showing | Block |
|---|---|
| running text | `Paragraph` |
| a quotation, which may itself quote | `Quote` |
| a code listing, drawn as given | `Code` |
| one item of a list | `ListItem` |
| a picture a terminal can only name | `Image` |
| a file named but not retrievable | `Attachment` |
| a link, numbered so the text can refer to it | `Link` |

A `Document` holds a tuple of these; `typesetting.rows_for` lays it out into the
`Row`s a `Prose` part draws — quotations in cyan, listings in green, nesting
indented, over-long words broken rather than dropped. `transliterate`, at the top
level of `sextile`, folds text a terminal cannot draw down to what it can.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.content.blocks import Code, Document, ListItem, Paragraph, Quote
from sextile.formatting import Prose
from sextile.viewdata.typesetting import rows_for

_DOC = Document(blocks=(
    Paragraph(("Running text wraps to the width of the frame.",)),
    Quote((Paragraph(("A quotation is drawn in cyan.",)),)),
    ListItem("A list item, marked and indented."),
    Code(("CODE  is drawn  as given",)),
))

router = PageRouter()


@router.page("1", name="digest", title="Digest")
async def digest(request: PageRequest) -> Page:
    return PageLayout(title="DIGEST", parts=[Prose(entries=rows_for(_DOC))]).build(request)


app = Sextile(name="Reader", pages=[*router])
```

See {py:mod}`sextile.content.blocks` for the detail.
