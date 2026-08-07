"""Reading what a terminal sends.

The parser recognises syntax only. Whether `MAIN` or `82489493` names anything
is not its business, and neither is whether `N` does something on this frame --
that keeps the grammar small and lets pages decide their own keys.

Bytes arrive a few at a time down a 75-baud line, so everything here is fed
incrementally and must survive being split anywhere.
"""

import pytest

from sextile.session.commands import (
    ENTRY_LIMIT,
    Back,
    Clear,
    Command,
    CommandParser,
    GoTo,
    Next,
    Redisplay,
    Refresh,
    Select,
)

#: RETURN in Prestel mode transmits this, and it is what terminates a request.
VIEWDATA_HASH = b"\x5f"


def parse(data: bytes) -> list[Command]:
    return CommandParser().feed(data)


class TestPageRequests:
    def test_a_page_number_is_a_request_to_go_there(self) -> None:
        assert parse(b"*8489493" + VIEWDATA_HASH) == [GoTo("8489493")]

    def test_return_terminates_a_request(self) -> None:
        #  Measured against Commstar: RETURN transmits 0x5F, not 0x23.
        assert parse(b"*1" + VIEWDATA_HASH) == [GoTo("1")]

    def test_a_typed_hash_also_terminates(self) -> None:
        #  SHIFT-3 sends 0x23, which is what a plain terminal sends for '#'.
        assert parse(b"*1#") == [GoTo("1")]

    def test_a_carriage_return_also_terminates(self) -> None:
        #  So that the service can be driven from an ordinary terminal.
        assert parse(b"*1\r") == [GoTo("1")]

    def test_a_keyword_is_carried_through_unjudged(self) -> None:
        #  Whether MAIN names anything is the numbering layer's business.
        assert parse(b"*MAIN#") == [GoTo("MAIN")]

    def test_a_keyword_is_normalised_to_upper_case(self) -> None:
        assert parse(b"*main#") == [GoTo("MAIN")]

    def test_an_empty_request_is_not_a_command(self) -> None:
        assert parse(b"*#") == [Next()]


class TestPrestelCommands:
    @pytest.mark.parametrize(
        ("keyed", "expected"),
        [
            (b"*0#", Back()),
            (b"*00#", Redisplay()),
            (b"*09#", Refresh()),
            (b"*#", Next()),
        ],
    )
    def test_the_conventional_commands(self, keyed: bytes, expected: Command) -> None:
        assert parse(keyed) == [expected]

    def test_a_bare_hash_advances_a_frame(self) -> None:
        assert parse(VIEWDATA_HASH) == [Next()]

    def test_two_stars_cancel_a_part_typed_request(self) -> None:
        assert parse(b"*824**") == [Clear()]

    def test_one_star_cancels_outright(self) -> None:
        #  The command line goes away and the footer comes back, so a reader who
        #  changes their mind is not trapped in a buffer they no longer want.
        parser = CommandParser()
        assert parser.feed(b"*824*") == [Clear()]
        assert parser.entry == ""

    def test_a_digit_after_a_cancel_is_an_ordinary_keypress(self) -> None:
        assert parse(b"*824*1") == [Clear(), Select("1")]

    def test_two_stars_cancel_and_begin_again(self) -> None:
        #  Which is what Prestel's `**` did, without the parser knowing the
        #  sequence: it is simply cancel followed by begin.
        parser = CommandParser()
        assert parser.feed(b"*824**") == [Clear()]
        assert parser.entry == "*"

    def test_prestel_habits_still_work(self) -> None:
        assert parse(b"*824**456#") == [Clear(), GoTo("456")]

    def test_a_fresh_request_after_a_cancel_is_read_normally(self) -> None:
        parser = CommandParser()
        parser.feed(b"*824*")
        assert parser.feed(b"*8#") == [GoTo("8")]


