"""The framework's pages, as handlers a route can name directly.

Three pages come with the framework and are registered nowhere: a service
maps them into its own numbering or does without. Each is a method on the
application, which a `PageRoute` cannot name without an instance to bind it
to -- so every service was writing the same three-line passthrough, three
times over. These are those passthroughs, written once:

    PageRoute("92", pages.history, title="Where you have been")

The handler's own name becomes the route's, as for any handler, so the line
above answers `address_for("history")` without saying so.

Only the pages that need nothing but the request are here. The readership
pages want the service's own log handed over, and the guide wants the keys
only a service can know, so those keep their thin wrappers where they are
used.
"""

from sextile.application import PageRequest
from sextile.page import Page


async def history(request: PageRequest) -> Page:
    """Where this caller has been, at whatever number the service gives it."""
    return await request.app.history(request)


async def contents(request: PageRequest) -> Page:
    """Every page the service advertises, at the service's own number."""
    return await request.app.contents(request)


async def names(request: PageRequest) -> Page:
    """The words a reader can key, at the service's own number."""
    return await request.app.names(request)
