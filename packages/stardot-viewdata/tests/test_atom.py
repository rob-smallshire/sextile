"""Parsing phpBB's Atom feed into posts.

Tested against feeds captured from the live board rather than invented ones, so
the awkward details are the real awkward details: the title carrying its forum
name, the identifiers hidden in URLs, and the author's numeric id buried in a
statistics footer that the renderer will later throw away.
"""

import re
from datetime import UTC, datetime
from pathlib import Path

import pytest

from stardot_viewdata.feed.atom import FeedFormatError, parse_feed
from stardot_viewdata.model import Feed

FIXTURES = Path(__file__).parent / "data"

BOARD_FEED = (FIXTURES / "board-feed.xml").read_text(encoding="utf-8")
TOPIC_FEED = (FIXTURES / "topic-28000-feed.xml").read_text(encoding="utf-8")
FORUM_FEED = (FIXTURES / "forum-53-feed.xml").read_text(encoding="utf-8")

ALL_FEEDS = [
    pytest.param(BOARD_FEED, id="board"),
    pytest.param(TOPIC_FEED, id="topic"),
    pytest.param(FORUM_FEED, id="forum"),
]

#  Only these carry a <category>; a topic feed names its forum only through
#  the rel=up link. See TestTopicFeedsAreShapedDifferently.
FEEDS_WITH_FORUMS = [pytest.param(BOARD_FEED, id="board"), pytest.param(FORUM_FEED, id="forum")]


@pytest.fixture
def board() -> Feed:
    return parse_feed(BOARD_FEED)


class TestFeedLevel:
    def test_the_board_feed_names_the_board(self, board: Feed) -> None:
        assert board.title == "stardot.org.uk"

    def test_the_feed_reports_when_it_was_updated(self, board: Feed) -> None:
        assert board.updated is not None
        assert board.updated.tzinfo is not None
        #  The board-wide feed is updated by its newest post.
        assert board.updated == board.posts[0].updated

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
        for post in board.posts:
            assert f"p={post.post_id}" in post.url

    def test_posts_appear_newest_first(self, board: Feed) -> None:
        ids = [post.post_id for post in board.posts]
        assert ids == sorted(ids, reverse=True)

    def test_the_forum_id_comes_from_the_category(self, board: Feed) -> None:
        assert board.posts[0].forum_id == 54

    def test_the_author_id_is_recovered_from_the_statistics_footer(self, board: Feed) -> None:
        #  The only place a numeric user id appears, and it is inside the very
        #  markup the renderer strips. It must be read before that happens.
        for post in board.posts:
            assert post.author_id is not None
            assert f"u={post.author_id}" in post.content_html.replace("&amp;", "&")

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
        first = parse_feed(TOPIC_FEED).posts[0]
        document = TOPIC_FEED.replace(
            f'<link href="{first.url}"/>',
            '<link href="https://stardot.org.uk/forums/index.php"/>',
            1,
        )
        assert parse_feed(document).posts[0].post_id == first.post_id


class TestPostFields:
    def test_the_author_name(self) -> None:
        assert parse_feed(TOPIC_FEED).posts[0].author_name == "!FOZ!"

    def test_the_forum_name(self, board: Feed) -> None:
        assert board.posts[0].forum_name == "programming"

    def test_the_subject_has_the_forum_name_stripped(self, board: Feed) -> None:
        #  phpBB titles read "forum name - subject", joined by a bullet.
        for post in board.posts:
            assert "\u2022" not in post.subject
            assert not post.subject.startswith(post.forum_name)

    def test_a_reply_is_recognised(self, board: Feed) -> None:
        assert board.posts[0].is_reply

    def test_the_topic_title_drops_the_reply_marker(self) -> None:
        assert parse_feed(TOPIC_FEED).posts[0].topic_title == (
            "ROMs that copy themselves to SRAM? (ADFS E00?)"
        )

    def test_a_first_post_is_not_a_reply(self) -> None:
        forum = parse_feed(FORUM_FEED)
        openers = [post for post in forum.posts if not post.is_reply]
        assert openers
        assert all(post.topic_title == post.subject for post in openers)

    def test_timestamps_are_timezone_aware(self, board: Feed) -> None:
        assert all(post.published.tzinfo is not None for post in board.posts)
        assert parse_feed(TOPIC_FEED).posts[0].published == datetime.fromisoformat(
            "2023-11-23T08:23:04+01:00"
        )

    def test_the_url_is_the_canonical_post_link(self) -> None:
        assert parse_feed(TOPIC_FEED).posts[0].url == (
            "https://stardot.org.uk/forums/viewtopic.php?p=409158#p409158"
        )

    def test_the_content_is_the_whole_post_body(self) -> None:
        content = parse_feed(TOPIC_FEED).posts[0].content_html
        assert "Steve Picton" in content
        assert "bootloaders he wrote" in content

    def test_the_content_is_not_truncated(self) -> None:
        #  phpBB can be configured to send an extract; this board sends it all,
        #  and the renderer's design depends on that.
        for post in parse_feed(BOARD_FEED).posts:
            assert "Statistics: Posted by" in post.content_html