class TestImmediateKeys:
    def test_a_digit_selects(self) -> None:
        assert parse(b"3") == [Select("3")]

    def test_a_letter_selects(self) -> None:
        #  Not every viewdata service is a numeric keypad: N for next and R for
        #  reply are ordinary on bulletin boards, and pages may offer them.
        assert parse(b"N") == [Select("N")]

    def test_a_letter_is_normalised_to_upper_case(self) -> None:
        assert parse(b"n") == [Select("N")]

    def test_several_keys_arrive_as_several_commands(self) -> None:
        assert parse(b"123") == [Select("1"), Select("2"), Select("3")]

    def test_keys_typed_during_a_request_are_part_of_it(self) -> None:
        assert parse(b"*123#") == [GoTo("123")]


class TestArrivingInPieces:
    def test_a_request_split_anywhere_is_still_one_command(self) -> None:
        for split in range(1, 10):
            keyed = b"*8489493#"
            parser = CommandParser()
            commands = parser.feed(keyed[:split]) + parser.feed(keyed[split:])
            assert commands == [GoTo("8489493")], f"split at {split}"

    def test_one_byte_at_a_time(self) -> None:
        parser = CommandParser()
        commands: list[Command] = []
        for byte in b"*1#2":
            commands.extend(parser.feed(bytes([byte])))
        assert commands == [GoTo("1"), Select("2")]

    def test_an_unterminated_request_yields_nothing_yet(self) -> None:
        assert parse(b"*8489") == []


class TestNoise:
    @pytest.mark.parametrize("noise", [b"\x00", b"\x1b", b" "])
    def test_bytes_that_are_not_keys_are_ignored(self, noise: bytes) -> None:
        #  A terminal sends line feeds and stray control bytes; none of them
        #  mean anything here.
        assert parse(noise) == []

    def test_noise_does_not_disturb_a_request_in_progress(self) -> None:
        assert parse(b"*84\x1b89\x00493#") == [GoTo("8489493")]

    def test_the_eighth_bit_is_ignored(self) -> None:
        #  A 7E1 line can deliver the parity bit set on a noisy connection.
        assert parse(bytes([0x80 | ord("3")])) == [Select("3")]


class TestRunawayInput:
    def test_an_over_long_request_is_abandoned(self) -> None:
        parser = CommandParser()
        assert parser.feed(b"*" + b"9" * (ENTRY_LIMIT + 10)) == [Clear()]

    def test_the_parser_recovers_after_abandoning_one(self) -> None:
        parser = CommandParser()
        parser.feed(b"*" + b"9" * (ENTRY_LIMIT + 10))
        assert parser.feed(b"*1#") == [GoTo("1")]


class TestTheEntrySoFar:
    """What the reader has typed, so a service can echo it."""

    def test_nothing_is_pending_to_begin_with(self) -> None:
        assert CommandParser().entry == ""

    def test_a_part_typed_request_is_visible(self) -> None:
        parser = CommandParser()
        parser.feed(b"*824")
        assert parser.entry == "*824"

    def test_completing_a_request_empties_it(self) -> None:
        parser = CommandParser()
        parser.feed(b"*824#")
        assert parser.entry == ""

    def test_an_immediate_key_never_appears_there(self) -> None:
        parser = CommandParser()
        parser.feed(b"3")
        assert parser.entry == ""


class TestTheCursorKeys:
    """The BBC's arrows arrive as viewdata cursor-control codes.

    Measured against Commstar: LEFT, RIGHT, UP and DOWN transmit 0x88-0x8B, and
    the 7E1 line strips the eighth bit, leaving 0x08-0x0B. They mean the same
    four things as WASD, so they parse to the same commands.
    """

    @pytest.mark.parametrize(
        ("code", "same_as"),
        [
            (0x08, "A"),  # cursor left
            (0x09, "D"),  # cursor right
            (0x0A, "S"),  # cursor down
            (0x0B, "W"),  # cursor up
        ],
    )
    def test_an_arrow_means_what_its_letter_means(self, code: int, same_as: str) -> None:
        assert parse(bytes([code])) == parse(same_as.encode())

    @pytest.mark.parametrize("code", [0x08, 0x09, 0x0A, 0x0B])
    def test_an_arrow_with_its_eighth_bit_still_set_is_read(self, code: int) -> None:
        #  A line that did not strip the parity bit delivers 0x88-0x8B.
        assert parse(bytes([0x80 | code])) == parse(bytes([code]))

    def test_the_four_arrows_together(self) -> None:
        assert parse(bytes([0x0B, 0x0A, 0x08, 0x09])) == [
            Select("W"),
            Select("S"),
            Select("A"),
            Select("D"),
        ]

    def test_an_arrow_during_a_request_is_ignored(self) -> None:
        #  Part-way through typing *824 an arrow means nothing; it must not
        #  silently become part of the number.
        assert parse(b"*82" + bytes([0x08]) + b"4#") == [GoTo("824")]

    def test_copy_is_not_a_key_we_see(self) -> None:
        #  Measured: Commstar consumes COPY locally and transmits nothing.
        assert parse(bytes([0x0C])) == []


