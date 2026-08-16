# Add middleware

A how-to guide: wrap every page a service builds — to time it, to log it, to say
who may reach it.

```python
import logging

from sextile import CallNext, Page, PageRequest, PageRouter, Sextile, notice_page
from sextile.middleware import log_pages

log = logging.getLogger("service")


async def announce(request: PageRequest, call_next: CallNext) -> Page | None:
    log.info("building *%s#", request.address)
    return await call_next(request)


router = PageRouter()


@router.page("1", name="index", title="Home")
async def index(request: PageRequest) -> Page:
    return notice_page(request, "Hello.")


app = Sextile(name="Service", pages=[*router], middleware=[announce, log_pages()])
```

Calling `*1#` and then a page that is not there writes:

```text
service INFO building *1#
sextile.serving INFO *1# 1 frames in 0.000s
service INFO building *2#
sextile.serving INFO *2# not here in 0.000s
```

A `Middleware` is handed the request and `CallNext`, the rest of the chain: it may
read the request, call `call_next` and change what comes back, or answer instead
and never call it. The first in the list is outermost. `log_pages` is the one the
framework ships for the log; `record_visits` is the other, feeding the readership
pages.
