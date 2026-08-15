"""The framework's own pages as handlers, and one call to route them all.

The pure page builders are in `sextile.builtin`, taking exactly what they draw.
The functions here gather what each needs from `request.app` -- the route's
title, how to label a visited address, the service's index -- and are the
`(request) -> Page` handlers a service routes. Registered nowhere: a service
maps each into its own numbering or does without.

`guide_page` is called directly, because the rows it adds are the service's own.
The rest are routed through `standard_pages`, which returns the routes for
whichever of these a service gives a number, each carrying the framework's own
title, detail and keywords, so a service names the page once and retypes
nothing::

    Sextile(pages=[*my_pages, *standard_pages(history="92", contents="93", keywords="94")])

The readership pages -- what has been read lately, most, and how many have
called -- read the service's own visit log, so they are given the `StateKey`
the log is held under, the same key a service hands `record_visits`.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta

from sextile.builtin import contents as _contents
from sextile.builtin import guidance as _guidance
from sextile.builtin import history as _history
from sextile.builtin import names as _names
from sextile.builtin import readership as _readership
from sextile.layout import CHOICES_PER_FRAME
from sextile.page import Page
from sextile.pages import notice_page
from sextile.requests import PageRequest
from sextile.routing import Handler, PageRoute
from sextile.state import StateKey
from sextile.visits import Visits

__all__ = [
    "callers",
    "callers_page",
    "contents",
    "contents_page",
    "guide_page",
    "history",
    "history_page",
    "keywords",
    "keywords_page",
    "popular",
    "popular_page",
    "recent",
    "recent_page",
    "standard_pages",
]

#: Said in place of a readership page where the service keeps no log. A service
#: that runs without one is offering the page but has nothing to fill it, which
#: a reader cannot tell from a fault unless the page says so.
_NO_LOG = "No log of what has been looked up is kept here."


#  Each of these builds one framework page from the request it answers,
#  gathering what the page needs from `request.app` -- the title the route was
#  given, how to label a visited address, the service's own index -- and handing
#  it to the pure builder in `sextile.builtin`. They were methods on `Sextile`;
#  as free functions the application object stays a router and answerer, and a
#  service reaches a framework page the same way it reaches any handler.


async def history_page(request: PageRequest) -> Page:
    """Where this caller has been, newest first, as a menu of shortcuts.

    Key 1 for the page before this one -- the same as `*0#` -- 2 for the one
    before that, and so on. Registered nowhere: a service maps it into its own
    numbering with `standard_pages`, or does not offer it at all.
    """
    app = request.app
    return _history.history_page(
        request=request,
        been=request.history,
        label=app.label_for,
        title=(app.title_for(request.address) or _history.TITLE).upper(),
    )


async def contents_page(request: PageRequest) -> Page:
    """Every page this service advertises, with the number that fetches it.

    Pages with fields are listed as `*52<user_id>#` rather than enumerated:
    nobody can list every user on a screen, and everybody holding a user number
    can be told where to put it.
    """
    app = request.app
    return _contents.contents_page(
        request=request,
        pages=app.routes(),
        title=(app.title_for(request.address) or _contents.TITLE).upper(),
    )


async def keywords_page(request: PageRequest) -> Page:
    """The words a reader can key in place of a page number.

    Generated from the service's keywords, so it cannot drift from what the
    service answers.
    """
    app = request.app
    return _names.names_page(
        request=request,
        named=app.keywords(),
        label=app.label_for,
        title=(app.title_for(request.address) or _names.TITLE).upper(),
    )


async def guide_page(
    request: PageRequest,
    *,
    moving_rows: Sequence[_guidance.GuideRow] = (),
    asking_rows: Sequence[_guidance.GuideRow] = (),
    show_item_keys: bool = True,
) -> Page:
    """How to get about, as a table of the keys this service answers.

    The framework's own keys -- the digits, the way home, the syntax of a
    request, the key that turns a page -- are drawn from what it already knows.
    A service adds through `moving_rows` and `asking_rows` the rows only it can
    supply: the keys a particular page answers, such as a letter typed into a
    field, or a single key such as `F`.

    Args:
        request: The request this page answers.
        moving_rows: The service's own rows about moving about, joining the
            first frame after the framework's.
        asking_rows: The service's own rows about asking for something, joining
            the second frame.
        show_item_keys: Whether the compass shows `A` and `D`. False for a
            service that does not wire them to `request.neighbours` and so does
            not answer them.

    Returns:
        The guide, as two frames of keys.
    """
    app = request.app
    #  The framework draws its own keys so the guide cannot drift from them. The
    #  `0` row takes its words from the index page's own title, so it reads "back
    #  to the main menu" or "the main index" as that page is titled, and the two
    #  cannot disagree.
    return _guidance.guide_page(
        request=request,
        title=(app.title_for(request.address) or _guidance.TITLE).upper(),
        home_label=app.label_for(app.index).lower(),
        moving_rows=moving_rows,
        asking_rows=asking_rows,
        show_item_keys=show_item_keys,
    )


async def recent_page(
    request: PageRequest,
    visits: Visits,
    *,
    limit: int = CHOICES_PER_FRAME,
    prefix: str = "",
) -> Page:
    """What has been looked at lately, as a menu of where to look.

    Args:
        request: The request this page answers.
        visits: The log to read.
        limit: How many to show, defaulting to the nine a frame holds. More than
            that runs on to further frames.
        prefix: Narrows it to a namespace of the numbering, so a service can ask
            for one namespace's pages alone.

    Returns:
        A menu of the pages looked at lately, newest first.
    """
    app = request.app
    return _readership.recent_page(
        request=request,
        visits=await visits.recent(limit, prefix=prefix),
        label=app.label_for,
        title=(app.title_for(request.address) or _readership.RECENT_TITLE).upper(),
    )


async def popular_page(
    request: PageRequest,
    visits: Visits,
    *,
    limit: int = CHOICES_PER_FRAME,
    prefix: str = "",
    since: datetime | None = None,
) -> Page:
    """What has been looked at most, as a menu of where to look.

    Args:
        request: The request this page answers.
        visits: The log to read.
        limit: How many to show, defaulting to the nine a frame holds. More than
            that runs on to further frames.
        prefix: Narrows it to a namespace of the numbering.
        since: Counts only what has been read since then, for "most read lately"
            rather than most read ever.

    Returns:
        A menu of the pages looked at most, the most read first.
    """
    app = request.app
    return _readership.popular_page(
        request=request,
        visits=await visits.popular(limit, prefix=prefix, since=since),
        label=app.label_for,
        title=(app.title_for(request.address) or _readership.POPULAR_TITLE).upper(),
    )


async def callers_page(
    request: PageRequest,
    visits: Visits,
    *,
    periods: Sequence[tuple[timedelta, str]] = _readership.PERIODS,
) -> Page:
    """How many have called, over each of a few periods.

    A count of connections rather than of anybody. `periods` is the service's to
    choose; a period longer than the log's retention simply reads low.
    """
    when = datetime.now(UTC)
    app = request.app
    return _readership.callers_page(
        request=request,
        counts=[
            (said, await visits.callers(since=when - window))
            for window, said in periods
        ],
        title=(app.title_for(request.address) or _readership.CALLERS_TITLE).upper(),
    )


async def history(request: PageRequest) -> Page:
    """Where this caller has been, at whatever number the service gives it."""
    return await history_page(request)


async def contents(request: PageRequest) -> Page:
    """Every page the service advertises, at the service's own number."""
    return await contents_page(request)


