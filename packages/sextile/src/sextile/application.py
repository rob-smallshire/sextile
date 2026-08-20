"""The application: a service that answers page requests by routing.

`Sextile` routes a page number to a handler and returns the page the handler
builds. Connections, sessions, the protocol and the numbering are the
framework's, behind `respond`; a handler is a service's.

A handler is `async` and takes a `PageRequest`, not a page number:

    @app.page("52{field:int}")
    async def item(request: PageRequest, field: int) -> Page:
        ...

Each field a `pattern` names is passed to the handler by keyword. `async`
because a handler often answers from a database or an HTTP API, and a call
awaiting one should not hold the others.

`PageRequest` is `sextile.requests`'s and `PageRoute`/`PageRouter` are
`sextile.routing`'s; both are re-exported here, `sextile` being where a service
imports from.
"""

from collections.abc import (
    Awaitable,
    Callable,
    Iterable,
    Mapping,
    Sequence,
)
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from typing import Final

from sextile import keys
from sextile.formatting import MenuItem
from sextile.layout import HOME_KEY
from sextile.middleware import Middleware, chained
from sextile.page import Page, PageAddress, UnknownPageError, keyed
from sextile.pages import notice_page
from sextile.requests import Neighbours, PageRequest
from sextile.routing import (
    Converter,
    ConverterFactory,
    Handler,
    Match,
    PageRoute,
    PageRouter,
    Router,
    declaring,
)
from sextile.state import State

__all__ = [
    "Handler",
    "Neighbours",
    "PageRequest",
    "PageRoute",
    "PageRouter",
    "Sextile",
]

#: How much of a mistyped request is worth quoting back.
_QUOTED: Final = 30


type NotFoundHandler = Callable[[PageRequest, str], Awaitable[Page]]
type TimeoutHandler = Callable[[PageRequest, int], Awaitable[Page]]
type FailureHandler = Callable[[PageRequest, Exception], Awaitable[Page]]
type BusyHandler = Callable[[PageRequest], Awaitable[Page]]

type Lifespan = Callable[["Sextile"], AbstractAsyncContextManager[None]]
type ResolveHandler = Callable[[str], PageAddress | None]


