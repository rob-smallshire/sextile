"""What a page is called.

A page address is the page number itself -- the digits a reader keys between
`*` and `#`. The framework carries nothing richer, because a page number is the
one name that means the same thing to the reader, to the terminal, to the
application and to anyone quoting it in the pub.

A frame letter is not part of an address. It appears on screen so a reader knows
there is more below, but it is never keyed.
"""

import pytest

from sextile.addressing import PageAddress, UnknownPageError, frame_letter, keyed


class TestParsing:
    def test_digits_are_an_address(self) -> None:
        assert PageAddress("82489493").digits == "82489493"

    def test_an_address_prints_as_its_digits(self) -> None:
        assert str(PageAddress("42")) == "42"

    def test_a_single_digit_is_an_address(self) -> None:
        assert PageAddress("1").digits == "1"

    #  Measured against Commstar: page numbers have no practical length limit,
    #  so nothing here imposes one.
    def test_a_long_address_is_accepted(self) -> None:
        assert PageAddress("9" * 40).digits == "9" * 40

    def test_an_empty_address_is_refused(self) -> None:
        with pytest.raises(UnknownPageError):
            PageAddress("")

    @pytest.mark.parametrize("text", ["4a", "MAIN", "8.2", "-1", " 42", "42 "])
    def test_anything_but_digits_is_refused(self, text: str) -> None:
        with pytest.raises(UnknownPageError):
            PageAddress(text)

    #  Arabic-Indic digits are digits to str.isdigit, and are not what a viewdata
    #  keypad sends.
    def test_non_ascii_digits_are_refused(self) -> None:
        with pytest.raises(UnknownPageError):
            PageAddress("٤٢")


class TestIdentity:
    def test_the_same_digits_are_the_same_address(self) -> None:
        assert PageAddress("42") == PageAddress("42")

    def test_addresses_are_hashable(self) -> None:
        #  History, sequences and a frame's choices all key on addresses.
        assert len({PageAddress("42"), PageAddress("42"), PageAddress("43")}) == 2

    def test_leading_zeros_make_a_different_address(self) -> None:
        #  Whether a page may be named two ways is the application's affair; an
        #  address is only the digits it is made of.
        assert PageAddress("042") != PageAddress("42")


class TestDisplay:
    def test_the_first_frame_is_a(self) -> None:
        assert PageAddress("82489493").frame_number(0) == "82489493a"

    def test_a_later_frame_is_a_later_letter(self) -> None:
        assert PageAddress("82489493").frame_number(1) == "82489493b"

    def test_frames_are_lettered_from_a(self) -> None:
        assert [frame_letter(index) for index in range(3)] == ["a", "b", "c"]

    def test_a_page_has_at_most_twenty_six_frames(self) -> None:
        assert frame_letter(25) == "z"
        with pytest.raises(ValueError):
            frame_letter(26)

    def test_there_is_no_frame_before_the_first(self) -> None:
        with pytest.raises(ValueError):
            frame_letter(-1)


class TestKeyingAPageNumber:
    def test_a_number_is_keyed_between_a_star_and_a_hash(self) -> None:
        assert keyed(PageAddress("91")) == "*91#"

    def test_and_so_is_a_keyword(self) -> None:
        #  `*MAIN#` is keyed exactly as `*1#` is, which is why this takes both.
        assert keyed("MAIN") == "*MAIN#"

    def test_a_pattern_is_shown_the_way_it_is_keyed_too(self) -> None:
        #  What a contents page lists: the fields stay as they are written.
        assert keyed("82<post_id>") == "*82<post_id>#"
