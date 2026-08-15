"""The interface between the framework and whatever is running on it.

An application answers page requests. Sextile supplies one that answers them by
routing, which is the shape almost every service will want, and an application
free to answer them some other way is still an application.

A handler is a function of a request, not of a page number: two callers keying
the same number may legitimately be shown different things once there is such a
thing as being logged in.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest

from sextile import handlers
from sextile.application import (
    Neighbours,
    PageRequest,
    PageRoute,
    Sextile,
)
from sextile.middleware import CallNext, Middleware
from sextile.page import Page, PageAddress, PageFrame, UnknownPageError
from sextile.routing import Converter, NoSuchRouteError
from sextile.session.session import Session
from sextile.state import StateKey
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.frame import Frame

#: A key a lifespan writes and a handler reads, standing in for whatever a real
#: service opens: an archive, an index, a clock.
ARCHIVE = StateKey[str]("archive")


def blank() -> Frame:
    return Frame()


def one_frame() -> Page:
    return Page(frames=(PageFrame(blank()),))


def saying(what: str) -> Page:
    canvas = Canvas()
    canvas.row(0).text(what)
    return Page(frames=(PageFrame(canvas.frame),))


def request_for(app: Sextile, digits: str, **params: object) -> PageRequest:
    return PageRequest(address=PageAddress(digits), app=app, params=params)


def row_of(page: Page | None, row: int = 0) -> str:
    assert page is not None, "expected a page, and the application had none"
    characters, _ = page.frames[0].frame.to_grid()
    return characters[row].rstrip()


class TestRouting:
    async def test_a_handler_answers_its_page(self) -> None:
        app = Sextile()

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            return saying("MAIN")

        assert row_of(await app.fetch("1")) == "MAIN"

    async def test_a_handler_is_given_what_the_pattern_captured(self) -> None:
        app = Sextile()

        @app.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            return saying(f"POST {post_id}")

        assert row_of(await app.fetch("82489493")) == "POST 489493"

    async def test_a_handler_is_given_the_request_it_answers(self) -> None:
        app = Sextile()

        @app.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            return saying(str(request.address))

        assert row_of(await app.fetch("82489493")) == "82489493"

    async def test_the_decorator_gives_the_function_back(self) -> None:
        app = Sextile()

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            return one_frame()

        assert await main(request_for(app, "1")) is not None

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
        assert await app.fetch("6") is None

    async def test_a_word_that_names_nothing_says_so(self) -> None:
        app = Sextile()
        page = await app.not_found(request_for(app, "1"), "BANANA")
        assert "BANANA" in row_of(page, row=2)

    async def test_an_application_can_say_it_its_own_way(self) -> None:
        app = Sextile()

        @app.on_not_found
        async def missing(request: PageRequest, target: str) -> Page:
            return saying(f"NO {target}")

        assert row_of(await app.not_found(request_for(app, "1"), "BANANA")) == "NO BANANA"


class TestResolving:
    async def test_digits_name_themselves(self) -> None:
        app = Sextile()
        assert app.resolve("82489493") == PageAddress("82489493")

    async def test_a_keyword_names_a_page(self) -> None:
        app = Sextile()
        app.add_keyword("MAIN", "1")
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

        app.add_keyword("LATEST", app.address_for("latest"))
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

        page = await app.fetch("1", session=state)
        assert row_of(page) == "komadori"

    async def test_a_handler_can_leave_something_behind(self) -> None:
        app = Sextile()
        state: dict[str, object] = {}

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            request.session["seen"] = True
            return one_frame()

        await app.fetch("1", session=state)
        assert state == {"seen": True}


class TestNeighbours:
    #  Which post is "next" depends on how the reader got here: from a day's
    #  index it is the next post that day, from a forum the next in that forum.
    #  Arrive by keying a number and there is no sequence, so none is offered.

    async def test_a_request_knows_of_no_neighbours_by_default(self) -> None:
        request = request_for(Sextile(), "821")
        assert request.neighbours.previous is None
        assert request.neighbours.next is None

    async def test_a_handler_can_offer_what_it_was_told_of(self) -> None:
        app = Sextile()

        @app.page("82{post_id:int}")
        async def post(request: PageRequest, post_id: int) -> Page:
            following = request.neighbours.next
            choices = {"N": following} if following else {}
            return Page(frames=(PageFrame(blank(), choices=choices),))

        page = await app.fetch(
            "821", neighbours=Neighbours(next=PageAddress("822"))
        )
        assert page is not None
        assert page.frames[0].destination("N") == PageAddress("822")


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


class Recording(Sextile):
    """A service that records when it is started and stopped."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[str] = []

    async def startup(self) -> None:
        self.events.append("startup")

    async def shutdown(self) -> None:
        self.events.append("shutdown")


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