class Sextile:
    """An application that answers by routing page numbers to handlers."""

    def __init__(
        self,
        *,
        name: str = "",
        home: str | PageAddress = "1",
        index: str | PageAddress | None = None,
        converters: Mapping[str, Converter | ConverterFactory] | None = None,
        pages: Iterable[PageRoute] = (),
        middleware: Sequence[Middleware] = (),
        lifespan: Lifespan | None = None,
    ) -> None:
        """Assemble a service from its pages, converters, middleware and lifespan.

        Args:
            name: What the service calls itself, shown where it names itself to
                a caller. Empty leaves it unnamed.
            home: The page a caller arrives on when the line opens.
            index: The page `0` leads to from every frame. Defaults to `home`.
            converters: Field shapes the patterns use, by the name a pattern
                names them with. Given here rather than added later because a
                pattern must know a field shape before it compiles.
            pages: The routes to register, each a `PageRoute` or the spread of a
                `PageRouter`.
            middleware: What wraps every page, the first given outermost.
            lifespan: An async context manager opened at `startup` and closed at
                `shutdown`, which fills `state` before yielding.

        Everything arrives in one call, so registration order is unobservable.
        """
        self._name = name
        self._router: Router[Handler] = Router()
        self._pages: dict[str, PageRoute] = {}
        self._not_found: NotFoundHandler | None = None
        self._timed_out: TimeoutHandler | None = None
        self._failed: FailureHandler | None = None
        self._busy: BusyHandler | None = None
        self._unresolved: ResolveHandler | None = None
        self._middleware = tuple(middleware)
        self._lifespan = lifespan
        self._running: AbstractAsyncContextManager[None] | None = None
        self._state = State()
        self._home = home if isinstance(home, PageAddress) else PageAddress(home)
        wanted = self._home if index is None else index
        self._index = wanted if isinstance(wanted, PageAddress) else PageAddress(wanted)
        #  Before the declared pages, not after: a page declared beside the
        #  page given here would otherwise name a converter that did not exist
        #  yet, a page number using a field shape of the service's own.
        for shape, converter in (converters or {}).items():
            self._router.converter(shape, converter)
        for route in pages:
            self.add_page(route)

    @property
    def name(self) -> str:
        """What the service calls itself, or empty."""
        return self._name

    @property
    def home(self) -> PageAddress:
        """The page a caller arrives on when the line opens."""
        return self._home

    @property
    def index(self) -> PageAddress:
        """The page `0` leads to from every frame, `home` unless set apart."""
        return self._index

    # -- building it --------------------------------------------------------

    def add_page(self, route: PageRoute) -> None:
        """Register one page, the operation `page` and the constructor build on.

        Args:
            route: The page to register, its name taken from the handler where
                the route gives none.
        """
        name = route.name or route.handler.__name__
        self._router.add(route.pattern, route.handler, name=name)
        if route.title:
            #  What `routes()` and `route()` read back: the route as declared,
            #  its name resolved and its keyed form read off the numbering it
            #  has just been registered into.
            self._pages[name] = replace(
                route, name=name, keyed=self._router.named(name).keyed
            )
        for keyword in route.keywords:
            self.add_keyword(keyword, self.address_for(name))

    def page[H: Handler](
        self,
        pattern: str,
        *,
        name: str | None = None,
        title: str = "",
        detail: str = "",
        keywords: Sequence[str] = (),
        label: str | Callable[..., str] | None = None,
    ) -> Callable[[H], H]:
        """Register the decorated handler for every page number `pattern` matches.

        Args:
            pattern: The page numbers this answers: literal digits and named
                fields.
            name: What `address_for` calls the route. The handler's own name
                where none is given.
            title: What to call the page where it is listed rather than shown --
                in a menu, in the history, in the contents. A page with no title
                is not advertised, which keeps a title frame off the contents.
            detail: A second line, wherever the title gets one.
            keywords: Words a reader may key instead of the number.
            label: What to call the page in a list of visited pages, where the
                title is wrong because the number carried a field. See
                `PageRoute.label`.

        Returns:
            A decorator that registers its handler and returns it unchanged.

        Generic in the handler so a strictly checked service stays strictly
        checked past the decorator.
        """
        #  The same builder as `PageRouter.page`, so the two decorators cannot
        #  drift into constructing a route differently. This one registers it
        #  now; the router's collects it for a later `Sextile(pages=...)`.
        return declaring(
            self.add_page,
            pattern,
            name=name,
            title=title,
            detail=detail,
            keywords=keywords,
            label=label,
        )

    def route(self, name: str) -> PageRoute | None:
        """Return the advertised route named `name`, or None.

        Args:
            name: The name a route was registered under.

        Returns:
            The route with its `keyed` form filled in, or None where the name
            registered no advertised page: a page given no title is routed but
            not kept here.
        """
        return self._pages.get(name)

    def menu_item(self, name: str) -> MenuItem:
        """A menu entry for a registered page, from what it said about itself.

        The text and detail are the page's own, registered words, so a menu
        offering the page and a listing naming it cannot drift apart.

        Args:
            name: The name the page was registered under.

        Returns:
            An item carrying the page's title and detail, leading to its
            address.

        Raises:
            ValueError: If no page is registered under `name`.
        """
        about = self.route(name)
        if about is None:
            raise ValueError(f"{name!r} is not a page that says what it is")
        return MenuItem(
            text=about.title, detail=about.detail, destination=self.address_for(name)
        )

    def routes(self) -> tuple[PageRoute, ...]:
        """List every page this service advertises, in registration order.

        Returns:
            The advertised routes, in the order registered rather than the
            router's most-literal-first match order.
        """
        return tuple(self._pages.values())

    def add_keyword(self, keyword: str, address: str | PageAddress) -> None:
        """Let a word be keyed in place of a page number: `*MAIN#` for `*1#`."""
        self._router.alias(keyword, address)

    def add_converter(self, name: str, converter: Converter | ConverterFactory) -> None:
        """Offer a field shape this application's numbering needs."""
        self._router.converter(name, converter)


    def on_not_found[H: NotFoundHandler](self, handler: H) -> H:
        """Register the handler that builds the page for a number naming nothing."""
        self._not_found = handler
        return handler

    def on_timed_out[H: TimeoutHandler](self, handler: H) -> H:
        """Register the handler that builds the frame shown as an idle line drops."""
        self._timed_out = handler
        return handler

    def on_failed[H: FailureHandler](self, handler: H) -> H:
        """Register the handler that builds the frame shown when a handler raises."""
        self._failed = handler
        return handler

    def on_busy[H: BusyHandler](self, handler: H) -> H:
        """Register the handler that builds the frame shown when the board is full."""
        self._busy = handler
        return handler

    def on_unresolved[H: ResolveHandler](self, handler: H) -> H:
        """Register a resolver for a keyed target the numbering does not name.

        Args:
            handler: Given the target a reader keyed, it returns the address the
                target means or None where it means nothing.

        Returns:
            The handler, so it may be used as a decorator.

        Tried after the numbering, never before it, so a registered keyword
        keeps meaning what it was registered to mean.
        """
        self._unresolved = handler
        return handler

    # -- answering ----------------------------------------------------------

    async def respond(self, request: PageRequest) -> Page | None:
        """Answer a request, through the middleware and then the router.

        Args:
            request: The request to answer.

        Returns:
            The page built for it, or None where no route matches its address.
        """
        return await self._chain(request)

    async def _build(self, request: PageRequest) -> Page | None:
        """The page itself, with nothing wrapped round it."""
        found = self._router.match(request.address)
        if found is not None:
            return await found.target(request, **found.params)
        return None

    async def _chain(self, request: PageRequest) -> Page | None:
        """The middleware, outermost first, and the page at the bottom."""
        return await chained(self._build, self._middleware)(request)

    def params_for(self, address: PageAddress) -> Mapping[str, object] | None:
        """Read the fields a page number's route captured, or None.

        Args:
            address: The page number to read.

        Returns:
            The captured fields by name, the same reading that served the page,
            or None where no route matches.
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

    async def not_found(self, request: PageRequest, target: str) -> Page:
        """Build the page shown for a target that names nothing here.

        Args:
            request: The page the reader is on, which they stay on.
            target: What they keyed that led nowhere.

        Returns:
            The page an `on_not_found` handler builds, or the framework's own
            notice. A notice rather than silence, which on a service that answers
            slowly is not distinguishable from a line fault.
        """
        if self._not_found is not None:
            return await self._not_found(request, target)
        return notice_page(
            request,
            f"{keyed(target[:_QUOTED])} is NOT a page here.",
            title="UNKNOWN PAGE",
            home=None,
            furniture=(),
        )

    async def timed_out(self, request: PageRequest, frame_index: int) -> Page:
        """Build the frame shown as an idle line is released for want of a reply.

        Args:
            request: The page the reader was on.
            frame_index: Which frame of it they were on.

        Returns:
            The page an `on_timed_out` handler builds, or the framework's own.
            A whole frame, not a line over what was showing: a message
            overprinting a frame is hard to pick out from it.
        """
        if self._timed_out is not None:
            return await self._timed_out(request, frame_index)
        return notice_page(
            request,
            "No reply for some time, so the line",
            "has been released.",
            "",
            f"You were reading *{request.address}#.",
            *(["", f"Thank you for calling {self.name}."] if self.name else []),
            title="RINGING OFF",
            home=None,
            furniture=(),
            hang_up=True,
        )

    async def busy(self, request: PageRequest) -> Page:
        """Build the frame shown to a caller the board has no room for.

        Args:
            request: The page the caller would have arrived on.

        Returns:
            The page an `on_busy` handler builds, or the framework's own. A whole
            frame and then the line drops: a busy signal a caller can read,
            rather than a line that opens and dies without a word.
        """
        if self._busy is not None:
            return await self._busy(request)
        return notice_page(
            request,
            "All lines are busy just now.",
            "",
            "Please call again shortly.",
            *(["", f"Thank you for trying {self.name}."] if self.name else []),
            title="LINES BUSY",
            home=None,
            furniture=(),
            hang_up=True,
        )

    async def failed(self, request: PageRequest, error: Exception) -> Page:
        """Build the frame shown when a handler raises building a page that exists.

        Args:
            request: The page the reader asked for.
            error: What the handler raised, for an `on_failed` handler that reads
                it. The framework's own notice does not.

        Returns:
            The page an `on_failed` handler builds, or the framework's own.
            Distinct from `not_found`: that number names nothing, this one names
            a page the service could not build.
        """
        if self._failed is not None:
            return await self._failed(request, error)
        return notice_page(
            request,
            f"{keyed(request.address)} could not be built.",
            "",
            "This is a fault at our end, not yours,",
            "and the service has made a note of it.",
            "",
            f"Key {HOME_KEY} for the index, or {keyed(keys.REFRESH)} to try it",
            "again.",
            title="SERVICE ERROR",
            home=None,
            furniture=(),
        )

    def address_for(self, name: str, **params: object) -> PageAddress:
        """The address a named route answers, built from its own pattern."""
        return self._router.address_for(name, **params)

    def match(self, address: PageAddress) -> Match[Handler] | None:
        """Match an address to the route that answers it and what it captured.

        Args:
            address: The page number to match.

        Returns:
            The `Match` for the route that answers it, or None where none does.
        """
        return self._router.match(address)

    def title_for(self, address: PageAddress) -> str | None:
        """Read the title a page was registered with, as registered, or None.

        Args:
            address: The page number to read the title of.

        Returns:
            The registered title, or None where the address is unrouted or its
            route was given no title. Not upper-cased: the layout upper-cases it
            when it draws a heading, and a listing reads it as it is.
        """
        found = self.match(address)
        about = self._pages.get(found.name) if found and found.name else None
        return about.title if about and about.title else None

    def label_for(self, address: PageAddress) -> str:
        """Name a page for a list of pages a reader has visited.

        Args:
            address: The page number to label.

        Returns:
            The route's `label` where it set one, so a page whose number carried
            a field reads as the one page rather than the kind of page: a
            `str.format` template filled from the captured fields, or a callable
            passed them by keyword. With no `label`, the registered title
            followed by the field values, or the keyed number where the address
            is unrouted or untitled.
        """
        found = self.match(address)
        if found is None or found.name is None:
            return keyed(address)
        about = self._pages.get(found.name)
        if about is not None and about.label is not None:
            if callable(about.label):
                return about.label(**found.params)
            return about.label.format(**found.params)
        called = about.title if about is not None else found.name
        fields = " ".join(str(value) for value in found.params.values())
        return f"{called} {fields}".strip()

    def keywords(self) -> dict[str, PageAddress]:
        """Return the keyword-to-address jumps, for a page that lists them."""
        return self._router.keywords()

    # -- lifespan -----------------------------------------------------------

    @property
    def state(self) -> State:
        """What the service holds while running, written by the lifespan.

        A page is given the read-only view of this as `request.state`; the
        writable store is the lifespan's, which sets a `StateKey` on it before
        yielding.
        """
        return self._state

    async def startup(self) -> None:
        """Open the lifespan, filling `state` for the pages that read it."""
        if self._lifespan is not None:
            self._running = self._lifespan(self)
            await self._running.__aenter__()

    async def shutdown(self) -> None:
        """Close the lifespan and clear `state`."""
        if self._running is not None:
            #  Whatever the lifespan set up is torn down by the same function
            #  that set it up, which is the reason for it being a context
            #  manager rather than a pair of handlers: setup and teardown
            #  cannot drift apart when they are two halves of one function.
            await self._running.__aexit__(None, None, None)
            self._running = None
        self._state.clear()

    async def fetch(
        self,
        target: str | PageAddress,
        *,
        neighbours: Neighbours | None = None,
        session: State | None = None,
        history: tuple[PageAddress, ...] = (),
    ) -> Page | None:
        """Fetch a page by its number, in process, as a session would request it.

        A request carries more than the number: what the service holds, and the
        service itself. Assembling one by hand at each call site is easy to get
        subtly wrong, so the assembly lives here once. `render_page` uses it,
        and so should anything else that wants a page without a socket.
        """
        address = target if isinstance(target, PageAddress) else PageAddress(target)
        return await self.respond(
            PageRequest(
                address=address,
                neighbours=neighbours or Neighbours(),
                session=session if session is not None else State(),
                history=history,
                state=self._state,
                app=self,
            )
        )


