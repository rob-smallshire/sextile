"""What a service is made of, from its own registrations.

The point of it is the pages whose numbers carry a field. Nobody can list every
contributor on a screen; everybody holding a contributor number can be told
where to put it, and only the framework knows the patterns well enough to say.
"""

from sextile.addressing import PageAddress
from sextile.application import PageInfo
from sextile.contents import TITLE, contents_page
from sextile.page import Page


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


def listed(*pages: PageInfo) -> Page:
    return contents_page(address=at("93"), pages=pages, home=at("1"))


def text_of(page: Page, index: int = 0) -> str:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


CONTRIBUTORS = PageInfo(name="contributors", keyed="5", title="By contributor")
ONE = PageInfo(name="contributor", keyed="52<user_id>", title="One contributor")


class TestWhatItShows:
    def test_a_page_and_the_number_that_fetches_it(self) -> None:
        shown = text_of(listed(CONTRIBUTORS))
        assert "*5#" in shown
        assert "By contributor" in shown

    def test_a_field_is_shown_as_a_placeholder_not_enumerated(self) -> None:
        #  The whole idea: one line stands for every contributor there is.
        assert "*52<user-id>#" in text_of(listed(ONE))

    def test_the_underscore_is_the_character_set_and_not_a_typo(self) -> None:
        #  G0 has no underscore -- 0x5F is `#` -- so transliteration lands on a
        #  hyphen, which happens to read better anyway.
        assert "user_id" not in text_of(listed(ONE))

    def test_the_titles_line_up_in_a_column(self) -> None:
        #  Set against the widest number, so the page reads as two columns.
        rows = text_of(listed(CONTRIBUTORS, ONE)).splitlines()
        assert rows[2].index("By contributor") == rows[3].index("One contributor")

    def test_it_is_titled(self) -> None:
        assert TITLE in text_of(listed(CONTRIBUTORS))

    def test_a_service_advertising_nothing_says_so(self) -> None:
        assert "no pages" in text_of(listed())


class TestLongerServices:
    def build(self, count: int) -> Page:
        return listed(
            *(
                PageInfo(name=f"page{number}", keyed=str(number), title=f"Page {number}")
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
        rows = text_of(listed(ONE, CONTRIBUTORS)).splitlines()
        assert rows[2].index("*5#") >= 0
        assert "By contributor" in rows[2]
        assert "One contributor" in rows[3]

    def test_which_puts_a_namespace_next_to_its_members(self) -> None:
        #  Sorting the digits as text does this for free, because that is what a
        #  scheme whose first digit names a namespace already means.
        pages = [
            PageInfo(name="post", keyed="82<post_id>", title="One post"),
            PageInfo(name="main", keyed="1", title="Main index"),
            PageInfo(name="posts", keyed="8", title="Latest posts"),
            PageInfo(name="about", keyed="9", title="About"),
        ]
        shown = [row.strip() for row in text_of(listed(*pages)).splitlines() if "*" in row]
        assert [row.split()[0] for row in shown] == ["*1#", "*8#", "*82<post-id>#", "*9#"]
