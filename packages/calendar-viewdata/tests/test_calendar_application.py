"""A calendar as a Viewdata service.

These tests are here for two reasons. One is the ordinary one: the service
should work. The other is that this application exists to hold the framework to
its claim -- if a page here ever needs something the framework offers only
because a forum wanted it, the seam has moved and this is where it shows.
"""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta

import pytest

from calendar_viewdata import build_application
from sextile import Arrival, Page, PageAddress, Sextile, UnknownPageError

#: A Sunday, so a week boundary falls where it can be seen.
WHEN = datetime(2026, 8, 2, 14, 30, 15, tzinfo=UTC)


@pytest.fixture
async def app() -> AsyncIterator[Sextile]:
    service = build_application(now=lambda: WHEN)
    await service.startup()
    yield service
    await service.shutdown()


async def page_at(app: Sextile, digits: str, arrival: Arrival | None = None) -> Page:
    #  `ask` assembles the request as a session would -- with what the service
    #  holds, and the service itself -- so a test need not remember either.
    page = await app.ask(digits, arrival=arrival)
    assert page is not None, f"*{digits}# is not a page here"
    return page


def text_of(page: Page, index: int = 0) -> str:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


class TestThePages:
    @pytest.mark.parametrize(
        "digits", ["1", "2", "3", "3220260802", "4", "4220260802", "9", "90"]
    )
    async def test_every_page_number_is_answered(
        self, digits: str, app: Sextile
    ) -> None:
        assert await app.ask(digits) is not None

    @pytest.mark.parametrize("digits", ["5", "6", "0", "33", "3220261301"])
    async def test_a_number_the_service_has_not_got_is_not_answered(
        self, digits: str, app: Sextile
    ) -> None:
        assert await app.ask(digits) is None

    async def test_the_index_says_what_day_it_is(self, app: Sextile) -> None:
        assert "Sunday 02 August 2026" in text_of(await page_at(app, "1"))

    async def test_the_time_is_shown_to_the_second(self, app: Sextile) -> None:
        assert "14:30:15" in text_of(await page_at(app, "2"))

    async def test_a_month_is_drawn_as_a_grid(self, app: Sextile) -> None:
        shown = text_of(await page_at(app, "3"))
        assert "AUGUST 2026" in shown
        #  August 2026 begins on a Saturday and has 31 days.
        assert "31" in shown
        assert "MO  TU  WE  TH  FR  SA  SU" in shown


class TestMovingAboutTheYear:
    #  A month offers the months either side, which is what the horizontal keys
    #  are for. Nothing about that is calendar-specific -- it is the same axis
    #  the forum uses for the posts either side of one.

    async def test_a_month_offers_the_one_before_and_the_one_after(
        self, app: Sextile
    ) -> None:
        page = await page_at(app, "3220260802")
        assert page.frames[0].destination("A") == PageAddress("3220260701")
        assert page.frames[0].destination("D") == PageAddress("3220260901")

    async def test_stepping_back_past_january_lands_in_december(
        self, app: Sextile
    ) -> None:
        page = await page_at(app, "3220260115")
        assert page.frames[0].destination("A") == PageAddress("3220251201")

    async def test_stepping_on_past_december_lands_in_january(
        self, app: Sextile
    ) -> None:
        page = await page_at(app, "3220261215")
        assert page.frames[0].destination("D") == PageAddress("3220270101")

    async def test_a_day_leads_to_its_own_month(self, app: Sextile) -> None:
        page = await page_at(app, "4220260802")
        assert page.frames[0].destination("1") == PageAddress("3220260802")


class TestTheDaysToCome:
    async def test_the_menu_begins_today(self, app: Sextile) -> None:
        page = await page_at(app, "4")
        assert page.destinations[0] == PageAddress("4220260802")

    async def test_it_runs_across_several_frames(self, app: Sextile) -> None:
        #  Twenty-eight days will not fit nine to a frame.
        assert len((await page_at(app, "4")).frames) == 4

    async def test_the_sequence_runs_on_across_frames(self, app: Sextile) -> None:
        page = await page_at(app, "4")
        assert page.destinations[9] == PageAddress("4220260811")

    async def test_a_day_reached_by_number_offers_no_neighbours(
        self, app: Sextile
    ) -> None:
        page = await page_at(app, "4220260802")
        assert page.frames[0].destination("D") is None

    async def test_a_day_reached_through_the_menu_offers_them(
        self, app: Sextile
    ) -> None:
        page = await page_at(
            app,
            "4220260802",
            Arrival(preceding=PageAddress("4220260801"), following=PageAddress("4220260803")),
        )
        assert page.frames[0].destination("D") == PageAddress("4220260803")
        assert page.frames[0].destination("A") == PageAddress("4220260801")


