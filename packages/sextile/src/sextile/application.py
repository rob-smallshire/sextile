"""The interface between the framework and whatever is running on it.

An application answers page requests. `Sextile` answers them by routing, which
is the shape almost every service will want; an application that answers them
some other way -- one page generated, one proxied, one drawn -- is still an
application, which is why this is a base class with useful defaults rather than
a router with a hole in it.

A handler is a function of a *request*, not of a page number:

    @app.page("82{post_id:int}")
    async def post(request: PageRequest, post_id: int) -> Page:
        ...

That distinction matters more here than the corresponding one does on the web.
A viewdata terminal is a display and nothing more, so everything a session knows
is held at this end; two callers keying the same number can legitimately be
shown different things once there is such a thing as being logged in, or as
having arrived from a particular menu.

Handlers are `async` because the second thing every application does after
answering from memory is answer from somewhere else -- a database, an HTTP API,
a device. The one caller kept waiting should not be all of them.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, MutableMapping
from dataclasses import dataclass, field
from typing import Final

from sextile.addressing import PageAddress, UnknownPageError
from sextile.page import Page, PageFrame
from sextile.routing import Converter, Router
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour

#: How much of a mistyped request is worth quoting back.
_QUOTED: Final = 30


@dataclass(frozen=True)
class Arrival:
    """The pages either side of this one, in the sequence being read.

    Which sequence depends on how the reader got here: a page reached through
    one menu has that menu's pages either side of it, and through another has
    that one's. A page reached by keying its number has neither, and should be
    offered neither.
    """

    preceding: PageAddress | None = None
    following: PageAddress | None = None


@dataclass(frozen=True)
class PageRequest:
    """One page, asked for."""

    address: PageAddress

    params: dict[str, object] = field(default_factory=dict)
    """What the route's pattern captured. Also passed to the handler as keyword
    arguments, so a handler need not unpack them."""

    arrival: Arrival = Arrival()

    session: MutableMapping[str, object] = field(default_factory=dict)
    """What this caller has accumulated over their connection. The connection is
    the session -- the terminal keeps nothing but the frame on screen -- so this
    is where anything outlasting a single page belongs."""


type Handler = Callable[..., Awaitable[Page]]
type NotFoundHandler = Callable[[str], Awaitable[Page]]


class Application(ABC):
    """What a Sextile server serves.

    Only `respond` must be supplied. The rest have defaults that are right until
    an application has a reason to disagree with them.
    """

    @abstractmethod
    async def respond(self, request: PageRequest) -> Page | None:
        """Build the page this request asks for, or None if there is no such page.

        None rather than a notice, because the two are shown differently: a page
        that exists is somewhere the reader has gone, and a page that does not
        is something said to a reader who has not moved.
        """
        raise NotImplementedError

    @property
    def home(self) -> PageAddress:
        """Where a caller is put when the line opens.

        Page 1 unless a service says otherwise. A caller has to arrive
        somewhere, and the terminal has no address of its own to offer.
        """
        return PageAddress("1")

    def resolve(self, target: str) -> PageAddress:
        """The page a typed request names, or raise ``UnknownPageError``.

        Digits name themselves. An application offering keywords overrides this,
        as `Sextile` does.
        """
        return PageAddress(target.strip())

    async def not_found(self, target: str) -> Page:
        """Say that a request named nothing here.

        Silence would be indistinguishable from a line fault, which on a service
        that answers slowly by design is exactly the wrong thing to be.
        """
        return _plain_notice(target)

    #  Empty on purpose, and not abstract: an application with nothing to open
    #  should not have to say so.
    async def startup(self) -> None:  # noqa: B027
        """Open whatever this application needs open. Called before the first call."""

    async def shutdown(self) -> None:  # noqa: B027
        """Close it again. Called after the last."""


class Sextile(Application):
    """An application that answers by routing page numbers to handlers."""

    def __init__(self, *, home: str | PageAddress = "1") -> None:
        self._router: Router[Handler] = Router()
        self._mounted: list[tuple[str, Application]] = []
        self._not_found: NotFoundHandler | None = None
        self._home = home if isinstance(home, PageAddress) else PageAddress(home)

    @property
    def home(self) -> PageAddress:
        return self._home

    # -- building it --------------------------------------------------------

    def page[H: Handler](self, pattern: str, *, name: str | None = None) -> Callable[[H], H]:
        """Register a handler for every page number matching ``pattern``.

        The route takes the handler's own name unless told otherwise, so a page
        linking to another names it once rather than twice.

        Generic in the handler so that decorating one does not throw its own
        signature away: a service checked strictly should stay checked strictly
        on the far side of the decorator.
        """

        def register(handler: H) -> H:
            self._router.add(pattern, handler, name=name or handler.__name__)
            return handler

        return register

    def alias(self, keyword: str, address: str | PageAddress) -> None:
        """Let a word be keyed in place of a page number: `*MAIN#` for `*1#`."""
        self._router.alias(keyword, address)

    def converter(self, name: str, converter: Converter) -> None:
        """Offer a field shape this application's numbering needs."""
        self._router.converter(name, converter)

    def mount(self, prefix: str, application: Application) -> None:
        """Hand every page number beginning ``prefix`` to another application.

        The mounted application is given the address unchanged, which is not
        what a web framework would do. It cannot be: the application draws the
        page number into the frame itself, so a number stripped of its prefix
        would be drawn as something the reader could not key back. The prefix
        decides *who* answers, and nothing more.

        Mount at `""` to hand over everything not answered here, which is how a
        service that is one application rather than several is assembled.
        """
        if prefix and not (prefix.isascii() and prefix.isdigit()):
            raise ValueError(f"{prefix!r} is not the start of a page number")
        self._mounted.append((prefix, application))
        #  Longest prefix first, so a specific mount is not shadowed by a
        #  general one however they were added.
        self._mounted.sort(key=lambda mount: -len(mount[0]))

    def on_not_found[H: NotFoundHandler](self, handler: H) -> H:
        """Register what this service says about a page it has not got."""
        self._not_found = handler
        return handler

    # -- answering ----------------------------------------------------------

    async def respond(self, request: PageRequest) -> Page | None:
        found = self._router.match(request.address)
        if found is not None:
            return await found.target(request, **found.params)
        for prefix, application in self._mounted:
            if request.address.digits.startswith(prefix):
                answered = await application.respond(request)
                if answered is not None:
                    return answered
        return None

    def resolve(self, target: str) -> PageAddress:
        try:
            return self._router.resolve(target)
        except UnknownPageError:
            for _, application in self._mounted:
                try:
                    return application.resolve(target)
                except UnknownPageError:
                    continue
            raise

    async def not_found(self, target: str) -> Page:
        if self._not_found is None:
            return await super().not_found(target)
        return await self._not_found(target)

    def address_for(self, name: str, **params: object) -> PageAddress:
        """The address a named route answers, built from its own pattern."""
        return self._router.address_for(name, **params)

    def keywords(self) -> dict[str, PageAddress]:
        """The named jumps, for a page that wants to list them."""
        return self._router.keywords()

    # -- lifespan -----------------------------------------------------------

    async def startup(self) -> None:
        for _, application in self._mounted:
            await application.startup()

    async def shutdown(self) -> None:
        for _, application in self._mounted:
            await application.shutdown()


def _plain_notice(target: str) -> Page:
    """The framework's own way of saying a page is not here.

    Deliberately plain, and drawn without the header-and-footer furniture that
    `sextile.viewdata.chrome` offers. A service that has furniture of its own
    should say this in it, and one that has not should still be legible.
    """
    canvas = Canvas()
    canvas.row(0).text("UNKNOWN PAGE", Colour.CYAN)
    canvas.row(2).text(f"*{target[:_QUOTED]}# is NOT a page here.", Colour.WHITE)
    return Page(frames=(PageFrame(canvas.frame),))
