"""The words a reader can key in place of a page number.

A third framework page in the same shape as the other two: built here, mapped
into a service's numbering or not offered at all. What it lists is generated
from the aliases, so it cannot drift from what the service actually answers --
which is exactly what a hand-written list of keywords in a help page does.
"""

from sextile.application import Sextile
from sextile.builtin.names import TITLE, names_page
from sextile.page import Page, PageAddress
from sextile.testing import request_for, text_of

_APP = Sextile()


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


def listed(**named: str) -> Page:
    return names_page(
        request=request_for(_APP, at("94")),
        named={word: at(digits) for word, digits in named.items()},
        label=lambda where: f"page {where}",
    )


class TestWhatItShows:
    def test_a_word_and_where_it_leads(self) -> None:
        shown = text_of(listed(MAIN="1"))
        assert "*MAIN#" in shown
        assert "page 1" in shown

    def test_words_are_listed_alphabetically(self) -> None:
        #  A reader looking for one is looking it up, not browsing.
        shown = text_of(listed(WHO="5", ABOUT="9", MAIN="1"))
        assert shown.index("ABOUT") < shown.index("MAIN") < shown.index("WHO")

    def test_several_words_for_one_page_are_all_shown(self) -> None:
        shown = text_of(listed(MAIN="1", HOME="1", INDEX="1"))
        for word in ("*MAIN#", "*HOME#", "*INDEX#"):
            assert word in shown

    def test_it_is_titled(self) -> None:
        assert TITLE in text_of(listed(MAIN="1"))

    def test_a_service_with_no_words_says_so(self) -> None:
        assert "no words" in text_of(listed()).lower()

    def test_zero_leads_home(self) -> None:
        assert listed(MAIN="1").frames[0].destination("0") == at("1")


class TestLongerLists:
    def build(self, count: int) -> Page:
        return listed(**{f"WORD{number:02d}": "1" for number in range(count)})

    def test_twenty_fit_one_frame(self) -> None:
        assert len(self.build(20).frames) == 1

    def test_more_run_on(self) -> None:
        assert len(self.build(21).frames) == 2

    def test_the_frames_are_walkable(self) -> None:
        page = self.build(21)
        assert "S" in page.frames[0].moves
        assert "#" in page.frames[0].moves
        assert "W" in page.frames[1].moves