class TestWhatAServiceIsCalled:
    #  The framework names nothing. A service that wants to be named in what
    #  the framework says for it has to say what it is called.

    def test_a_service_may_be_nameless(self) -> None:
        assert Sextile().name == ""

    def test_a_service_can_be_named(self) -> None:
        assert Sextile(name="Stardot").name == "Stardot"

    async def test_the_name_is_used_where_the_framework_speaks(self) -> None:
        app = Sextile(name="Stardot")
        page = await app.timed_out(request_for(app, "1"), 0)
        assert "Thank you for calling Stardot." in row_of(page, row=7)

    async def test_a_nameless_service_is_not_thanked_on_its_behalf(self) -> None:
        #  Better to say nothing than to say "Thank you for calling ." or, worse,
        #  to thank the reader for calling the framework.
        app = Sextile()
        page = await app.timed_out(request_for(app, "1"), 0)
        assert "connect" not in "".join(
            page.frames[0].frame.to_grid()[0]
        )


class TestRingingOffForWantOfAReply:
    #  A page rather than a line of text written over whatever was showing.
    #  Being cut off is worth a screen of its own, and a message overprinting a
    #  frame is hard to pick out from the frame.

    async def test_there_is_something_to_show(self) -> None:
        app = Sextile()
        page = await app.timed_out(request_for(app, "1"), 0)
        assert "no reply" in row_of(page, row=2).lower()

    async def test_it_says_the_line_has_gone(self) -> None:
        app = Sextile()
        assert "OFF" in row_of(await app.timed_out(request_for(app, "1"), 0)).upper()

    async def test_it_says_where_the_reader_had_got_to(self) -> None:
        #  So they can key it again on calling back, which is the one piece of
        #  their session worth handing over: the terminal keeps nothing. The
        #  page they were on is the request's address.
        app = Sextile()
        page = await app.timed_out(request_for(app, "82489493"), 0)
        assert "*82489493#" in row_of(page, row=5)

    async def test_a_service_can_say_it_its_own_way(self) -> None:
        app = Sextile()

        @app.on_timed_out
        async def gone(request: PageRequest, frame_index: int) -> Page:
            return saying(f"YOU WERE ON *{request.address}#")

        assert row_of(await app.timed_out(request_for(app, "8"), 0)) == "YOU WERE ON *8#"

    async def test_it_leaves_room_to_type_beneath(self) -> None:
        #  The reader is about to talk to their modem, and the cursor is put
        #  below the last thing said.
        app = Sextile(name="Stardot")
        page = await app.timed_out(request_for(app, "1"), 0)
        assert page.frames[0].frame.last_written_row() < 20



class TestWhereTheReaderHasBeen:
    #  The terminal keeps nothing, so if a service wants to offer a way back
    #  through the call it has to be told the way back.

    async def test_a_request_carries_no_history_by_default(self) -> None:
        assert request_for(Sextile(), "1").history == ()

    async def test_a_handler_is_told_where_the_reader_has_been(self) -> None:
        app = Sextile()

        @app.page("1")
        async def main(request: PageRequest) -> Page:
            return saying(" ".join(str(been) for been in request.history))

        page = await app.fetch(
            "1", history=(PageAddress("8"), PageAddress("82489493"))
        )
        assert row_of(page) == "8 82489493"


