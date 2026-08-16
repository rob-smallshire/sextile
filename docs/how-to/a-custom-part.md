# A custom part

A how-to guide: content that is a sequence drawn its own way is a
`SequencePart` subclass, which flows across as many frames as it takes.

```{sextile-frame}
:page: "8"
:show-code:

from dataclasses import dataclass

from sextile import Flow, Page, PageLayout, PageRequest, PageRouter, Sextile
from sextile.formatting import RowSequencePart
from sextile.viewdata.canvas import RowWriter
from sextile.viewdata.controls import Colour

router = PageRouter()

_TABLE = [("Arsenal", 63), ("City", 61), ("Liverpool", 58), ("Villa", 54), ("Spurs", 50)]


@dataclass(frozen=True, kw_only=True)
class Standings(RowSequencePart[tuple[str, int]]):
    def draw(self, row: RowWriter, entry: tuple[str, int]) -> None:
        name, points = entry
        row.text(f"{name:<12}", Colour.CYAN).text(f"{points:>3}", Colour.YELLOW)


@router.page("8", name="league", title="League table")
async def league(request: PageRequest) -> Page:
    return PageLayout(parts=[Flow(Standings(entries=_TABLE))]).build(request)


app = Sextile(name="Sport", pages=[*router])
```

A `RowSequencePart` writes each entry along its rows: override `draw` with a
`RowWriter` that runs left to right, and set `rows_per_entry` where an entry wants
a second row (`draw_detail` writes it). Wrap the part in `Flow` so the layout
carries the overflow onto further frames. For a picture positioned by cell,
subclass `SequencePart` and draw the cells yourself; for entries a reader chooses
by digit, subclass `NumberedRowSequencePart` and override `destination`. A part of
the frame's furniture — a header or footer — is a `Furnishing` instead.
