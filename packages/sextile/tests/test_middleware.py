"""What the framework wraps round every page.

One piece of middleware ships with Sextile, and it exists because of the wire.
A frame takes eight seconds to reach a reader at 1200 baud, so "it felt slow"
tells nobody anything: from the far end of a telephone line the wire and the
page are indistinguishable. This tells them apart.
"""

import logging

import pytest

from sextile import Page, PageAddress, PageFrame, PageRequest, PageRoute, Sextile
from sextile.middleware import log_pages
from sextile.viewdata.canvas import Canvas


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
        with caplog.at_level(logging.INFO, logger="sextile.pages"):
            await _app(clock).respond(PageRequest(address=PageAddress("1")))
        assert "*1#" in caplog.text
        assert "0.250s" in caplog.text

    async def test_how_many_frames_it_came_to(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #  Which is what a frame costs on the wire, so it is the number worth
        #  having beside the time.
        clock = Clock()
        with caplog.at_level(logging.INFO, logger="sextile.pages"):
            await _app(clock).respond(PageRequest(address=PageAddress("1")))
        assert "1 frames" in caplog.text

    async def test_a_page_that_is_not_there_is_logged_too(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #  A count of pages built that quietly left out the ones nobody could
        #  reach would be the wrong count.
        clock = Clock()
        with caplog.at_level(logging.INFO, logger="sextile.pages"):
            await _app(clock).respond(PageRequest(address=PageAddress("7")))
        assert "not here" in caplog.text


class TestSayingWhenSomethingIsSlow:
    async def test_a_quick_page_is_unremarkable(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = Clock()
        clock.step = 0.01
        with caplog.at_level(logging.INFO, logger="sextile.pages"):
            await _app(clock).respond(PageRequest(address=PageAddress("1")))
        assert caplog.records[0].levelno == logging.INFO

    async def test_a_slow_one_is_a_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = Clock()
        clock.step = 4.0
        with caplog.at_level(logging.INFO, logger="sextile.pages"):
            await _app(clock).respond(PageRequest(address=PageAddress("1")))
        assert caplog.records[0].levelno == logging.WARNING

    async def test_even_when_the_page_was_not_there(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        #  A missing page is ordinary. Taking four seconds to decide it was
        #  missing is not, and the level follows the duration rather than the
        #  outcome.
        clock = Clock()
        clock.step = 4.0
        with caplog.at_level(logging.INFO, logger="sextile.pages"):
            await _app(clock).respond(PageRequest(address=PageAddress("7")))
        assert caplog.records[0].levelno == logging.WARNING

    async def test_how_slow_is_slow_is_a_setting(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        clock = Clock()
        clock.step = 0.5
        with caplog.at_level(logging.INFO, logger="sextile.pages"):
            await _app(clock, slow=0.1).respond(PageRequest(address=PageAddress("1")))
        assert caplog.records[0].levelno == logging.WARNING
