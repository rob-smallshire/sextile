"""What a connected terminal is doing.

The session holds where the reader is, what they have seen, and how they got
there. Everything it does is a response to one command, and every response is
either a frame to send or nothing at all -- there is no other way to talk to a
terminal that can only display what arrives.
"""

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

import pytest

from sextile.model import Post
from sextile.pages.numbering import (
    About,
    ContributorsIndex,
    DaysIndex,
    ForumsIndex,
    MainIndex,
    PostsIndex,
)
from sextile.pages.numbering import (
    Post as PostPage,
)
from sextile.session.session import Session
from sextile.store.repository import Repository

BST = timezone(timedelta(hours=1))


def make_post(post_id: int, minute: int = 0) -> Post:
    when = datetime(2026, 8, 2, 9, 0, tzinfo=BST) + timedelta(minutes=minute)
    return Post(
        post_id=post_id,
        forum_id=53,
        forum_name="programming",
        author_id=10058,
        author_name="Iapetus",
        subject=f"Re: Topic {post_id}",
        published=when,
        updated=when,
        url=f"https://stardot.org.uk/forums/viewtopic.php?p={post_id}",
        content_html="<p>Some words.</p>",
    )


@pytest.fixture
def repository() -> Iterator[Repository]:
    with Repository.in_memory() as repository:
        for offset in range(25):
            repository.add_post(make_post(489000 + offset, offset))
        yield repository


@pytest.fixture
def session(repository: Repository) -> Session:
    return Session(repository)


def screen(session: Session) -> str:
    frame = session.current_frame()
    assert frame is not None
    characters, _ = frame.to_grid()
    return "\n".join(characters)


class TestOpening:
    def test_a_session_opens_on_the_main_index(self, session: Session) -> None:
        assert session.reference == MainIndex()

    def test_the_opening_frame_is_ready_to_send(self, session: Session) -> None:
        assert session.greeting() is not None
        assert "SEXTILE" in screen(session)

    def test_a_session_is_not_finished_to_begin_with(self, session: Session) -> None:
        assert not session.finished


class TestGoingToPages:
    def test_a_page_number_goes_there(self, session: Session) -> None:
        session.receive(b"*8#")
        assert session.reference == PostsIndex()

    def test_a_post_number_goes_there(self, session: Session) -> None:
        session.receive(b"*82489000#")
        assert session.reference == PostPage(489000)

    def test_a_keyword_goes_there_too(self, session: Session) -> None:
        #  Not every viewdata service was purely numeric, and ours need not be.
        session.receive(b"*8#")
        session.receive(b"*MAIN#")
        assert session.reference == MainIndex()

    @pytest.mark.parametrize(
        ("keyword", "expected"),
        [
            (b"*LATEST#", PostsIndex()),
            (b"*DAYS#", DaysIndex()),
            (b"*FORUMS#", ForumsIndex()),
            (b"*WHO#", ContributorsIndex()),
            (b"*ABOUT#", About()),
        ],
    )
    def test_the_named_jumps(self, session: Session, keyword: bytes, expected: object) -> None:
        session.receive(keyword)
        assert session.reference == expected

    def test_an_unknown_page_leaves_the_reader_where_they_were(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"*222222#")
        assert session.reference == PostsIndex()

    def test_an_unknown_page_says_so_rather_than_ignoring_the_reader(
        self, session: Session
    ) -> None:
        response = session.receive(b"*222222#")
        assert response
        assert "NOT" in _text(response[-1]).upper()


class TestSelecting:
    def test_a_digit_follows_the_choice_it_names(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"1")
        assert session.reference == PostPage(489024)

    def test_zero_returns_to_the_main_index(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"0")
        assert session.reference == MainIndex()

    def test_a_key_the_frame_does_not_offer_is_ignored(self, session: Session) -> None:
        session.receive(b"*9#")  # About, which offers only 0
        assert session.receive(b"7") == []
        assert session.reference == About()

    def test_a_letter_key_is_ignored_where_no_page_offers_one(self, session: Session) -> None:
        #  Pages may offer letters later; none does yet, and an unoffered key
        #  must do nothing rather than something surprising.
        assert session.receive(b"N") == []


class TestFrames:
    def test_hash_advances_a_frame(self, session: Session) -> None:
        session.receive(b"*8#")
        assert session.frame_index == 0
        session.receive(b"#")
        assert session.frame_index == 1

    def test_the_frame_letter_shows_in_the_page_number(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"#")
        assert "8b" in screen(session)

    def test_hash_on_the_last_frame_stays_put(self, session: Session) -> None:
        #  Wrapping round would loop a reader who cannot see they have.
        session.receive(b"*9#")
        before = session.frame_index
        session.receive(b"#")
        assert session.frame_index == before

    def test_going_to_a_new_page_starts_at_its_first_frame(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"#")
        session.receive(b"*1#")
        assert session.frame_index == 0


class TestHistory:
    def test_back_returns_to_the_previous_page(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"*9#")
        session.receive(b"*0#")
        assert session.reference == PostsIndex()

    def test_back_remembers_the_frame_that_was_showing(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"#")
        session.receive(b"*9#")
        session.receive(b"*0#")
        assert session.frame_index == 1

    def test_back_unwinds_more_than_one_step(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"*3#")
        session.receive(b"*9#")
        session.receive(b"*0#")
        session.receive(b"*0#")
        assert session.reference == PostsIndex()

    def test_back_at_the_beginning_does_nothing_harmful(self, session: Session) -> None:
        session.receive(b"*0#")
        assert session.reference == MainIndex()

    def test_selecting_a_choice_is_remembered_too(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"1")
        session.receive(b"*0#")
        assert session.reference == PostsIndex()


