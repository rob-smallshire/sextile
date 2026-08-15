"""The application: a service that answers page requests by routing.

`Sextile` answers a page request by routing its number to a handler. It is the
one application class: everything about connections, sessions, the protocol and
the numbering is on the framework's side of `respond`, and what the pages say
is the service's.

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

from collections.abc import (
    Awaitable,
    Callable,
    Iterable,
    Mapping,
    MutableMapping,
    Sequence,
)
from contextlib import AbstractAsyncContextManager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Final

from sextile import keys
from sextile.addressing import PageAddress, UnknownPageError, keyed
from sextile.builtin import contents, guidance, history, names, readership
from sextile.builtin.contents import contents_page
from sextile.builtin.history import history_page
from sextile.builtin.names import names_page
from sextile.declarations import (
    Handler,
    PageRoute,
    PageRouter,
    declaring,
)
from sextile.formatting import MenuItem
from sextile.layout import CHOICES_PER_FRAME, HOME_KEY
from sextile.page import Page
from sextile.pages import notice_page
from sextile.requests import Neighbours, PageRequest
from sextile.routing import Converter, ConverterFactory, Match, Router
from sextile.state import State
from sextile.visits import Visits

__all__ = [
    "Handler",
    "Middleware",
    "Neighbours",
    "Next",
    "PageRequest",
    "PageRoute",
    "PageRouter",
    "Sextile",
]

#: How much of a mistyped request is worth quoting back.
_QUOTED: Final = 30


type NotFoundHandler = Callable[[PageRequest, str], Awaitable[Page]]
type PartingHandler = Callable[[PageRequest, int], Awaitable[Page]]
type FailureHandler = Callable[[PageRequest, Exception], Awaitable[Page]]

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
        self._name = name
        self._router: Router[Handler] = Router()
        self._pages: dict[str, PageRoute] = {}
        self._not_found: NotFoundHandler | None = None
        self._timed_out: PartingHandler | None = None
        self._failed: FailureHandler | None = None
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
            #  What `routes()` and `route()` read back: the route as declared,
            #  its name resolved and its keyed form read off the numbering it
            #  has just been registered into.
            self._pages[name] = replace(
                route, name=name, keyed=self._router.named(name).keyed
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
        label: str | Callable[..., str] | None = None,
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

        ``label`` is what to call the page in a list of visited pages, when the
        listed title is wrong because the number carried a field. See
        `PageRoute.label`.

        Generic in the handler so that decorating one does not throw its own
        signature away: a service checked strictly should stay checked strictly
        on the far side of the decorator.
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
        """The registered route named `name`, with its `keyed` form filled in.

        None where no advertised page was registered under `name`: a page given
        no title is routed but not kept here.
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
        """Every page this service advertises, in the order it registered them.

        Registration order rather than the router's match order, which would put
        the most literal pattern first.
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

        The same reading of a number that served the page, for a service that
        has the number and wants the fields again -- reading its own log back,
        most likely. Taking the digits apart by hand would be the numbering
        written down twice.
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
        """Say that ``target`` named nothing here.

        Silence would be indistinguishable from a line fault, which on a service
        that answers slowly by design is exactly the wrong thing to be. A
        service registering `@app.on_not_found` says it its own way instead.
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
        """Say that the line is being released for want of a reply.

        ``request`` is the page the reader was on; ``frame_index`` says which
        frame of it. A page rather than a line of text over whatever was
        showing, for the same reason every other thing this service says is a
        page: a message overprinting a frame is hard to pick out from the frame.
        A service registering `@app.on_timed_out` says goodbye its own way.
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

    async def failed(self, request: PageRequest, error: Exception) -> Page:
        """Say that a page which exists could not be built.

        The viewdata equivalent of a 500, and deliberately not the same page as
        `not_found`: one says the reader asked for something that is not here,
        this says the service could not build something that is. ``error`` is
        what the handler raised, for a service registering `@app.on_failed` that
        wants to say it its own way; the framework's own words do not read it.
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
        """What answers this address, and what its pattern captured.

        The numbering read backwards, for an application that has an address and
        wants to know what it names -- taking the digits apart again would be
        the scheme written down twice.
        """
        return self._router.match(address)

    def title_for(self, address: PageAddress) -> str | None:
        """The title a page was registered with, as registered.

        None where the address is unrouted or its route was given no title. Not
        upper-cased: the layout shouts it as it draws the heading, and a listing
        reads it as it is.
        """
        found = self.match(address)
        about = self._pages.get(found.name) if found and found.name else None
        return about.title if about and about.title else None

    def label_for(self, address: PageAddress) -> str:
        """What to call a page in a list of pages a reader has visited.

        The route's `label` when it set one, so a page whose number carries a
        field reads as the page a reader was on ("Post 489493") rather than as
        the kind of page it is ("One post"). A `str.format` template is filled
        from the captured fields; a callable is passed them as keyword arguments.

        With no `label`, the registered title followed by the field values, or
        the keyed number for a page that is unrouted or untitled.
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
        """The named jumps, for a page that wants to list them."""
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
        if self._lifespan is not None:
            self._running = self._lifespan(self)
            await self._running.__aenter__()

    async def shutdown(self) -> None:
        if self._running is not None:
            #  Whatever the lifespan set up is torn down by the same function
            #  that set it up, which is the reason for it being a context
            #  manager rather than a pair of handlers: setup and teardown
            #  cannot drift apart when they are two halves of one function.
            await self._running.__aexit__(None, None, None)
            self._running = None
        self._state.clear()

    async def history_page(self, request: PageRequest) -> Page:
        """Where this caller has been, newest first, as a menu of shortcuts.

        Not registered anywhere by the framework: a service maps it into its own
        numbering, or does not offer it at all.

            self.page("92", name="history")(self.history_page)
            self.alias("HISTORY", self.address_for("history"))

        Key 1 for the page before this one -- the same as `*0#` -- 2 for the one
        before that, and so on.
        """
        return history_page(
            request=request,
            been=request.history,
            label=self.label_for,
            title=(self.title_for(request.address) or history.TITLE).upper(),
        )

    async def guide_page(
        self,
        request: PageRequest,
        *,
        moving: "Sequence[guidance.GuideRow]" = (),
        asking: "Sequence[guidance.GuideRow]" = (),
        items: bool = True,
    ) -> Page:
        """How to get about, as a table of the keys this service answers.

        Registered nowhere, like `history`, `contents` and `names`. Most of
        what a guide has to say is the framework's -- the digits, the way home,
        the syntax of a request, the key that turns a page -- and a guide that
        drifts from the thing it describes is worse than none.

        A service passes its own keys, since only it knows them: one page may
        answer letters typed into a field, another a single key such as `F`.
        `moving` joins the first frame and `asking` the second. `items=False`
        leaves `A` and `D` off the compass, for a service that does not wire
        them to `request.neighbours` and so does not answer them.

        The row for `0` says "back to the main menu" on a service whose first
        page is called one, and "back to the main index" on a service whose is
        called that: it is the page's own title, so the two cannot disagree.
        """
        return guidance.guide_page(
            request=request,
            title=(self.title_for(request.address) or guidance.TITLE).upper(),
            home_called=self.label_for(self.index).lower(),
            moving=moving,
            asking=asking,
            items=items,
        )

    async def recent_page(
        self,
        request: PageRequest,
        visits: Visits,
        *,
        limit: int = CHOICES_PER_FRAME,
        prefix: str = "",
    ) -> Page:
        """What has been looked at lately, as a menu of where to look.

        Args:
            request: The request for this page.
            visits: The log to read.
            limit: How many to show, defaulting to the nine a frame holds. More
                than that goes on to further frames rather than being dropped.
            prefix: Narrows it to a namespace, which is what a first digit
                already means: a service can ask for one namespace's pages
                alone.

        Registered nowhere, like the history, the contents and the words. The
        log is the service's -- it decides where it is kept and how long for --
        and the page is the framework's, a page number being the framework's
        own vocabulary.
        """
        return readership.recent_page(
            request=request,
            visits=await visits.recent(limit, prefix=prefix),
            label=self.label_for,
            title=(self.title_for(request.address) or readership.RECENT_TITLE).upper(),
        )

    async def popular_page(
        self,
        request: PageRequest,
        visits: Visits,
        *,
        limit: int = CHOICES_PER_FRAME,
        prefix: str = "",
        since: datetime | None = None,
    ) -> Page:
        """What has been looked at most, as a menu of where to look.

        Args:
            request: The request for this page.
            visits: The log to read.
            limit: How many to show, defaulting to the nine a frame holds. More
                than that goes on to further frames rather than being dropped.
            prefix: Narrows it to a namespace of the numbering.
            since: Counts only what has been read since then, where the service
                wants "most read lately" rather than most read ever.
        """
        return readership.popular_page(
            request=request,
            visits=await visits.popular(limit, prefix=prefix, since=since),
            label=self.label_for,
            title=(self.title_for(request.address) or readership.POPULAR_TITLE).upper(),
        )

    async def callers_page(
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
            request=request,
            counts=[
                (said, await visits.callers(since=when - window))
                for window, said in periods
            ],
            title=(self.title_for(request.address) or readership.CALLERS_TITLE).upper(),
        )

    async def keywords_page(self, request: PageRequest) -> Page:
        """The words a reader can key in place of a page number.

        Registered nowhere, like `history` and `contents`. Generated from the
        aliases, so it cannot drift from what the service answers -- which is
        precisely what a list of keywords typed into a help page does.
        """
        return names_page(
            request=request,
            named=self.keywords(),
            label=self.label_for,
            title=(self.title_for(request.address) or names.TITLE).upper(),
        )

    async def contents_page(self, request: PageRequest) -> Page:
        """Every page this service advertises, with the number that fetches it.

        Registered nowhere, like `history`; a service maps it in or does not.
        Pages with fields are listed as `*52<user_id>#` rather than enumerated,
        which is the point: nobody can list every user on a screen, and
        everybody holding a user number can be told where to put it.
        """
        return contents_page(
            request=request,
            pages=self.routes(),
            title=(self.title_for(request.address) or contents.TITLE).upper(),
        )

    async def fetch(
        self,
        target: str | PageAddress,
        *,
        neighbours: Neighbours | None = None,
        session: MutableMapping[str, object] | None = None,
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
                session=session if session is not None else {},
                history=history,
                state=self._state,
                app=self,
            )
        )


def _wrap(middleware: Middleware, build: Next) -> Next:
    """Bind one middleware to the rest of the chain below it.

    A function rather than a closure written in place, so that it captures this
    iteration's values rather than the last iteration's.
    """

    async def wrapped(request: PageRequest) -> Page | None:
        return await middleware(request, build)

    return wrapped