class TestAskingWhatAnAddressIs:
    """An application's own numbering, read back.

    Working out what `82489493` is by taking the digits apart again would be the
    numbering scheme written down twice.
    """

    def test_a_routed_address_gives_its_route_and_fields(self) -> None:
        app = Sextile()

        @app.page("82{post_id:int}", name="post")
        async def post(request: PageRequest, post_id: int) -> Page:
            return one_frame()

        found = app.match(PageAddress("82489493"))
        assert found is not None
        assert found.name == "post"
        assert found.params == {"post_id": 489493}

    def test_an_address_with_no_route_gives_nothing(self) -> None:
        assert Sextile().match(PageAddress("6")) is None


class TestLabellingAPage:
    """What to call a page in a list of pages a reader has visited.

    Route names are the application's own words, so a generic label comes out in
    the service's vocabulary without the framework knowing any of it.
    """

    def test_a_page_is_labelled_by_its_route(self) -> None:
        app = Sextile()

        @app.page("8", name="latest posts")
        async def posts(request: PageRequest) -> Page:
            return one_frame()

        assert app.label_for(PageAddress("8")) == "latest posts"

    def test_its_fields_come_after_the_name(self) -> None:
        app = Sextile()

        @app.page("82{post_id:int}", name="post")
        async def post(request: PageRequest, post_id: int) -> Page:
            return one_frame()

        assert app.label_for(PageAddress("82489493")) == "post 489493"

    def test_an_unrouted_page_is_labelled_by_its_number(self) -> None:
        assert Sextile().label_for(PageAddress("6")) == "*6#"

    def test_a_route_may_give_a_label_template_over_its_fields(self) -> None:
        #  What replaced the describe hook: the words for a field page go beside
        #  the route, as a format template filled from the captured fields.
        app = Sextile(
            pages=[
                PageRoute(
                    "82{post_id:int}", _nothing, name="post", title="One post",
                    label="Post {post_id}",
                )
            ]
        )
        assert app.label_for(PageAddress("82489493")) == "Post 489493"

    def test_a_label_may_be_a_callable_over_the_fields(self) -> None:
        app = Sextile(
            pages=[
                PageRoute(
                    "82{post_id:int}", _nothing, name="post", title="One post",
                    label=lambda post_id: f"#{post_id}",
                )
            ]
        )
        assert app.label_for(PageAddress("82489493")) == "#489493"

    def test_a_route_without_a_label_falls_back_to_the_title(self) -> None:
        app = Sextile(
            pages=[PageRoute("1", _nothing, name="main", title="Main index")]
        )
        assert app.label_for(PageAddress("1")) == "Main index"


class TestSayingWhatAPageIsAtRegistration:
    """The words go where the page is declared, and everything else reads them.

    Otherwise a service names each page three times over -- in its menu, in
    whatever labels a history, and in its own guide -- and the three drift.
    """

    def test_a_page_can_be_given_a_title(self) -> None:
        app = Sextile()

        @app.page("5", name="users", title="By user")
        async def users(request: PageRequest) -> Page:
            return one_frame()

        found = app.route("users")
        assert found is not None
        assert found.title == "By user"

    def test_and_a_line_of_detail(self) -> None:
        app = Sextile()

        @app.page("5", name="users", title="By user", detail="who registered")
        async def users(request: PageRequest) -> Page:
            return one_frame()

        found = app.route("users")
        assert found is not None
        assert found.detail == "who registered"

    def test_the_title_is_what_labels_it(self) -> None:
        app = Sextile()

        @app.page("5", name="users", title="By user")
        async def users(request: PageRequest) -> Page:
            return one_frame()

        assert app.label_for(PageAddress("5")) == "By user"

    def test_a_titled_page_with_fields_is_labelled_with_them(self) -> None:
        app = Sextile()

        @app.page("52{user_id:int}", name="user", title="User")
        async def user(request: PageRequest, user_id: int) -> Page:
            return one_frame()

        assert app.label_for(PageAddress("5210058")) == "User 10058"

    def test_an_untitled_page_falls_back_to_its_route_name(self) -> None:
        app = Sextile()

        @app.page("5", name="users")
        async def users(request: PageRequest) -> Page:
            return one_frame()

        assert app.label_for(PageAddress("5")) == "users"

    def test_asking_about_a_page_there_is_not(self) -> None:
        assert Sextile().route("nothing") is None


