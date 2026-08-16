# End the call

A how-to guide: a page that says goodbye and drops the line.

```{sextile-frame}
:page: "90"
:show-code:

from sextile import Page, PageRequest, PageRouter, Sextile, farewell_page

router = PageRouter()


@router.page("90", name="goodbye", title="Log off", keywords=("BYE",))
async def goodbye(request: PageRequest) -> Page:
    return farewell_page(request, "GOODBYE", "Thank you for calling.", "", "Ring off.")


app = Sextile(name="Service", pages=[*router])
```

`farewell_page` is the shape for the last page a caller sees: it offers no way
home, there being none to come back from, and drops the line once it has been
shown. Pass `hang_up=False` to show it without releasing the line — for a parting
the session itself is about to make.
