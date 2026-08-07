"""Where posts come from.

This is the seam. Everything above it -- the store, the numbering, the renderer,
the session layer -- knows only about `Post` and `Feed`, never about Atom, phpBB
or HTTP. A richer backend, most likely a small read-only phpBB extension, can
implement this protocol and slot in without disturbing anything else.

The Atom adapter is the first implementation, and a deliberately limited one: it
can offer the board's latest posts, a forum's, and a topic's, because those are
the three routes phpBB actually publishes. Notably it cannot resolve a post to
its topic, since the feed never says and robots.txt forbids the page that would.
"""

from typing import Final, Protocol

from stardot_viewdata.feed.client import FeedClient
from stardot_viewdata.model import Feed

#: phpBB's feed routes are path-based. Query parameters are silently ignored.
FEED_ROOT: Final = "/forums/app.php/feed"

STARDOT_BASE_URL: Final = "https://stardot.org.uk"


class PostSource(Protocol):
    """A source of forum posts."""

    async def latest_posts(self) -> Feed:
        """The board's most recent posts."""
        ...

    async def newest_topics(self) -> Feed:
        """The posts opening the board's newest topics."""
        ...

    async def active_topics(self) -> Feed:
        """The posts of the board's most recently active topics."""
        ...

    async def posts_in_forum(self, forum_id: int) -> Feed:
        """The most recent posts in one forum."""
        ...

    async def posts_in_topic(self, topic_id: int) -> Feed:
        """The most recent posts in one topic."""
        ...


class AtomFeedSource:
    """Posts read from phpBB's syndication feeds."""

    def __init__(self, client: FeedClient) -> None:
        self._client = client

    async def latest_posts(self) -> Feed:
        return await self._client.fetch_feed(FEED_ROOT)

    async def newest_topics(self) -> Feed:
        return await self._client.fetch_feed(f"{FEED_ROOT}/topics")

    async def active_topics(self) -> Feed:
        return await self._client.fetch_feed(f"{FEED_ROOT}/topics_active")

    async def posts_in_forum(self, forum_id: int) -> Feed:
        return await self._client.fetch_feed(f"{FEED_ROOT}/forum/{forum_id}")

    async def posts_in_topic(self, topic_id: int) -> Feed:
        return await self._client.fetch_feed(f"{FEED_ROOT}/topic/{topic_id}")