class TestListingThePages:
    #  What a service is made of, from the registrations rather than from a
    #  list somebody has to remember to update.

    def build(self) -> Sextile:
        async def anything(request: PageRequest, **fields: object) -> Page:
            return one_frame()

        app = Sextile()
        app.page("1", name="main", title="Main index")(anything)
        app.page("5", name="users", title="By user")(anything)
        app.page("52{user_id:int}", name="user", title="One user")(anything)
        app.page("90", name="logoff")(anything)
        return app

    def test_titled_pages_are_listed(self) -> None:
        assert [page.name for page in self.build().routes()] == [
            "main",
            "users",
            "user",
        ]

    def test_a_page_with_no_title_is_left_out(self) -> None:
        #  Giving one a title is how a service says it may be advertised, so a
        #  logoff page or a title frame stays off the list without a flag.
        assert "logoff" not in [page.name for page in self.build().routes()]

    def test_each_carries_the_number_a_reader_would_key(self) -> None:
        listed = {page.name: page.keyed for page in self.build().routes()}
        assert listed["users"] == "5"
        assert listed["user"] == "52<user_id>"

    def test_they_come_in_the_order_they_were_registered(self) -> None:
        #  Not the order the router tries them in, which is about matching.
        assert [page.keyed for page in self.build().routes()] == ["1", "5", "52<user_id>"]


class TestWhereZeroGoes:
    """`home` is where a caller arrives; `index` is where `0` goes.

    The same question until a service has something to show before its index --
    a title frame is arrived at once and never returned to.
    """

    def test_they_are_the_same_by_default(self) -> None:
        app = Sextile()
        assert app.index == app.home == PageAddress("1")

    def test_a_service_opening_on_a_title_frame_keeps_them_apart(self) -> None:
        app = Sextile(home="0", index="1")
        assert app.home == PageAddress("0")
        assert app.index == PageAddress("1")

    async def test_the_framework_s_own_pages_use_the_index(self) -> None:
        app = Sextile(home="0", index="1")
        page = await handlers.history_page(
            PageRequest(address=PageAddress("92"), app=app, history=(PageAddress("8"),))
        )
        assert page.frames[0].destination("0") == PageAddress("1")




class TestWhenAPageBreaks:
    """The viewdata equivalent of a 500.

    Distinct from the unknown-page notice on purpose: one says the reader asked
    for something that is not here, the other says the service could not build
    something that is. Telling them the first when it is the second sends them
    away thinking they mistyped.
    """

    async def test_there_is_something_to_show(self) -> None:
        app = Sextile()
        page = await app.failed(request_for(app, "82489493"), RuntimeError("boom"))
        assert "SERVICE ERROR" in row_of(page).upper()

    async def test_it_names_the_page_that_broke(self) -> None:
        app = Sextile()
        page = await app.failed(request_for(app, "82489493"), RuntimeError("boom"))
        assert "*82489493#" in row_of(page, row=2)

    async def test_it_says_whose_fault_it_is(self) -> None:
        #  A reader on a 1200 baud line will otherwise assume they did it.
        app = Sextile()
        page = await app.failed(request_for(app, "8"), RuntimeError("boom"))
        assert "our end" in "\n".join(page.frames[0].frame.to_grid()[0]).lower()

    async def test_a_service_can_say_it_its_own_way(self) -> None:
        app = Sextile()

        @app.on_failed
        async def broke(request: PageRequest, error: Exception) -> Page:
            return saying(f"SORRY ABOUT *{request.address}#")

        assert row_of(await app.failed(request_for(app, "8"), RuntimeError("boom"))) == (
            "SORRY ABOUT *8#"
        )

    async def test_the_service_is_handed_the_exception(self) -> None:
        #  What a service actually wants, to log it its own way or tell the
        #  reader which kind of thing went wrong.
        app = Sextile()
        seen: list[Exception] = []

        @app.on_failed
        async def broke(request: PageRequest, error: Exception) -> Page:
            seen.append(error)
            return saying("SORRY")

        boom = RuntimeError("the archive is on fire")
        await app.failed(request_for(app, "8"), boom)
        assert seen == [boom]

    async def test_it_leaves_room_to_type_beneath(self) -> None:
        app = Sextile()
        page = await app.failed(request_for(app, "1"), RuntimeError("boom"))
        assert page.frames[0].frame.last_written_row() < 20


