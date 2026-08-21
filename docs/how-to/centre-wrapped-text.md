# Centre wrapped text

A how-to guide: centre a wrapped display string — a masthead's description, a
title — so it breaks into even lines rather than a full first line and an orphan.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import (
    Lines, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile, TextAlign,
)
from sextile.viewdata.wrapping import Breaking, wrap_within

router = PageRouter()

_DESCRIPTION = "Local development board for the Content Provider API"


@router.page("1", name="board", title="The board")
async def board(request: PageRequest) -> Page:
    lines = wrap_within(_DESCRIPTION, cells=39, rows=2, breaking=Breaking.DISPLAY)
    return PageLayout(parts=[OnOneFrame(Lines(lines, align=TextAlign.CENTRE))]).build(request)


app = Sextile(name="Directory", pages=[*router])
```

`wrap_within(..., breaking=Breaking.DISPLAY)` counts the last line's slack, so a
short string breaks into two even lines; `Lines(lines, align=TextAlign.CENTRE)`
then centres each. Left it to the default `Breaking.PARAGRAPH` and the same
string fills the first line and strands the second — right for body text, where a
final short line is expected, but top-heavy once centred.

Why the two are separate: breaking chooses where the lines end
({py:mod}`sextile.viewdata.wrapping`), alignment chooses where each line sits (a
`Lines` part, computed at draw time). `TextAlign` is `LEFT`, `CENTRE` or `RIGHT`,
kept apart from the placement `Align` of {doc}`compose-a-frame` so a justified
mode could never leak into a placement. Body text stays left; the breaking and
alignment terms are in {doc}`../reference/glossary`.