async def keywords(request: PageRequest) -> Page:
    """The words a reader can key, at the service's own number."""
    return await keywords_page(request)


def recent(visits: StateKey[Visits]) -> Handler:
    """A handler for the pages looked at lately, reading `visits` from the log."""

    async def handler(request: PageRequest) -> Page:
        log = request.state.get(visits)
        if log is None:
            return notice_page(request, _NO_LOG)
        return await recent_page(request, log)

    return handler


def popular(visits: StateKey[Visits]) -> Handler:
    """A handler for the pages looked at most, reading `visits` from the log."""

    async def handler(request: PageRequest) -> Page:
        log = request.state.get(visits)
        if log is None:
            return notice_page(request, _NO_LOG)
        return await popular_page(request, log)

    return handler


def callers(visits: StateKey[Visits]) -> Handler:
    """A handler for how many have called, reading `visits` from the log."""

    async def handler(request: PageRequest) -> Page:
        log = request.state.get(visits)
        if log is None:
            return notice_page(request, _NO_LOG)
        return await callers_page(request, log)

    return handler


#: The framework's own words for each standard page: its route title, the detail
#: shown where it is listed, and the keywords that reach it. A service takes
#: these rather than retyping them, so a change here reaches every service.
_PLAIN: dict[str, tuple[Handler, str, str, tuple[str, ...]]] = {
    "history": (history, "Where you have been", "this call, newest first", ("HISTORY", "BEEN")),
    "contents": (contents, "Every page", "and the number that fetches it", ("PAGES", "CONTENTS")),
    "keywords": (keywords, "Words you can key", "instead of a page number", ("KEYWORDS", "WORDS")),
}
_LOGGED: dict[str, tuple[Callable[[StateKey[Visits]], Handler], str, str, tuple[str, ...]]] = {
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
    visits: StateKey[Visits] | None = None,
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
        visits: The `StateKey` the visit log is held under, which `recent`,
            `popular` and `callers` read; the same key a service hands
            `record_visits`.

    Returns:
        A `PageRoute` for each page given a number, in the order named above.

    Raises:
        ValueError: If `recent`, `popular` or `callers` is given without
            `visits` to read the log from.
    """
    numbered_logs = {"recent": recent, "popular": popular, "callers": callers}
    if any(numbered_logs.values()) and visits is None:
        raise ValueError(
            "recent, popular and callers each need the visit-log key; pass visits="
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
