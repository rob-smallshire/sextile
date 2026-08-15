"""Declaring what a page is, beside where it is written.

Everything about a page is declared once, in one place: its place in the
numbering, what builds it, what to call it where it is listed, and the words
that reach it. `PageRoute` is that declaration as a value, and a service is a
list of them; `PageRouter` collects them from `@router.page` for a handler that
lives in a module of its own. Declaring pages as data makes registration order
unobservable.
"""

from collections.abc import Awaitable, Callable, Iterable, Iterator, Sequence
from dataclasses import dataclass

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
