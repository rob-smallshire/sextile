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
like the message. Keying a page the service has not got shows the same notice:

```{sextile-frame}
import asyncio

from sextile import Page, PageRequest, PageRouter, Sextile, menu_page
from sextile.testing import request_for

router = PageRouter()


@router.page("1", name="inbox", title="Inbox")
async def inbox(request: PageRequest) -> Page:
    return menu_page(request, items=[], empty=["No messages."])


app = Sextile(name="Mail", pages=[*router])


async def _missing() -> Page:
    await app.startup()
    page = await app.not_found(request_for(app, app.index), "7")
    await app.shutdown()
    return page


page = asyncio.run(_missing())
```
