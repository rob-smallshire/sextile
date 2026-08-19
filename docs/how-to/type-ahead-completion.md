# Type-ahead completion

A how-to guide: a field with the best few matches beneath it, updating at each
keystroke, chosen by a digit.

```{sextile-frame}
:page: "3"
:keys: "TRO"
:show-code:

from collections.abc import Sequence

from sextile import Lines, MenuItem, OnOneFrame, Page, PageAddress, PageLayout, PageRequest, PageRouter, Sextile
from sextile.forms import TypeAhead

router = PageRouter()

_PLACES = ["Trondheim", "Tromsø", "Troon", "Truro", "Oslo", "Bergen"]

@router.page("3", name="search", title="Find a place")
async def search(request: PageRequest) -> Page:
    async def lookup(typed: str) -> Sequence[MenuItem]:
        matches = [name for name in _PLACES if name.upper().startswith(typed.upper())]
        return [MenuItem(text=name, detail="", destination=PageAddress("31")) for name in matches[:3]]

    field = TypeAhead(lookup=lookup, label="PLACE:", no_match="No place of that name.")
    return PageLayout(
        parts=[OnOneFrame(Lines(("Key a place name.", ""))), OnOneFrame(field)],
    ).build(request)

app = Sextile(name="Weather", pages=[*router])
```

`lookup` is awaited with what has been keyed and returns the entries to suggest;
letters type into the field, a digit chooses the numbered match — leading wherever
that entry's `destination` says — and RETURN takes the one marked with `#`.
`no_match` is said when nothing matches.

Why three suggestions and not nine: the list is redrawn on the wire at each
keystroke, and nine rows cost nearly three seconds at 1200 baud where three cost
about one. The measurement is in {doc}`../reference/viewdata-encoding`, the
reasoning in {doc}`../explanation/design-decisions`. The form API is
{py:mod}`sextile.forms`; for a plain field the reader types into, see
{doc}`accept-typed-input`.
