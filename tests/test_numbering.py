"""Page numbers.

The first digit names a namespace, the second says what kind of page within it:
the bare root is the index, 1 is reserved for search, and 2 introduces a member.
So 4 lists the forums and 4253 is one of them.

Because a page request is terminated by `#`, numbers need not be prefix-free --
only distinct -- which is what lets the fields vary in width.

Identifiers come from Stardot itself. Nothing here allocates a number, so
nothing can renumber, and a page number means the same thing on the web forum
as it does on a BBC Micro.
"""

from datetime import date

import pytest

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
    Post,
    PostsIndex,
    Topic,
    TopicsIndex,
    UnknownPageError,
    format_page_number,
    parse_page_number,
)

EVERY_KIND = [
    ("1", MainIndex()),
    ("3", DaysIndex()),
    ("3220260802", Day(date(2026, 8, 2))),
    ("4", ForumsIndex()),
    ("4253", Forum(53)),
    ("5", ContributorsIndex()),
    ("5210058", Contributor(10058)),
    ("7", TopicsIndex()),
    ("7233387", Topic(33387)),
    ("8", PostsIndex()),
    ("82489493", Post(489493)),
    ("9", About()),
    ("90", Logoff()),
]


class TestParsing:
    @pytest.mark.parametrize(("number", "reference"), EVERY_KIND)
    def test_every_kind_of_page(self, number: str, reference: PageRef) -> None:
        assert parse_page_number(number) == reference

    def test_a_bare_root_is_the_namespace_index(self) -> None:
        assert parse_page_number("4") == ForumsIndex()

    def test_a_second_digit_of_two_introduces_a_member(self) -> None:
        assert parse_page_number("4253") == Forum(53)

    def test_a_real_stardot_post(self) -> None:
        #  p=489493 in the feed, viewtopic.php?p=489493 on the web.
        assert parse_page_number("82489493") == Post(489493)


class TestNamespaceStructure:
    @pytest.mark.parametrize("root", ["3", "4", "5", "7", "8"])
    def test_the_index_is_never_spelled_root_zero(self, root: str) -> None:
        #  The bare root already names the index; accepting both spellings would
        #  give one page two numbers.
        with pytest.raises(UnknownPageError):
            parse_page_number(f"{root}0")

    @pytest.mark.parametrize("number", ["41", "51", "71", "81", "31", "11"])
    def test_search_is_reserved_but_not_yet_built(self, number: str) -> None:
        with pytest.raises(UnknownPageError):
            parse_page_number(number)

    @pytest.mark.parametrize("number", ["43", "49", "8353", "7433387"])
    def test_unallocated_kinds_are_rejected(self, number: str) -> None:
        with pytest.raises(UnknownPageError):
            parse_page_number(number)

    @pytest.mark.parametrize("root", ["3", "4", "5", "7", "8"])
    def test_a_member_prefix_with_no_identifier_names_nothing(self, root: str) -> None:
        with pytest.raises(UnknownPageError):
            parse_page_number(f"{root}2")


class TestRoundTripping:
    @pytest.mark.parametrize(("number", "reference"), EVERY_KIND)
    def test_formatting_inverts_parsing(self, number: str, reference: PageRef) -> None:
        assert format_page_number(reference) == number

    @pytest.mark.parametrize(("number", "_reference"), EVERY_KIND)
    def test_parsing_inverts_formatting(self, number: str, _reference: PageRef) -> None:
        assert format_page_number(parse_page_number(number)) == number


class TestRejection:
    @pytest.mark.parametrize("number", ["", " ", "abc", "8489493a", "84 89", "-1", "8.5"])
    def test_anything_but_digits_is_rejected(self, number: str) -> None:
        with pytest.raises(UnknownPageError):
            parse_page_number(number)

    @pytest.mark.parametrize("number", ["0", "00", "01", "2", "6", "20", "60"])
    def test_reserved_namespaces_are_unknown(self, number: str) -> None:
        #  0 is left free because the Prestel commands *0#, *00# and *09# live
        #  there; 2 and 6 are simply unallocated.
        with pytest.raises(UnknownPageError):
            parse_page_number(number)

    @pytest.mark.parametrize("number", ["42053", "52010058", "820489493", "7203"])
    def test_a_member_id_may_not_have_a_leading_zero(self, number: str) -> None:
        #  Stardot's identifiers never do, so accepting them would give one page
        #  two numbers.
        with pytest.raises(UnknownPageError):
            parse_page_number(number)

    def test_nine_zero_is_logoff_rather_than_a_leading_zero_member(self) -> None:
        #  9 has no members, so 90 is free to keep the Prestel logoff convention.
        assert parse_page_number("90") == Logoff()

    @pytest.mark.parametrize("number", ["91", "900", "99"])
    def test_nothing_else_hangs_off_nine(self, number: str) -> None:
        with pytest.raises(UnknownPageError):
            parse_page_number(number)


class TestDays:
    def test_a_day_is_eight_digits_of_iso_basic_date(self) -> None:
        assert parse_page_number("3220260802") == Day(date(2026, 8, 2))

    @pytest.mark.parametrize("number", ["322026080", "32202608022", "32123"])
    def test_a_day_must_be_exactly_eight_digits(self, number: str) -> None:
        with pytest.raises(UnknownPageError):
            parse_page_number(number)

    @pytest.mark.parametrize("number", ["3220261301", "3220260230", "3200000000"])
    def test_an_impossible_date_is_rejected(self, number: str) -> None:
        with pytest.raises(UnknownPageError):
            parse_page_number(number)

    def test_a_leap_day_is_accepted(self) -> None:
        assert parse_page_number("3220240229") == Day(date(2024, 2, 29))

    def test_days_are_typeable_for_browsing(self) -> None:
        #  Yesterday's posts without touching a menu, which is the whole reason
        #  dates survive in the scheme at all.
        assert format_page_number(Day(date(2026, 8, 1))) == "3220260801"


class TestFrames:
    """Frames are a display detail; a user types only the page number."""

    def test_frames_are_lettered_from_a(self) -> None:
        from sextile.pages.numbering import frame_letter

        assert frame_letter(0) == "a"
        assert frame_letter(25) == "z"

    @pytest.mark.parametrize("index", [-1, 26, 100])
    def test_a_page_has_at_most_twenty_six_frames(self, index: int) -> None:
        from sextile.pages.numbering import frame_letter

        with pytest.raises(ValueError):
            frame_letter(index)
