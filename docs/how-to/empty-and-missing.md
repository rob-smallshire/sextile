# An empty list, and a missing page

A how-to guide: a menu with nothing in it explains itself; a page that is not
there returns `None`, and the session says so without moving the reader.

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Page, PageRequest, PageRouter, Sextile, menu_page

router = PageRouter()


@router.page("1", name="inbox", title="Inbox")
async def inbox(request: PageRequest) -> Page:
    messages: list[str] = []  # none today
    return menu_page(
        request,
        items=[],
        empty=["No messages.", "", "Nothing has come in yet."],
    )


app = Sextile(name="Mail", pages=[*router])
```

An empty menu on a service that answers slowly reads as a fault unless it says
otherwise, so `menu_page(empty=[...])` draws the reason where the entries would go —
a string for one row, a sequence for several.

A page that could exist but does not — a message the archive has not got — is a
different thing. Return `None`, and the session shows the service's not-found
notice and leaves the reader where they were; do not draw a blank page that looks
like the message. Keying `*7#`, a page this service has not got, shows the notice
over the inbox — the reader's next key works from the inbox still:

```{sextile-frame}
:page: "1"
:keys: "*7#"

from sextile import Page, PageRequest, PageRouter, Sextile, menu_page

router = PageRouter()


@router.page("1", name="inbox", title="Inbox")
async def inbox(request: PageRequest) -> Page:
    return menu_page(request, items=[], empty=["No messages."])


app = Sextile(name="Mail", pages=[*router])
```

Why a missing page returns `None` rather than a notice, and how that differs from
a page that failed, is in {doc}`../explanation/design-decisions`. Give the
not-found notice the service's own words with {doc}`customise-notices`.
