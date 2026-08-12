"""What readers have been looking at, as pages a reader can look at.

Both are menus rather than tables: every row is a page number, so every row is
somewhere to go. A list of what other people have been reading that you cannot
follow is a list that has been written at you.
"""

from datetime import UTC, datetime, timedelta

from sextile.addressing import PageAddress
from sextile.page import Page
from sextile.readership import popular_page, recent_page
from sextile.visits import Visit

NOON = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)

NAMES = {"1": "Main menu", "3": "Find a place", "321333": "Trondheim"}


def describe(address: PageAddress) -> str:
    return NAMES.get(address.digits, "")


def text_of(page: Page) -> str:
    found = page.frame(0)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


def visit(page: str, *, ago: timedelta = timedelta(), times: int = 1) -> Visit:
    return Visit(page=PageAddress(page), at=NOON - ago, times=times)


class TestLatelyRead:
    def test_every_row_is_somewhere_to_go(self) -> None:
        page = recent_page(
            address=PageAddress("96"),
            visits=[visit("3"), visit("1")],
            describe=describe,
            home=PageAddress("1"),
            now=NOON,
        )
        found = page.frame(0)
        assert found is not None
        assert found.destination("1") == PageAddress("3")
        assert found.destination("2") == PageAddress("1")

    def test_it_says_how_long_ago_in_plain_words(self) -> None:
        page = recent_page(
            address=PageAddress("96"),
            visits=[
                visit("1", ago=timedelta(seconds=20)),
                visit("3", ago=timedelta(hours=2)),
                visit("321333", ago=timedelta(days=3)),
            ],
            describe=describe,
            home=PageAddress("1"),
            now=NOON,
        )
        shown = text_of(page)
        assert "just now" in shown
        assert "2 hours ago" in shown
        assert "3 days ago" in shown

    def test_one_of_something_is_singular(self) -> None:
        page = recent_page(
            address=PageAddress("96"),
            visits=[visit("1", ago=timedelta(hours=1))],
            describe=describe,
            home=PageAddress("1"),
            now=NOON,
        )
        assert "1 hour ago" in text_of(page)

    def test_a_page_the_service_will_not_name_is_left_off(self) -> None:
        #  A log is a record of what was fetched and a menu is an offer, so the
        #  two are not the same list: a number that answered last week and does
        #  not answer now belongs in one and not the other.
        page = recent_page(
            address=PageAddress("96"),
            visits=[visit("9999"), visit("1")],
            describe=describe,
            home=PageAddress("1"),
            now=NOON,
        )
        found = page.frame(0)
        assert found is not None
        assert found.destination("1") == PageAddress("1")

    def test_nothing_read_yet_says_so(self) -> None:
        #  Rather than an empty frame, which on a service that answers slowly
        #  is indistinguishable from a fault.
        page = recent_page(
            address=PageAddress("96"),
            visits=[],
            describe=describe,
            home=PageAddress("1"),
            now=NOON,
        )
        assert "Nothing has been read yet." in text_of(page)


class TestMostRead:
    def test_it_says_how_often(self) -> None:
        page = popular_page(
            address=PageAddress("97"),
            visits=[visit("1", times=12), visit("3", times=1)],
            describe=describe,
            home=PageAddress("1"),
        )
        shown = text_of(page)
        assert "read 12 times" in shown
        assert "read once" in shown

    def test_and_the_number_that_fetches_each(self) -> None:
        page = popular_page(
            address=PageAddress("97"),
            visits=[visit("321333", times=4)],
            describe=describe,
            home=PageAddress("1"),
        )
        assert "*321333#" in text_of(page)
