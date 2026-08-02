"""Keeping the archive fed.

The board-wide feed is a window ten posts wide, and at the observed rate it
drains in about two and a half hours. So the archive is only as good as the
polling behind it, and a poll that ever finds every post new is evidence that
something was missed.

Seeding is the other half. A first run has nothing to show, and waiting hours
for the window to fill is a poor introduction, so several feed routes are swept
once to gather what the board is currently syndicating.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest

from sextile.feed.ingest import poll, seed
from sextile.model import Feed, Post
from sextile.store.repository import Repository

BST = timezone(timedelta(hours=1))


def make_post(post_id: int, forum_id: int | None = 53) -> Post:
    when = datetime(2026, 8, 2, 9, 0, tzinfo=BST) + timedelta(minutes=post_id % 100)
    return Post(
        post_id=post_id,
        forum_id=forum_id,
        forum_name=f"forum {forum_id}",
        author_id=10058,
        author_name="Iapetus",
        subject=f"Re: Topic {post_id}",
        published=when,
        updated=when,
        url=f"https://stardot.org.uk/forums/viewtopic.php?p={post_id}",
        content_html="<p>Words.</p>",
    )


def feed_of(*post_ids: int, forum_id: int | None = 53) -> Feed:
    return Feed(
        title="stardot.org.uk",
        updated=None,
        posts=tuple(make_post(post_id, forum_id) for post_id in post_ids),
    )


class RecordingSource:
    """A source that answers from a script and records what was asked."""

    def __init__(
        self,
        *,
        latest: list[Feed] | None = None,
        newest_topics: Feed | None = None,
        active_topics: Feed | None = None,
        forums: dict[int, Feed] | None = None,
    ) -> None:
        self._latest = latest or [feed_of()]
        self._newest_topics = newest_topics or feed_of()
        self._active_topics = active_topics or feed_of()
        self._forums = forums or {}
        self.asked: list[str] = []

    async def latest_posts(self) -> Feed:
        self.asked.append("latest")
        index = min(self.asked.count("latest") - 1, len(self._latest) - 1)
        return self._latest[index]

    async def newest_topics(self) -> Feed:
        self.asked.append("newest_topics")
        return self._newest_topics

    async def active_topics(self) -> Feed:
        self.asked.append("active_topics")
        return self._active_topics

    async def posts_in_forum(self, forum_id: int) -> Feed:
        self.asked.append(f"forum:{forum_id}")
        return self._forums.get(forum_id, feed_of(forum_id=forum_id))

    async def posts_in_topic(self, topic_id: int) -> Feed:  # pragma: no cover - unused here
        self.asked.append(f"topic:{topic_id}")
        return feed_of()


class FakeSleeper:
    def __init__(self) -> None:
        self.slept: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.slept.append(seconds)


@pytest.fixture
def repository() -> Iterator[Repository]:
    with Repository.in_memory() as repository:
        yield repository


class TestPolling:
    async def test_a_poll_stores_what_it_finds(self, repository: Repository) -> None:
        source = RecordingSource(latest=[feed_of(1, 2, 3)])
        await poll(source, repository, interval=300, sleep=FakeSleeper(), rounds=1)
        assert repository.count_posts() == 3

    async def test_polling_repeats(self, repository: Repository) -> None:
        source = RecordingSource(latest=[feed_of(1, 2), feed_of(2, 3), feed_of(3, 4)])
        await poll(source, repository, interval=300, sleep=FakeSleeper(), rounds=3)
        assert source.asked.count("latest") == 3
        assert repository.count_posts() == 4

    async def test_it_waits_between_polls_but_not_before_the_first(
        self, repository: Repository
    ) -> None:
        sleeper = FakeSleeper()
        await poll(RecordingSource(), repository, interval=300, sleep=sleeper, rounds=3)
        assert sleeper.slept == [300, 300]

    async def test_results_are_reported_for_each_poll(self, repository: Repository) -> None:
        source = RecordingSource(latest=[feed_of(1, 2), feed_of(1, 2)])
        results = await poll(source, repository, interval=1, sleep=FakeSleeper(), rounds=2)
        assert [result.added for result in results] == [2, 0]

    async def test_a_failing_poll_does_not_end_the_polling(
        self, repository: Repository
    ) -> None:
        class Flaky(RecordingSource):
            async def latest_posts(self) -> Feed:
                self.asked.append("latest")
                if len(self.asked) == 1:
                    raise OSError("the board is down")
                return feed_of(1, 2)

        #  A board that is briefly unreachable is ordinary. Giving up would mean
        #  a restart is needed every time Stardot reboots.
        results = await poll(Flaky(), repository, interval=1, sleep=FakeSleeper(), rounds=2)
        assert len(results) == 2
        assert results[0].failed
        assert results[1].added == 2


class TestSeeding:
    async def test_seeding_sweeps_the_routes_the_board_publishes(
        self, repository: Repository
    ) -> None:
        source = RecordingSource(
            latest=[feed_of(1, 2)],
            newest_topics=feed_of(3, 4),
            active_topics=feed_of(5, 6),
        )
        await seed(source, repository)
        assert "latest" in source.asked
        assert "newest_topics" in source.asked
        assert "active_topics" in source.asked
        assert repository.count_posts() == 6

    async def test_seeding_then_follows_the_forums_it_discovered(
        self, repository: Repository
    ) -> None:
        #  Forum ids are not knowable in advance; they arrive with the posts.
        source = RecordingSource(
            latest=[feed_of(1, forum_id=53)],
            newest_topics=feed_of(2, forum_id=54),
            forums={53: feed_of(10, 11, forum_id=53), 54: feed_of(20, forum_id=54)},
        )
        await seed(source, repository)
        assert "forum:53" in source.asked
        assert "forum:54" in source.asked
        assert repository.count_posts() == 5

    async def test_each_forum_is_visited_once(self, repository: Repository) -> None:
        source = RecordingSource(latest=[feed_of(1, 2, 3, forum_id=53)])
        await seed(source, repository)
        assert source.asked.count("forum:53") == 1

    async def test_seeding_reports_what_it_gathered(self, repository: Repository) -> None:
        source = RecordingSource(latest=[feed_of(1, 2)], newest_topics=feed_of(3))
        results = await seed(source, repository)
        assert sum(result.added for result in results) == repository.count_posts()

    async def test_a_route_the_board_refuses_does_not_stop_the_sweep(
        self, repository: Repository
    ) -> None:
        class PartlyBroken(RecordingSource):
            async def newest_topics(self) -> Feed:
                self.asked.append("newest_topics")
                raise OSError("not enabled on this board")

        source = PartlyBroken(latest=[feed_of(1, 2)])
        results = await seed(source, repository)
        assert any(result.failed for result in results)
        assert repository.count_posts() == 2
