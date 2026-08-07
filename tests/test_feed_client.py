"""Fetching feeds from Stardot, politely.

Stardot's robots.txt asks for a 60-second crawl delay and forbids some paths.
Sextile is a small service reading a public feed, and behaving well is not
optional -- so the pacing and the robots rules are tested rather than trusted to
a comment, using a fake clock so the tests do not actually wait a minute.
"""

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from stardot_viewdata.feed.client import FeedClient, ForbiddenByRobotsError

FIXTURES = Path(__file__).parent / "data"
BOARD_FEED = (FIXTURES / "board-feed.xml").read_text()

ROBOTS = """
User-agent: *
Allow: /
Crawl-delay: 60
Disallow: /forums/viewtopic.php?p=
Disallow: /forums/search.php
"""


class FakeClock:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def make_client(
    clock: FakeClock,
    handler: Callable[[httpx.Request], httpx.Response] | None = None,
) -> FeedClient:
    def default_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        return httpx.Response(200, text=BOARD_FEED)

    transport = httpx.MockTransport(handler or default_handler)
    return FeedClient(
        base_url="https://stardot.org.uk",
        client=httpx.AsyncClient(transport=transport, base_url="https://stardot.org.uk"),
        clock=clock.time,
        sleep=clock.sleep,
    )


class TestPoliteness:
    async def test_the_first_request_need_not_wait(self) -> None:
        clock = FakeClock()
        async with make_client(clock) as client:
            await client.fetch("/forums/app.php/feed")
        assert clock.slept == []

    async def test_successive_requests_are_spaced_by_the_crawl_delay(self) -> None:
        clock = FakeClock()
        async with make_client(clock) as client:
            await client.fetch("/forums/app.php/feed")
            await client.fetch("/forums/app.php/feed/topics")
        #  robots.txt asked for 60 seconds and it was obeyed without being told.
        assert clock.slept == [60.0]

    async def test_time_already_spent_counts_towards_the_delay(self) -> None:
        clock = FakeClock()
        async with make_client(clock) as client:
            await client.fetch("/forums/app.php/feed")
            clock.now += 45.0
            await client.fetch("/forums/app.php/feed/topics")
        assert clock.slept == [15.0]

    async def test_a_long_gap_needs_no_wait_at_all(self) -> None:
        clock = FakeClock()
        async with make_client(clock) as client:
            await client.fetch("/forums/app.php/feed")
            clock.now += 3600.0
            await client.fetch("/forums/app.php/feed/topics")
        assert clock.slept == []

    async def test_robots_is_fetched_once_however_many_feeds_follow(self) -> None:
        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(request.url.path)
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=ROBOTS)
            return httpx.Response(200, text=BOARD_FEED)

        clock = FakeClock()
        async with make_client(clock, handler) as client:
            await client.fetch("/forums/app.php/feed")
            await client.fetch("/forums/app.php/feed/topics")
        assert requested.count("/robots.txt") == 1


class TestRobotsRules:
    async def test_a_disallowed_path_is_refused_before_it_is_requested(self) -> None:
        requested: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            requested.append(str(request.url))
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=ROBOTS)
            return httpx.Response(200, text="<html/>")

        clock = FakeClock()
        async with make_client(clock, handler) as client:
            with pytest.raises(ForbiddenByRobotsError):
                await client.fetch("/forums/viewtopic.php?p=489493")
        assert not any("viewtopic" in url for url in requested)

    async def test_the_feed_is_allowed(self) -> None:
        clock = FakeClock()
        async with make_client(clock) as client:
            assert await client.fetch("/forums/app.php/feed")

    async def test_an_unreachable_robots_is_treated_as_forbidding_everything(self) -> None:
        #  Failing closed is the only safe reading: we cannot know what the site
        #  would have asked for.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(500)
            return httpx.Response(200, text=BOARD_FEED)

        clock = FakeClock()
        async with make_client(clock, handler) as client:
            with pytest.raises(ForbiddenByRobotsError):
                await client.fetch("/forums/app.php/feed")

    async def test_a_missing_robots_permits_fetching(self) -> None:
        #  404 means the site has no rules, which is not the same as unreachable.
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(404)
            return httpx.Response(200, text=BOARD_FEED)

        clock = FakeClock()
        async with make_client(clock, handler) as client:
            assert await client.fetch("/forums/app.php/feed")


class TestIdentification:
    async def test_requests_carry_an_identifying_user_agent(self) -> None:
        seen: list[str] = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append(request.headers.get("user-agent", ""))
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=ROBOTS)
            return httpx.Response(200, text=BOARD_FEED)

        clock = FakeClock()
        async with make_client(clock, handler) as client:
            await client.fetch("/forums/app.php/feed")
        assert all("Sextile" in agent for agent in seen)


class TestFailures:
    @pytest.mark.parametrize("status", [403, 404, 500, 503])
    async def test_an_error_response_is_raised(self, status: int) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=ROBOTS)
            return httpx.Response(status)

        clock = FakeClock()
        async with make_client(clock, handler) as client:
            with pytest.raises(httpx.HTTPStatusError):
                await client.fetch("/forums/app.php/feed")