class TestFieldShapesOfAnApplicationsOwn:
    """A service may need a field the framework does not offer.

    The constructor takes its converters as well as its pages, and registers
    the converters first, so a page given in `pages=` may use a field shape of
    the service's own without the order of the two arguments mattering.
    """

    def test_a_page_given_at_construction_may_use_one(self) -> None:
        tens = Converter(
            field_pattern=r"[0-9]{2}",
            width=2,
            parse=lambda digits: int(digits) * 10,
            format=lambda value: f"{int(value) // 10:02d}",  # type: ignore[call-overload]
        )

        async def counted(request: PageRequest, count: int) -> Page:
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        app = Sextile(
            converters={"tens": tens},
            pages=[PageRoute("7{count:tens}", counted, name="counted")],
        )
        assert app.address_for("counted", count=420) == PageAddress("742")
        assert app.match(PageAddress("742")) is not None

    def test_registering_one_afterwards_still_works(self) -> None:
        #  For a service built round a module-level application, where the
        #  decorator has an object to hang on and ordering never arises.
        app = Sextile()
        app.add_converter("pair", Converter(field_pattern=r"[0-9]{2}", width=2, parse=int))

        @app.page("8{n:pair}", name="paired")
        async def paired(request: PageRequest, n: int) -> Page:
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        assert app.match(PageAddress("842")) is not None


class TestWhatAServiceHoldsWhileItRuns:
    """One function opens and closes it, and the pages are handed the result.

    A pair of handlers was tried first and replaced. Setup and teardown as two
    functions have to be kept in step by hand and hoist whatever they open into
    somewhere both can see; as two halves of one function they cannot drift,
    and the thing opened is an ordinary local held across the yield. Starlette
    deprecated its own startup and shutdown handlers for this, which is the
    same lesson learned earlier by somebody else.
    """

    async def test_the_lifespan_runs_before_the_first_call(self) -> None:
        done: list[str] = []

        @asynccontextmanager
        async def lifespan(app: Sextile) -> AsyncIterator[None]:
            done.append("opened")
            yield
            done.append("closed")

        app = Sextile(lifespan=lifespan)
        await app.startup()
        assert done == ["opened"]
        await app.shutdown()
        assert done == ["opened", "closed"]

    async def test_what_it_writes_is_what_the_service_holds(self) -> None:
        @asynccontextmanager
        async def lifespan(app: Sextile) -> AsyncIterator[None]:
            app.state[ARCHIVE] = "an archive"
            yield

        app = Sextile(lifespan=lifespan)
        await app.startup()
        assert app.state[ARCHIVE] == "an archive"

    async def test_a_page_is_handed_it(self) -> None:
        #  Which is the point: a handler reaches what the service opened
        #  without the service having to be a class holding it.
        seen: list[str] = []

        @asynccontextmanager
        async def lifespan(app: Sextile) -> AsyncIterator[None]:
            app.state[ARCHIVE] = "an archive"
            yield

        app = Sextile(lifespan=lifespan)

        @app.page("1", name="main")
        async def main(request: PageRequest) -> Page:
            seen.append(request.state[ARCHIVE])
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        await app.startup()
        await Session(app).greeting()
        assert seen == ["an archive"]

    async def test_it_is_given_the_application(self) -> None:
        #  So that a lifespan may reach the numbering -- and because a factory
        #  has no name for the application until the constructor has returned.
        seen: list[str] = []

        @asynccontextmanager
        async def lifespan(app: Sextile) -> AsyncIterator[None]:
            seen.append(app.name)
            yield

        await Sextile(name="Weather", lifespan=lifespan).startup()
        assert seen == ["Weather"]

    async def test_a_service_with_no_lifespan_still_starts(self) -> None:
        app = Sextile()
        await app.startup()
        assert ARCHIVE not in app.state
        await app.shutdown()

    async def test_and_lets_go_of_it_afterwards(self) -> None:
        @asynccontextmanager
        async def lifespan(app: Sextile) -> AsyncIterator[None]:
            app.state[ARCHIVE] = "an archive"
            yield

        app = Sextile(lifespan=lifespan)
        await app.startup()
        await app.shutdown()
        assert ARCHIVE not in app.state


