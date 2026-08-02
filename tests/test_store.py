"""The archive.

The feed is a window ten posts wide; the archive is what Sextile accumulates by
watching it. So the store must be idempotent -- the same post seen on twenty
consecutive polls is still one post -- and it must survive a post being edited
after we first saw it.

Days are London days, because that is where the board's readers are. The tests
below pin that against the alternative of UTC, which would put a late-evening
summer post on the wrong day.
"""

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from sextile.model import Post
from sextile.store.repository import Repository

BST = timezone(timedelta(hours=1))


def make_post(
    post_id: int = 489493,
    *,
    forum_id: int | None = 53,
    forum_name: str = "new projects in development: games",
    author_id: int | None = 10058,
    author_name: str = "Iapetus",
    subject: str = "Re: Head over Heels",
    published: datetime | None = None,
    content_html: str = "<p>What a great project!</p>",
) -> Post:
    when = published or datetime(2026, 8, 2, 21, 20, 27, tzinfo=BST)
    return Post(
        post_id=post_id,
        forum_id=forum_id,
        forum_name=forum_name,
        author_id=author_id,
        author_name=author_name,
        subject=subject,
        published=when,
        updated=when,
        url=f"https://stardot.org.uk/forums/viewtopic.php?p={post_id}#p{post_id}",
        content_html=content_html,
    )


@pytest.fixture
def repository() -> Iterator[Repository]:
    with Repository.in_memory() as repository:
        yield repository


class TestStoringPosts:
    def test_a_new_store_is_empty(self, repository: Repository) -> None:
        assert repository.count_posts() == 0

    def test_a_post_is_stored_and_read_back(self, repository: Repository) -> None:
        post = make_post()
        repository.add_post(post)
        assert repository.post(489493) == post

    def test_an_unknown_post_is_absent(self, repository: Repository) -> None:
        assert repository.post(1) is None

    def test_storing_the_same_post_twice_stores_one_post(self, repository: Repository) -> None:
        #  The feed shows the same ten posts on every poll.
        assert repository.add_post(make_post()) is True
        assert repository.add_post(make_post()) is False
        assert repository.count_posts() == 1

    def test_an_edited_post_replaces_its_earlier_content(self, repository: Repository) -> None:
        repository.add_post(make_post(content_html="<p>original</p>"))
        repository.add_post(make_post(content_html="<p>corrected</p>"))
        stored = repository.post(489493)
        assert stored is not None
        assert stored.content_html == "<p>corrected</p>"
        assert repository.count_posts() == 1

    def test_a_post_without_a_forum_is_storable(self, repository: Repository) -> None:
        #  Per-topic feeds carry no category naming the forum.
        repository.add_post(make_post(forum_id=None, forum_name=""))
        stored = repository.post(489493)
        assert stored is not None
        assert stored.forum_id is None

    def test_a_post_without_an_author_id_is_storable(self, repository: Repository) -> None:
        repository.add_post(make_post(author_id=None))
        stored = repository.post(489493)
        assert stored is not None
        assert stored.author_id is None

    def test_timestamps_survive_the_round_trip_with_their_instant_intact(
        self, repository: Repository
    ) -> None:
        post = make_post(published=datetime(2026, 8, 2, 21, 20, 27, tzinfo=BST))
        repository.add_post(post)
        stored = repository.post(489493)
        assert stored is not None
        assert stored.published == post.published
        assert stored.published.astimezone(UTC) == datetime(2026, 8, 2, 20, 20, 27, tzinfo=UTC)


class TestLatestPosts:
    def test_the_newest_come_first(self, repository: Repository) -> None:
        for offset in range(5):
            repository.add_post(
                make_post(
                    post_id=100 + offset,
                    published=datetime(2026, 8, 2, 12, 0, tzinfo=BST) + timedelta(minutes=offset),
                )
            )
        assert [post.post_id for post in repository.latest_posts(limit=3)] == [104, 103, 102]

    def test_the_limit_is_honoured(self, repository: Repository) -> None:
        for post_id in range(100, 110):
            repository.add_post(make_post(post_id=post_id))
        assert len(repository.latest_posts(limit=4)) == 4


