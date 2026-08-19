# Link between pages

A how-to guide: reach another page by name, so a link never respells a number.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Page, PageRequest, PageRouter, Sextile, menu_page, notice_page

router = PageRouter()


@router.page("1", name="index", title="News service")
async def index(request: PageRequest) -> Page:
    app = request.app
    return menu_page(request, items=[app.menu_item("headlines"), app.menu_item("sport")])


@router.page("11", name="headlines", title="Headlines", detail="today", keywords=("NEWS",))
async def headlines(request: PageRequest) -> Page:
    return notice_page(request, "Nothing yet.")


@router.page("12", name="sport", title="Sport", keywords=("SPORT",))
async def sport(request: PageRequest) -> Page:
    return notice_page(request, "Rained off.")


app = Sextile(name="News", pages=[*router])
```

`app.menu_item("headlines")` builds a menu entry from a registered page — its
title, detail and number — so the menu shows what the page calls itself.
`app.address_for("headlines")` is the same read as a bare address, for a link that
is not a menu entry. `keywords=` gives a page a word to key instead of its number:
`*NEWS#` reaches `*11#`.

Number a page by a field of your own with {doc}`write-a-converter`. Why a page
number is one name shared by everyone, keyed and drawn alike, is in
{doc}`../explanation/design-decisions`.
