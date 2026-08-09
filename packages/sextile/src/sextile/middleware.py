"""Things worth wrapping round every page.

Middleware answers what is true of every page, where a handler answers what one
page says. The framework ships the one that every service turns out to want and
nothing else: what a service should log about itself is not a question a
framework can answer, but *that* it should log something is not in doubt.

Written as functions returning middleware rather than as classes, because each
of them is one closure over one setting and a class would be four lines of
ceremony round it.
"""

import logging
import time
from collections.abc import Callable
from typing import Final

from sextile.application import Middleware, Next, PageRequest
from sextile.page import Page

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
    log = logger or logging.getLogger("sextile.pages")

    async def timing(request: PageRequest, build: Next) -> Page | None:
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
