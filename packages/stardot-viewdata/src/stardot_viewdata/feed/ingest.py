"""Keeping the archive fed.

The board-wide feed is a window ten posts wide, and at the rate Stardot runs it
drains in about two and a half hours. So the number worth reporting from a poll
is how many posts were new: if that ever equals how many were offered, the
window drained between polls and something was missed.

A first run has nothing to show, and waiting hours for the window to fill is a
poor introduction to a service. Seeding therefore sweeps every route the board
publishes -- the latest posts, the newest topics, the active topics, then each
forum it has just learned about, and then each topic -- which gathers a great
deal more in one pass than a single windowful, and gathers it as threads rather
than as a scatter of unrelated replies.

Neither operation gives up on a failure. A board that is briefly unreachable,
or a route this board has not enabled, is ordinary; stopping would mean a
restart every time Stardot reboots.
"""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final, Protocol

from stardot_viewdata.model import Feed, Post
from stardot_viewdata.store.repository import Repository

#: Comfortably inside the board's 60-second crawl delay, and well ahead of the
#: two and a half hours the feed window takes to drain.
DEFAULT_POLL_INTERVAL: Final = 300.0


class PollableSource(Protocol):
    """The routes polling and seeding draw on."""

    async def latest_posts(self) -> Feed: ...

    async def newest_topics(self) -> Feed: ...

    async def active_topics(self) -> Feed: ...

    async def posts_in_forum(self, forum_id: int) -> Feed: ...

    async def posts_in_topic(self, topic_id: int) -> Feed: ...


@dataclass(frozen=True)
class IngestResult:
    """What one fetch found."""

    seen: int
    added: int
    problems: tuple[str, ...] = ()
    failure: str = ""
    route: str = "latest"

    @property
    def failed(self) -> bool:
        return bool(self.failure)

    @property
    def window_may_have_drained(self) -> bool:
        """Whether every post on offer was new, suggesting some were missed."""
        return self.seen > 0 and self.added == self.seen


async def ingest_once(source: PollableSource, repository: Repository) -> IngestResult:
    """Poll for the latest posts and store whatever has not been seen before."""
    return await _ingest(source.latest_posts(), repository, route="latest")


async def poll(
    source: PollableSource,
    repository: Repository,
    *,
    interval: float = DEFAULT_POLL_INTERVAL,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    rounds: int | None = None,
    on_result: Callable[[IngestResult], None] | None = None,
) -> list[IngestResult]:
    """Poll for new posts until told to stop.

    ``rounds`` bounds the polling, which the tests need and a caller wanting a
    single sweep may find useful; left unset it runs until cancelled.
    """
    results: list[IngestResult] = []
    round_number = 0
    while rounds is None or round_number < rounds:
        if round_number:
            await sleep(interval)
        result = await ingest_once(source, repository)
        results.append(result)
        if on_result is not None:
            on_result(result)
        round_number += 1
    return results


async def seed(
    source: PollableSource,
    repository: Repository,
    *,
    on_result: Callable[[IngestResult], None] | None = None,
) -> list[IngestResult]:
    """Gather everything the board is currently syndicating.

    The forum routes come last because a forum's id is not knowable in advance:
    it arrives with the posts fetched from the other routes.
    """
    results = [
        await _ingest(source.latest_posts(), repository, route="latest posts"),
        await _ingest(source.newest_topics(), repository, route="newest topics"),
        await _ingest(source.active_topics(), repository, route="active topics"),
    ]
    for result in results:
        if on_result is not None:
            on_result(result)

    for forum_id, name, _ in await asyncio.to_thread(repository.forums):
        result = await _ingest(
            source.posts_in_forum(forum_id), repository, route=f"forum {forum_id}: {name}"
        )
        results.append(result)
        if on_result is not None:
            on_result(result)

    #  Following each topic is what turns a scatter of replies into threads that
    #  can be read: the board-wide feed shows ten posts of ten different threads,
    #  a per-topic feed ten posts of one.
    for topic_id, title, _ in await asyncio.to_thread(repository.topics, 200):
        result = await _ingest(
            source.posts_in_topic(topic_id), repository, route=f"topic {topic_id}: {title}"
        )
        results.append(result)
        if on_result is not None:
            on_result(result)
    return results


async def _ingest(fetch: Awaitable[Feed], repository: Repository, *, route: str) -> IngestResult:
    try:
        feed = await fetch
    except Exception as error:
        #  A board that is briefly unreachable, or a route it has not enabled,
        #  is ordinary rather than fatal.
        return IngestResult(
            seen=0, added=0, failure=f"{type(error).__name__}: {error}", route=route
        )
    #  The store is synchronous; keep the blocking explicit and at the boundary.
    added = await asyncio.to_thread(_store, repository, feed.posts)
    return IngestResult(
        seen=len(feed.posts), added=added, problems=feed.problems, route=route
    )


def _store(repository: Repository, posts: tuple[Post, ...]) -> int:
    return sum(1 for post in posts if repository.add_post(post))
