# Customise the not-found and failed notices

A how-to guide: give the service its own wording for the page a caller could not
reach.

```{sextile-frame}
:page: "1"
:keys: "*7#"
:show-code:

from sextile import Page, PageRequest, PageRouter, Sextile, notice_page

router = PageRouter()


@router.page("1", name="index", title="Directory")
async def index(request: PageRequest) -> Page:
    return notice_page(request, "Key a page number.")


app = Sextile(name="Directory", pages=[*router])


@app.on_not_found
async def unknown(request: PageRequest, target: str) -> Page:
    return notice_page(
        request,
        f"There is no page *{target}#.",
        "",
        "Key *1# for the index.",
        title="NO SUCH PAGE",
    )
```

`on_not_found(request, target)` registers the notice for a page the service has
not got; `on_failed(request, error)` and `on_timed_out(request, seconds)` do the
same for a handler that raised and one that ran too long. Each returns a `Page`,
so it is built with `notice_page` or any layout. The session shows it over the
page the reader was on and leaves them there — keying `*7#` above draws the notice
without moving off page `1` — so it names a way on rather than assuming one.
