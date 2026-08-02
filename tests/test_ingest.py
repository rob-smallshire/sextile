"""Taking what a feed offers and adding it to the archive.

The feed shows the same ten posts on every poll, so the interesting number is
not how many posts arrived but how many were new. That is what tells us whether
the archive is keeping up with the board or falling behind its ten-post window.
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from sextile.feed.atom import parse_feed
from sextile.feed.ingest import ingest_once
from sextile.model import Feed
from sextile.store.repository import Repository

FIXTURES = Path(__file__).parent / "data"
BOARD_FEED = (FIXTURES / "board-feed.xml").read_text()


class FakeSource:
    """A source that returns prepared feeds, one per call."""

    def __init__(self, *feeds: Feed) -> None:
        self._feeds = list(feeds)
        self.calls = 0

    async def latest_posts(self) -> Feed:
        self.calls += 1
        return self._feeds[min(self.calls - 1, len(self._feeds) - 1)]

    async def newest_topics(self) -> Feed:  # pragma: no cover - unused
        raise NotImplementedError

    async def active_topics(self) -> Feed:  # pragma: no cover - unused
        raise NotImplementedError

    async def posts_in_forum(self, forum_id: int) -> Feed:  # pragma: no cover - unused
        raise NotImplementedError

    async def posts_in_topic(self, topic_id: int) -> Feed:  # pragma: no cover - unused
        raise NotImplementedError


@pytest.fixture
def repository() -> Iterator[Repository]:
    with Repository.in_memory() as repository:
        yield repository


async def test_a_first_poll_stores_everything_it_finds(repository: Repository) -> None:
    result = await ingest_once(FakeSource(parse_feed(BOARD_FEED)), repository)
    assert result.seen == 10
    assert result.added == 10
    assert repository.count_posts() == 10


async def test_a_second_poll_of_an_unchanged_feed_adds_nothing(repository: Repository) -> None:
    source = FakeSource(parse_feed(BOARD_FEED))
    await ingest_once(source, repository)
    result = await ingest_once(source, repository)
    assert result.seen == 10
    assert result.added == 0
    assert repository.count_posts() == 10


async def test_only_the_new_posts_count_as_added(repository: Repository) -> None:
    first = parse_feed(BOARD_FEED)
    #  A later poll where the two oldest have dropped out of the window and two
    #  newer ones have appeared.
    later = Feed(
        title=first.title,
        updated=first.updated,
        posts=first.posts[:8]
        + tuple(
            post.__class__(**{**vars(post), "post_id": post.post_id + 1000})
            for post in first.posts[:2]
        ),
    )
    await ingest_once(FakeSource(first), repository)
    result = await ingest_once(FakeSource(later), repository)
    assert result.seen == 10
    assert result.added == 2
    assert repository.count_posts() == 12


async def test_problems_in_the_feed_are_carried_through(repository: Repository) -> None:
    document = BOARD_FEED.replace(
        "https://stardot.org.uk/forums/viewtopic.php?p=489493#p489493",
        "https://stardot.org.uk/forums/index.php",
    )
    result = await ingest_once(FakeSource(parse_feed(document)), repository)
    assert result.seen == 9
    assert len(result.problems) == 1


async def test_an_empty_feed_is_not_an_error(repository: Repository) -> None:
    result = await ingest_once(FakeSource(Feed(title="", updated=None, posts=())), repository)
    assert result.added == 0
    assert result.problems == ()
