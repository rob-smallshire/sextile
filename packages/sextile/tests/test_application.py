"""The interface between the framework and whatever is running on it.

An application answers page requests. Sextile supplies one that answers them by
routing, which is the shape almost every service will want, and an application
free to answer them some other way is still an application.

A handler is a function of a request, not of a page number: two callers keying
the same number may legitimately be shown different things once there is such a
thing as being logged in.
"""

import pytest

from sextile.addressing import PageAddress, UnknownPageError
from sextile.application import Application, Arrival, PageRequest, Sextile
from sextile.page import Page, PageFrame
from sextile.routing import NoSuchRouteError
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.frame import Frame


def blank() -> Frame:
    return Frame()


def one_frame() -> Page:
    return Page(frames=(PageFrame(blank()),))


def saying(what: str) -> Page:
    canvas = Canvas()
    canvas.row(0).text(what)
    return Page(frames=(PageFrame(canvas.frame),))


def request_for(digits: str, **params: object) -> PageRequest:
    return PageRequest(address=PageAddress(digits), params=params)


def text_of(page: Page | None, row: int = 0) -> str:
    assert page is not None, "expected a page, and the application had none"
    characters, _ = page.frames[0].frame.to_grid()
    return characters[row].rstrip()


class TestRouting:
    async def test_a_handler_answers_its_page(self) -> None:
        app = Sextile()

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            return saying("MAIN")

        assert text_of(await app.respond(request_for("1"))) == "MAIN"

    async def test_a_handler_is_given_what_the_pattern_captured(self) -> None:
        app = Sextile()

        @app.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            return saying(f"POST {post_id}")

        assert text_of(await app.respond(request_for("82489493"))) == "POST 489493"

    async def test_a_handler_is_given_the_request_it_answers(self) -> None:
        app = Sextile()

        @app.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            return saying(str(request.address))

        assert text_of(await app.respond(request_for("82489493"))) == "82489493"

    async def test_the_decorator_gives_the_function_back(self) -> None:
        app = Sextile()

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            return one_frame()

        assert await main(request_for("1")) is not None

    async def test_a_route_is_named_for_the_function_that_answers_it(self) -> None:
        #  So that a page can link to another by name without being told twice
        #  what to call it.
        app = Sextile()

        @app.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            return one_frame()

        assert app.address_for("post", post_id=1) == PageAddress("821")

    async def test_a_route_may_be_named_something_else(self) -> None:
        app = Sextile()

        @app.page("8", name="latest")
        async def posts_index(request: PageRequest) -> Page:
            return one_frame()

        assert app.address_for("latest") == PageAddress("8")


class TestSayingSo:
    #  An unrouted page is answered with nothing rather than with a notice: the
    #  two are shown differently. A page that exists is somewhere the reader has
    #  gone; a page that does not is something said to a reader who has not
    #  moved, and the session needs to be able to tell them apart.

    async def test_an_unrouted_page_is_not_answered(self) -> None:
        app = Sextile()
        assert await app.respond(request_for("6")) is None

    async def test_a_word_that_names_nothing_says_so(self) -> None:
        app = Sextile()
        page = await app.not_found("BANANA")
        assert "BANANA" in text_of(page, row=2)

    async def test_an_application_can_say_it_its_own_way(self) -> None:
        app = Sextile()

        @app.on_not_found
        async def missing(target: str) -> Page:
            return saying(f"NO {target}")

        assert text_of(await app.not_found("BANANA")) == "NO BANANA"


class TestResolving:
    async def test_digits_name_themselves(self) -> None:
        app = Sextile()
        assert app.resolve("82489493") == PageAddress("82489493")

    async def test_a_keyword_names_a_page(self) -> None:
        app = Sextile()
        app.alias("MAIN", "1")
        assert app.resolve("MAIN") == PageAddress("1")

    async def test_a_word_that_is_no_keyword_names_nothing(self) -> None:
        app = Sextile()
        with pytest.raises(UnknownPageError):
            app.resolve("BANANA")

    async def test_a_keyword_may_name_a_route_by_its_name(self) -> None:
        app = Sextile()

        @app.page("8", name="latest")
        async def posts_index(request: PageRequest) -> Page:
            return one_frame()

        app.alias("LATEST", app.address_for("latest"))
        assert app.resolve("LATEST") == PageAddress("8")


