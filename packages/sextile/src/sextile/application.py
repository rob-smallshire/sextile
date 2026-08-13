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

The request a handler takes is `sextile.requests`'s; the vocabulary for
declaring a page beside its handler is `sextile.declarations`'s. Both are
re-exported here, `sextile` itself being where a service imports from.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping, MutableMapping, Sequence
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from typing import Final, Self

from sextile import contents, guidance, history, keys, names, readership
from sextile.addressing import PageAddress, UnknownPageError, keyed
from sextile.contents import contents_page
from sextile.declarations import (
    Handler,
    PageInfo,
    PageRoute,
    page,
    routes_in,
    routes_on,
)
from sextile.history import history_page
from sextile.names import names_page
from sextile.page import Page, PageFrame
from sextile.requests import Arrival, PageRequest, Parting
from sextile.routing import Converter, ConverterFactory, Match, Router
from sextile.templates import CHOICES_PER_FRAME, HOME_KEY
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.visits import Visits

__all__ = [
    "Application",
    "Arrival",
    "Handler",
    "Middleware",
    "Next",
    "PageInfo",
    "PageRequest",
    "PageRoute",
    "Parting",
    "Sextile",
    "page",
    "routes_in",
    "routes_on",
]

#: How much of a mistyped request is worth quoting back.
_QUOTED: Final = 30


type NotFoundHandler = Callable[[str], Awaitable[Page]]
type PartingHandler = Callable[[Parting], Awaitable[Page]]
type FailureHandler = Callable[[PageAddress], Awaitable[Page]]

type Next = Callable[[PageRequest], Awaitable[Page | None]]

type Middleware = Callable[[PageRequest, Next], Awaitable[Page | None]]
"""Something wrapped round every page a service builds.

A page handler answers what one page *says*; middleware answers what is true
of every page -- who is asking, how long it took, whether they may. It is
given the request and the rest of the chain, and may look, may change what
comes back, or may answer instead and never call it at all.

The framework deliberately has no opinion about authentication, and this is
why it does not need one: a service that wants it wraps its pages.
"""


