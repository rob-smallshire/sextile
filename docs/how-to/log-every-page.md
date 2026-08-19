# Log every page

A how-to guide: write a line to the log for each page a service builds, and how
long it took.

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

`log_pages` is the framework's own timing middleware: it names each page and its
build time, and logs a build past `slow=` seconds as a warning, so a slow build
is told apart from a slow wire. `announce` is one of your own — the inspect move,
reading the request and calling `call_next` — and the first in the list is
outermost, so it runs before `log_pages`. The chain, its order and the other two
moves are in {doc}`../explanation/middleware`.