class TestDaysAreLondonDays:
    """The boundary that would be wrong under UTC."""

    def test_a_late_summer_evening_post_belongs_to_its_london_day(
        self, repository: Repository
    ) -> None:
        #  00:30 on 3 August in London is 23:30 on 2 August in UTC. A reader in
        #  Britain posted this in the small hours of the third.
        repository.add_post(make_post(published=datetime(2026, 8, 3, 0, 30, tzinfo=BST)))
        assert [post.post_id for post in repository.posts_on(date(2026, 8, 3))] == [489493]
        assert repository.posts_on(date(2026, 8, 2)) == []

    def test_posts_on_a_day_read_oldest_first(self, repository: Repository) -> None:
        #  A day reads like a conversation, so it runs forwards.
        for offset in range(3):
            repository.add_post(
                make_post(
                    post_id=200 + offset,
                    published=datetime(2026, 8, 2, 9, 0, tzinfo=BST) + timedelta(hours=offset),
                )
            )
        assert [post.post_id for post in repository.posts_on(date(2026, 8, 2))] == [200, 201, 202]

    def test_days_are_listed_newest_first_with_their_counts(self, repository: Repository) -> None:
        repository.add_post(make_post(post_id=1, published=datetime(2026, 8, 1, 9, tzinfo=BST)))
        repository.add_post(make_post(post_id=2, published=datetime(2026, 8, 2, 9, tzinfo=BST)))
        repository.add_post(make_post(post_id=3, published=datetime(2026, 8, 2, 10, tzinfo=BST)))
        assert repository.days() == [(date(2026, 8, 2), 2), (date(2026, 8, 1), 1)]

    def test_a_day_with_no_posts_is_empty(self, repository: Repository) -> None:
        assert repository.posts_on(date(1981, 12, 1)) == []


class TestForumsAndContributors:
    def test_forums_are_listed_with_their_post_counts(self, repository: Repository) -> None:
        repository.add_post(make_post(post_id=1, forum_id=53, forum_name="games"))
        repository.add_post(make_post(post_id=2, forum_id=53, forum_name="games"))
        repository.add_post(make_post(post_id=3, forum_id=54, forum_name="programming"))
        assert repository.forums() == [(53, "games", 2), (54, "programming", 1)]

    def test_posts_in_a_forum(self, repository: Repository) -> None:
        repository.add_post(make_post(post_id=1, forum_id=53))
        repository.add_post(make_post(post_id=2, forum_id=54))
        assert [post.post_id for post in repository.posts_in_forum(53)] == [1]

    def test_contributors_are_listed_with_their_post_counts(self, repository: Repository) -> None:
        repository.add_post(make_post(post_id=1, author_id=10058, author_name="Iapetus"))
        repository.add_post(make_post(post_id=2, author_id=9120, author_name="BigEd"))
        repository.add_post(make_post(post_id=3, author_id=9120, author_name="BigEd"))
        assert repository.contributors() == [(9120, "BigEd", 2), (10058, "Iapetus", 1)]

    def test_posts_by_a_contributor(self, repository: Repository) -> None:
        repository.add_post(make_post(post_id=1, author_id=10058))
        repository.add_post(make_post(post_id=2, author_id=9120))
        assert [post.post_id for post in repository.posts_by_author(10058)] == [1]

    def test_posts_with_no_forum_are_omitted_from_the_forum_index(
        self, repository: Repository
    ) -> None:
        repository.add_post(make_post(post_id=1, forum_id=None, forum_name=""))
        assert repository.forums() == []


class TestPersistence:
    def test_the_archive_outlives_the_process(self, tmp_path: Path) -> None:
        database_filepath = tmp_path / "sextile.sqlite"
        with Repository.open(database_filepath) as repository:
            repository.add_post(make_post())
        with Repository.open(database_filepath) as reopened:
            assert reopened.count_posts() == 1
            assert reopened.post(489493) is not None

    def test_opening_an_existing_archive_does_not_disturb_it(self, tmp_path: Path) -> None:
        database_filepath = tmp_path / "sextile.sqlite"
        with Repository.open(database_filepath) as repository:
            repository.add_post(make_post())
        with Repository.open(database_filepath):
            pass
        with Repository.open(database_filepath) as reopened:
            assert reopened.count_posts() == 1
