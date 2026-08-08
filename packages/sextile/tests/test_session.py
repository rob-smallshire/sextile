"""What a connected terminal is doing.

The session holds where the reader is, what they have seen, and how they got
there. Everything it does is a response to one command, and every response is
either a frame to send or nothing at all -- there is no other way to talk to a
terminal that can only display what arrives.

Nothing here knows what the service on the other side is about. The application
these tests drive is a made-up one with a menu, some items and a goodbye page,
and that is deliberate: if the session needed to know it was serving a forum,
the framework would not be one.
"""

import pytest
from exemplar import Board

from sextile.addressing import PageAddress
from sextile.application import PageRequest, Sextile
from sextile.page import Page
from sextile.session.session import Session
from sextile.viewdata.frame import FRAME_PREAMBLE


@pytest.fixture
def board() -> Board:
    return Board()


@pytest.fixture
async def session(board: Board) -> Session:
    opened = Session(board)
    await opened.greeting()
    return opened


def screen(session: Session) -> str:
    frame = session.current_frame()
    assert frame is not None
    characters, _ = frame.to_grid()
    return "\n".join(characters)


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


def _text(message: bytes) -> str:
    return "".join(chr(byte) for byte in message if 0x20 <= byte < 0x7F)


class TestOpening:
    async def test_a_session_opens_on_the_application_s_home_page(self, board: Board) -> None:
        assert Session(board).address == board.home

    async def test_the_opening_frame_is_ready_to_send(self, board: Board) -> None:
        opened = Session(board)
        assert await opened.greeting() is not None
        assert "THE BOARD" in screen(opened)

    async def test_a_session_may_be_started_somewhere_else(self, board: Board) -> None:
        opened = Session(board, start=at("8"))
        await opened.greeting()
        assert "ITEMS" in screen(opened)

    async def test_a_session_is_not_finished_to_begin_with(self, session: Session) -> None:
        assert not session.finished

    async def test_a_home_page_that_is_not_there_still_shows_something(self) -> None:
        #  A caller must be given a frame. Dropping the line on connecting would
        #  be indistinguishable from the service being down.
        empty = Sextile()
        opened = Session(empty)
        assert await opened.greeting()
        assert opened.current_frame() is not None


class TestGoingToPages:
    async def test_a_page_number_goes_there(self, session: Session) -> None:
        await session.receive(b"*8#")
        assert session.address == at("8")

    async def test_a_longer_number_goes_there_too(self, session: Session) -> None:
        await session.receive(b"*821000#")
        assert session.address == at("821000")

    async def test_a_keyword_goes_there(self, session: Session) -> None:
        #  Not every viewdata service was purely numeric, and ours need not be.
        await session.receive(b"*8#")
        await session.receive(b"*MAIN#")
        assert session.address == at("1")

    async def test_an_unknown_page_leaves_the_reader_where_they_were(
        self, session: Session
    ) -> None:
        await session.receive(b"*8#")
        await session.receive(b"*222222#")
        assert session.address == at("8")

    async def test_an_unknown_page_says_so_rather_than_ignoring_the_reader(
        self, session: Session
    ) -> None:
        response = await session.receive(b"*222222#")
        assert response
        assert "NOT" in _text(response[-1]).upper()

    async def test_a_word_that_names_no_page_says_so_as_well(self, session: Session) -> None:
        response = await session.receive(b"*BANANA#")
        assert response
        assert "BANANA" in _text(response[-1])

    async def test_the_frame_shown_for_an_unknown_page_is_not_stepped_into(
        self, session: Session
    ) -> None:
        #  It is something said to the reader, not somewhere they have gone: it
        #  must not enter the history either.
        await session.receive(b"*8#")
        await session.receive(b"*222222#")
        await session.receive(b"*0#")
        assert session.address == at("1")


class TestSelecting:
    async def test_a_digit_follows_the_choice_it_names(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"1")
        assert session.address == at("821024")

    async def test_zero_returns_to_the_main_index(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"0")
        assert session.address == at("1")

    async def test_a_key_the_frame_does_not_offer_is_ignored(self, session: Session) -> None:
        await session.receive(b"*9#")
        assert await session.receive(b"7") == []
        assert session.address == at("9")

    async def test_a_letter_key_is_ignored_where_no_page_offers_one(
        self, session: Session
    ) -> None:
        assert await session.receive(b"D") == []


