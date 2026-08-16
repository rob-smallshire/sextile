# Customise the not-found and failed notices

A how-to guide: give the service its own wording for the page a caller could not
reach.

```{sextile-frame}
:hide-lines: 1,17-27
:show-code:

import asyncio

from sextile import Page, PageRequest, Sextile, notice_page
from sextile.testing import request_for

app = Sextile(name="Directory")


@app.on_not_found
async def unknown(request: PageRequest, target: str) -> Page:
    return notice_page(
        request,
        f"There is no page *{target}#.",
        "",
        "Key *1# for the index.",
        title="NO SUCH PAGE",
    )


async def _notice() -> Page:
    await app.startup()
    page = await app.not_found(request_for(app, app.index), "7")
    await app.shutdown()
    return page


page = asyncio.run(_notice())
```

`on_not_found(request, target)` registers the notice for a page the service has
not got; `on_failed(request, error)` and `on_timed_out(request, seconds)` do the
same for a handler that raised and one that ran too long. Each returns a `Page`, so it is
built with `notice_page` or any layout. The session shows it and leaves the reader
where they were, so it names a way on rather than assuming one.
