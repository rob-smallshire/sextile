"""The one-call page shapes, built on `PageLayout`.

Each of these is the commonest kind of Viewdata page said in a single call: a
notice, a menu, some prose. They take the request the page answers, so the
title, the way home and the page number default from it as they do for the
layout underneath.
"""

from sextile.addressing import PageAddress
from sextile.application import Sextile
from sextile.declarations import PageRoute
from sextile.layout import Shortcut
from sextile.page import Page, PageFrame
from sextile.pages import notice_page
from sextile.testing import request_for
from sextile.viewdata.canvas import Canvas

_APP = Sextile()


async def _nothing(request: object, **fields: object) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))


def _titled(name: str, title: str, number: str = "1") -> Sextile:
    return Sextile(pages=[PageRoute(number, _nothing, name=name, title=title)])


def text_of(page: Page, index: int = 0) -> str:
    characters, _ = page.frames[index].frame.to_grid()
    return "\n".join(characters)


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
            shortcuts=[Shortcut(key="R", destination=PageAddress("7"), says="reply")],
        )
        found = page.frame(0)
        assert found is not None
        assert found.destination("R") == PageAddress("7")
