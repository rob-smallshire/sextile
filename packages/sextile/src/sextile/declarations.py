"""Declaring what a page is, beside where it is written.

Everything about a page is declared once, in one place: its place in the
numbering, what builds it, what to call it where it is listed, and the words
that reach it. `PageRoute` is that declaration as a value; `@page` attaches the
same declaration to the function or method that builds the page, gathered by
`routes_in` for a module and by `routes_on` for an instance. Declaring pages as
data makes registration order unobservable.
"""

from collections.abc import Awaitable, Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass
from types import ModuleType
from typing import Final

from sextile.page import Page

#: A page handler. `None` rather than a page means there is no such page --
#: something *said* to a reader who has not moved, as against somewhere they
#: have gone -- and the session tells the two apart.
type Handler = Callable[..., Awaitable[Page | None]]


@dataclass(frozen=True)
class PageInfo:
    """What a service declared about a page when it registered it.

    The words belong where the page is declared, so they are stated once rather
    than copied into every menu, list and guide that names the page.
    """

    name: str
    """The route's name, which `address_for` also answers to."""

    keyed: str
    """The number a reader would key, fields shown as `<name>`: `52<user_id>`."""

    title: str
    """What to call it. A page with no title is not advertised."""

    detail: str = ""
    """A second line, for a menu with room for one."""


@dataclass(frozen=True)
class PageRoute:
    """One page of a service, declared as a value rather than as a decoration.

    Everything about a page is here: its place in the numbering, what builds it,
    what to call it where it is listed, and the words that reach it. The service
    is a list of these. Declaring pages as data makes registration order
    unobservable: converters, pages, middleware and lifespan all arrive in one
    constructor call, so no step has to run before another.
    """

    pattern: str
    """The page numbers this answers: literal digits and named fields."""

    handler: Handler
    """What builds the page. `None` rather than a page means there is no such
    page, which the session shows differently from one it could not build."""

    name: str | None = None
    """What `address_for` calls it. The handler's own name unless given."""

    title: str = ""
    """What to call this page where it is *listed* rather than shown -- in a
    menu, in the history, in the contents. A page with no title is not
    advertised, which is how a title frame stays off the contents."""

    detail: str = ""
    """A second line, wherever the title gets one."""

    keywords: Sequence[str] = ()
    """Words a reader may key instead of the number."""


