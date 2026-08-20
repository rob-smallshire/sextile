# Remember a caller

A how-to guide: keep something for one caller across the pages they visit — here,
a bookmark on each page they mark, listed back on a page of their own.

```{sextile-frame}
:page: "11"
:show-code:

from collections.abc import Sequence

from sextile import (
    MenuItem, Page, PageAddress, PageRequest, PageRouter, Sextile, Shortcut,
    StateKey, menu_page, notice_page,
)

BOOKMARKS = StateKey[list[PageAddress]]("bookmarks")

_ITEMS = {1: "Weather", 2: "News", 3: "Sport"}

router = PageRouter()


@router.page("1{n:int}", name="item", title="Page")
async def item(request: PageRequest, n: int) -> Page | None:
    name = _ITEMS.get(n)
    if name is None:
        return None
    keep = request.app.address_for("keep", n=n)
    return notice_page(
        request, name, title=name,
        shortcuts=[Shortcut(key="B", destination=keep, label="bookmark")],
    )


@router.page("2{n:int}", name="keep")
async def keep(request: PageRequest, n: int) -> Page:
    marked = request.session.get(BOOKMARKS) or []
    here = request.app.address_for("item", n=n)
    if here not in marked:
        request.session[BOOKMARKS] = [*marked, here]
    return notice_page(request, "Bookmarked.", shortcuts=[Shortcut("9", request.app.address_for("bookmarks"), label="bookmarks")])


@router.page("9", name="bookmarks", title="Your bookmarks", keywords=("MARKS",))
async def bookmarks(request: PageRequest) -> Page:
    marked: Sequence[PageAddress] = request.session.get(BOOKMARKS) or []
    items = [MenuItem(_ITEMS[int(address.digits[1:])], "", address) for address in marked]
    return menu_page(request, items=items, empty=["No bookmarks yet.", "", "Press B on a page to keep it."])


app = Sextile(name="Bookmarks", pages=[*router])
```

`Shortcut(key="B", destination=...)` offers `B` on every frame of the item page,
leading to the `keep` page for that item. `keep`'s handler appends the item's
address to `request.session[BOOKMARKS]` — the caller's own store, read with
`.get(BOOKMARKS) or []` for the first visit — so the next page sees the mark.

Pressing `B` on two pages and then keying `*9#` lists them:

```{sextile-frame}
:page: "11"
:keys: "B*12#B*9#"

from collections.abc import Sequence

from sextile import (
    MenuItem, Page, PageAddress, PageRequest, PageRouter, Sextile, Shortcut,
    StateKey, menu_page, notice_page,
)

BOOKMARKS = StateKey[list[PageAddress]]("bookmarks")

_ITEMS = {1: "Weather", 2: "News", 3: "Sport"}

router = PageRouter()


@router.page("1{n:int}", name="item", title="Page")
async def item(request: PageRequest, n: int) -> Page | None:
    name = _ITEMS.get(n)
    if name is None:
        return None
    keep = request.app.address_for("keep", n=n)
    return notice_page(
        request, name, title=name,
        shortcuts=[Shortcut(key="B", destination=keep, label="bookmark")],
    )


@router.page("2{n:int}", name="keep")
async def keep(request: PageRequest, n: int) -> Page:
    marked = request.session.get(BOOKMARKS) or []
    here = request.app.address_for("item", n=n)
    if here not in marked:
        request.session[BOOKMARKS] = [*marked, here]
    return notice_page(request, "Bookmarked.", shortcuts=[Shortcut("9", request.app.address_for("bookmarks"), label="bookmarks")])


@router.page("9", name="bookmarks", title="Your bookmarks", keywords=("MARKS",))
async def bookmarks(request: PageRequest) -> Page:
    marked: Sequence[PageAddress] = request.session.get(BOOKMARKS) or []
    items = [MenuItem(_ITEMS[int(address.digits[1:])], "", address) for address in marked]
    return menu_page(request, items=items, empty=["No bookmarks yet.", "", "Press B on a page to keep it."])


app = Sextile(name="Bookmarks", pages=[*router])
```

Why the bookmarks are the caller's and not the service's: `request.session` is
one caller's own store, `request.state` the shared one the lifespan opened. The
session is the connection, so the bookmarks last exactly as long as the line is
up and are gone when the caller rings off — nothing is kept between calls,
because a viewdata terminal keeps nothing but the frame on screen. That is the
Viewdata model, not a limitation of the framework; {doc}`../explanation/why-sextile`
says why the state lives at the server and dies with the line. To keep something
past ring-off, write it to a service database from `request.state` instead — the
readership log in {doc}`the-visits-log` is the pattern.
