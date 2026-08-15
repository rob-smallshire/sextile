"""One-call page shapes: the commonest Viewdata pages, each said in a call.

A notice, a menu, some prose. Each takes the request the page answers and
builds a `PageLayout`, so the title, the way home and the page number default
from the request exactly as they do for the layout underneath, and a page that
outgrows the one-call form graduates to a full `PageLayout` without changing
shape.

    async def now(request: PageRequest) -> Page:
        return notice_page(request, "It is noon.")

The framework's own notices are these too: `Sextile.not_found`, `.failed` and
`.timed_out` build a `notice_page` with `furniture=()`.
"""

from collections.abc import Sequence

from sextile.addressing import PageAddress
from sextile.formatting import Entry, Lines, Menu
from sextile.layout import (
    _DEFAULT_HOME,
    DEFAULT_FURNITURE,
    Flowing,
    Furnishing,
    Once,
    PageLayout,
    Shortcut,
    _DefaultHome,
)
from sextile.page import Page
from sextile.requests import PageRequest
from sextile.viewdata.controls import Colour

__all__ = [
    "menu_page",
    "notice_page",
]

#: What a page's `home` is when the caller leaves it unset: the app's index,
#: filled in by `PageLayout.build`. The same sentinel the layout uses, so a
#: page shape and a raw layout default the way home identically.
type _Home = PageAddress | Shortcut | None | _DefaultHome


def notice_page(
    request: PageRequest,
    *lines: str,
    title: str | None = None,
    home: _Home = _DEFAULT_HOME,
    numbered: bool = True,
    shortcuts: Sequence[Shortcut] = (),
    hang_up: bool = False,
    furniture: Sequence[Furnishing] = DEFAULT_FURNITURE,
) -> Page:
    """A page that simply says something.

    Args:
        request: The request this page answers.
        *lines: What to say, one string a row; empty strings leave a blank row.
        title: The header, or None to take the registered title of the page.
        home: Where `0` leads; unset takes `request.app.index`, `None` offers
            no way home.
        numbered: Whether the header shows the page number. `False` for a
            notice answering a request that names no page of its own.
        shortcuts: Keys offered on every frame besides the digits and `0`.
        hang_up: Whether the line drops once the page has been shown.
        furniture: The bands round the content. `()` draws a masthead-style
            notice with no header or footer, where the title heads the content
            in cyan instead; this is how the framework says things for itself.

    Returns:
        The page, of as many frames as the lines needed.
    """
    if furniture:
        return PageLayout(
            title=title,
            home=home,
            numbered=numbered,
            shortcuts=shortcuts,
            hang_up=hang_up,
            furniture=furniture,
            parts=[Flowing(Lines(said=lines))],
        ).build(request)
    #  No header to carry the title, so it heads the content in cyan and the
    #  lines follow a blank row down -- the plain notice the framework draws
    #  for itself, kept to the top rows with room beneath for the cursor.
    heading = [Once(Lines(said=(title,), colour=Colour.CYAN))] if title else []
    return PageLayout(
        home=home,
        shortcuts=shortcuts,
        hang_up=hang_up,
        furniture=(),
        parts=[*heading, Once(Lines(said=("", *lines)))],
    ).build(request)


def menu_page(
    request: PageRequest,
    *,
    items: Sequence[Entry],
    title: str | None = None,
    home: _Home = _DEFAULT_HOME,
    preamble: Sequence[str] = (),
    empty: str | None = None,
    shortcuts: Sequence[Shortcut] = (),
    item: str = "item",
) -> Page:
    """A menu: a list of choices, nine to a frame, each numbered 1-9.

    Args:
        request: The request this page answers.
        items: The choices, anything satisfying `Entry`; `MenuItem` is the
            ready-made one. A service with a richer type of its own passes it
            directly.
        title: The header, or None to take the registered title of the page.
        home: Where `0` leads; unset takes `request.app.index`, `None` offers
            no way home.
        preamble: Lines shown once on the first frame, above the entries, with
            a blank row between.
        empty: Said in place of the entries where there are none, so an empty
            menu explains itself rather than looking like a fault. None leaves
            the frame blank.
        shortcuts: Keys offered on every frame besides the digits and `0`.
        item: What `A` and `D` move between, as the footer names it.

    Returns:
        The page, of as many frames as the entries needed.
    """
    lead = [Once(Lines(said=(*preamble, "")))] if preamble else []
    return PageLayout(
        title=title,
        home=home,
        shortcuts=shortcuts,
        item=item,
        parts=[*lead, Flowing(Menu(entries=items, empty=empty or ""))],
    ).build(request)
