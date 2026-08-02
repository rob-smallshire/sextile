"""Adding what a feed offers to the archive.

The feed shows the same ten posts on every poll, so the number worth reporting
is how many were new. If a poll ever adds ten, the window has drained between
polls and posts have been missed -- which is the signal that the interval is too
long, not merely that the board is busy.
"""

import asyncio
from dataclasses import dataclass

from sextile.feed.source import PostSource
from sextile.model import Post
from sextile.store.repository import Repository


@dataclass(frozen=True)
class IngestResult:
    """What one poll found."""

    seen: int
    added: int
    problems: tuple[str, ...] = ()

    @property
    def window_may_have_drained(self) -> bool:
        """Whether every post on offer was new, suggesting some were missed."""
        return self.seen > 0 and self.added == self.seen


async def ingest_once(source: PostSource, repository: Repository) -> IngestResult:
    """Poll for the latest posts and store whatever has not been seen before."""
    feed = await source.latest_posts()
    #  The store is synchronous; keep the blocking explicit and at the boundary.
    added = await asyncio.to_thread(_store, repository, feed.posts)
    return IngestResult(seen=len(feed.posts), added=added, problems=feed.problems)


def _store(repository: Repository, posts: tuple[Post, ...]) -> int:
    return sum(1 for post in posts if repository.add_post(post))