class TestATargetTheNumberingDoesNotName:
    """A service may search its own data for what a reader keyed.

    A viewdata reader keys letters and the numbering knows only the keywords it
    was given, so a service holding a gazetteer, a callsign list or a postcode
    table wants a say before the word is called unknown.
    """

    def test_a_word_no_keyword_names_is_offered_to_the_service(self) -> None:
        app = Sextile()
        app.page("82{n:int}", name="thing")(_nothing)

        @app.on_unresolved
        def look_it_up(target: str) -> PageAddress | None:
            return PageAddress("8242") if target == "TROMBONE" else None

        assert app.resolve("TROMBONE") == PageAddress("8242")

    def test_and_may_still_say_it_names_nothing(self) -> None:
        app = Sextile()

        @app.on_unresolved
        def look_it_up(target: str) -> PageAddress | None:
            return None

        with pytest.raises(UnknownPageError):
            app.resolve("TROMBONE")

    def test_a_registered_keyword_is_not_shadowed_by_it(self) -> None:
        #  The handler is a last resort and never a first one. A service whose
        #  search could quietly take over its own keywords would be a service
        #  whose numbering means something different on Tuesdays.
        app = Sextile()
        app.page("1", name="main")(_nothing)
        app.add_keyword("MAIN", PageAddress("1"))

        @app.on_unresolved
        def look_it_up(target: str) -> PageAddress | None:
            return PageAddress("999")

        assert app.resolve("MAIN") == PageAddress("1")

    def test_a_service_without_one_is_unaffected(self) -> None:
        app = Sextile()
        with pytest.raises(UnknownPageError):
            app.resolve("TROMBONE")


async def _nothing(request: PageRequest, **fields: object) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))


class TestSayingAPagesKeywordsWhereItIsDeclared:
    """Both ways of declaring a page take the same words about it.

    The class form took `keywords` and the instance form did not, so a service
    built round a module-level application had to say a page's name in the
    decorator and its keywords in a separate `alias` call somewhere else --
    which is the two-copies problem the decorator exists to solve.
    """

    def test_a_keyword_may_be_declared_beside_the_page(self) -> None:
        app = Sextile()
        app.page("5", name="users", title="By user",
                 keywords=("WHO", "USERS"))(_nothing)
        assert app.resolve("WHO") == PageAddress("5")
        assert app.resolve("USERS") == PageAddress("5")

    def test_a_page_with_no_title_may_still_have_one(self) -> None:
        #  Being unadvertised and being unreachable by word are different
        #  things: a logoff page stays off the contents and still answers *BYE#.
        app = Sextile()
        app.page("90", name="goodbye", keywords=("BYE",))(_nothing)
        assert app.resolve("BYE") == PageAddress("90")
        assert app.route("goodbye") is None


