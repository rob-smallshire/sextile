"""What readers have been looking at, as pages a reader can look at.

Both are menus rather than tables: every row is a page number, so every row is
somewhere to go. A list of what other people have been reading that you cannot
follow is a list that has been written at you.
"""

from datetime import UTC, datetime, timedelta

from sextile.addressing import PageAddress
from sextile.application import Sextile
from sextile.page import Page
from sextile.pages.readership import callers_page, popular_page, recent_page
from sextile.testing import request_for
from sextile.visits import Visit

_APP = Sextile()

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
            request=request_for(_APP, "96"),
            visits=[visit("3"), visit("1")],
            describe=describe,
            now=NOON,
        )
        found = page.frame(0)
        assert found is not None
        assert found.destination("1") == PageAddress("3")
        assert found.destination("2") == PageAddress("1")

    def test_it_says_how_long_ago_in_plain_words(self) -> None:
        page = recent_page(
            request=request_for(_APP, "96"),
            visits=[
                visit("1", ago=timedelta(seconds=20)),
                visit("3", ago=timedelta(hours=2)),
                visit("321333", ago=timedelta(days=3)),
            ],
            describe=describe,
            now=NOON,
        )
        shown = text_of(page)
        assert "just now" in shown
        assert "2 hours ago" in shown
        assert "3 days ago" in shown

    def test_one_of_something_is_singular(self) -> None:
        page = recent_page(
            request=request_for(_APP, "96"),
            visits=[visit("1", ago=timedelta(hours=1))],
            describe=describe,
            now=NOON,
        )
        assert "1 hour ago" in text_of(page)

    def test_a_page_the_service_will_not_name_is_left_off(self) -> None:
        #  A log is a record of what was fetched and a menu is an offer, so the
        #  two are not the same list: a number that answered last week and does
        #  not answer now belongs in one and not the other.
        page = recent_page(
            request=request_for(_APP, "96"),
            visits=[visit("9999"), visit("1")],
            describe=describe,
            now=NOON,
        )
        found = page.frame(0)
        assert found is not None
        assert found.destination("1") == PageAddress("1")

    def test_nothing_read_yet_says_so(self) -> None:
        #  Rather than an empty frame, which on a service that answers slowly
        #  is indistinguishable from a fault.
        page = recent_page(
            request=request_for(_APP, "96"),
            visits=[],
            describe=describe,
            now=NOON,
        )
        assert "Nothing has been read yet." in text_of(page)

    def test_more_than_a_frame_holds_goes_on_to_the_next(self) -> None:
        #  A caller asking for twenty gets twenty, nine to a frame like
        #  any other menu. Showing nine and dropping the rest without saying so
        #  would make the limit mean something other than what it says.
        page = recent_page(
            request=request_for(_APP, "96"),
            visits=[visit("1") for _ in range(20)],
            describe=describe,
            now=NOON,
        )
        assert len(page.frames) == 3


class TestMostRead:
    def test_it_says_how_often(self) -> None:
        page = popular_page(
            request=request_for(_APP, "97"),
            visits=[visit("1", times=12), visit("3", times=1)],
            describe=describe,
        )
        shown = text_of(page)
        assert "read 12 times" in shown
        assert "read once" in shown

    def test_and_the_number_that_fetches_each(self) -> None:
        page = popular_page(
            request=request_for(_APP, "97"),
            visits=[visit("321333", times=4)],
            describe=describe,
        )
        assert "*321333#" in text_of(page)


class TestWhoHasCalled:
    """The only figure a service keeps about its readers.

    A count of connections and not of anybody: the log holds a token minted
    per session and nothing else, so the page can say how many and never who
    -- and says as much on itself, since a figure about readers that does not
    say what it counts invites the worst guess.
    """

    def test_a_count_for_every_period(self) -> None:
        shown = text_of(
            callers_page(
                request=request_for(_APP, "98"),
                counts=[("Last 24 hours", 4), ("Last 7 days", 19)],
            )
        )
        assert "Last 24 hours" in shown
        assert "4" in shown
        assert "Last 7 days" in shown
        assert "19" in shown

    def test_the_counts_line_up(self) -> None:
        #  A column of figures a reader can compare at a glance, which is the
        #  whole use of a page like this.
        rows = text_of(
            callers_page(
                request=request_for(_APP, "98"),
                counts=[("Last 24 hours", 4), ("Last 30 days", 1234)],
            )
        ).splitlines()
        first = next(row for row in rows if "Last 24 hours" in row)
        second = next(row for row in rows if "Last 30 days" in row)
        #  Right-aligned, so 4 and 1234 end in the same column whatever their
        #  width -- which is what lets a reader compare them down the page.
        assert len(first.rstrip()) == len(second.rstrip())

    def test_it_says_what_a_caller_is(self) -> None:
        shown = text_of(
            callers_page(
                request=request_for(_APP, "98"),
                counts=[("Last 7 days", 3)],
            )
        )
        assert "never who" in shown

    def test_nobody_at_all_says_so(self) -> None:
        #  Rather than three noughts, which read as a fault on a service that
        #  has only just been switched on.
        shown = text_of(
            callers_page(
                request=request_for(_APP, "98"),
                counts=[("Last 7 days", 0), ("Last 30 days", 0)],
            )
        )
        assert "Nobody has called yet." in shown

    def test_and_nought_goes_home(self) -> None:
        page = callers_page(
            request=request_for(_APP, "98"), counts=[]
        )
        found = page.frame(0)
        assert found is not None
        assert found.destination("0") == PageAddress("1")