class TestTopicFeedsAreShapedDifferently:
    """A post from a per-topic feed learns its forum from the `rel="up"` link.

    Per-topic feeds carry no `<category>`, and their titles have no forum name
    prepended. They used to leave a post not knowing its forum at all; the
    `rel="up"` link the board added now supplies it.
    """

    def test_a_topic_feed_names_its_forum_through_the_up_link(self) -> None:
        topic = parse_feed(TOPIC_FEED)
        assert topic.posts
        assert all(post.forum_id == 3 for post in topic.posts)

    def test_but_the_up_link_there_carries_no_forum_name(self) -> None:
        #  Its title attribute is empty in a topic feed, so the name has to
        #  arrive with posts from another route. The store prefers a known name
        #  to a blank one; see tests/test_store.py.
        assert all(post.forum_name == "" for post in parse_feed(TOPIC_FEED).posts)

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
        first = parse_feed(TOPIC_FEED).posts[0]
        document = TOPIC_FEED.replace(first.url, "https://stardot.org.uk/forums/index.php")
        feed = parse_feed(document)
        assert len(feed.posts) == 9
        assert len(feed.problems) == 1

    def test_a_missing_author_id_is_tolerated(self) -> None:
        #  A deleted or anonymised account has no profile link, which is a
        #  degraded post rather than an unusable one.
        first = parse_feed(TOPIC_FEED).posts[0]
        assert first.author_id is not None
        document = TOPIC_FEED.replace(
            f"memberlist.php?mode=viewprofile&amp;u={first.author_id}", "index.php"
        )
        post = parse_feed(document).posts[0]
        assert post.author_id is None
        assert post.post_id == first.post_id


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


class TestTheForumLink:
    """phpBB offers a link naming the entry's forum, alongside `<category>`.

    It matters most for per-topic feeds, which carry no category at all and so
    produced posts that did not know their forum. The relation it uses has
    already changed once, from `up` to `category`, so the link is recognised by
    the shape of its URL rather than by that name.
    """

    @pytest.mark.parametrize(
        "rel",
        ['rel="category"', 'rel="up"', 'rel="related"', ""],
    )
    def test_any_relation_carrying_a_forum_url_is_read(self, rel: str) -> None:
        document = _feed_with_entry(
            _WHEN + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=489542"/>'
            f'<link {rel} href="https://stardot.org.uk/forums/viewforum.php?f=54" '
            'title="programming"/>'
        )
        post = parse_feed(document).posts[0]
        assert post.forum_id == 54
        assert post.forum_name == "programming"

    def test_the_forum_comes_from_an_up_link_when_there_is_no_category(self) -> None:
        post = parse_feed(_feed_with_entry(_LINKS_ONLY)).posts[0]
        assert post.forum_id == 54
        assert post.forum_name == "programming"

    def test_a_category_is_preferred_to_an_up_link(self) -> None:
        #  Both name the forum; the category is the older and more specific.
        document = _feed_with_entry(
            _LINKS_ONLY
            + '<category term="games" scheme="https://stardot.org.uk/forums/viewforum.php?f=53"'
            ' label="games"/>'
        )
        post = parse_feed(document).posts[0]
        assert post.forum_id == 53
        assert post.forum_name == "games"

    def test_an_up_link_pointing_elsewhere_is_ignored(self) -> None:
        #  It names the forum today; it should not be mistaken for one if that
        #  ever changes.
        document = _feed_with_entry(
            _WHEN + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=489542"/>'
            '<link rel="up" href="https://stardot.org.uk/forums/index.php" title="Board"/>'
        )
        post = parse_feed(document).posts[0]
        assert post.forum_id is None

    def test_an_entry_with_neither_still_parses(self) -> None:
        document = _feed_with_entry(
            _WHEN + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=489542"/>'
        )
        post = parse_feed(document).posts[0]
        assert post.post_id == 489542
        assert post.forum_id is None


_WHEN = "<updated>2026-08-03T10:53:00+01:00</updated>"

_LINKS_ONLY = (
    _WHEN + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=489542#p489542"/>'
    '<link rel="up" type="text/html" '
    'href="https://stardot.org.uk/forums/viewforum.php?f=54" title="programming" />'
)