class TestDeclaringPagesAsData:
    """A service's pages, given to the constructor as a list.

    The canonical form, and the one that makes ordering unobservable: the
    converters a pattern needs, the pages themselves, the words that reach
    them and what the service holds all arrive in one call, so there is no
    "before" and "after" for a service to get wrong. Four of the five gaps
    this framework had were that ordering showing through.

    `@app.page` remains, defined in terms of this, so a small service still
    reads as a small service.
    """

    def test_a_page_given_to_the_constructor_answers(self) -> None:
        app = Sextile(pages=[PageRoute("1", _nothing, name="main")])
        assert app.match(PageAddress("1")) is not None

    def test_it_takes_the_handler_s_own_name_unless_told_one(self) -> None:
        async def users(request: PageRequest) -> Page:
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        app = Sextile(pages=[PageRoute("5", users)])
        assert app.address_for("users") == PageAddress("5")

    def test_what_a_page_is_called_comes_with_it(self) -> None:
        app = Sextile(
            pages=[
                PageRoute("5", _nothing, name="who", title="By user",
                          detail="browse by name")
            ]
        )
        about = app.route("who")
        assert about is not None
        assert (about.title, about.detail) == ("By user", "browse by name")

    def test_and_so_do_the_words_that_reach_it(self) -> None:
        app = Sextile(
            pages=[PageRoute("5", _nothing, name="who", keywords=("WHO", "USERS"))]
        )
        assert app.resolve("WHO") == PageAddress("5")
        assert app.resolve("USERS") == PageAddress("5")

    def test_a_field_shape_of_the_service_s_own_is_already_known(self) -> None:
        #  The ordering problem, gone rather than patched: both arrive in the
        #  same call, so there is no way to give them in the wrong order.
        tens = Converter(field_pattern=r"[0-9]{2}", width=2, parse=int)
        app = Sextile(
            converters={"tens": tens},
            pages=[PageRoute("7{count:tens}", _nothing, name="counted")],
        )
        assert app.match(PageAddress("742")) is not None

    def test_the_decorator_still_works_beside_it(self) -> None:
        app = Sextile(pages=[PageRoute("1", _nothing, name="main")])

        @app.page("9", name="about", title="About")
        async def about(request: PageRequest) -> Page:
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        assert app.match(PageAddress("1")) is not None
        assert app.match(PageAddress("9")) is not None

    def test_a_service_declaring_nothing_is_still_a_service(self) -> None:
        assert Sextile().routes() == ()


class TestMiddleware:
    """Something wrapped round every page a service builds.

    The one Starlette shape Sextile had nothing resembling, and the natural
    home for the things its design document lists as absent: authentication,
    logging, timing. A page handler answers what a page *says*; middleware
    answers what is true of every page.
    """

    async def test_it_sees_a_page_being_built(self) -> None:
        seen: list[PageAddress] = []

        async def watching(request: PageRequest, build: CallNext) -> Page | None:
            seen.append(request.address)
            return await build(request)

        app = Sextile(middleware=[watching], pages=[PageRoute("1", _nothing, name="main")])
        await app.fetch("1")
        assert seen == [PageAddress("1")]

    async def test_it_may_answer_instead_of_the_page(self) -> None:
        #  Which is what makes authentication possible without the framework
        #  having an opinion about how anybody logs in.
        instead = Page(frames=(PageFrame(frame=Canvas().frame),))

        async def refusing(request: PageRequest, build: CallNext) -> Page | None:
            return instead

        app = Sextile(middleware=[refusing], pages=[PageRoute("1", _nothing, name="main")])
        assert await app.fetch("1") is instead

    async def test_it_may_change_what_comes_back(self) -> None:
        async def hanging_up(request: PageRequest, build: CallNext) -> Page | None:
            page = await build(request)
            return None if page is None else Page(frames=page.frames, hang_up=True)

        app = Sextile(middleware=[hanging_up], pages=[PageRoute("1", _nothing, name="main")])
        page = await app.fetch("1")
        assert page is not None and page.hang_up

    async def test_the_first_given_is_the_outermost(self) -> None:
        #  As Starlette's are. The reader of a list should see the request
        #  entering at the top and leaving at the bottom.
        order: list[str] = []

        def noting(label: str) -> Middleware:
            async def note(request: PageRequest, build: CallNext) -> Page | None:
                order.append(f"into {label}")
                page = await build(request)
                order.append(f"out of {label}")
                return page

            return note

        app = Sextile(
            middleware=[noting("first"), noting("second")],
            pages=[PageRoute("1", _nothing, name="main")],
        )
        await app.fetch("1")
        assert order == ["into first", "into second", "out of second", "out of first"]

    async def test_a_page_that_is_not_there_still_reaches_it(self) -> None:
        #  A middleware counting pages would otherwise count only the ones
        #  that existed, which is not what anybody means by counting requests.
        seen: list[PageAddress] = []

        async def watching(request: PageRequest, build: CallNext) -> Page | None:
            seen.append(request.address)
            return await build(request)

        app = Sextile(middleware=[watching])
        assert await app.fetch("7") is None
        assert seen == [PageAddress("7")]

    async def test_a_service_with_none_is_unaffected(self) -> None:
        app = Sextile(pages=[PageRoute("1", _nothing, name="main")])
        assert await app.fetch("1") is not None