class TestFrames:
    async def test_hash_advances_a_frame(self, session: Session) -> None:
        await session.receive(b"*8#")
        assert session.frame_index == 0
        await session.receive(b"#")
        assert session.frame_index == 1

    async def test_the_frame_letter_shows_in_the_page_number(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"#")
        assert "8b" in screen(session)

    async def test_hash_on_the_last_frame_stays_put(self, session: Session) -> None:
        #  Wrapping round would loop a reader who cannot see they have.
        await session.receive(b"*9#")
        before = session.frame_index
        await session.receive(b"#")
        assert session.frame_index == before

    async def test_going_to_a_new_page_starts_at_its_first_frame(
        self, session: Session
    ) -> None:
        await session.receive(b"*8#")
        await session.receive(b"#")
        await session.receive(b"*1#")
        assert session.frame_index == 0


class TestHistory:
    async def test_back_returns_to_the_previous_page(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"*9#")
        await session.receive(b"*0#")
        assert session.address == at("8")

    async def test_back_remembers_the_frame_that_was_showing(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"#")
        await session.receive(b"*9#")
        await session.receive(b"*0#")
        assert session.frame_index == 1

    async def test_back_unwinds_more_than_one_step(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"*821000#")
        await session.receive(b"*9#")
        await session.receive(b"*0#")
        await session.receive(b"*0#")
        assert session.address == at("8")

    async def test_back_at_the_beginning_does_nothing_harmful(self, session: Session) -> None:
        await session.receive(b"*0#")
        assert session.address == at("1")

    async def test_selecting_a_choice_is_remembered_too(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"1")
        await session.receive(b"*0#")
        assert session.address == at("8")


class TestRedisplayAndRefresh:
    async def test_redisplay_sends_the_same_frame_again(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"#")
        response = await session.receive(b"*00#")
        assert response
        assert session.frame_index == 1

    async def test_refresh_builds_the_page_again(
        self, session: Session, board: Board
    ) -> None:
        await session.receive(b"*8#")
        board.items.insert(0, 9999)
        response = await session.receive(b"*09#")
        assert response
        assert "page 829999" in screen(session)

    async def test_redisplay_does_not_notice_what_has_changed(
        self, session: Session, board: Board
    ) -> None:
        #  That is the difference between the two commands.
        await session.receive(b"*8#")
        board.items.insert(0, 9999)
        await session.receive(b"*00#")
        assert "page 829999" not in screen(session)


class TestRingingOff:
    async def test_a_page_that_says_so_ends_the_session(self, session: Session) -> None:
        await session.receive(b"*90#")
        assert session.finished

    async def test_the_page_is_sent_before_the_line_drops(self, session: Session) -> None:
        response = await session.receive(b"*90#")
        assert "GOODBYE" in _text(response[-1]).upper()

    async def test_a_keyword_can_reach_it_as_well(self, session: Session) -> None:
        await session.receive(b"*BYE#")
        assert session.finished

    async def test_an_ordinary_page_does_not_end_it(self, session: Session) -> None:
        await session.receive(b"*8#")
        assert not session.finished


class TestSessionState:
    #  The connection is the session, so a handler has somewhere to keep what
    #  this caller has done.

    async def test_a_handler_can_leave_something_for_the_next_page(
        self, board: Board
    ) -> None:
        seen: list[str] = []

        @board.page("7", name="counter")
        async def counter(request: PageRequest) -> Page:
            been = int(str(request.session.get("been", 0)))
            request.session["been"] = been + 1
            seen.append(f"{been}")
            return await board.notice(request)

        opened = Session(board)
        await opened.greeting()
        await opened.receive(b"*7#")
        await opened.receive(b"*7#")
        assert seen == ["0", "1"]

    async def test_two_callers_do_not_share_it(self, board: Board) -> None:
        first, second = Session(board), Session(board)
        first.state["user"] = "komadori"
        assert second.state == {}


