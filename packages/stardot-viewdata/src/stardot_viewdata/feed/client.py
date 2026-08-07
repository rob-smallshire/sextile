"""Fetching from Stardot, politely.

Stardot's robots.txt asks for a 60-second crawl delay and forbids a handful of
paths, including `viewtopic.php?p=` -- which is exactly the page that would
reveal a post's topic id. Sextile is a small service reading a public feed on
behalf of one or two people, and the cost of behaving well here is a few seconds
of waiting, so the rules are enforced in code rather than remembered in a
comment.

Two deliberate choices about failure. If robots.txt cannot be read at all,
everything is treated as forbidden: we cannot know what the site would have
asked for, and guessing in our own favour is not our call. If it is simply
absent, there are no rules to obey and fetching proceeds.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from types import TracebackType
from typing import Final, Self

import httpx

from sextile import __version__
from stardot_viewdata.feed.atom import parse_feed
from stardot_viewdata.feed.robots import RobotsRules
from stardot_viewdata.model import Feed

USER_AGENT: Final = f"Sextile/{__version__} (+viewdata gateway for Stardot)"

#: Used only if robots.txt names no crawl delay of its own.
DEFAULT_CRAWL_DELAY: Final = 60.0

_ROBOTS_PATH: Final = "/robots.txt"


class ForbiddenByRobotsError(RuntimeError):
    """A path robots.txt does not permit us to fetch."""


class FeedClient:
    """An HTTP client that waits its turn and reads the site's rules."""

    def __init__(
        self,
        base_url: str,
        *,
        client: httpx.AsyncClient | None = None,
        user_agent: str = USER_AGENT,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._user_agent = user_agent
        self._clock = clock
        self._sleep = sleep
        self._client = client or httpx.AsyncClient(base_url=self._base_url, http2=False)
        self._rules: RobotsRules | None = None
        self._robots_read = False
        self._last_request: float | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def fetch(self, path: str) -> str:
        """Fetch a path, obeying robots.txt and the crawl delay."""
        await self._read_robots()
        if not self._permitted(path):
            raise ForbiddenByRobotsError(f"robots.txt does not permit fetching {path}")
        await self._wait_for_turn()
        response = await self._get(path)
        response.raise_for_status()
        return response.text

    async def fetch_feed(self, path: str) -> Feed:
        """Fetch a path and parse it as an Atom feed."""
        return parse_feed(await self.fetch(path))

    # -- politeness ---------------------------------------------------------

    async def _read_robots(self) -> None:
        if self._robots_read:
            return
        self._robots_read = True
        try:
            response = await self._get(_ROBOTS_PATH, paced=False)
        except httpx.HTTPError:
            self._rules = None
            return
        if response.status_code == 404:
            #  No rules to obey, which is not the same as being unable to read them.
            self._rules = RobotsRules.parse("")
        elif response.status_code == 200:
            self._rules = RobotsRules.parse(response.text)
        else:
            self._rules = None

    def _permitted(self, path: str) -> bool:
        if self._rules is None:
            return False
        return self._rules.permits(self._user_agent, path)

    def _crawl_delay(self) -> float:
        if self._rules is None:
            return DEFAULT_CRAWL_DELAY
        declared = self._rules.crawl_delay(self._user_agent)
        return DEFAULT_CRAWL_DELAY if declared is None else declared

    async def _wait_for_turn(self) -> None:
        if self._last_request is None:
            return
        remaining = self._crawl_delay() - (self._clock() - self._last_request)
        if remaining > 0:
            await self._sleep(remaining)

    async def _get(self, path: str, *, paced: bool = True) -> httpx.Response:
        #  Reading robots.txt is the courtesy that makes the crawl delay
        #  knowable, and by convention is not itself subject to it. Counting it
        #  would make every startup wait a minute before its first useful
        #  request, for no benefit to the site.
        if paced:
            self._last_request = self._clock()
        return await self._client.get(path, headers={"User-Agent": self._user_agent})