def declaring[H: Handler](
    keep: Callable[[PageRoute], object],
    pattern: str,
    *,
    name: str | None,
    title: str,
    detail: str,
    keywords: Sequence[str],
) -> Callable[[H], H]:
    """A `@page`-style decorator that hands the `PageRoute` it builds to `keep`.

    The one implementation behind `Sextile.page` and `PageRouter.page`: both
    build a `PageRoute` from the same arguments and differ only in where it
    goes, so neither decorator can come to build one differently from the other.

    Args:
        keep: What to do with the route the decorated handler declares --
            `Sextile.add_page` for a service, a list's `append` for a router.
        pattern: The page numbers the handler answers.
        name: What `address_for` calls it, or None to take the handler's name.
        title: What to call it where it is listed rather than shown.
        detail: A second line, wherever the title gets one.
        keywords: Words a reader may key instead of the number.

    Returns:
        A decorator that registers its handler and returns it unchanged.
    """

    def register(handler: H) -> H:
        keep(
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


class PageRouter:
    """Pages declared together, in a module of their own, for one service.

    A handler that lives apart from the `Sextile` it serves is declared with
    `@router.page(...)`, the same call as `@app.page`, and the module's pages
    reach the service in one spread. Iterating a router yields its `PageRoute`s
    in the order they were declared, so a service reads the way its source does.

    Example:
        router = PageRouter()

        @router.page("3", title="By day", keywords=("WHO",))
        async def days(request: PageRequest) -> Page:
            ...

        app = Sextile(pages=[*router, *standard_pages(history="92")])
    """

    def __init__(self) -> None:
        self._routes: list[PageRoute] = []

    def page[H: Handler](
        self,
        pattern: str,
        *,
        name: str | None = None,
        title: str = "",
        detail: str = "",
        keywords: Sequence[str] = (),
    ) -> Callable[[H], H]:
        """Declare a page beside the function that builds it.

        The same call as `Sextile.page`, for a handler in a module that has no
        application object to hang it on. The route takes the handler's own name
        unless given one.

        Args:
            pattern: The page numbers this answers: literal digits and fields.
            name: What `address_for` calls it, or None for the handler's name.
            title: What to call it where it is listed. Untitled is unadvertised.
            detail: A second line, wherever the title gets one.
            keywords: Words a reader may key instead of the number.

        Returns:
            A decorator that collects its handler's route and returns it
            unchanged, so a service checked strictly stays so past the decorator.
        """
        return declaring(
            self._routes.append,
            pattern,
            name=name,
            title=title,
            detail=detail,
            keywords=keywords,
        )

    def include(self, routes: Iterable[PageRoute]) -> None:
        """Add every route in `routes`, after the ones this router already has."""
        self._routes.extend(routes)

    def __iter__(self) -> Iterator[PageRoute]:
        return iter(self._routes)


#: Where a declared page keeps what was said about it until a service is built.
_DECLARED: Final = "__sextile_page__"


@dataclass(frozen=True)
class _Declaration:
    """A page declared beside its handler, waiting to be gathered."""

    pattern: str
    name: str | None
    title: str
    detail: str
    keywords: tuple[str, ...]


def page[H](
    pattern: str,
    *,
    name: str | None = None,
    title: str = "",
    detail: str = "",
    keywords: Sequence[str] = (),
) -> Callable[[H], H]:
    """Declare a page beside the function or method that builds it.

        class Board(Sextile):
            @page("5", title="By user", detail="browse by name")
            async def users(self, request: PageRequest) -> Page:
                ...

    `app.page(...)` does the same thing, but only where an application object
    already exists to hang it on. A service whose handlers are methods has no
    `self` at class-definition time, so registering with `app.page` would put
    the registrations a long way from the functions they describe. This keeps
    them together. The same declaration on a module-level function is gathered
    by `routes_in`.

    Collected when the application is constructed, in the order they are
    written, base classes first. The route takes the handler's name unless
    given one, leading underscores stripped.

    Unbounded in the handler's type: what is decorated here may be an unbound
    method, taking a `self` that does not exist yet.
    """

    def declare(handler: H) -> H:
        setattr(
            handler,
            _DECLARED,
            _Declaration(
                pattern=pattern,
                name=name,
                title=title,
                detail=detail,
                keywords=tuple(keywords),
            ),
        )
        return handler

    return declare


def routes_in(module: ModuleType) -> tuple[PageRoute, ...]:
    """The pages a module declares with `@page`, in the order they are written.

    The module-level counterpart of declaring pages on a class, for the
    service whose handlers are ordinary functions. The declaration sits on
    the function that builds the page, and the factory says
    `pages=routes_in(pages_module)` instead of keeping a separate list that has
    to trail its handlers.

    Decorate a function where it is defined, not where it is imported: the
    declaration rides on the function object itself, so decorating a
    borrowed handler would declare it for everyone who imports it. A route
    for somebody else's handler -- the framework's own pages, say -- is one
    `PageRoute` line beside the call to this.
    """
    return tuple(
        _route(attribute, value, declaration)
        for attribute, value in vars(module).items()
        if (declaration := _declared_on(value)) is not None
    )


def routes_on(instance: object) -> tuple[PageRoute, ...]:
    """The pages an instance's class declared with `@page`, handlers bound.

    Base classes first, and within each the order they are written, so that
    `pages()` lists a service the way its source reads. Keyed by attribute so
    that a subclass overriding a page replaces it rather than colliding with
    it.
    """
    declared: dict[str, _Declaration] = {}
    for klass in reversed(type(instance).__mro__):
        for attribute, value in vars(klass).items():
            found = _declared_on(value)
            if found is not None:
                declared[attribute] = found
    return tuple(
        _route(attribute, getattr(instance, attribute), declaration)
        for attribute, declaration in declared.items()
    )


def _declared_on(value: object) -> _Declaration | None:
    found = getattr(value, _DECLARED, None)
    return found if isinstance(found, _Declaration) else None


def _route(attribute: str, handler: Handler, declaration: _Declaration) -> PageRoute:
    return PageRoute(
        pattern=declaration.pattern,
        handler=handler,
        name=declaration.name or attribute.lstrip("_"),
        title=declaration.title,
        detail=declaration.detail,
        keywords=declaration.keywords,
    )