class TestTheTopicLink:
    """Reading a topic id from whatever link carries one.

    Stardot's feed does not offer one yet. When it does, the relation name it
    chooses should not matter: a topic id is recognised by the shape of the URL
    it appears in, so `related`, `collection`, `up` or a bespoke IRI all work.
    These entries are therefore synthetic.
    """

    @pytest.mark.parametrize(
        "rel",
        [
            'rel="related"',
            'rel="collection"',
            'rel="up"',
            'rel="index"',
            'rel="https://stardot.org.uk/rel/topic"',
            "",  # no rel at all
        ],
    )
    def test_any_relation_carrying_a_topic_url_is_read(self, rel: str) -> None:
        document = _feed_with_entry(
            _WHEN + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=489542"/>'
            f'<link {rel} href="https://stardot.org.uk/forums/viewtopic.php?t=33387"/>'
        )
        assert parse_feed(document).posts[0].topic_id == 33387

    def test_a_topic_id_alongside_other_parameters_is_found(self) -> None:
        document = _feed_with_entry(
            _WHEN + '<link href="https://stardot.org.uk/forums/'
            'viewtopic.php?f=3&amp;t=33387&amp;p=489542#p489542"/>'
        )
        post = parse_feed(document).posts[0]
        assert post.topic_id == 33387
        assert post.post_id == 489542

    def test_a_post_link_alone_yields_no_topic(self) -> None:
        document = _feed_with_entry(
            _WHEN + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=489542"/>'
        )
        assert parse_feed(document).posts[0].topic_id is None

    def test_a_forum_link_is_not_mistaken_for_a_topic(self) -> None:
        assert parse_feed(_feed_with_entry(_LINKS_ONLY)).posts[0].topic_id is None

    @pytest.mark.parametrize("document", ALL_FEEDS)
    def test_every_captured_post_now_carries_a_topic_id(self, document: str) -> None:
        #  This test used to assert the opposite, and was written to say so when
        #  the gap closed. The board added a topic link and it did.
        for post in parse_feed(document).posts:
            assert post.topic_id is not None
            assert f"t={post.topic_id}" in document

    def test_all_posts_in_a_topic_feed_share_one_topic_id(self) -> None:
        assert len({post.topic_id for post in parse_feed(TOPIC_FEED).posts}) == 1


class TestEntityReferences:
    """Titles and author names arrive HTML-escaped inside CDATA.

    phpBB marks them `type="html"`, and CDATA is taken literally by the XML
    parser, so `&amp;` survives as five characters. The body escapes this fate
    only because it goes through an HTML parser; these fields do not, and were
    reaching the screen as `&amp;CA` where the poster wrote `&CA`.
    """

    @pytest.mark.parametrize(
        ("escaped", "expected"),
        [
            ("ADFS stuffs &amp;CA into the buffer", "ADFS stuffs &CA into the buffer"),
            ('Windows &quot;Drag and Drop&quot; App', 'Windows "Drag and Drop" App'),
            ("a &lt; b &gt; c", "a < b > c"),
            ("Bob&apos;s ROM", "Bob's ROM"),
            ("&#163;5 well spent", "£5 well spent"),
            ("&#x26;80 and &#38;81", "&80 and &81"),
            ("Tube &amp; Econet", "Tube & Econet"),
        ],
    )
    def test_a_subject_is_unescaped(self, escaped: str, expected: str) -> None:
        document = _feed_with_entry(
            _WHEN
            + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=1"/>'
            + f"<title type=\"html\"><![CDATA[programming • {escaped}]]></title>"
        )
        assert parse_feed(document).posts[0].subject == expected

    def test_unescaping_happens_once(self) -> None:
        #  A poster who literally typed `&amp;` arrives double-escaped, and must
        #  not be unescaped twice into a bare ampersand.
        document = _feed_with_entry(
            _WHEN
            + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=1"/>'
            + '<title type="html"><![CDATA[f • write &amp;amp; read]]></title>'
        )
        assert parse_feed(document).posts[0].subject == "write &amp; read"

    def test_an_author_name_is_unescaped(self) -> None:
        document = _feed_with_entry(
            _WHEN
            + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=1"/>'
            + "<author><name><![CDATA[Rock &amp; Roll]]></name></author>"
        )
        assert parse_feed(document).posts[0].author_name == "Rock & Roll"

    def test_a_forum_name_from_an_attribute_needs_no_help(self) -> None:
        #  XML attributes are unescaped by the parser itself; only CDATA is not.
        document = _feed_with_entry(
            _WHEN
            + '<link href="https://stardot.org.uk/forums/viewtopic.php?p=1"/>'
            + '<category term="x" label="Tube &amp; Econet" '
            'scheme="https://stardot.org.uk/forums/viewforum.php?f=9"/>'
        )
        assert parse_feed(document).posts[0].forum_name == "Tube & Econet"

    @pytest.mark.parametrize("document", ALL_FEEDS)
    def test_no_entity_reference_survives_into_a_subject(self, document: str) -> None:
        for post in parse_feed(document).posts:
            assert not _ENTITY.search(post.subject), post.subject

    @pytest.mark.parametrize("document", ALL_FEEDS)
    def test_no_entity_reference_survives_into_an_author_name(self, document: str) -> None:
        for post in parse_feed(document).posts:
            assert not _ENTITY.search(post.author_name), post.author_name


_ENTITY = re.compile(r"&(?:[a-zA-Z][a-zA-Z0-9]{1,10}|#[0-9]{1,6}|#[xX][0-9a-fA-F]{1,5});")
