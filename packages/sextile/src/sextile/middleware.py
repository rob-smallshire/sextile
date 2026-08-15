"""Middleware: what wraps every page, and the two the framework ships.

`Middleware` is the type and `CallNext` the rest of the chain it is handed;
`chained` composes a sequence of them round a page builder. Middleware answers
what is true of every page, where a handler answers what one page says. The
framework ships the two that every service turns out to want and nothing else:
what a service should log about itself is not a question a framework can answer,
but *that* it should log something is not in doubt.

`log_pages` writes to the machine's log, for whoever runs the service.
`record_visits` writes to a log the service can read back, for whoever reads
it -- a list of what has been looked at lately is a page, not a diagnostic.

Written as functions returning middleware rather than as classes, because each
of them is one closure over one setting and a class would be four lines of
ceremony round it.
"""

import logging
import secrets
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Final

from sextile.page import Page
from sextile.requests import PageRequest
from sextile.state import StateKey
from sextile.visits import Visits

__all__ = [
    "CallNext",
    "Middleware",
    "log_pages",
    "record_visits",
]


type CallNext = Callable[[PageRequest], Awaitable[Page | None]]

type Middleware = Callable[[PageRequest, CallNext], Awaitable[Page | None]]
"""Something wrapped round every page a service builds.

A page handler answers what one page *says*; middleware answers what is true
of every page -- who is asking, how long it took, whether they may. It is
given the request and the rest of the chain, and may look, may change what
comes back, or may answer instead and never call it at all.

The framework deliberately has no opinion about authentication, and this is
why it does not need one: a service that wants it wraps its pages.
"""


def _wrap(middleware: Middleware, build: CallNext) -> CallNext:
    """Bind one middleware to the rest of the chain below it.

    A function rather than a closure written in place, so that it captures this
    iteration's values rather than the last iteration's.
    """

    async def wrapped(request: PageRequest) -> Page | None:
        return await middleware(request, build)

    return wrapped


def chained(build: CallNext, middleware: Sequence[Middleware]) -> CallNext:
    """`build` with `middleware` wrapped round it, outermost first.

    Args:
        build: The page builder at the bottom of the chain.
        middleware: The middleware to wrap round it, the first given outermost.

    Returns:
        A `CallNext` that enters the outermost middleware and reaches `build`
        at the bottom.

    Composed per request rather than once, which costs a closure apiece and
    buys the obvious thing: middleware may be added to an application that has
    already answered something, and a service assembled in pieces does not have
    to know it has finished being assembled.
    """
    #  Reversed, so that the first given is the outermost: a reader of the list
    #  should see a request entering at the top and leaving at the bottom.
    for one in reversed(middleware):
        build = _wrap(one, build)
    return build

#: Longer than this and the page is worth naming in the log by itself. A frame
#: takes eight seconds to send at 1200 baud, so a page that takes a second to
#: *build* is not yet the reader's problem -- but it is on its way to being.
SLOW: Final = 1.0


def log_pages(
    logger: logging.Logger | None = None,
    *,
    slow: float = SLOW,
    clock: Callable[[], float] = time.monotonic,
) -> Middleware:
    """Log every page a service builds, and how long it took.

    On a board where a frame takes eight seconds to reach the reader, "it felt
    slow" is not evidence: the wire and the page are indistinguishable from the
    far end of a telephone line. This separates them. Anything past ``slow`` is
    logged as a warning, since a page that is slow to build is slow before the
    wire has been asked to do anything at all.

    A page that is not there is logged too. A count of pages built that quietly
    omitted the ones nobody could reach would be the wrong count.
    """
    log = logger or logging.getLogger("sextile.serving")

    async def timing(request: PageRequest, build: CallNext) -> Page | None:
        began = clock()
        page = await build(request)
        took = clock() - began
        frames = 0 if page is None else len(page.frames)
        #  Logged at the level the *duration* deserves rather than the level
        #  the outcome deserves: a missing page is ordinary, and a page that
        #  took four seconds to decide it was missing is not.
        log.log(
            logging.WARNING if took >= slow else logging.INFO,
            "*%s# %s in %.3fs",
            request.address,
            f"{frames} frames" if page is not None else "not here",
            took,
        )
        return page

    return timing


def _token() -> str:
    """An opaque name for one connection, and nothing about who is on it."""
    return secrets.token_hex(8)


#: What a caller's token is kept under, in what that caller has accumulated.
#: The session's, so it lasts exactly as long as their line and goes when they
#: ring off.
CALLER: Final = "sextile.caller"


def record_visits(
    visits: StateKey[Visits], *, token: Callable[[], str] = _token
) -> Middleware:
    """Note every page a service builds, for the pages that read the log back.

    Takes the `StateKey` the service's log is held under. A service opens its
    log in its lifespan -- where a thing that has to be closed belongs -- so
    there is no log to hand over when the middleware is made; it hands over the
    key, and the log is read from `request.state` per page.

    The caller is a token minted the first time this middleware sees a session
    and kept in the session after -- so counting readers can say how many and
    nothing about who. Nothing identifying is asked for and nothing is stored:
    a service that keeps what it does not need is a service that has to be
    trusted about it.

    A page that was not there is recorded too. A count of pages fetched that
    quietly omitted the ones nobody could reach would be the wrong count, and
    the numbers readers key wrongly are worth knowing; they are left out of
    what is read back rather than left out of the log.
    """

    async def recording(request: PageRequest, build: CallNext) -> Page | None:
        page = await build(request)
        log = request.state.get(visits)
        if log is None:
            #  A service that offered a lookup and holds nothing under it. The
            #  page has already been built and the reader is owed it, so the
            #  visit goes unrecorded rather than the page going unsent.
            return page
        caller = request.session.get(CALLER)
        if not isinstance(caller, str):
            caller = token()
            request.session[CALLER] = caller
        await log.record(request.address, caller=caller, found=page is not None)
        return page

    return recording




