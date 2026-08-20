"""What the framework wraps round every page.

Two pieces of middleware ship with Sextile. One exists because of the wire: a
frame takes eight seconds to reach a reader at 1200 baud, so "it felt slow"
tells nobody anything, and from the far end of a telephone line the wire and
the page are indistinguishable. The other writes a log the service can read
back, since a list of what has been looked at lately is a page rather than a
diagnostic.
"""

import logging

import pytest

from sextile import Page, PageAddress, PageFrame, PageRequest, PageRoute, Sextile, StateKey
from sextile.middleware import CALLER, Middleware, log_pages, record_visits
from sextile.state import State
from sextile.viewdata.canvas import Canvas
from sextile.visits import SqliteVisits, Visits

#: Any page at all, for a middleware that does not look at one.
_SOMETHING = Page(frames=(PageFrame(frame=Canvas().frame),))

#: The key the visit log is held under, as a service would key it.
VISITS = StateKey[Visits]("visits")


def _holding(log: Visits) -> State:
    state = State()
    state[VISITS] = log
    return state


class Clock:
    """A clock that moves only when told, so a test never waits."""

    def __init__(self) -> None:
        self.now = 0.0
        self.step = 0.0

    def __call__(self) -> float:
        was, self.now = self.now, self.now + self.step
        return was


async def _page(request: PageRequest) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))


def _app(clock: Clock, **wanted: object) -> Sextile:
    return Sextile(
        middleware=[log_pages(clock=clock, **wanted)],  # type: ignore[arg-type]
        pages=[PageRoute("1", _page, name="main")],
    )


class TestLoggingEveryPage:
    async def test_a_page_is_named_and_timed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = Clock()
        clock.step = 0.25
        with caplog.at_level(logging.INFO, logger="sextile.serving"):
            await _app(clock).fetch("1")
        assert "*1#" in caplog.text
        assert "0.250s" in caplog.text

    async def test_how_many_frames_it_came_to(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #  Which is what a frame costs on the wire, so it is the number worth
        #  having beside the time.
        clock = Clock()
        with caplog.at_level(logging.INFO, logger="sextile.serving"):
            await _app(clock).fetch("1")
        assert "1 frames" in caplog.text

    async def test_a_page_that_is_not_there_is_logged_too(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #  A count of pages built that quietly left out the ones nobody could
        #  reach would be the wrong count.
        clock = Clock()
        with caplog.at_level(logging.INFO, logger="sextile.serving"):
            await _app(clock).fetch("7")
        assert "not here" in caplog.text


class TestSayingWhenSomethingIsSlow:
    async def test_a_quick_page_is_unremarkable(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = Clock()
        clock.step = 0.01
        with caplog.at_level(logging.INFO, logger="sextile.serving"):
            await _app(clock).fetch("1")
        assert caplog.records[0].levelno == logging.INFO

    async def test_a_slow_one_is_a_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = Clock()
        clock.step = 4.0
        with caplog.at_level(logging.INFO, logger="sextile.serving"):
            await _app(clock).fetch("1")
        assert caplog.records[0].levelno == logging.WARNING

    async def test_even_when_the_page_was_not_there(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #  A missing page is ordinary. Taking four seconds to decide it was
        #  missing is not, and the level follows the duration rather than the
        #  outcome.
        clock = Clock()
        clock.step = 4.0
        with caplog.at_level(logging.INFO, logger="sextile.serving"):
            await _app(clock).fetch("7")
        assert caplog.records[0].levelno == logging.WARNING

    async def test_how_slow_is_slow_is_a_setting(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = Clock()
        clock.step = 0.5
        with caplog.at_level(logging.INFO, logger="sextile.serving"):
            await _app(clock, slow=0.1).fetch("1")
        assert caplog.records[0].levelno == logging.WARNING


class TestRecordingVisits:
    """A row per page built, for the pages that read the log back.

    What it must not do is identify anybody: counting readers wants to know how
    many and nothing else.
    """

    async def test_every_page_is_recorded(self) -> None:
        log = SqliteVisits.open(":memory:")
        await _through(record_visits(VISITS), PageAddress("3"), state=_holding(log))
        assert [visit.page.digits for visit in await log.recent(9)] == ["3"]

    async def test_a_page_that_was_not_there_is_recorded_too(self) -> None:
        #  A count of pages fetched that quietly omitted the ones nobody could
        #  reach would be the wrong count.
        log = SqliteVisits.open(":memory:")
        await _through(record_visits(VISITS), PageAddress("9999"), page=None, state=_holding(log))
        assert await log.recent(9) == []
        assert await log.callers() == 1

    async def test_one_caller_is_one_token_however_many_pages(self) -> None:
        log = SqliteVisits.open(":memory:")
        recording = record_visits(VISITS)
        session = State()
        for number in ("1", "3", "4"):
            await _through(recording, PageAddress(number), session=session, state=_holding(log))
        assert await log.callers() == 1

    async def test_and_two_sessions_are_two_callers(self) -> None:
        log = SqliteVisits.open(":memory:")
        recording = record_visits(VISITS)
        for _ in range(2):
            await _through(recording, PageAddress("1"), session=State(), state=_holding(log))
        assert await log.callers() == 2

    async def test_the_token_says_nothing_about_who(self) -> None:
        #  Nothing identifying is asked for and nothing is stored: a service
        #  that keeps what it does not need has to be trusted about it.
        log = SqliteVisits.open(":memory:")
        session = State()
        await _through(
            record_visits(VISITS), PageAddress("1"), session=session, state=_holding(log)
        )
        token = session.get(CALLER)
        assert token is not None
        assert token.isalnum()

    async def test_a_service_holding_no_log_still_gets_its_page(self) -> None:
        #  The page has been built and the reader is owed it, so the visit goes
        #  unrecorded rather than the page going unsent.
        page = await _through(record_visits(VISITS), PageAddress("1"))
        assert page is not None

    async def test_and_one_that_holds_one_has_it_found(self) -> None:
        log = SqliteVisits.open(":memory:")
        await _through(
            record_visits(VISITS),
            PageAddress("1"),
            state=_holding(log),
        )
        assert [visit.page.digits for visit in await log.recent(9)] == ["1"]


async def _through(
    middleware: Middleware,
    address: PageAddress,
    *,
    page: Page | None = _SOMETHING,
    session: State | None = None,
    state: State | None = None,
) -> Page | None:
    async def build(request: PageRequest) -> Page | None:
        return page

    return await middleware(
        PageRequest(
            address=address,
            app=Sextile(),
            session=session if session is not None else State(),
            state=state if state is not None else State(),
        ),
        build,
    )
