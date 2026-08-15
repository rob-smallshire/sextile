"""The one-call page shapes, built on `PageLayout`.

Each of these is the commonest kind of Viewdata page said in a single call: a
notice, a menu, some prose. They take the request the page answers, so the
title, the way home and the page number default from it as they do for the
layout underneath.
"""

from sextile.application import Sextile
from sextile.declarations import PageRoute
from sextile.formatting import MenuItem
from sextile.layout import Shortcut
from sextile.page import Page, PageAddress, PageFrame
from sextile.pages import farewell_page, menu_page, notice_page, prose_page
from sextile.testing import request_for, text_of
from sextile.viewdata.canvas import Canvas

_APP = Sextile()


async def _nothing(request: object, **fields: object) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))


def _titled(name: str, title: str, number: str = "1") -> Sextile:
    return Sextile(pages=[PageRoute(number, _nothing, name=name, title=title)])


def footer_of(page: Page, index: int = 0) -> str:
    return text_of(page, index).splitlines()[-1]


class TestNoticePage:
    def test_it_says_its_lines(self) -> None:
        page = notice_page(request_for(_APP), "Line one.", "Line two.")
        shown = text_of(page)
        assert "Line one." in shown
        assert "Line two." in shown

    def test_its_header_comes_from_the_registration(self) -> None:
        app = _titled("now", "The time now", "2")
        page = notice_page(request_for(app, "2"), "It is noon.")
        assert "THE TIME NOW" in text_of(page).splitlines()[0]

    def test_a_given_title_is_used_instead(self) -> None:
        page = notice_page(request_for(_APP), "x", title="SPECIAL")
        assert "SPECIAL" in text_of(page).splitlines()[0]

    def test_it_offers_the_way_home_by_default(self) -> None:
        page = notice_page(request_for(_APP), "x")
        found = page.frame(0)
        assert found is not None
        assert found.destination("0") == PageAddress("1")
        assert "0 index" in footer_of(page)

    def test_it_can_offer_no_way_home(self) -> None:
        page = notice_page(request_for(_APP), "x", home=None)
        found = page.frame(0)
        assert found is not None
        assert found.destination("0") is None

    def test_it_can_ring_off(self) -> None:
        assert notice_page(request_for(_APP), "Goodbye.", hang_up=True).hang_up

    def test_a_shortcut_is_offered_on_the_frame(self) -> None:
        page = notice_page(
            request_for(_APP),
            "x",
            shortcuts=[Shortcut(key="R", destination=PageAddress("7"), label="reply")],
        )
        found = page.frame(0)
        assert found is not None
        assert found.destination("R") == PageAddress("7")


def _items(count: int) -> list[MenuItem]:
    return [MenuItem(f"Item {n}", f"detail {n}", PageAddress(f"8{n}")) for n in range(count)]


class TestMenuPage:
    def test_it_numbers_the_entries(self) -> None:
        page = menu_page(request_for(_APP, "8"), items=_items(3))
        found = page.frame(0)
        assert found is not None
        assert found.destination("1") == PageAddress("80")
        assert found.destination("3") == PageAddress("82")

    def test_nine_to_a_frame(self) -> None:
        page = menu_page(request_for(_APP, "8"), items=_items(12))
        assert len(page.frames) == 2

    def test_a_preamble_is_shown_on_the_first_frame_only(self) -> None:
        page = menu_page(
            request_for(_APP, "8"), items=_items(12), preamble=("Everything here.",)
        )
        assert "Everything here." in text_of(page, 0)
        assert "Everything here." not in text_of(page, 1)

    def test_an_empty_menu_says_why(self) -> None:
        page = menu_page(request_for(_APP), items=[], empty="Nothing yet.")
        assert "Nothing yet." in text_of(page)

    def test_its_header_comes_from_the_registration(self) -> None:
        app = _titled("posts", "Latest posts", "8")
        page = menu_page(request_for(app, "8"), items=_items(1))
        assert "LATEST POSTS" in text_of(page).splitlines()[0]


class TestMenuItem:
    def test_it_carries_a_registered_page_s_words(self) -> None:
        app = _titled("news", "The news")
        item = app.menu_item("news")
        assert item.text == "The news"
        assert item.destination == PageAddress("1")

    def test_an_unregistered_name_is_refused(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="not a page"):
            _APP.menu_item("nowhere")


class TestProsePage:
    def test_it_shows_its_paragraphs(self) -> None:
        page = prose_page(request_for(_APP), "First para.", "Second para.")
        shown = text_of(page)
        assert "First para." in shown
        assert "Second para." in shown

    def test_its_header_comes_from_the_registration(self) -> None:
        app = _titled("about", "About this")
        page = prose_page(request_for(app, "1"), "Something.")
        assert "ABOUT THIS" in text_of(page).splitlines()[0]


class TestFarewellPage:
    def test_the_title_heads_it_and_the_lines_follow(self) -> None:
        page = farewell_page(
            request_for(_APP), "GOODBYE", "Thank you for calling.", "", "Ring off."
        )
        rows = text_of(page).splitlines()
        assert rows[0].strip() == "GOODBYE"
        assert "Thank you for calling." in rows[2]
        assert "Ring off." in rows[4]

    def test_it_offers_no_keys(self) -> None:
        #  A footer naming the index would mislead on a page there is no coming
        #  back from.
        found = farewell_page(request_for(_APP), "GOODBYE", "Bye.").frame(0)
        assert found is not None
        assert not found.choices
        assert not found.moves

    def test_it_ends_the_call_by_default(self) -> None:
        assert farewell_page(request_for(_APP), "GOODBYE").hang_up

    def test_but_may_be_shown_without_dropping_the_line(self) -> None:
        assert not farewell_page(request_for(_APP), "RINGING OFF", hang_up=False).hang_up
