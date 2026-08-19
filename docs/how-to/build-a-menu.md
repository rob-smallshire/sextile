# List more than nine items

A how-to guide: a menu numbers its entries `1`–`9`, so a longer list runs on to
further frames a reader pages through.

```{sextile-frame}
:page: "1"
:frames: a,b
:show-code:

from sextile import MenuItem, Page, PageRequest, PageRouter, Sextile, menu_page

router = PageRouter()

_PLACES = [
    "Aberdeen", "Belfast", "Cardiff", "Dover", "Exeter", "Glasgow", "Hull",
    "Ipswich", "Leeds", "Manchester", "Norwich", "Oxford", "Perth", "York",
]


@router.page("1", name="places", title="Places", keywords=("PLACES",))
async def places(request: PageRequest) -> Page:
    return menu_page(
        request,
        items=[MenuItem(name, "", request.app.address_for("places")) for name in _PLACES],
    )


app = Sextile(name="Gazetteer", pages=[*router])
```

`menu_page` takes as many entries as you give it and lays out nine to a frame,
carrying the rest onto the next. The footer names `S` and `W` to page down and up;
`#` turns the frame too. Nothing above has to know how many frames there will be.

A menu is a `Part` the layout paginates; the parts model is in
{doc}`../reference/layout`, and why a page carries its choices per frame is in
{doc}`../explanation/design-decisions`.
