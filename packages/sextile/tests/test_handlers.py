"""The framework's own pages, routed into a service by one call.

`standard_pages` returns the routes for whichever framework pages a service
gives a number, so every service stops writing the same passthroughs. The tests
say only that each reaches the application's own page and carries the framework's
own words: what the pages show is tested where they are built.
"""

import pytest

from sextile import PageRequest, PageRoute, Sextile, StateKey, handlers, standard_pages
from sextile.addressing import PageAddress
from sextile.state import State
from sextile.visits import SqliteVisits, Visits

VISITS = StateKey[Visits]("visits")


def _asking(app: Sextile, number: str, log: Visits | None = None) -> PageRequest:
    """A request for a page on a service, optionally holding a visit log."""
    state = State()
    if log is not None:
        state[VISITS] = log
    return PageRequest(address=PageAddress(number), app=app, state=state)


class TestStandardPages:
    @pytest.fixture
    def app(self) -> Sextile:
        return Sextile(pages=list(standard_pages(history="92", contents="93", keywords="94")))

    async def test_each_answers_at_the_number_it_was_given(self, app: Sextile) -> None:
        assert await app.ask("92") is not None
        assert await app.ask("93") is not None
        assert await app.ask("94") is not None

    def test_the_route_carries_the_framework_s_own_words(self, app: Sextile) -> None:
        (history,) = (page for page in app.pages() if page.name == "history")
        assert history.title == "Where you have been"
        assert app.resolve("HISTORY") == PageAddress("92")

    def test_a_page_left_out_is_not_routed(self) -> None:
        app = Sextile(pages=list(standard_pages(history="92")))
        assert app.address_for("history") == PageAddress("92")
        assert [page.name for page in app.pages()] == ["history"]


class TestReadershipPages:
    async def test_they_read_the_log_when_it_is_there(self) -> None:
        app = Sextile()
        log = SqliteVisits.open(":memory:")
        for factory in (handlers.recent, handlers.popular, handlers.callers):
            page = await factory(VISITS)(_asking(app, "96", log))
            assert page is not None

    async def test_they_say_so_when_there_is_no_log(self) -> None:
        page = await handlers.recent(VISITS)(_asking(Sextile(), "96"))
        assert page is not None
        rows, _ = page.frames[0].frame.to_grid()
        assert any("No log" in row for row in rows)

    def test_standard_pages_routes_them_when_a_finder_is_given(self) -> None:
        app = Sextile(
            pages=list(
                standard_pages(recent="96", popular="97", callers="98", visits=VISITS)
            )
        )
        assert app.address_for("recent") == PageAddress("96")
        assert app.address_for("callers") == PageAddress("98")

    def test_a_readership_page_without_a_finder_is_refused(self) -> None:
        with pytest.raises(ValueError, match="visits"):
            standard_pages(recent="96")


class TestTheHandlersDirectly:
    async def test_a_plain_handler_reaches_the_application_s_page(self) -> None:
        app = Sextile(pages=[PageRoute("92", handlers.history, title="Been")])
        assert await app.ask("92") is not None
        assert app.address_for("history") == PageAddress("92")