class TestWhatIsSent:
    async def test_a_page_is_sent_as_a_whole_frame(self, session: Session) -> None:
        #  A command line is drawn over one row instead; see TestTheCommandLine.
        response = await session.receive(b"*8#")
        assert response
        for message in response:
            assert message.startswith(FRAME_PREAMBLE)

    async def test_a_part_typed_request_is_echoed_rather_than_ignored(
        self, session: Session
    ) -> None:
        #  It used to be answered with silence. Commstar does not echo, so the
        #  reader was typing blind; now the footer row shows what they have.
        response = await session.receive(b"*84")
        assert len(response) == 1
        assert "*84" in _text(response[0])

    async def test_every_byte_survives_a_seven_bit_line(self, session: Session) -> None:
        for keyed in [b"*1#", b"*8#", b"*821000#", b"*9#", b"#", b"*0#"]:
            for message in await session.receive(keyed):
                assert all(byte < 0x80 for byte in message)


class TestMovingWithinAPage:
    """`#` and `W` walk the frames of whatever is showing."""

    async def test_s_advances_and_w_goes_back(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"#")
        assert session.frame_index == 1
        await session.receive(b"W")
        assert session.frame_index == 0

    async def test_w_on_the_first_frame_does_nothing(self, session: Session) -> None:
        await session.receive(b"*8#")
        assert await session.receive(b"W") == []
        assert session.frame_index == 0

    async def test_hash_on_the_last_frame_does_nothing(self, session: Session) -> None:
        await session.receive(b"*9#")
        assert await session.receive(b"#") == []

    async def test_moving_frames_does_not_disturb_the_history(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"#")
        await session.receive(b"W")
        await session.receive(b"*0#")
        assert session.address == at("1")


class TestMovingBetweenItems:
    """`D` and `A` walk the sequence the reader arrived through."""

    async def test_next_follows_the_menu_that_was_used(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"1")
        await session.receive(b"D")
        assert session.address == at("821023")

    async def test_previous_goes_back_up_the_sequence(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"2")
        await session.receive(b"A")
        assert session.address == at("821024")

    async def test_the_sequence_continues_past_the_end_of_a_menu_frame(
        self, session: Session
    ) -> None:
        #  The ninth choice of frame a is followed by the first of frame b.
        await session.receive(b"*8#")
        await session.receive(b"9")
        await session.receive(b"D")
        assert session.address == at("821015")

    async def test_the_first_of_a_sequence_offers_no_previous(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"1")
        assert await session.receive(b"A") == []

    async def test_keying_a_page_number_leaves_no_sequence_to_walk(
        self, session: Session
    ) -> None:
        await session.receive(b"*821000#")
        assert await session.receive(b"D") == []
        assert await session.receive(b"A") == []

    async def test_walking_on_leaves_the_sequence_intact(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"1")
        await session.receive(b"D")
        await session.receive(b"D")
        assert session.address == at("821022")

    async def test_leaving_for_a_different_page_abandons_the_sequence(
        self, session: Session
    ) -> None:
        await session.receive(b"*8#")
        await session.receive(b"1")
        await session.receive(b"*9#")
        assert await session.receive(b"D") == []


class TestTheConventionalKeyStillWorks:
    """`#` is the one key a viewdata reader tries without being told."""

    async def test_hash_still_advances_a_frame(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"#")
        assert session.frame_index == 1

    async def test_hash_and_s_do_the_same_thing(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"#")
        by_hash = session.frame_index
        await session.receive(b"W")
        await session.receive(b"S")
        assert session.frame_index == by_hash

    async def test_hash_does_nothing_where_s_would_do_nothing(self, session: Session) -> None:
        await session.receive(b"*9#")
        assert await session.receive(b"#") == []
        assert await session.receive(b"S") == []