class TestSayingWhenThingsAre:
    @pytest.mark.parametrize(
        ("day", "expected"),
        [
            (date(2026, 8, 2), "today"),
            (date(2026, 8, 3), "tomorrow"),
            (date(2026, 8, 1), "yesterday"),
            (date(2026, 8, 12), "in 10 days"),
            (date(2026, 7, 23), "10 days ago"),
        ],
    )
    async def test_a_day_says_how_far_off_it_is(
        self, day: date, expected: str, app: Sextile
    ) -> None:
        page = await page_at(app, f"42{day:%Y%m%d}")
        assert expected in text_of(page)

    async def test_a_day_says_where_it_falls_in_the_year(
        self, app: Sextile
    ) -> None:
        shown = text_of(await page_at(app, "4220260802"))
        assert "Day 214 of 365" in shown
        assert "Week 31" in shown

    async def test_a_leap_year_has_a_day_more(self, app: Sextile) -> None:
        assert "of 366" in text_of(await page_at(app, "4220240301"))


class TestNamedJumps:
    @pytest.mark.parametrize(
        ("keyword", "digits"),
        [("MAIN", "1"), ("NOW", "2"), ("TIME", "2"), ("MONTH", "3"), ("BYE", "90")],
    )
    def test_a_keyword_names_a_page(
        self, keyword: str, digits: str, app: Sextile
    ) -> None:
        assert app.resolve(keyword) == PageAddress(digits)

    def test_a_word_that_is_no_keyword_names_nothing(self, app: Sextile) -> None:
        with pytest.raises(UnknownPageError):
            app.resolve("BANANA")


class TestRingingOff:
    async def test_the_goodbye_page_drops_the_line(self, app: Sextile) -> None:
        assert (await page_at(app, "90")).hang_up

    async def test_no_other_page_does(self, app: Sextile) -> None:
        for digits in ["1", "2", "3", "4", "9"]:
            assert not (await page_at(app, digits)).hang_up


class TestTheClock:
    async def test_the_service_reads_the_clock_each_time_it_is_asked(self) -> None:
        #  Which is what makes `*09#` -- fetch this page afresh -- mean
        #  something on the page showing the time.
        moments = iter([WHEN, WHEN + timedelta(hours=1)])
        app = build_application(now=lambda: next(moments))
        await app.startup()
        first = text_of(await page_at(app, "2"))
        second = text_of(await page_at(app, "2"))
        assert "14:30:15" in first
        assert "15:30:15" in second


class TestEveryPageOffersTheWayBack:
    async def test_zero_returns_to_the_index(self, app: Sextile) -> None:
        for digits in ["1", "2", "3", "3220260802", "4", "4220260802", "9"]:
            page = await page_at(app, digits)
            for frame in page.frames:
                assert frame.destination("0") == PageAddress("1")

    async def test_except_from_the_page_that_rings_off(
        self, app: Sextile
    ) -> None:
        #  There is no coming back from it, so a key saying otherwise would do
        #  nothing -- and a frame names only the keys that do something.
        page = await page_at(app, "90")
        assert page.frames[0].choices == {}


class TestThePagesThatComeFree:
    """Two framework pages, mapped in with three lines each.

    They are here as much to show what a service gets for nothing as to be
    useful: the calendar wrote neither of them.
    """

    async def test_where_you_have_been(self, app: Sextile) -> None:
        page_shown = await page_at(app, "92")
        assert "WHERE YOU HAVE BEEN" in text_of(page_shown)

    async def test_every_page(self, app: Sextile) -> None:
        shown = text_of(await page_at(app, "93"))
        assert "The days to come" in shown
        assert "*42<day>#" in shown

    async def test_the_pages_are_titled_where_they_are_written(
        self, app: Sextile
    ) -> None:
        assert app.describe(PageAddress("4")) == "The days to come"

    async def test_the_words_you_can_key(self, app: Sextile) -> None:
        shown = text_of(await page_at(app, "94"))
        assert "*MONTH#" in shown
        assert "This month" in shown

    async def test_the_word_list_is_generated_and_cannot_drift(
        self, app: Sextile
    ) -> None:
        shown = text_of(await page_at(app, "94"))
        for word in app.keywords():
            assert f"*{word}#" in shown

    @pytest.mark.parametrize("keyword", ["HISTORY", "PAGES"])
    def test_their_keywords_are_declared_beside_them(
        self, keyword: str, app: Sextile
    ) -> None:
        assert app.resolve(keyword) is not None
