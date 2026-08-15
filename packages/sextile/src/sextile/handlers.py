"""The framework's own pages as handlers, and one call to route them all.

The pages themselves are in `sextile.builtin`, and are registered nowhere: a
service maps them into its own numbering or does without. Each is reached
through a method on the application, which a `PageRoute` cannot name without an
instance to bind it to. These handlers are that binding.

`standard_pages` is the one line most services want: it returns the routes for
whichever of these the service gives a number, carrying the framework's own
title, detail and keywords so a service need not retype them.

    Sextile(pages=[*my_pages, *standard_pages(history="92", contents="93", keywords="94")])

The readership pages -- what has been read lately, most, and how many have
called -- read the service's own visit log, so they are given a `Finder` for
it, the same `held_in(name)` a service already hands `record_visits`.
"""

from collections.abc import Callable

from sextile.declarations import Handler, PageRoute
from sextile.middleware import Finder
from sextile.page import Page
from sextile.pages import notice_page
from sextile.requests import PageRequest

__all__ = [
    "callers",
    "contents",
    "history",
    "keywords",
    "popular",
    "recent",
    "standard_pages",
]

#: Said in place of a readership page where the service keeps no log. A service
#: that runs without one is offering the page but has nothing to fill it, which
#: a reader cannot tell from a fault unless the page says so.
_NO_LOG = "No log of what has been looked up is kept here."


async def history(request: PageRequest) -> Page:
    """Where this caller has been, at whatever number the service gives it."""
    return await request.app.history_page(request)


async def contents(request: PageRequest) -> Page:
    """Every page the service advertises, at the service's own number."""
    return await request.app.contents_page(request)


async def keywords(request: PageRequest) -> Page:
    """The words a reader can key, at the service's own number."""
    return await request.app.keywords_page(request)


def recent(visits: Finder) -> Handler:
    """A handler for the pages looked at lately, reading `visits` from the log."""

    async def handler(request: PageRequest) -> Page:
        log = visits(request)
        if log is None:
            return notice_page(request, _NO_LOG)
        return await request.app.recent_page(request, log)

    return handler


def popular(visits: Finder) -> Handler:
    """A handler for the pages looked at most, reading `visits` from the log."""

    async def handler(request: PageRequest) -> Page:
        log = visits(request)
        if log is None:
            return notice_page(request, _NO_LOG)
        return await request.app.popular_page(request, log)

    return handler


def callers(visits: Finder) -> Handler:
    """A handler for how many have called, reading `visits` from the log."""

    async def handler(request: PageRequest) -> Page:
        log = visits(request)
        if log is None:
            return notice_page(request, _NO_LOG)
        return await request.app.callers_page(request, log)

    return handler


#: The framework's own words for each standard page: its route title, the detail
#: shown where it is listed, and the keywords that reach it. A service takes
#: these rather than retyping them, so a change here reaches every service.
_PLAIN: dict[str, tuple[Handler, str, str, tuple[str, ...]]] = {
    "history": (history, "Where you have been", "this call, newest first", ("HISTORY", "BEEN")),
    "contents": (contents, "Every page", "and the number that fetches it", ("PAGES", "CONTENTS")),
    "keywords": (keywords, "Words you can key", "instead of a page number", ("KEYWORDS", "WORDS")),
}
_LOGGED: dict[str, tuple[Callable[[Finder], Handler], str, str, tuple[str, ...]]] = {
    "recent": (recent, "Pages lately read", "this call and before", ("READ",)),
    "popular": (popular, "Pages read most", "the most read first", ("POPULAR",)),
    "callers": (callers, "Who has called", "over the last few periods", ("CALLERS",)),
}


def standard_pages(
    *,
    history: str | None = None,
    contents: str | None = None,
    keywords: str | None = None,
    recent: str | None = None,
    popular: str | None = None,
    callers: str | None = None,
    visits: Finder | None = None,
) -> tuple[PageRoute, ...]:
    """Routes for the framework's own pages, at whatever numbers a service gives.

    Each argument is the page number to route that page at, or None to leave it
    out. The route carries the framework's own title, detail and keywords, so a
    service names the page once, by its number, and retypes nothing.

    Args:
        history: Where the caller has been this call.
        contents: Every page the service advertises.
        keywords: The words a reader can key in place of a number.
        recent: What has been looked at lately.
        popular: What has been looked at most.
        callers: How many have called.
        visits: How to find the visit log from a request, which `recent`,
            `popular` and `callers` read. The `held_in(name)` a service hands
            `record_visits` is one.

    Returns:
        A `PageRoute` for each page given a number, in the order named above.

    Raises:
        ValueError: If `recent`, `popular` or `callers` is given without
            `visits` to read the log from.
    """
    numbered_logs = {"recent": recent, "popular": popular, "callers": callers}
    if any(numbered_logs.values()) and visits is None:
        raise ValueError(
            "recent, popular and callers each need a visits finder; pass visits="
        )
    routes = []
    for name, number in (("history", history), ("contents", contents), ("keywords", keywords)):
        if number is not None:
            handler, title, detail, words = _PLAIN[name]
            routes.append(
                PageRoute(number, handler, name=name, title=title, detail=detail, keywords=words)
            )
    for name, number in numbered_logs.items():
        if number is not None:
            assert visits is not None  # the guard above, restated for the type checker
            factory, title, detail, words = _LOGGED[name]
            routes.append(
                PageRoute(
                    number, factory(visits), name=name, title=title, detail=detail, keywords=words
                )
            )
    return tuple(routes)