class TestTheCommandLine:
    """What a reader sees while typing a page request.

    Commstar does not echo it, so unless Sextile draws it the reader is typing
    blind. It replaces the footer, and goes away again when the request is done
    or cancelled.
    """

    async def test_a_star_puts_the_command_line_up(self, session: Session) -> None:
        response = await session.receive(b"*")
        assert response
        assert "cancels" in _text(response[-1])

    async def test_it_shows_what_has_been_typed(self, session: Session) -> None:
        await session.receive(b"*")
        response = await session.receive(b"824")
        assert "*824" in _text(response[-1])

    async def test_it_follows_every_keystroke(self, session: Session) -> None:
        await session.receive(b"*8")
        assert "2" in _text((await session.receive(b"2"))[-1])
        assert "4" in _text((await session.receive(b"4"))[-1])

    async def test_it_does_not_clear_the_screen(self, session: Session) -> None:
        #  The page beneath has to survive, or there was no point drawing a row.
        for response in await session.receive(b"*824"):
            assert 0x0C not in response

    async def test_a_cancel_puts_the_footer_back(self, session: Session) -> None:
        await session.receive(b"*824")
        response = await session.receive(b"*")
        assert response
        assert "menu" in _text(response[-1])
        assert "cancels" not in _text(response[-1])

    async def test_cancelling_and_beginning_again_shows_an_empty_buffer(
        self, session: Session
    ) -> None:
        await session.receive(b"*824")
        response = await session.receive(b"**")
        assert "824" not in _text(response[-1])
        assert "cancels" in _text(response[-1])

    async def test_completing_a_request_redraws_the_whole_page(
        self, session: Session
    ) -> None:
        await session.receive(b"*8")
        response = await session.receive(b"#")
        assert response[-1].startswith(FRAME_PREAMBLE)
        assert session.address == at("8")

    async def test_an_unknown_page_leaves_no_command_line_behind(
        self, session: Session
    ) -> None:
        await session.receive(b"*222222")
        response = await session.receive(b"#")
        assert "cancels" not in _text(response[-1])

    async def test_a_request_that_changes_nothing_still_restores_the_footer(
        self, session: Session
    ) -> None:
        #  `*#` on a single-frame page moves nowhere, but the command line must
        #  not be left on screen.
        await session.receive(b"*9#")
        await session.receive(b"*")
        response = await session.receive(b"#")
        assert response
        assert "menu" in _text(response[-1])

    async def test_an_ordinary_keypress_draws_no_command_line(
        self, session: Session
    ) -> None:
        await session.receive(b"*8#")
        for response in await session.receive(b"1"):
            assert "cancels" not in _text(response)

    async def test_every_byte_survives_a_seven_bit_line(self, session: Session) -> None:
        for keyed in (b"*", b"8", b"2", b"*", b"#"):
            for response in await session.receive(keyed):
                assert all(byte < 0x80 for byte in response)


class TestTheCommandLineIsNotRepainted:
    """A keystroke that only adds a character sends that character.

    The cursor is already sitting where it goes, so it advances itself.
    Repainting forty cells and stepping the cursor back across them is visible
    as a flicker once the cursor is on -- which is the whole reason it is on.
    """

    async def test_the_first_star_draws_the_whole_line(self, session: Session) -> None:
        assert len((await session.receive(b"*"))[-1]) > 20

    async def test_a_further_digit_costs_one_byte(self, session: Session) -> None:
        await session.receive(b"*8")
        assert await session.receive(b"2") == [b"2"]

    async def test_digit_after_digit_costs_one_byte_each(self, session: Session) -> None:
        await session.receive(b"*")
        assert await session.receive(b"8") == [b"8"]
        assert await session.receive(b"2") == [b"2"]
        assert await session.receive(b"4") == [b"4"]

    async def test_a_delete_costs_three_bytes(self, session: Session) -> None:
        #  Cursor left, a space over the character, cursor left again.
        await session.receive(b"*824")
        assert await session.receive(b"\x7f") == [bytes([0x08, 0x20, 0x08])]

    async def test_the_line_is_correct_again_after_a_delete(self, session: Session) -> None:
        await session.receive(b"*824")
        await session.receive(b"\x7f")
        assert await session.receive(b"9") == [b"9"]

    async def test_a_scrolling_buffer_redraws(self, session: Session) -> None:
        #  Past the buffer's width everything shifts, so one byte will not do.
        await session.receive(b"*" + b"9" * 30)
        assert len((await session.receive(b"9"))[-1]) > 20

    async def test_a_letter_is_encoded_for_the_terminal(self, session: Session) -> None:
        #  Not merely echoed: a page request may name a keyword.
        await session.receive(b"*MAIN")
        assert await session.receive(b"X") == [b"X"]