class TestSessionState:
    #  The connection is the session, so a handler has somewhere to keep what
    #  this caller has done. Nothing uses it yet; being logged in will.

    async def test_a_request_carries_the_caller_s_own_state(self) -> None:
        app = Sextile()
        state: dict[str, object] = {"user": "komadori"}

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            return saying(str(request.session["user"]))

        page = await app.respond(PageRequest(address=PageAddress("1"), session=state))
        assert text_of(page) == "komadori"

    async def test_a_handler_can_leave_something_behind(self) -> None:
        app = Sextile()
        state: dict[str, object] = {}

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            request.session["seen"] = True
            return one_frame()

        await app.respond(PageRequest(address=PageAddress("1"), session=state))
        assert state == {"seen": True}


class TestArrival:
    #  Which post is "next" depends on how the reader got here: from a day's
    #  index it is the next post that day, from a forum the next in that forum.
    #  Arrive by keying a number and there is no sequence, so none is offered.

    async def test_a_request_knows_of_no_neighbours_by_default(self) -> None:
        request = request_for("821")
        assert request.arrival.preceding is None
        assert request.arrival.following is None

    async def test_a_handler_can_offer_what_it_was_told_of(self) -> None:
        app = Sextile()

        @app.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            following = request.arrival.following
            choices = {"N": following} if following else {}
            return Page(frames=(PageFrame(blank(), choices=choices),))

        page = await app.respond(
            PageRequest(
                address=PageAddress("821"),
                arrival=Arrival(following=PageAddress("822")),
            )
        )
        assert page is not None
        assert page.frames[0].destination("N") == PageAddress("822")


class TestMounting:
    #  A mounted application sees the address unchanged. Stripping a prefix, as
    #  a web framework does, cannot work here: the application draws the page
    #  number into the frame itself, and a number drawn before the parent could
    #  correct it would be a number the reader cannot key.

    async def test_a_mounted_application_answers_below_its_prefix(self) -> None:
        app = Sextile()
        inner = Sextile()

        @inner.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            return saying(f"POST {post_id}")

        app.mount("8", inner)
        assert text_of(await app.respond(request_for("82489493"))) == "POST 489493"

    async def test_a_mounted_application_is_given_the_whole_address(self) -> None:
        app = Sextile()
        inner = Sextile()

        @inner.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            return saying(str(request.address))

        app.mount("8", inner)
        assert text_of(await app.respond(request_for("82489493"))) == "82489493"

    async def test_an_application_mounted_at_the_root_answers_everything(self) -> None:
        app = Sextile()
        inner = Sextile()

        @inner.page("1")
        async def main(request: PageRequest) -> Page:
            return saying("MAIN")

        app.mount("", inner)
        assert text_of(await app.respond(request_for("1"))) == "MAIN"

    async def test_the_host_s_own_routes_are_preferred(self) -> None:
        app = Sextile()
        inner = Sextile()

        @inner.page("1")
        async def theirs(request: PageRequest) -> Page:
            return saying("THEIRS")

        @app.page("1")
        async def ours(request: PageRequest) -> Page:
            return saying("OURS")

        app.mount("", inner)
        assert text_of(await app.respond(request_for("1"))) == "OURS"

    async def test_a_page_no_mounted_application_has_is_not_answered(self) -> None:
        app = Sextile()
        app.mount("8", Sextile())
        assert await app.respond(request_for("82489493")) is None

    async def test_a_page_the_first_mount_declines_falls_to_the_next(self) -> None:
        first, second = Sextile(), Sextile()

        @second.page("1")
        async def main(request: PageRequest) -> Page:
            return saying("SECOND")

        app = Sextile()
        app.mount("", first)
        app.mount("", second)
        answered = await app.respond(request_for("1"))
        assert answered is not None
        assert text_of(answered) == "SECOND"

    async def test_a_mounted_application_s_keywords_are_offered_too(self) -> None:
        app = Sextile()
        inner = Sextile()
        inner.alias("MAIN", "1")
        app.mount("", inner)
        assert app.resolve("MAIN") == PageAddress("1")

    async def test_mounting_starts_and_stops_what_is_mounted(self) -> None:
        app = Sextile()
        inner = Recording()
        app.mount("8", inner)
        await app.startup()
        await app.shutdown()
        assert inner.events == ["startup", "shutdown"]