class TestAPageKnowingItsService:
    """`request.app`, which is Starlette's name for the same thing.

    What lets a handler be an ordinary function declared beside its fellows
    rather than a closure built inside a factory: a page offering another page
    has to ask the numbering where that one is, and this is how it asks.
    """

    async def test_a_handler_is_handed_the_service(self) -> None:
        seen: list[str] = []

        async def main(request: PageRequest) -> Page:
            seen.append(request.app.name)
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        app = Sextile(name="Weather", pages=[PageRoute("1", main, name="main")])
        await Session(app).greeting()
        assert seen == ["Weather"]

    async def test_which_is_how_it_builds_another_page_s_number(self) -> None:
        built: list[PageAddress] = []

        async def main(request: PageRequest) -> Page:
            built.append(request.app.address_for("about"))
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        app = Sextile(
            pages=[
                PageRoute("1", main, name="main"),
                PageRoute("9", _nothing, name="about"),
            ]
        )
        await Session(app).greeting()
        assert built == [PageAddress("9")]

    async def test_the_app_is_the_service_that_answered(self) -> None:
        seen: list[Sextile] = []

        async def main(request: PageRequest) -> Page:
            seen.append(request.app)
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        app = Sextile(pages=[PageRoute("1", main, name="main")])
        await Session(app).greeting()
        assert seen == [app]


class TestHeadingAPage:
    def test_title_for_is_the_registered_title_as_registered(self) -> None:
        app = Sextile(
            pages=[PageRoute("5", _nothing, name="users", title="By user")]
        )
        assert app.title_for(PageAddress("5")) == "By user"

    def test_an_untitled_or_unrouted_address_has_no_title(self) -> None:
        #  The layout shouts a registered title into the header where the page
        #  gave none; that a page so headed reads "WHERE YOU HAVE BEEN" is
        #  covered where a whole page is built. Here only the value it reads.
        app = Sextile(pages=[PageRoute("5", _nothing, name="users")])
        assert app.title_for(PageAddress("5")) is None
        assert app.title_for(PageAddress("6")) is None


class TestAskingForAPageWithoutASocket:
    """What a test, a renderer or a tool does instead of building a request.

    A request carries what the service holds and the service itself, and
    building one by hand means remembering both -- or quietly not, and then
    failing in a way that has nothing to do with what was being tested.
    """

    async def test_a_page_number_is_answered(self) -> None:
        app = Sextile(pages=[PageRoute("1", _nothing, name="main")])
        assert await app.fetch("1") is not None

    async def test_a_page_number_it_has_not_got_is_not(self) -> None:
        app = Sextile()
        assert await app.fetch("7") is None

    async def test_the_page_is_handed_what_the_service_holds(self) -> None:
        seen: list[str] = []

        @asynccontextmanager
        async def lifespan(app: Sextile) -> AsyncIterator[None]:
            app.state[ARCHIVE] = "an archive"
            yield

        async def main(request: PageRequest) -> Page:
            seen.append(request.state[ARCHIVE])
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        app = Sextile(lifespan=lifespan, pages=[PageRoute("1", main, name="main")])
        await app.startup()
        await app.fetch("1")
        assert seen == ["an archive"]

    async def test_where_the_reader_came_from_may_be_said(self) -> None:
        #  So that a page offering its neighbours can be tested at all.
        seen: list[PageAddress | None] = []

        async def main(request: PageRequest) -> Page:
            seen.append(request.neighbours.next)
            return Page(frames=(PageFrame(frame=Canvas().frame),))

        app = Sextile(pages=[PageRoute("1", main, name="main")])
        await app.fetch("1", neighbours=Neighbours(next=PageAddress("2")))
        assert seen == [PageAddress("2")]
