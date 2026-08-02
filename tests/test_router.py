"""Turning a page reference into frames a terminal can be sent.

Menus are the heart of it. A viewdata reader selects with a single keypress, so
a menu offers at most nine choices per frame and `#` moves to the next nine.
Digit 0 always returns to the main index, which is the one key a lost reader can
rely on.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone

import pytest

from sextile.model import Post
from sextile.pages.numbering import (
    About,
    Contributor,
    ContributorsIndex,
    Day,
    DaysIndex,
    Forum,
    ForumsIndex,
    Logoff,
    MainIndex,
    PageRef,
    PostsIndex,
    Topic,
    TopicsIndex,
)
from sextile.pages.numbering import (
    Post as PostPage,
)
from sextile.pages.page import Page, PageFrame
from sextile.pages.router import CHOICES_PER_FRAME, resolve
from sextile.store.repository import Repository

BST = timezone(timedelta(hours=1))


def make_post(post_id: int, *, subject: str = "Re: Head over Heels", **overrides: object) -> Post:
    defaults = {
        "forum_id": 53,
        "forum_name": "new projects in development: games",
        "author_id": 10058,
        "author_name": "Iapetus",
        "published": datetime(2026, 8, 2, 21, 20, tzinfo=BST),
        "content_html": "<p>What a great project!</p>",
    }
    defaults.update(overrides)
    when = defaults.pop("published")
    assert isinstance(when, datetime)
    return Post(
        post_id=post_id,
        subject=subject,
        published=when,
        updated=when,
        url=f"https://stardot.org.uk/forums/viewtopic.php?p={post_id}",
        **defaults,  # type: ignore[arg-type]
    )


@pytest.fixture
def repository() -> Iterator[Repository]:
    with Repository.in_memory() as repository:
        for offset in range(25):
            repository.add_post(
                make_post(
                    489000 + offset,
                    subject=f"Re: Topic number {offset}",
                    published=datetime(2026, 8, 2, 9, 0, tzinfo=BST) + timedelta(minutes=offset),
                )
            )
        yield repository


def _selectable(frame: PageFrame) -> set[PageRef]:
    """The numbered choices, excluding 0, which is the way back on every frame."""
    return {destination for digit, destination in frame.choices.items() if digit != "0"}


def text_of(page: Page, index: int = 0) -> str:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


class TestEveryReferenceResolves:
    @pytest.mark.parametrize(
        "reference",
        [
            MainIndex(),
            PostsIndex(),
            DaysIndex(),
            Day(datetime(2026, 8, 2).date()),
            ForumsIndex(),
            Forum(53),
            ContributorsIndex(),
            Contributor(10058),
            PostPage(489000),
            About(),
            Logoff(),
            TopicsIndex(),
            Topic(33387),
        ],
    )
    def test_a_page_is_always_produced(self, reference: PageRef, repository: Repository) -> None:
        page = resolve(reference, repository)
        assert page.frames

    def test_the_page_knows_its_own_number(self, repository: Repository) -> None:
        assert resolve(PostPage(489000), repository).number == "82489000"

    def test_frames_are_lettered(self, repository: Repository) -> None:
        page = resolve(PostsIndex(), repository)
        assert page.frame_number(0) == "8a"
        assert page.frame_number(1) == "8b"


class TestMissingThings:
    def test_an_unknown_post_says_so_rather_than_failing(self, repository: Repository) -> None:
        assert "NOT" in text_of(resolve(PostPage(999999), repository)).upper()

    def test_a_day_with_no_posts_says_so(self, repository: Repository) -> None:
        page = resolve(Day(datetime(1981, 12, 1).date()), repository)
        assert "NO POSTS" in text_of(page).upper()

    def test_topics_are_honestly_reported_as_unavailable(self, repository: Repository) -> None:
        #  The feed carries no topic ids, so this cannot be built yet. Saying so
        #  is better than offering an empty menu.
        assert "NOT AVAILABLE" in text_of(resolve(TopicsIndex(), repository)).upper()


class TestMenus:
    def test_a_menu_offers_at_most_nine_choices_per_frame(self, repository: Repository) -> None:
        page = resolve(PostsIndex(), repository)
        for index in range(len(page.frames)):
            found = page.frame(index)
            assert found is not None
            assert len(found.choices) <= CHOICES_PER_FRAME + 1  # the nine, plus 0

    def test_choices_are_numbered_from_one(self, repository: Repository) -> None:
        found = resolve(PostsIndex(), repository).frame(0)
        assert found is not None
        assert set(found.choices) >= {"1", "2", "3"}
        assert "10" not in found.choices

    def test_a_choice_leads_to_the_thing_it_names(self, repository: Repository) -> None:
        found = resolve(PostsIndex(), repository).frame(0)
        assert found is not None
        #  Latest first, so choice 1 is the newest post.
        assert found.choices["1"] == PostPage(489024)

    def test_later_frames_offer_the_later_items(self, repository: Repository) -> None:
        #  Only the numbered choices differ: 0 is the way back on every frame.
        page = resolve(PostsIndex(), repository)
        first = page.frame(0)
        second = page.frame(1)
        assert first is not None and second is not None
        assert _selectable(first).isdisjoint(_selectable(second))

    def test_zero_always_returns_to_the_main_index(self, repository: Repository) -> None:
        references: list[PageRef] = [
            PostsIndex(),
            DaysIndex(),
            ForumsIndex(),
            ContributorsIndex(),
        ]
        for reference in references:
            found = resolve(reference, repository).frame(0)
            assert found is not None
            assert found.choices["0"] == MainIndex()

    def test_a_long_menu_spills_onto_further_frames(self, repository: Repository) -> None:
        #  Twenty-five posts at nine a frame.
        assert len(resolve(PostsIndex(), repository).frames) == 3

    def test_every_item_is_reachable_across_the_frames(self, repository: Repository) -> None:
        page = resolve(PostsIndex(), repository)
        reachable = {
            destination
            for index in range(len(page.frames))
            for destination in (page.frame(index) or page.frames[0]).choices.values()
        }
        assert len([r for r in reachable if isinstance(r, PostPage)]) == 25


class TestTheMainIndex:
    def test_it_offers_the_other_indexes(self, repository: Repository) -> None:
        found = resolve(MainIndex(), repository).frame(0)
        assert found is not None
        destinations = set(found.choices.values())
        assert PostsIndex() in destinations
        assert DaysIndex() in destinations
        assert ForumsIndex() in destinations

    def test_it_says_how_much_is_held(self, repository: Repository) -> None:
        assert "25" in text_of(resolve(MainIndex(), repository))


class TestContentPages:
    def test_a_post_page_shows_its_subject_and_author(self, repository: Repository) -> None:
        rendered = text_of(resolve(PostPage(489000), repository))
        assert "Topic number 0" in rendered
        assert "Iapetus" in rendered

    def test_a_post_page_shows_its_body(self, repository: Repository) -> None:
        assert "great project" in text_of(resolve(PostPage(489000), repository))

    def test_a_day_lists_its_posts(self, repository: Repository) -> None:
        page = resolve(Day(datetime(2026, 8, 2).date()), repository)
        found = page.frame(0)
        assert found is not None
        assert found.choices

    def test_a_forum_lists_its_posts(self, repository: Repository) -> None:
        found = resolve(Forum(53), repository).frame(0)
        assert found is not None
        assert found.choices["1"] is not None

    def test_a_contributor_lists_their_posts(self, repository: Repository) -> None:
        found = resolve(Contributor(10058), repository).frame(0)
        assert found is not None
        assert found.choices["1"] is not None


class TestEveryFrameIsSendable:
    @pytest.mark.parametrize(
        "reference",
        [MainIndex(), PostsIndex(), DaysIndex(), ForumsIndex(), PostPage(489000), About()],
    )
    def test_no_frame_carries_an_eighth_bit(
        self, reference: PageRef, repository: Repository
    ) -> None:
        page = resolve(reference, repository)
        for index in range(len(page.frames)):
            found = page.frame(index)
            assert found is not None
            assert all(byte < 0x80 for byte in found.frame.to_bytes())

    @pytest.mark.parametrize(
        "reference", [MainIndex(), PostsIndex(), PostPage(489000), About()]
    )
    def test_every_frame_carries_its_own_page_number(
        self, reference: PageRef, repository: Repository
    ) -> None:
        page = resolve(reference, repository)
        for index in range(len(page.frames)):
            assert page.frame_number(index) in text_of(page, index)


def test_a_post_whose_author_has_no_id_still_renders() -> None:
    with Repository.in_memory() as repository:
        repository.add_post(make_post(1, author_id=None, author_name="Anonymous"))
        assert "Anonymous" in text_of(resolve(PostPage(1), repository))


def test_the_archive_being_empty_is_not_an_error() -> None:
    with Repository.in_memory() as repository:
        page = resolve(MainIndex(), repository)
        assert page.frames
        assert "0" in text_of(page)


def test_utc_is_displayed_in_the_boards_own_timezone() -> None:
    #  Stored in UTC, read by people in Britain.
    with Repository.in_memory() as repository:
        repository.add_post(make_post(1, published=datetime(2026, 8, 2, 20, 20, tzinfo=UTC)))
        assert "21:20" in text_of(resolve(PostPage(1), repository))
