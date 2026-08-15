"""Where this caller has been, as a menu of shortcuts.

A framework page, because there is nothing service-specific about it: what it
lists are addresses, and what it calls them comes from the route names, which
are the application's own words.

It is registered nowhere. A service maps it into its numbering or does not offer
it at all, which is why these tests build it directly.
"""

import pytest

from sextile.addressing import PageAddress
from sextile.application import Sextile
from sextile.builtin.history import TITLE, history_page
from sextile.layout import CHOICES_PER_FRAME
from sextile.page import Page
from sextile.testing import request_for

_APP = Sextile()


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


def built(*been: str, address: str = "92") -> Page:
    return history_page(
        request=request_for(_APP, at(address)),
        been=tuple(at(digits) for digits in been),
        describe=lambda where: f"page {where}",
    )


def text_of(page: Page, index: int = 0) -> str:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


class TestTheOrder:
    #  The session keeps history oldest first; a reader wants it newest first,
    #  so that key 1 means what `*0#` means.

    def test_the_first_entry_is_the_page_before_this_one(self) -> None:
        page = built("1", "8", "82489493")
        assert page.frames[0].destination("1") == at("82489493")

    def test_the_second_is_the_one_before_that(self) -> None:
        page = built("1", "8", "82489493")
        assert page.frames[0].destination("2") == at("8")

    def test_and_so_on_back_to_the_beginning(self) -> None:
        page = built("1", "8", "82489493")
        assert page.frames[0].destination("3") == at("1")

    def test_a_page_visited_twice_appears_twice(self) -> None:
        #  It is a path, not a set: position is what the digits count.
        page = built("8", "82489493", "8")
        assert page.frames[0].destination("1") == at("8")
        assert page.frames[0].destination("3") == at("8")


class TestItLeavesItselfOut:
    #  Visiting it is a move like any other, so it enters the history too -- and
    #  a list of places to go back to has no business offering the one showing.

    def test_its_own_address_is_not_listed(self) -> None:
        page = built("1", "8", "92", address="92")
        assert page.frames[0].destination("1") == at("8")
        assert page.frames[0].destination("2") == at("1")

    def test_even_where_it_was_visited_more_than_once(self) -> None:
        page = built("92", "1", "92", address="92")
        assert set(page.frames[0].choices.values()) == {at("1")}


class TestSayingSo:
    def test_a_caller_who_has_been_nowhere_is_told(self) -> None:
        #  An empty menu with no explanation looks like a fault.
        assert "nowhere" in text_of(built()).lower()

    def test_and_offered_only_the_way_out(self) -> None:
        assert built().frames[0].choices == {"0": at("1")}


class TestLongerHistories:
    def test_nine_to_a_frame(self) -> None:
        page = built(*(str(number) for number in range(11, 11 + CHOICES_PER_FRAME)))
        assert len(page.frames) == 1

    def test_more_than_nine_runs_on(self) -> None:
        page = built(*(str(number) for number in range(11, 31)))
        assert len(page.frames) == 3

    def test_every_entry_can_be_chosen(self) -> None:
        #  Keys run 1-9 on every frame, as every other viewdata menu's do. An
        #  entry shown but not selectable would be worse than not shown.
        page = built(*(str(number) for number in range(11, 31)))
        listed = sum(len(frame.choices) - 1 for frame in page.frames)
        assert listed == 20

    def test_a_later_frame_says_how_far_back_its_entries_are(self) -> None:
        #  The digit only counts the steps on the first frame; after that only
        #  the label can say.
        page = built(*(str(number) for number in range(11, 31)))
        assert "10 back" in text_of(page, 1)

    def test_the_first_entry_of_all_is_one_back(self) -> None:
        assert "one back" in text_of(built("1", "8"))

    def test_the_frames_are_walkable(self) -> None:
        page = built(*(str(number) for number in range(11, 31)))
        assert "S" in page.frames[0].moves
        assert "#" in page.frames[0].moves
        assert "W" in page.frames[1].moves
        assert "S" not in page.frames[-1].moves


class TestWhatItLooksLike:
    def test_it_is_titled(self) -> None:
        assert TITLE in text_of(built("1"))

    def test_a_service_may_title_it_otherwise(self) -> None:
        page = history_page(
            request=request_for(_APP, at("92")),
            been=(at("1"),),
            describe=lambda where: "somewhere",
            title="RECENTLY READ",
        )
        assert "RECENTLY READ" in text_of(page)

    def test_the_entries_are_labelled_by_the_describer(self) -> None:
        assert "page 82489493" in text_of(built("82489493"))

    def test_and_show_the_number_to_key(self) -> None:
        #  `#` travels as 0x5F, drawn as `#`, so the grid shows it.
        assert "*82489493#" in text_of(built("82489493"))

    @pytest.mark.parametrize("digits", ["1", "82489493"])
    def test_zero_leads_home_from_every_frame(self, digits: str) -> None:
        page = built(digits)
        for frame in page.frames:
            assert frame.destination("0") == at("1")