class TestRedisplayAndRefresh:
    def test_redisplay_sends_the_same_frame_again(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"#")
        response = session.receive(b"*00#")
        assert response
        assert session.frame_index == 1

    def test_refresh_rebuilds_the_page_from_the_archive(
        self, session: Session, repository: Repository
    ) -> None:
        session.receive(b"*8#")
        repository.add_post(make_post(500000, 99))
        response = session.receive(b"*09#")
        assert response
        assert "Topic 500000" in screen(session)

    def test_redisplay_does_not_notice_new_posts(
        self, session: Session, repository: Repository
    ) -> None:
        #  That is the difference between the two commands.
        session.receive(b"*8#")
        repository.add_post(make_post(500000, 99))
        session.receive(b"*00#")
        assert "Topic 500000" not in screen(session)


class TestLoggingOff:
    def test_the_logoff_page_ends_the_session(self, session: Session) -> None:
        session.receive(b"*90#")
        assert session.finished

    def test_a_goodbye_is_sent_before_the_line_drops(self, session: Session) -> None:
        response = session.receive(b"*90#")
        assert "GOODBYE" in _text(response[-1]).upper()

    def test_the_keyword_works_as_well(self, session: Session) -> None:
        session.receive(b"*BYE#")
        assert session.finished


class TestWhatIsSent:
    def test_every_response_is_a_whole_frame(self, session: Session) -> None:
        response = session.receive(b"*8#")
        assert response
        for message in response:
            assert message.startswith(bytes([0x0C, 0x1E]))

    def test_nothing_is_sent_for_a_part_typed_request(self, session: Session) -> None:
        assert session.receive(b"*84") == []

    def test_every_byte_survives_a_seven_bit_line(self, session: Session) -> None:
        for keyed in [b"*1#", b"*8#", b"*82489000#", b"*9#", b"#", b"*0#"]:
            for message in session.receive(keyed):
                assert all(byte < 0x80 for byte in message)


def _text(message: bytes) -> str:
    return "".join(chr(byte) for byte in message if 0x20 <= byte < 0x7F)


class TestMovingWithinAPage:
    """`#` and `B` walk the frames of whatever is showing."""

    def test_hash_advances_and_b_goes_back(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"#")
        assert session.frame_index == 1
        session.receive(b"B")
        assert session.frame_index == 0

    def test_b_on_the_first_frame_does_nothing(self, session: Session) -> None:
        session.receive(b"*8#")
        assert session.receive(b"B") == []
        assert session.frame_index == 0

    def test_hash_on_the_last_frame_does_nothing(self, session: Session) -> None:
        session.receive(b"*9#")
        assert session.receive(b"#") == []

    def test_moving_frames_does_not_disturb_the_history(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"#")
        session.receive(b"B")
        session.receive(b"*0#")
        assert session.reference == MainIndex()


class TestMovingBetweenPosts:
    """`N` and `P` walk the sequence the reader arrived through."""

    def test_next_post_follows_the_menu_that_was_used(self, session: Session) -> None:
        session.receive(b"*8#")  # latest posts, newest first
        session.receive(b"1")  # the newest
        session.receive(b"N")
        assert session.reference == PostPage(489023)

    def test_previous_post_goes_back_up_the_sequence(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"2")
        session.receive(b"P")
        assert session.reference == PostPage(489024)

    def test_the_sequence_continues_past_the_end_of_a_menu_frame(
        self, session: Session
    ) -> None:
        #  The ninth choice of frame a is followed by the first of frame b.
        session.receive(b"*8#")
        session.receive(b"9")
        session.receive(b"N")
        assert session.reference == PostPage(489015)

    def test_the_first_of_a_sequence_offers_no_previous(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"1")
        assert session.receive(b"P") == []

    def test_the_last_of_a_sequence_offers_no_next(self, session: Session) -> None:
        session.receive(b"*3220260802#")  # a day, oldest first
        session.receive(b"1")
        assert session.receive(b"P") == []

    def test_typing_a_page_number_leaves_no_sequence_to_walk(self, session: Session) -> None:
        session.receive(b"*82489000#")
        assert session.receive(b"N") == []
        assert session.receive(b"P") == []

    def test_a_day_gives_that_day_as_the_sequence(self, session: Session) -> None:
        session.receive(b"*3220260802#")
        session.receive(b"1")  # oldest that day
        session.receive(b"N")
        assert session.reference == PostPage(489001)

    def test_walking_on_leaves_the_sequence_intact(self, session: Session) -> None:
        session.receive(b"*8#")
        session.receive(b"1")
        session.receive(b"N")
        session.receive(b"N")
        assert session.reference == PostPage(489022)

    def test_leaving_for_a_different_page_abandons_the_sequence(
        self, session: Session
    ) -> None:
        session.receive(b"*8#")
        session.receive(b"1")
        session.receive(b"*9#")
        assert session.receive(b"N") == []
