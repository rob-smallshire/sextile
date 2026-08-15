"""What a service is made of, from its own registrations.

The point of it is the pages whose numbers carry a field. Nobody can list every
user on a screen; everybody holding a user number can be told
where to put it, and only the framework knows the patterns well enough to say.
"""

from sextile.application import Sextile
from sextile.builtin.contents import TITLE, contents_page
from sextile.declarations import PageRoute
from sextile.page import Page, PageAddress, PageFrame
from sextile.requests import PageRequest
from sextile.testing import request_for, text_of
from sextile.viewdata.canvas import Canvas

_APP = Sextile()


async def _blank(request: PageRequest) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))


def info(name: str, keyed: str, title: str) -> PageRoute:
    """A registered route as `pages()` hands one back: `keyed` already filled.

    The pattern and handler are what a real registration would carry and what
    the contents page ignores; `keyed` and `title` are what it reads.
    """
    return PageRoute(pattern=keyed, handler=_blank, name=name, title=title, keyed=keyed)


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


def listed(*pages: PageRoute) -> Page:
    return contents_page(request=request_for(_APP, at("93")), pages=pages)


USERS = info(name="users", keyed="5", title="By user")
ONE = info(name="user", keyed="52<user_id>", title="One user")


class TestWhatItShows:
    def test_a_page_and_the_number_that_fetches_it(self) -> None:
        shown = text_of(listed(USERS))
        assert "*5#" in shown
        assert "By user" in shown

    def test_a_field_is_shown_as_a_placeholder_not_enumerated(self) -> None:
        #  The whole idea: one line stands for every user there is.
        assert "*52<user-id>#" in text_of(listed(ONE))

    def test_the_underscore_is_the_character_set_and_not_a_typo(self) -> None:
        #  G0 has no underscore -- 0x5F is `#` -- so transliteration lands on a
        #  hyphen, which happens to read better anyway.
        assert "user_id" not in text_of(listed(ONE))

    def test_the_titles_line_up_in_a_column(self) -> None:
        #  Set against the widest number, so the page reads as two columns.
        rows = text_of(listed(USERS, ONE)).splitlines()
        assert rows[2].index("By user") == rows[3].index("One user")

    def test_it_is_titled(self) -> None:
        assert TITLE in text_of(listed(USERS))

    def test_a_service_advertising_nothing_says_so(self) -> None:
        assert "no pages" in text_of(listed())


class TestLongerServices:
    def build(self, count: int) -> Page:
        return listed(
            *(
                info(name=f"page{number}", keyed=str(number), title=f"Page {number}")
                for number in range(10, 10 + count)
            )
        )

    def test_twenty_fit_one_frame(self) -> None:
        assert len(self.build(20).frames) == 1

    def test_more_run_on(self) -> None:
        assert len(self.build(21).frames) == 2

    def test_the_frames_are_walkable(self) -> None:
        page = self.build(21)
        assert "S" in page.frames[0].moves
        assert "W" in page.frames[1].moves

    def test_zero_leads_home_from_each(self) -> None:
        for frame in self.build(21).frames:
            assert frame.destination("0") == at("1")


class TestTheOrder:
    def test_pages_are_listed_by_number(self) -> None:
        #  Not by the order a service declares them in, which is about how its
        #  source reads.
        rows = text_of(listed(ONE, USERS)).splitlines()
        assert rows[2].index("*5#") >= 0
        assert "By user" in rows[2]
        assert "One user" in rows[3]

    def test_which_puts_a_namespace_next_to_its_members(self) -> None:
        #  Sorting the digits as text does this for free, because that is what a
        #  scheme whose first digit names a namespace already means.
        pages = [
            info(name="post", keyed="82<post_id>", title="One post"),
            info(name="main", keyed="1", title="Main index"),
            info(name="posts", keyed="8", title="Latest posts"),
            info(name="about", keyed="9", title="About"),
        ]
        shown = [row.strip() for row in text_of(listed(*pages)).splitlines() if "*" in row]
        assert [row.split()[0] for row in shown] == ["*1#", "*8#", "*82<post-id>#", "*9#"]


class TestWhatTheseBuiltInPagesAreCalled:
    """A built-in page is headed with what the service registered it as.

    Each of them has a name of its own, and a service that maps one into its
    numbering gives it another when it registers it -- so without this the same
    words are written twice, and the service's copy is the one that shows in
    menus and on the contents page.
    """

    async def test_a_service_s_own_words_are_used(self) -> None:
        app = Sextile()
        app.page("93", name="contents", title="Every page")(app.contents_page)
        assert "EVERY PAGE" in text_of(await _built(app, "93"))

    async def test_and_a_service_that_calls_it_something_else_gets_that(self) -> None:
        app = Sextile()
        app.page("50", name="contents", title="What is here")(app.contents_page)
        shown = text_of(await _built(app, "50"))
        assert "WHAT IS HERE" in shown
        assert TITLE not in shown

    async def test_a_service_that_said_nothing_keeps_the_framework_s_name(self) -> None:
        app = Sextile()
        app.page("50")(app.contents_page)
        assert TITLE in text_of(await _built(app, "50"))


async def _built(app: Sextile, digits: str) -> Page:
    page = await app.fetch(digits)
    assert page is not None
    return page