type Lifespan = Callable[["Sextile"], AbstractAsyncContextManager[Mapping[str, object] | None]]
type ResolveHandler = Callable[[str], PageAddress | None]
type DescribeHandler = Callable[[PageAddress], str | None]


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

    @property
    def index(self) -> PageAddress:
        """Where `0` goes: the page a reader who is lost can rely on.

        The same as `home` for most services, and not for one that opens on a
        title frame -- a caller arrives there once and should never be sent back
        to it. The two are the same question only until a service has something
        to show before its index.
        """
        return self.home

    def describe(self, address: PageAddress) -> str:
        """What to call a page in a list of pages.

        Used by the built-in history page, and worth overriding for anything a
        reader would rather see a title than a number for. `Sextile` derives it
        from the route's own name, which is the application's word for the thing
        and so needs no framework knowledge of what a service is about.
        """
        return keyed(address)

    def heading(self, address: PageAddress, default: str) -> str:
        """What to head a page with. The framework's own name, unless told.

        `Sextile` prefers what the service called the page when it registered
        it: a built-in page has a name of its own and is given another on the
        way in, and without this the two say the same thing twice -- with the
        service's copy the one that shows in menus and on a contents page.
        """
        return default

    async def history(self, request: PageRequest) -> Page:
        """Where this caller has been, newest first, as a menu of shortcuts.

        Not registered anywhere by the framework: a service maps it into its own
        numbering, or does not offer it at all.

            self.page("92", name="history")(self.history)
            self.alias("HISTORY", self.address_for("history"))

        Key 1 for the page before this one -- the same as `*0#` -- 2 for the one
        before that, and so on.
        """
        return history_page(
            address=request.address,
            been=request.history,
            describe=self.describe,
            home=self.index,
            title=self.heading(request.address, history.TITLE),
        )

    async def guide(
        self,
        request: PageRequest,
        *,
        moving: "Sequence[guidance.Key]" = (),
        asking: "Sequence[guidance.Key]" = (),
        items: bool = True,
    ) -> Page:
        """How to get about, as a table of the keys this service answers.

        Registered nowhere, like `history`, `contents` and `names`. Most of
        what a guide has to say is the framework's -- the digits, the way home,
        the syntax of a request, the key that turns a page -- and a guide that
        drifts from the thing it describes is worse than none.

        A service passes its own keys, since which they are is a thing only it
        knows: a search field answers letters, a forecast answers `F`, and a
        framework that guessed would be describing a service it had not met.
        `moving` joins the first frame and `asking` the second. `items=False`
        leaves `A` and `D` off the compass, for a service that does not wire
        them to `request.arrival` and so does not answer them.

        The row for `0` says "back to the main menu" on a service whose first
        page is called one, and "back to the main index" on a service whose is
        called that: it is the page's own title, so the two cannot disagree.
        """
        return guidance.guide_page(
            address=request.address,
            title=self.heading(request.address, guidance.TITLE),
            home=self.index,
            home_called=self.describe(self.index).lower(),
            moving=moving,
            asking=asking,
            items=items,
        )

    async def lately_read(
        self,
        request: PageRequest,
        visits: Visits,
        *,
        limit: int = CHOICES_PER_FRAME,
        prefix: str = "",
    ) -> Page:
        """What has been looked at lately, as a menu of where to look.

        Registered nowhere, like the history, the contents and the words. The
        log is the service's -- it decides where it is kept and how long for --
        and the page is the framework's, a page number being the framework's
        own vocabulary.

        `prefix` narrows it to a namespace, which is what a first digit already
        means: a weather service can ask for the forecasts alone.
        """
        return readership.recent_page(
            address=request.address,
            visits=await visits.recent(limit, prefix=prefix),
            describe=self.describe,
            home=self.index,
            title=self.heading(request.address, readership.RECENT_TITLE),
        )

    async def most_read(
        self,
        request: PageRequest,
        visits: Visits,
        *,
        limit: int = CHOICES_PER_FRAME,
        prefix: str = "",
        since: datetime | None = None,
    ) -> Page:
        """What has been looked at most, as a menu of where to look."""
        return readership.popular_page(
            address=request.address,
            visits=await visits.popular(limit, prefix=prefix, since=since),
            describe=self.describe,
            home=self.index,
            title=self.heading(request.address, readership.POPULAR_TITLE),
        )

    async def who_has_called(
        self,
        request: PageRequest,
        visits: Visits,
        *,
        periods: "Sequence[tuple[timedelta, str]]" = readership.PERIODS,
    ) -> Page:
        """How many have called, over each of a few periods.

        The only figure a service keeps about its readers, and a count of
        connections rather than of anybody. `periods` is the service's to
        choose: one longer than the log is kept for reads low, and silently.
        """
        when = datetime.now(UTC)
        return readership.callers_page(
            address=request.address,
            counts=[
                (said, await visits.callers(since=when - window))
                for window, said in periods
            ],
            home=self.index,
            title=self.heading(request.address, readership.CALLERS_TITLE),
        )

    def keywords(self) -> dict[str, PageAddress]:
        """The words this service answers to. None, unless it says so."""
        return {}

    async def names(self, request: PageRequest) -> Page:
        """The words a reader can key in place of a page number.

        Registered nowhere, like `history` and `contents`. Generated from the
        aliases, so it cannot drift from what the service answers -- which is
        precisely what a list of keywords typed into a help page does.
        """
        return names_page(
            address=request.address,
            named=self.keywords(),
            describe=self.describe,
            home=self.index,
            title=self.heading(request.address, names.TITLE),
        )

    async def contents(self, request: PageRequest) -> Page:
        """Every page this service advertises, with the number that fetches it.

        Registered nowhere, like `history`; a service maps it in or does not.
        Pages with fields are listed as `*52<user_id>#` rather than enumerated,
        which is the point: nobody can list every contributor on a screen, and
        everybody holding a contributor number can be told where to put it.
        """
        return contents_page(
            address=request.address,
            pages=self.advertised(),
            home=self.index,
            title=self.heading(request.address, contents.TITLE),
        )

    def advertised(self) -> tuple[PageInfo, ...]:
        """The pages this service is willing to list. None, unless it says so."""
        return ()

    def resolve(self, target: str) -> PageAddress:
        """The page a typed request names, or raise ``UnknownPageError``.

        Digits name themselves. An application offering keywords overrides this,
        as `Sextile` does.
        """
        return PageAddress(target.strip())

    @property
    def service(self) -> Mapping[str, object]:
        """What this application holds while it is running. Nothing, by default."""
        return {}

    async def ask(
        self,
        target: str | PageAddress,
        *,
        arrival: Arrival | None = None,
        session: MutableMapping[str, object] | None = None,
        history: tuple[PageAddress, ...] = (),
    ) -> Page | None:
        """Answer a page number, as a session would ask it.

        A request carries more than the number now -- what the service holds,
        and the service itself -- and building one by hand means remembering
        both. Every test of every application would remember them, or would
        quietly not, and a page reached without them fails in a way that has
        nothing to do with what was being tested.

        So the assembly lives here, once. `render_page` uses it, and so should
        anything else that wants a page without a socket.
        """
        address = target if isinstance(target, PageAddress) else PageAddress(target)
        return await self.respond(
            PageRequest(
                address=address,
                arrival=arrival or Arrival(),
                session=session if session is not None else {},
                history=history,
                service=self.service,
                application=self,
            )
        )

    async def not_found(self, target: str) -> Page:
        """Say that a request named nothing here.

        Silence would be indistinguishable from a line fault, which on a service
        that answers slowly by design is exactly the wrong thing to be.
        """
        return _plain_notice(
            "UNKNOWN PAGE", f"{keyed(target[:_QUOTED])} is NOT a page here."
        )

    @property
    def name(self) -> str:
        """What this service is called, for the few things the framework says.

        Empty unless a service says otherwise, and the framework will not invent
        one: a page thanking a reader for calling *Sextile* names the machinery
        rather than the service, which is nobody's idea of a farewell.
        """
        return ""

    async def failed(self, address: PageAddress) -> Page:
        """Say that a page which exists could not be built.

        The viewdata equivalent of a 500, and deliberately not the same page as
        `not_found`. One says the reader asked for something that is not here;
        this says the service could not build something that is. Telling them
        the first when it is the second sends them away thinking they mistyped,
        and hides the fault from whoever could fix it.

        It names the number, so that a reader can report which page it was, and
        says whose fault it is -- somebody on a 1200 baud line will otherwise
        assume they did it.
        """
        return _plain_notice(
            "SERVICE ERROR",
            f"{keyed(address)} could not be built.",
            "",
            "This is a fault at our end, not yours,",
            "and the service has made a note of it.",
            "",
            f"Key {HOME_KEY} for the index, or {keyed(keys.REFRESH)} to try it",
            "again.",
        )

    async def timed_out(self, parting: Parting) -> Page:
        """Say that the line is being released for want of a reply.

        A page rather than a line of text over whatever was showing, for the
        same reason every other thing this service says is a page: a message
        overprinting a frame is hard to pick out from the frame.

        A service ringing off deliberately says goodbye on a page of its own,
        being a page like any other with `hang_up` set. This is the involuntary
        one, which no page number reaches, so the framework has to ask for it --
        and hand over where the caller had got to, since the terminal keeps
        nothing and they may want to key it again.
        """
        return _plain_notice(
            "RINGING OFF",
            "No reply for some time, so the line",
            "has been released.",
            "",
            f"You were reading *{parting.address}#.",
            *(["", f"Thank you for calling {self.name}."] if self.name else []),
            hang_up=True,
        )

    #  Empty on purpose, and not abstract: an application with nothing to open
    #  should not have to say so.
    async def startup(self) -> None:  # noqa: B027
        """Open whatever this application needs open. Called before the first call."""

    async def shutdown(self) -> None:  # noqa: B027
        """Close it again. Called after the last."""


