"""Declaring pages in a module of their own, gathered by a `PageRouter`.

A handler that lives apart from the service it serves is declared with
`@router.page(...)`, the same call as `@app.page`, and the router's routes reach
the service in one spread: `Sextile(pages=[*router, ...])`. The tests say the
router collects what it is given in order, that a service built from it answers,
and that the two decorators cannot build a route differently.
"""

from sextile import Page, PageAddress, PageFrame, PageRequest, PageRoute, PageRouter, Sextile
from sextile.viewdata.canvas import Canvas


async def _blank(request: PageRequest) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))


class TestWhatARouterCollects:
    def test_a_decorated_handler_becomes_a_route(self) -> None:
        router = PageRouter()

        @router.page("3", title="By day", detail="newest first", keywords=("WHO",))
        async def days(request: PageRequest) -> Page:
            return await _blank(request)

        (route,) = list(router)
        assert route.pattern == "3"
        assert route.title == "By day"
        assert route.detail == "newest first"
        assert route.keywords == ("WHO",)

    def test_the_handler_comes_back_unchanged(self) -> None:
        #  The decorator returns the function it was given, so a module keeps a
        #  callable name where it declared one.
        router = PageRouter()

        @router.page("3")
        async def days(request: PageRequest) -> Page:
            return await _blank(request)

        assert list(router)[0].handler is days

    def test_a_route_takes_the_handler_s_name_by_default(self) -> None:
        router = PageRouter()

        @router.page("3")
        async def days(request: PageRequest) -> Page:
            return await _blank(request)

        assert list(router)[0].name is None

    def test_the_routes_come_out_in_declaration_order(self) -> None:
        router = PageRouter()

        @router.page("1")
        async def first(request: PageRequest) -> Page:
            return await _blank(request)

        @router.page("2")
        async def second(request: PageRequest) -> Page:
            return await _blank(request)

        @router.page("3")
        async def third(request: PageRequest) -> Page:
            return await _blank(request)

        assert [route.pattern for route in router] == ["1", "2", "3"]

    def test_include_adds_routes_after_its_own(self) -> None:
        router = PageRouter()

        @router.page("1")
        async def first(request: PageRequest) -> Page:
            return await _blank(request)

        router.include([PageRoute("2", _blank, name="two"), PageRoute("3", _blank, name="three")])
        assert [route.pattern for route in router] == ["1", "2", "3"]


class TestAServiceBuiltFromARouter:
    def _router(self) -> PageRouter:
        router = PageRouter()

        @router.page("3", title="By day", keywords=("WHO",))
        async def days(request: PageRequest) -> Page:
            return await _blank(request)

        return router

    async def test_a_spread_router_routes_its_pages(self) -> None:
        app = Sextile(pages=[*self._router()])
        assert await app.ask("3") is not None

    async def test_a_router_passed_whole_routes_its_pages(self) -> None:
        #  `pages` takes any iterable, so the router need not be spread.
        app = Sextile(pages=self._router())
        assert await app.ask("3") is not None

    def test_the_service_carries_the_declared_words(self) -> None:
        app = Sextile(pages=self._router())
        (page_info,) = app.pages()
        assert page_info.title == "By day"
        assert app.resolve("WHO") == PageAddress("3")


class TestTheTwoDecoratorsCannotDiverge:
    """`@app.page` and `@router.page` are one implementation, seen two ways.

    Declaring a page one way or the other leaves the service indistinguishable:
    same address, same listed words, same keyword. What proves it is that the
    same arguments reach the same `PageRoute` builder.
    """

    async def test_the_same_arguments_leave_the_same_service(self) -> None:
        by_router = PageRouter()

        @by_router.page("3", name="days", title="By day", keywords=("WHO",))
        async def days_a(request: PageRequest) -> Page:
            return await _blank(request)

        from_router = Sextile(pages=by_router)

        direct = Sextile()

        @direct.page("3", name="days", title="By day", keywords=("WHO",))
        async def days_b(request: PageRequest) -> Page:
            return await _blank(request)

        assert direct.address_for("days") == from_router.address_for("days")
        assert direct.menu_item("days") == from_router.menu_item("days")
        assert direct.resolve("WHO") == from_router.resolve("WHO")
