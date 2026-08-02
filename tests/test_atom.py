"""Parsing phpBB's Atom feed into posts.

Tested against feeds captured from the live board rather than invented ones, so
the awkward details are the real awkward details: the title carrying its forum
name, the identifiers hidden in URLs, and the author's numeric id buried in a
statistics footer that the renderer will later throw away.
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from sextile.feed.atom import FeedFormatError, parse_feed
from sextile.model import Feed

FIXTURES = Path(__file__).parent / "data"

BOARD_FEED = (FIXTURES / "board-feed.xml").read_text()
TOPIC_FEED = (FIXTURES / "topic-28000-feed.xml").read_text()
FORUM_FEED = (FIXTURES / "forum-53-feed.xml").read_text()

ALL_FEEDS = [
    pytest.param(BOARD_FEED, id="board"),
    pytest.param(TOPIC_FEED, id="topic"),
    pytest.param(FORUM_FEED, id="forum"),
]

#  Only these carry a category naming the forum; see TestForumIsNotAlwaysKnown.
FEEDS_WITH_FORUMS = [pytest.param(BOARD_FEED, id="board"), pytest.param(FORUM_FEED, id="forum")]


@pytest.fixture
def board() -> Feed:
    return parse_feed(BOARD_FEED)


class TestFeedLevel:
    def test_the_board_feed_names_the_board(self, board: Feed) -> None:
        assert board.title == "stardot.org.uk"

    def test_the_feed_reports_when_it_was_updated(self, board: Feed) -> None:
        assert board.updated == datetime.fromisoformat("2026-08-02T21:20:27+01:00")

    def test_the_board_feed_holds_ten_posts(self, board: Feed) -> None:
        assert len(board.posts) == 10

    @pytest.mark.parametrize("document", ALL_FEEDS)
    def test_every_captured_feed_parses_without_complaint(self, document: str) -> None:
        feed = parse_feed(document)
        assert feed.posts
        assert not feed.problems


class TestIdentifiers:
    """Everything the page numbering depends on."""

    def test_the_post_id_comes_from_the_link(self, board: Feed) -> None:
        assert board.posts[0].post_id == 489493

    def test_posts_appear_newest_first(self, board: Feed) -> None:
        ids = [post.post_id for post in board.posts]
        assert ids == sorted(ids, reverse=True)

    def test_the_forum_id_comes_from_the_category(self, board: Feed) -> None:
        assert board.posts[0].forum_id == 53

    def test_the_author_id_is_recovered_from_the_statistics_footer(self, board: Feed) -> None:
        #  The only place a numeric user id appears, and it is inside the very
        #  markup the renderer strips. It must be read before that happens.
        assert board.posts[0].author_id == 10058

    @pytest.mark.parametrize("document", ALL_FEEDS)
    def test_every_post_has_a_post_id_and_an_author_id(self, document: str) -> None:
        for post in parse_feed(document).posts:
            assert post.post_id > 0
            assert post.author_id is not None

    @pytest.mark.parametrize("document", FEEDS_WITH_FORUMS)
    def test_board_and_forum_feeds_identify_the_forum(self, document: str) -> None:
        for post in parse_feed(document).posts:
            assert post.forum_id is not None

    def test_the_post_id_falls_back_to_the_id_element(self) -> None:
        #  The link and the id carry the same URL, so losing one is survivable.
        document = BOARD_FEED.replace(
            '<link href="https://stardot.org.uk/forums/viewtopic.php?p=489493#p489493"/>',
            '<link href="https://stardot.org.uk/forums/index.php"/>',
            1,
        )
        assert parse_feed(document).posts[0].post_id == 489493


class TestPostFields:
    def test_the_author_name(self, board: Feed) -> None:
        assert board.posts[0].author_name == "Iapetus"

    def test_the_forum_name(self, board: Feed) -> None:
        assert board.posts[0].forum_name == "new projects in development: games"

    def test_the_subject_has_the_forum_name_stripped(self, board: Feed) -> None:
        #  phpBB titles read "forum name - subject", joined by a bullet.
        assert board.posts[0].subject == "Re: Head over Heels"

    def test_a_reply_is_recognised(self, board: Feed) -> None:
        assert board.posts[0].is_reply

    def test_the_topic_title_drops_the_reply_marker(self, board: Feed) -> None:
        assert board.posts[0].topic_title == "Head over Heels"

    def test_a_first_post_is_not_a_reply(self) -> None:
        forum = parse_feed(FORUM_FEED)
        openers = [post for post in forum.posts if not post.is_reply]
        assert openers
        assert all(post.topic_title == post.subject for post in openers)

    def test_timestamps_are_timezone_aware(self, board: Feed) -> None:
        post = board.posts[0]
        assert post.published.tzinfo is not None
        assert post.published == datetime.fromisoformat("2026-08-02T21:20:27+01:00")

    def test_the_url_is_the_canonical_post_link(self, board: Feed) -> None:
        assert board.posts[0].url == "https://stardot.org.uk/forums/viewtopic.php?p=489493#p489493"

    def test_the_content_is_the_whole_post_body(self, board: Feed) -> None:
        content = board.posts[0].content_html
        assert "What a great project!" in content
        assert "Jon Ritman" in content

    def test_the_content_is_not_truncated(self) -> None:
        #  phpBB can be configured to send an extract; this board sends it all,
        #  and the renderer's design depends on that.
        for post in parse_feed(BOARD_FEED).posts:
            assert "Statistics: Posted by" in post.content_html


class TestForumIsNotAlwaysKnown:
    """Per-topic feeds are shaped differently from the others.

    They carry no `<category>`, so a post read from one does not know its
    forum, and their titles are the bare subject with no forum name prepended.
    This matters for thread browsing later: a topic feed alone will not tell us
    which forum a thread lives in.
    """

    def test_a_topic_feed_names_no_forum(self) -> None:
        topic = parse_feed(TOPIC_FEED)
        assert topic.posts
        assert all(post.forum_id is None for post in topic.posts)

    def test_a_topic_feed_still_yields_usable_posts(self) -> None:
        post = parse_feed(TOPIC_FEED).posts[0]
        assert post.post_id == 409158
        assert post.author_name == "!FOZ!"
        assert post.author_id == 13433

    def test_a_topic_feed_subject_has_no_forum_prefix_to_strip(self) -> None:
        assert parse_feed(TOPIC_FEED).posts[0].subject == (
            "Re: ROMs that copy themselves to SRAM? (ADFS E00?)"
        )

    def test_all_posts_in_a_topic_feed_share_a_topic(self) -> None:
        titles = {post.topic_title for post in parse_feed(TOPIC_FEED).posts}
        assert len(titles) == 1


class TestOrdering:
    def test_published_and_updated_are_both_available(self, board: Feed) -> None:
        post = board.posts[0]
        assert post.published is not None
        assert post.updated is not None


class TestMalformedInput:
    @pytest.mark.parametrize("document", ["", "not xml at all", "<html><body/></html>"])
    def test_a_document_that_is_not_a_feed_is_rejected(self, document: str) -> None:
        with pytest.raises(FeedFormatError):
            parse_feed(document)

    def test_an_entry_without_a_post_id_is_reported_not_dropped_silently(self) -> None:
        document = _feed_with_entry('<link href="https://stardot.org.uk/forums/index.php"/>')
        feed = parse_feed(document)
        assert not feed.posts
        assert feed.problems

    def test_one_bad_entry_does_not_lose_the_others(self) -> None:
        #  Both the link and the id have to go before an entry is unusable.
        document = BOARD_FEED.replace(
            "https://stardot.org.uk/forums/viewtopic.php?p=489493#p489493",
            "https://stardot.org.uk/forums/index.php",
        )
        feed = parse_feed(document)
        assert len(feed.posts) == 9
        assert len(feed.problems) == 1

    def test_a_missing_author_id_is_tolerated(self) -> None:
        #  A deleted or anonymised account has no profile link, which is a
        #  degraded post rather than an unusable one.
        document = BOARD_FEED.replace("memberlist.php?mode=viewprofile&amp;u=10058", "index.php")
        post = parse_feed(document).posts[0]
        assert post.author_id is None
        assert post.post_id == 489493


def _feed_with_entry(entry_body: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<title>stardot.org.uk</title>"
        "<updated>2026-08-02T21:20:27+01:00</updated>"
        f"<entry>{entry_body}</entry>"
        "</feed>"
    )


def test_a_feed_may_legitimately_be_empty() -> None:
    document = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<title>stardot.org.uk</title>"
        "<updated>2026-08-02T21:20:27+01:00</updated>"
        "</feed>"
    )
    feed = parse_feed(document)
    assert feed.posts == ()
    assert feed.updated == datetime(2026, 8, 2, 20, 20, 27, tzinfo=UTC)