class TestLifespan:
    #  An application that owns a database or an HTTP client needs somewhere to
    #  open and close it that is not the first page request.

    async def test_an_application_starts_and_stops(self) -> None:
        app = Recording()
        await app.startup()
        await app.shutdown()
        assert app.events == ["startup", "shutdown"]

    async def test_starting_is_optional(self) -> None:
        app = Sextile()
        await app.startup()
        await app.shutdown()


class Recording(Application):
    """An application that is not a router, which is the point of it."""

    def __init__(self) -> None:
        self.events: list[str] = []

    async def respond(self, request: PageRequest) -> Page:
        self.events.append(f"respond {request.address}")
        return one_frame()

    async def startup(self) -> None:
        self.events.append("startup")

    async def shutdown(self) -> None:
        self.events.append("shutdown")


class TestAnApplicationThatIsNotARouter:
    async def test_it_answers_requests(self) -> None:
        app = Recording()
        await app.respond(request_for("1"))
        assert app.events == ["respond 1"]

    async def test_it_resolves_numbers_without_being_told_how(self) -> None:
        app = Recording()
        assert app.resolve("1") == PageAddress("1")

    async def test_it_has_something_to_say_about_a_page_it_has_not_got(self) -> None:
        app = Recording()
        page = await app.not_found("BANANA")
        assert "BANANA" in text_of(page, row=2)


class TestRegistrationMistakes:
    def test_a_pattern_may_not_be_routed_twice(self) -> None:
        app = Sextile()

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            return one_frame()

        with pytest.raises(ValueError):

            @app.page("1")
            async def other(request: PageRequest) -> Page:
                return one_frame()

    def test_an_address_cannot_be_built_for_a_route_there_is_not(self) -> None:
        app = Sextile()
        with pytest.raises(NoSuchRouteError):
            app.address_for("post", post_id=1)


class TestRingingOffForWantOfAReply:
    #  A page rather than a line of text written over whatever was showing.
    #  Being cut off is worth a screen of its own, and a message overprinting a
    #  frame is hard to pick out from the frame.

    async def test_there_is_something_to_show(self) -> None:
        app = Sextile()
        page = await app.timed_out()
        assert "no reply" in text_of(page, row=2).lower()

    async def test_it_says_the_line_has_gone(self) -> None:
        app = Sextile()
        assert "OFF" in text_of(await app.timed_out()).upper()

    async def test_a_service_can_say_it_its_own_way(self) -> None:
        app = Sextile()

        @app.on_timed_out
        async def gone() -> Page:
            return saying("STILL THERE? NO.")

        assert text_of(await app.timed_out()) == "STILL THERE? NO."

    async def test_it_leaves_room_to_type_beneath(self) -> None:
        #  The reader is about to talk to their modem, and the cursor is put
        #  below the last thing said.
        app = Sextile()
        page = await app.timed_out()
        assert page.frames[0].frame.last_written_row() < 20

    async def test_an_application_that_is_not_a_router_has_one_too(self) -> None:
        app = Recording()
        assert "no reply" in text_of(await app.timed_out(), row=2).lower()