class Sextile(Application):
    """An application that answers by routing page numbers to handlers."""

    @classmethod
    def of(cls, request: PageRequest) -> "Self":
        """The application a page belongs to, narrowed to the routing kind.

        For a handler that asks the numbering something -- `address_for`,
        `page_info` -- which is this class's surface rather than the
        `Application` one. Written here once rather than at the top of every
        service, and on the class rather than the request so that a service
        with an application type of its own narrows to that: `Board.of(...)`.
        """
        app = request.app
        if not isinstance(app, cls):
            raise RuntimeError(
                f"this page was asked outside a {cls.__name__} service and "
                "cannot ask the numbering anything"
            )
        return app

    def __init__(
        self,
        *,
        name: str = "",
        home: str | PageAddress = "1",
        index: str | PageAddress | None = None,
        converters: Mapping[str, Converter | ConverterFactory] | None = None,
        pages: Sequence[PageRoute] = (),
        middleware: Sequence[Middleware] = (),
        lifespan: Lifespan | None = None,
    ) -> None:
        self._name = name
        self._router: Router[Handler] = Router()
        self._pages: dict[str, PageInfo] = {}
        self._not_found: NotFoundHandler | None = None
        self._timed_out: PartingHandler | None = None
        self._failed: FailureHandler | None = None
        self._unresolved: ResolveHandler | None = None
        self._describing: DescribeHandler | None = None
        self._middleware = tuple(middleware)
        self._lifespan = lifespan
        self._running: AbstractAsyncContextManager[Mapping[str, object] | None] | None = None
        self._service: dict[str, object] = {}
        self._home = home if isinstance(home, PageAddress) else PageAddress(home)
        wanted = self._home if index is None else index
        self._index = wanted if isinstance(wanted, PageAddress) else PageAddress(wanted)
        #  Before the declared pages, not after: a page declared beside the
        #  method that builds it is registered here, so a pattern using a field
        #  shape of the service's own would otherwise name a converter that did
        #  not exist yet. `self.converter(...)` in a subclass constructor is
        #  always too late, there being nowhere to put it before `super()`.
        for shape, converter in (converters or {}).items():
            self._router.converter(shape, converter)
        #  Class declarations first, then the ones given here, so that a
        #  subclass assembled by a factory can add to what its class declared
        #  rather than being unable to say anything at all.
        self._register_declared()
        for route in pages:
            self.add_page(route)

    @property
    def name(self) -> str:
        return self._name

    @property
    def home(self) -> PageAddress:
        return self._home

    @property
    def index(self) -> PageAddress:
        return self._index

    # -- building it --------------------------------------------------------

    def add_page(self, route: PageRoute) -> None:
        """Register one page. What everything else here is written in terms of."""
        name = route.name or route.handler.__name__
        self._router.add(route.pattern, route.handler, name=name)
        if route.title:
            self._pages[name] = PageInfo(
                name=name,
                keyed=self._router.named(name).keyed,
                title=route.title,
                detail=route.detail,
            )
        for keyword in route.keywords:
            self.alias(keyword, self.address_for(name))

    def page[H: Handler](
        self,
        pattern: str,
        *,
        name: str | None = None,
        title: str = "",
        detail: str = "",
        keywords: Sequence[str] = (),
    ) -> Callable[[H], H]:
        """Register a handler for every page number matching ``pattern``.

        The route takes the handler's own name unless told otherwise, so a page
        linking to another names it once rather than twice.

        ``title`` and ``detail`` are what to call this page where it is listed
        rather than shown -- in a menu, in the history, in the contents. Saying
        them here means saying them once. A page given no title is not
        advertised in the contents, which is how a title frame or a logoff page
        stays off it without needing a flag of its own.

        ``keywords`` are words a reader may key instead of the number, aliased
        onto this page. Said here rather than in a separate `alias` call for
        the same reason the title is: a page should say what it is in one
        place.

        Generic in the handler so that decorating one does not throw its own
        signature away: a service checked strictly should stay checked strictly
        on the far side of the decorator.
        """

        def register(handler: H) -> H:
            self.add_page(
                PageRoute(
                    pattern=pattern,
                    handler=handler,
                    name=name,
                    title=title,
                    detail=detail,
                    keywords=keywords,
                )
            )
            return handler

        return register

    def _register_declared(self) -> None:
        """Register the pages this class declared with `@page`."""
        for route in routes_on(self):
            self.add_page(route)

    def page_info(self, name: str) -> PageInfo | None:
        """What was said about a named page when it was registered."""
        return self._pages.get(name)

    def advertised(self) -> tuple[PageInfo, ...]:
        return self.pages()

    def pages(self) -> tuple[PageInfo, ...]:
        """Every page this service advertises, in the order it registered them.

        Registration order rather than the router's, which is about matching and
        would put the most literal pattern first for reasons a reader does not
        care about.

        """
        return tuple(self._pages.values())

    def alias(self, keyword: str, address: str | PageAddress) -> None:
        """Let a word be keyed in place of a page number: `*MAIN#` for `*1#`."""
        self._router.alias(keyword, address)

    def converter(self, name: str, converter: Converter | ConverterFactory) -> None:
        """Offer a field shape this application's numbering needs."""
        self._router.converter(name, converter)


    def on_not_found[H: NotFoundHandler](self, handler: H) -> H:
        """Register what this service says about a page it has not got."""
        self._not_found = handler
        return handler

    def on_timed_out[H: PartingHandler](self, handler: H) -> H:
        """Register what this service says as it releases an idle caller."""
        self._timed_out = handler
        return handler

    def on_failed[H: FailureHandler](self, handler: H) -> H:
        """Register what this service says when a page will not build."""
        self._failed = handler
        return handler

    def on_describe[H: DescribeHandler](self, handler: H) -> H:
        """Register better words for a page than its registration can give.

        `describe` reads what a page said about itself, which is right for a
        page whose number is fixed and wrong for one whose number carries a
        field: "One post" is the right title in a list of *kinds* of page and
        the wrong one in a list of pages a reader has been to.

        Returning None means the registration's own words will do, so a handler
        need only say what it means to say differently.
        """
        self._describing = handler
        return handler

    def on_unresolved[H: ResolveHandler](self, handler: H) -> H:
        """Register a last resort for a target the numbering does not name.

        A reader keys letters and the numbering knows only its own keywords, so
        a service with a search of its own -- a place name, a callsign, a
        postcode -- wants a say before the target is called unknown. Returning
        None means it really is.

        Tried after the numbering and never before it: a keyword a service has
        registered must keep meaning what it was registered to mean.
        """
        self._unresolved = handler
        return handler

    # -- answering ----------------------------------------------------------

    async def respond(self, request: PageRequest) -> Page | None:
        return await self._chain(request)

    async def _build(self, request: PageRequest) -> Page | None:
        """The page itself, with nothing wrapped round it."""
        found = self._router.match(request.address)
        if found is not None:
            return await found.target(request, **found.params)
        return None

    async def _chain(self, request: PageRequest) -> Page | None:
        """The middleware, outermost first, and the page at the bottom.

        Built per request rather than once, which costs a closure apiece and
        buys the obvious thing: middleware may be added to an application that
        has already answered something, and a service assembled in pieces does
        not have to know it has finished being assembled.
        """
        build: Next = self._build
        #  Reversed, so that the first given is the outermost: a reader of the
        #  list should see a request entering at the top and leaving at the
        #  bottom.
        for middleware in reversed(self._middleware):
            build = _wrap(middleware, build)
        return await build(request)

    def params_for(self, address: PageAddress) -> Mapping[str, object] | None:
        """What a page number means: the fields its route captured, or None.

        The same reading of a number that served the page, offered to a service
        that has the number and wants the thing again -- reading its own log
        back, most likely. Taking the digits apart a second time is a second
        thing to get wrong when the numbering changes, and this numbering has
        changed once already.
        """
        found = self._router.match(address)
        return None if found is None else found.params

    def resolve(self, target: str) -> PageAddress:
        try:
            return self._router.resolve(target)
        except UnknownPageError:
            #  Last, so that a registered keyword always means what it was
            #  registered to mean: a service searching its own data must not be
            #  able to shadow its own numbering by accident.
            if self._unresolved is not None:
                found = self._unresolved(target)
                if found is not None:
                    return found
            raise

    async def not_found(self, target: str) -> Page:
        if self._not_found is None:
            return await super().not_found(target)
        return await self._not_found(target)

    async def timed_out(self, parting: Parting) -> Page:
        if self._timed_out is None:
            return await super().timed_out(parting)
        return await self._timed_out(parting)

    async def failed(self, address: PageAddress) -> Page:
        if self._failed is None:
            return await super().failed(address)
        return await self._failed(address)

    def address_for(self, name: str, **params: object) -> PageAddress:
        """The address a named route answers, built from its own pattern."""
        return self._router.address_for(name, **params)

    def route(self, address: PageAddress) -> Match[Handler] | None:
        """What answers this address, and what its pattern captured.

        The numbering read backwards, for an application that has an address and
        wants to know what it names -- taking the digits apart again would be
        the scheme written down twice.
        """
        return self._router.match(address)

    def describe(self, address: PageAddress) -> str:
        if self._describing is not None:
            said = self._describing(address)
            if said is not None:
                return said
        found = self.route(address)
        if found is None or found.name is None:
            return super().describe(address)
        about = self._pages.get(found.name)
        called = about.title if about is not None else found.name
        fields = " ".join(str(value) for value in found.params.values())
        return f"{called} {fields}".strip()

    def heading(self, address: PageAddress, default: str) -> str:
        found = self.route(address)
        about = self._pages.get(found.name) if found and found.name else None
        return about.title.upper() if about and about.title else default

    def keywords(self) -> dict[str, PageAddress]:
        """The named jumps, for a page that wants to list them."""
        return self._router.keywords()

    # -- lifespan -----------------------------------------------------------

    @property
    def service(self) -> Mapping[str, object]:
        """What the lifespan yielded, for as long as the service is running."""
        return self._service

    async def startup(self) -> None:
        if self._lifespan is not None:
            self._running = self._lifespan(self)
            held = await self._running.__aenter__()
            if held is not None:
                self._service.update(held)

    async def shutdown(self) -> None:
        if self._running is not None:
            #  Whatever the lifespan set up is torn down by the same function
            #  that set it up, which is the reason for it being a context
            #  manager rather than a pair of handlers: setup and teardown
            #  cannot drift apart when they are two halves of one function.
            await self._running.__aexit__(None, None, None)
            self._running = None
        self._service.clear()


def _wrap(middleware: Middleware, build: Next) -> Next:
    """One link of the chain. A function so the closure captures this loop's
    values rather than the last ones, which is the oldest bug in the world."""

    async def wrapped(request: PageRequest) -> Page | None:
        return await middleware(request, build)

    return wrapped


def _plain_notice(title: str, *lines: str, hang_up: bool = False) -> Page:
    """The framework's own way of saying something for itself.

    Deliberately plain, and drawn without the header-and-footer furniture that
    `sextile.viewdata.chrome` offers. A service that has furniture of its own
    should say these things in it, and one that has not should still be legible.

    Kept to the top few rows, which leaves somewhere for the cursor to go if
    this turns out to be the last thing the reader sees.
    """
    canvas = Canvas()
    canvas.row(0).text(title, Colour.CYAN)
    for offset, line in enumerate(lines):
        canvas.row(2 + offset).text(line, Colour.WHITE)
    return Page(frames=(PageFrame(canvas.frame),), hang_up=hang_up)