class TestCarriageReturnAndLineFeed:
    """CR LF is one terminator; a lone LF is the cursor-down key.

    An ordinary terminal sends both bytes when RETURN is pressed. A BBC sends
    0x0A only when its cursor-down key is pressed, that being the viewdata
    cursor-control code. So they cannot simply be treated alike.
    """

    def test_a_terminator_typed_at_a_terminal_is_one_command(self) -> None:
        assert parse(b"*8\r\n") == [GoTo("8")]

    def test_the_line_feed_does_not_arrive_as_a_stray_keypress(self) -> None:
        #  Otherwise every request from `nc` would be followed by a spurious
        #  move to the next frame.
        assert parse(b"*8\r\n") == [GoTo("8")]

    def test_a_bare_line_feed_is_the_cursor_down_key(self) -> None:
        assert parse(b"\n") == [Select("S")]

    def test_a_line_feed_well_after_a_return_is_a_keypress_again(self) -> None:
        assert parse(b"*8\r" + b"A" + b"\n") == [GoTo("8"), Select("A"), Select("S")]

    def test_the_pair_split_across_two_reads_is_still_one_terminator(self) -> None:
        parser = CommandParser()
        assert parser.feed(b"*8\r") == [GoTo("8")]
        assert parser.feed(b"\n") == []

    def test_two_line_feeds_after_a_return_move_once(self) -> None:
        assert parse(b"*8\r\n\n") == [GoTo("8"), Select("S")]


class TestDelete:
    """The BBC's DELETE key sends 0x7F, measured against Commstar.

    Distinct from RETURN, which sends 0x5F and terminates a request -- so a
    reader can rub out a mistyped digit without sending what they have.
    """

    def test_it_rubs_out_the_last_character(self) -> None:
        parser = CommandParser()
        parser.feed(b"*824\x7f")
        assert parser.entry == "*82"

    def test_several_deletes_rub_out_several(self) -> None:
        parser = CommandParser()
        parser.feed(b"*824\x7f\x7f")
        assert parser.entry == "*8"

    def test_deleting_the_star_cancels(self) -> None:
        #  The star is a character like any other, so rubbing it out undoes the
        #  request altogether, as though it had never been typed.
        parser = CommandParser()
        assert parser.feed(b"*\x7f") == [Clear()]
        assert parser.entry == ""

    def test_deleting_back_through_everything_cancels(self) -> None:
        parser = CommandParser()
        assert parser.feed(b"*82\x7f\x7f\x7f") == [Clear()]
        assert parser.entry == ""

    def test_a_key_after_deleting_the_star_is_an_ordinary_keypress(self) -> None:
        assert parse(b"*8\x7f\x7f1") == [Clear(), Select("1")]

    def test_what_is_left_is_still_a_usable_request(self) -> None:
        assert parse(b"*8249\x7f#") == [GoTo("824")]

    def test_delete_outside_a_request_does_nothing(self) -> None:
        assert parse(b"\x7f") == []

    def test_delete_is_not_the_terminator(self) -> None:
        #  0x5F ends a request; 0x7F edits one. Sending the same byte for both
        #  would make rubbing out impossible.
        assert parse(b"*8\x7f") == []
        assert parse(b"*8\x5f") == [GoTo("8")]
