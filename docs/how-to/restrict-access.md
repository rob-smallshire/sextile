# Restrict access

A how-to guide: turn callers away outside opening hours, by answering instead of
building the page they asked for.

```{sextile-frame}
:show-code:

from collections.abc import Callable
from datetime import datetime

from sextile import CallNext, Page, PageRequest, PageRouter, Sextile, notice_page

router = PageRouter()


@router.page("1", name="index", title="Booking office")
async def index(request: PageRequest) -> Page:
    return notice_page(request, "Key a service number.")


def open_between(first: int, last: int, *, now: Callable[[], datetime]) -> CallNext:
    async def hours(request: PageRequest, call_next: CallNext) -> Page | None:
        if first <= now().hour < last:
            return await call_next(request)
        return notice_page(
            request,
            "The booking office is closed.",
            "",
            f"Please call between {first:02d}:00 and {last:02d}:00.",
            title="CLOSED",
            home=None,
        )

    return hours


app = Sextile(
    name="Booking",
    pages=[*router],
    middleware=[open_between(8, 20, now=lambda: datetime(2026, 8, 19, 23, 0))],
)

frame = fetch(app, "1")
```

A middleware that returns a `Page` without calling `call_next` answers instead of
the handler, so every page it guards shows this frame and no page is built behind
it. It is outermost in `middleware=[...]`, so it decides before any inner
middleware or the page runs. Restrict some pages and not others by testing
`request.address` before you refuse, and take the caller's identity from
`request.session`, which lasts exactly as long as their line —
{doc}`remember-a-caller` keeps state there.

Why the framework offers no sign-in of its own: who may reach a page is the
service's policy, and the chain gives it the place to enforce one. The moves and
the order are in {doc}`../explanation/middleware`; wording a notice is
{doc}`customise-notices`.
