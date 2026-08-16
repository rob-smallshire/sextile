# Accept typed input

A how-to guide: a field a reader types a name into, with the best few matches
listed beneath it, updating at each keystroke.

```{sextile-frame}
:page: "3"
:keys: "TRO"
:show-code:

from collections.abc import Sequence

from sextile import Lines, MenuItem, OnOneFrame, Page, PageLayout, PageRequest, PageRouter, Sextile, notice_page
from sextile.forms import TypeAhead

router = PageRouter()

_PLACES = ["Trondheim", "Tromsø", "Troon", "Truro", "Oslo", "Bergen"]


@router.page("3", name="search", title="Find a place")
async def search(request: PageRequest) -> Page:
    app = request.app

    async def lookup(typed: str) -> Sequence[MenuItem]:
        matches = [name for name in _PLACES if name.upper().startswith(typed.upper())]
        return [
            MenuItem(text=name, detail="", destination=app.address_for("place"))
            for name in matches[:3]
        ]

    field = TypeAhead(lookup=lookup, label="PLACE:", no_match="No place of that name.")
    return PageLayout(
        parts=[OnOneFrame(Lines(("Key a place name.", ""))), OnOneFrame(field)],
    ).build(request)


@router.page("31", name="place", title="Place")
async def place(request: PageRequest) -> Page:
    return notice_page(request, "Here is the forecast.")


app = Sextile(name="Weather", pages=[*router])
```

A `TypeAhead` is a menu whose choices change as you type: `lookup` is awaited with
what has been keyed and returns the entries to suggest, letters type into the
field, and a digit chooses the numbered match — leading wherever that entry's
`destination` says. For several fields with one live at a time, and a submit, use
a `FieldSet` of `Field`. The list shows three, which is what a 1200-baud line
affords between keystrokes.
