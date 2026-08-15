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
from sextile.formatting import Entry, Lines, Menu, Prose
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
    "farewell_page",
    "menu_page",
    "notice_page",
    "prose_page",
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


def prose_page(
    request: PageRequest,
    *paragraphs: str,
    title: str | None = None,
    home: _Home = _DEFAULT_HOME,
    shortcuts: Sequence[Shortcut] = (),
) -> Page:
    """A page of running text, the line breaks left to the framework.

    Args:
        request: The request this page answers.
        *paragraphs: The paragraphs, each wrapped to the frame and spaced from
            the next. A long one runs on to further frames rather than being
            cut.
        title: The header, or None to take the registered title of the page.
        home: Where `0` leads; unset takes `request.app.index`, `None` offers
            no way home.
        shortcuts: Keys offered on every frame besides the digits and `0`.

    Returns:
        The page, of as many frames as the text needed.
    """
    return PageLayout(
        title=title,
        home=home,
        shortcuts=shortcuts,
        parts=[Flowing(Prose.of(*paragraphs))],
    ).build(request)


def farewell_page(
    request: PageRequest, title: str, *lines: str, hang_up: bool = True
) -> Page:
    """The page a caller sees last, after which the line drops.

    A `notice_page` with no furniture and no way home: a footer offering the
    index would mislead on a page there is no coming back from, and the rows it
    and the rules would take are the ones worth leaving blank, the reader being
    about to talk to their modem.

    Args:
        request: The request this page answers.
        title: The heading, drawn in cyan on the first row.
        *lines: What to say, one string a row, beginning two rows below the
            title.
        hang_up: Whether the line drops once shown. False for the involuntary
            parting, where the session drops the line itself.

    Returns:
        A page of a single frame, offering no keys.
    """
    return notice_page(
        request, *lines, title=title, home=None, furniture=(), hang_up=hang_up
    )
