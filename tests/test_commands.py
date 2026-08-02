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

    def test_two_stars_clear_a_part_typed_request(self) -> None:
        assert parse(b"*824**") == [Clear()]

    def test_a_request_typed_after_clearing_is_read_normally(self) -> None:
        parser = CommandParser()
        assert parser.feed(b"*824**") == [Clear()]
        assert parser.feed(b"*1#") == [GoTo("1")]

    def test_a_second_star_mid_request_starts_again(self) -> None:
        #  ** clears, so what follows is a fresh request rather than a mess.
        parser = CommandParser()
        parser.feed(b"*824**")
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
    @pytest.mark.parametrize("noise", [b"\n", b"\x00", b"\x1b", b"\x7f", b" "])
    def test_bytes_that_are_not_keys_are_ignored(self, noise: bytes) -> None:
        #  A terminal sends line feeds and stray control bytes; none of them
        #  mean anything here.
        assert parse(noise) == []

    def test_noise_does_not_disturb_a_request_in_progress(self) -> None:
        assert parse(b"*84\n89\x00493#") == [GoTo("8489493")]

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