class TestDeletingTheStar:
    async def test_it_puts_the_footer_back(self, session: Session) -> None:
        await session.receive(b"*8")
        await session.receive(b"\x7f")
        response = await session.receive(b"\x7f")
        assert response
        assert "menu" in _text(response[-1])
        assert "cancels" not in _text(response[-1])

    async def test_the_page_beneath_is_left_alone(self, session: Session) -> None:
        await session.receive(b"*8#")
        before = session.address
        await session.receive(b"*")
        await session.receive(b"\x7f")
        assert session.address == before

    async def test_a_digit_afterwards_selects_from_the_menu(self, session: Session) -> None:
        await session.receive(b"*8#")
        await session.receive(b"*")
        await session.receive(b"\x7f")
        await session.receive(b"1")
        assert session.address == at("821024")


class TestRubbingOutIsAlsoIncremental:
    async def test_a_delete_moves_back_blanks_and_moves_back(self, session: Session) -> None:
        await session.receive(b"*82")
        assert await session.receive(b"\x7f") == [bytes([0x08, 0x20, 0x08])]

    async def test_deletes_in_a_row_each_cost_three(self, session: Session) -> None:
        await session.receive(b"*824")
        assert await session.receive(b"\x7f") == [bytes([0x08, 0x20, 0x08])]
        assert await session.receive(b"\x7f") == [bytes([0x08, 0x20, 0x08])]

    async def test_typing_after_a_delete_costs_one(self, session: Session) -> None:
        await session.receive(b"*824")
        await session.receive(b"\x7f")
        assert await session.receive(b"9") == [b"9"]

    async def test_deleting_the_star_restores_the_footer_instead(
        self, session: Session
    ) -> None:
        await session.receive(b"*")
        response = await session.receive(b"\x7f")
        assert "menu" in _text(response[-1])

    async def test_a_scrolled_buffer_still_redraws(self, session: Session) -> None:
        #  Past the buffer's width the whole row shifts, so a small edit will
        #  not do.
        await session.receive(b"*" + b"9" * 30)
        assert len((await session.receive(b"\x7f"))[-1]) > 20


class TestTheIdleWarning:
    """A silent line is about to be released, and the reader is told.

    The bar is modal: while it is showing, the next key dismisses it and does
    nothing else. That is the only way to be able to say "press a key" without
    also saying "and you may end up somewhere you did not ask for".
    """

    async def test_nothing_is_showing_to_begin_with(self, session: Session) -> None:
        assert not session.warning_showing

    async def test_warning_draws_the_bar(self, session: Session) -> None:
        drawn = session.warn(1.0)
        assert drawn is not None
        assert "Press a key" in _text(drawn)
        assert session.warning_showing

    async def test_the_page_beneath_is_not_cleared(self, session: Session) -> None:
        drawn = session.warn(1.0)
        assert drawn is not None
        assert 0x0C not in drawn

    async def test_an_unchanged_bar_sends_nothing(self, session: Session) -> None:
        session.warn(1.0)
        assert session.warn(1.0) is None

    async def test_a_bar_that_has_drained_further_is_sent(self, session: Session) -> None:
        session.warn(1.0)
        assert session.warn(0.2) is not None

    async def test_a_key_dismisses_it_and_does_nothing_else(self, session: Session) -> None:
        await session.receive(b"*8#")
        before = session.address
        session.warn(0.5)
        response = await session.receive(b"1")
        assert session.address == before, "the key must not navigate"
        assert not session.warning_showing
        assert response

    async def test_the_page_s_own_footer_comes_back(self, session: Session) -> None:
        session.warn(0.5)
        response = await session.receive(b"1")
        assert "menu" in _text(response[-1])
        assert "Press a key" not in _text(response[-1])

    async def test_the_next_key_works_as_usual(self, session: Session) -> None:
        await session.receive(b"*8#")
        session.warn(0.5)
        await session.receive(b"1")
        await session.receive(b"1")
        assert session.address == at("821024")

    async def test_a_part_typed_request_survives_the_warning(
        self, session: Session
    ) -> None:
        #  The command line occupies the same row. Drawing over a request the
        #  reader is in the middle of typing would lose what they had typed.
        await session.receive(b"*82")
        assert session.warn(0.5) is None
        assert not session.warning_showing

    async def test_a_request_being_typed_still_completes(self, session: Session) -> None:
        await session.receive(b"*8")
        session.warn(0.5)
        await session.receive(b"#")
        assert session.address == at("8")

    async def test_dismissing_when_nothing_is_showing_changes_nothing(
        self, session: Session
    ) -> None:
        assert session.dismiss() is None
