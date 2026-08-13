"""The framework's pages, as handlers a route can name directly.

`history`, `contents` and `names` are methods on the application, which a
`PageRoute` cannot name without an instance to bind them to -- so every
service was writing the same three-line passthrough, three times over. These
handlers are those passthroughs written once, and the tests say only that
each reaches the application's own page: what the pages show is tested where
they are built.
"""

import pytest

from sextile import PageRoute, Sextile, pages
from sextile.addressing import PageAddress


class TestRoutingStraightToAFrameworkPage:
    @pytest.fixture
    def app(self) -> Sextile:
        return Sextile(
            pages=[
                PageRoute("92", pages.history, name="history",
                          title="Where you have been"),
                PageRoute("93", pages.contents, name="contents",
                          title="Every page"),
                PageRoute("94", pages.names, name="names",
                          title="Words you can key", keywords=("KEYWORDS",)),
            ]
        )

    async def test_history_answers_at_the_service_s_number(
        self, app: Sextile
    ) -> None:
        page = await app.ask("92")

        assert page is not None

    async def test_contents_answers_at_the_service_s_number(
        self, app: Sextile
    ) -> None:
        page = await app.ask("93")

        assert page is not None

    async def test_names_answers_at_the_service_s_number(
        self, app: Sextile
    ) -> None:
        page = await app.ask("94")

        assert page is not None

    async def test_the_route_needs_no_name_of_its_own(self) -> None:
        #  The handler's own name is the route's, as for any handler -- which
        #  is what lets the line in the service's list stay short.
        app = Sextile(pages=[PageRoute("92", pages.history, title="Been")])

        assert app.address_for("history") == PageAddress("92")
