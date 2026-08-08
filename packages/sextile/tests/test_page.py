"""What an application hands back.

A page is more than a list of frames. Pressing a digit goes somewhere, and where
it goes depends on which frame is showing -- frame b of a menu offers a
different nine choices from frame a. So the choices belong to the frame.

A page does not carry its own number. The address is what was asked for, and the
session already holds it; a page that named itself as well could disagree.
"""

import pytest

from sextile.addressing import PageAddress
from sextile.page import Page, PageFrame
from sextile.viewdata.frame import Frame


def blank() -> Frame:
    return Frame()


def to(digits: str) -> PageAddress:
    return PageAddress(digits)


class TestFrames:
    def test_a_page_must_have_a_frame(self) -> None:
        with pytest.raises(ValueError):
            Page(frames=())

    def test_a_frame_can_be_had_by_index(self) -> None:
        first, second = PageFrame(blank()), PageFrame(blank())
        page = Page(frames=(first, second))
        assert page.frame(1) is second

    def test_there_is_no_frame_beyond_the_last(self) -> None:
        page = Page(frames=(PageFrame(blank()),))
        assert page.frame(1) is None

    def test_there_is_no_frame_before_the_first(self) -> None:
        page = Page(frames=(PageFrame(blank()),))
        assert page.frame(-1) is None


class TestChoices:
    def test_a_key_leads_where_the_frame_says(self) -> None:
        frame = PageFrame(blank(), choices={"1": to("42")})
        assert frame.destination("1") == to("42")

    def test_a_key_the_frame_does_not_offer_leads_nowhere(self) -> None:
        frame = PageFrame(blank(), choices={"1": to("42")})
        assert frame.destination("2") is None

    def test_a_frame_offers_the_keys_that_do_something(self) -> None:
        frame = PageFrame(blank(), choices={"1": to("42")}, moves=frozenset("S"))
        assert frame.offers("1")
        assert frame.offers("S")
        assert not frame.offers("9")

    #  Keyed by character rather than by digit, so a page can offer `N` for next
    #  or `R` for reply without this type changing.
    def test_a_choice_need_not_be_a_digit(self) -> None:
        frame = PageFrame(blank(), choices={"R": to("42")})
        assert frame.destination("R") == to("42")


class TestSequence:
    #  What a menu offered, in the order it offered it: the run of pages the
    #  next and previous keys walk once a reader steps into it.

    def test_the_digits_of_one_frame_are_a_sequence(self) -> None:
        page = Page(
            frames=(PageFrame(blank(), choices={"1": to("821"), "2": to("822")}),),
        )
        assert page.destinations == (to("821"), to("822"))

    def test_the_sequence_runs_on_across_frames(self) -> None:
        page = Page(
            frames=(
                PageFrame(blank(), choices={"1": to("821")}),
                PageFrame(blank(), choices={"1": to("822")}),
            )
        )
        assert page.destinations == (to("821"), to("822"))

    def test_the_way_back_is_not_part_of_the_sequence(self) -> None:
        #  0 is the index on every page, and reading it as the first item of a
        #  run would make `next` mean something different from what was offered.
        page = Page(frames=(PageFrame(blank(), choices={"0": to("1"), "1": to("821")}),))
        assert page.destinations == (to("821"),)

    def test_keys_that_are_not_digits_are_not_part_of_the_sequence(self) -> None:
        page = Page(frames=(PageFrame(blank(), choices={"R": to("83"), "1": to("821")}),))
        assert page.destinations == (to("821"),)

    def test_a_page_offered_twice_appears_once(self) -> None:
        page = Page(
            frames=(
                PageFrame(blank(), choices={"1": to("821")}),
                PageFrame(blank(), choices={"1": to("821")}),
            )
        )
        assert page.destinations == (to("821"),)


class TestRingingOff:
    #  A page has to be able to say goodbye. The framework has no notion of a
    #  logoff page of its own, and should not acquire one: which number means
    #  farewell is the application's affair.

    def test_a_page_stays_connected_by_default(self) -> None:
        assert not Page(frames=(PageFrame(blank()),)).hang_up

    def test_a_page_can_ring_off_after_showing(self) -> None:
        assert Page(frames=(PageFrame(blank()),), hang_up=True).hang_up


class TestReadingOn:
    #  Prestel's `#` meant "next page" in a route as well as "next frame" of a
    #  long one. A page can say where it leads once its frames run out, which is
    #  what makes a title frame or a guide read as a sequence rather than a
    #  dead end.

    def test_a_page_leads_nowhere_by_default(self) -> None:
        assert Page(frames=(PageFrame(blank()),)).follows is None

    def test_a_page_can_say_what_comes_after_it(self) -> None:
        page = Page(frames=(PageFrame(blank()),), follows=to("1"))
        assert page.follows == to("1")
