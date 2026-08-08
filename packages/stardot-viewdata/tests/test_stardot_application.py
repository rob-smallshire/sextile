"""Stardot as a Sextile application.

What the service has: a numbering that is not allowed to drift, a set of named
jumps, and a rule that a page with nothing to show says so rather than appearing
to be broken.

Nothing here is about frames, sessions or the wire. Those belong to the
framework, and the framework is tested against a service that is about nothing
in particular, so that neither can quietly come to depend on the other.
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone

import pytest

from sextile import keys
from sextile.addressing import PageAddress, UnknownPageError
from sextile.application import Arrival, PageRequest
from sextile.page import Page
from stardot_viewdata import StardotApplication
from stardot_viewdata.application import MenuItem
from stardot_viewdata.model import Post
from stardot_viewdata.store.repository import Repository

BST = timezone(timedelta(hours=1))


def make_post(post_id: int, *, subject: str = "Re: Head over Heels", **overrides: object) -> Post:
    defaults: dict[str, object] = {
        "topic_id": 33387,
        "forum_id": 53,
        "forum_name": "new projects in development: games",
        "author_id": 10058,
        "author_name": "Iapetus",
        "published": datetime(2026, 8, 2, 21, 20, tzinfo=BST),
        "content_html": "<p>What a great project!</p>",
    }
    defaults.update(overrides)
    when = defaults.pop("published")
    assert isinstance(when, datetime)
    return Post(
        post_id=post_id,
        subject=subject,
        published=when,
        updated=when,
        url=f"https://stardot.org.uk/forums/viewtopic.php?p={post_id}",
        **defaults,  # type: ignore[arg-type]
    )


@pytest.fixture
def repository() -> Iterator[Repository]:
    with Repository.in_memory() as repository:
        for offset in range(25):
            repository.add_post(
                make_post(
                    489000 + offset,
                    subject=f"Re: Topic number {offset}",
                    published=datetime(2026, 8, 2, 9, 0, tzinfo=BST) + timedelta(minutes=offset),
                )
            )
        yield repository


@pytest.fixture
def app(repository: Repository) -> StardotApplication:
    return StardotApplication(repository=repository)


#: How a reader who keyed a number arrived: from nowhere in particular.
BY_NUMBER = Arrival()


async def page_at(app: StardotApplication, digits: str, arrival: Arrival = BY_NUMBER) -> Page:
    """The page at a number, which for a number the service has is always one."""
    page = await app.respond(PageRequest(address=PageAddress(digits), arrival=arrival))
    assert page is not None, f"*{digits}# is not a page here"
    return page


async def what_a_reader_sees(app: StardotApplication, digits: str) -> Page:
    """The page, or the notice shown in its place -- as the session would."""
    page = await app.respond(PageRequest(address=PageAddress(digits)))
    return page if page is not None else await app.not_found(digits)


def bytes_of(page: Page) -> list[bytes]:
    return [page_frame.frame.to_bytes() for page_frame in page.frames]


def text_of(page: Page, index: int = 0) -> str:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


#: Every page the service has.
EVERY_PAGE: list[str] = [
    "0",
    "1",
    "93",
    "94",
    "8",
    "82489000",
    "82999999",
    "7",
    "7233387",
    "3",
    "3220260802",
    "3219811201",
    "4",
    "4253",
    "5",
    "5210058",
    "9",
    "91",
    "90",
]


class TestTheNumbering:
    #  The scheme is Stardot's own and is not allowed to drift: a page number
    #  written on paper in 2026 should still fetch that page.

    @pytest.mark.parametrize("digits", EVERY_PAGE)
    async def test_every_page_number_is_answered(
        self, digits: str, app: StardotApplication
    ) -> None:
        assert await app.respond(PageRequest(address=PageAddress(digits))) is not None

    def test_a_page_number_is_built_from_the_board_s_own_identifier(
        self, app: StardotApplication
    ) -> None:
        assert app.address_for("post", post_id=489493) == PageAddress("82489493")
        assert app.address_for("forum", forum_id=53) == PageAddress("4253")
        assert app.address_for("topic", topic_id=33387) == PageAddress("7233387")
        assert app.address_for("contributor", user_id=10058) == PageAddress("5210058")
        assert app.address_for("day", day=datetime(2026, 8, 2).date()) == PageAddress("3220260802")

    @pytest.mark.parametrize("digits", ["2", "6", "11", "40", "9999"])
    async def test_a_reserved_or_unallocated_number_says_so(
        self, digits: str, app: StardotApplication
    ) -> None:
        assert "NOT a page here" in text_of(await what_a_reader_sees(app, digits))

    @pytest.mark.parametrize("digits", ["8201", "42053"])
    async def test_a_leading_zero_names_no_page(
        self, digits: str, app: StardotApplication
    ) -> None:
        #  Accepting one would give a single page two different numbers.
        assert "NOT a page here" in text_of(await what_a_reader_sees(app, digits))

    def test_the_index_has_one_number_and_not_two(self, app: StardotApplication) -> None:
        #  The bare root names it; <root>0 is not accepted as well.
        assert app.resolve("8") == PageAddress("8")


class TestNamedJumps:
    @pytest.mark.parametrize(
        ("keyword", "digits"),
        [
            ("MAIN", "1"),
            ("INDEX", "1"),
            ("HOME", "1"),
            ("LATEST", "8"),
            ("POSTS", "8"),
            ("DAYS", "3"),
            ("FORUMS", "4"),
            ("WHO", "5"),
            ("TOPICS", "7"),
            ("ABOUT", "9"),
            ("BYE", "90"),
        ],
    )
    def test_a_keyword_names_the_page_it_always_did(
        self, keyword: str, digits: str, app: StardotApplication
    ) -> None:
        assert app.resolve(keyword) == PageAddress(digits)

    def test_a_word_that_is_no_keyword_names_nothing(self, app: StardotApplication) -> None:
        with pytest.raises(UnknownPageError):
            app.resolve("BANANA")


class TestRingingOff:
    async def test_the_logoff_page_drops_the_line(self, app: StardotApplication) -> None:
        assert (await page_at(app, "90")).hang_up

    async def test_every_other_page_does_not(self, app: StardotApplication) -> None:
        assert not (await page_at(app, "1")).hang_up


class TestTheArchiveIsOpenedWhenTheServiceStarts:
    async def test_an_archive_passed_in_is_not_closed(self, repository: Repository) -> None:
        app = StardotApplication(repository=repository)
        await app.startup()
        await app.shutdown()
        assert repository.count_posts() == 25

    async def test_an_archive_of_its_own_is_opened_and_closed(self, tmp_path: object) -> None:
        from pathlib import Path

        assert isinstance(tmp_path, Path)
        app = StardotApplication(tmp_path / "archive.sqlite")
        await app.startup()
        assert app.repository.count_posts() == 0
        await app.shutdown()
        with pytest.raises(RuntimeError):
            _ = app.repository

    def test_asking_before_starting_says_so_rather_than_failing_obscurely(self) -> None:
        with pytest.raises(RuntimeError):
            _ = StardotApplication().repository


class TestSayingWhatIsMissing:
    async def test_a_post_not_held_says_so(self, app: StardotApplication) -> None:
        assert "NOT in the archive" in text_of(await page_at(app, "82999999"))

    async def test_a_day_with_no_posts_says_so(self, app: StardotApplication) -> None:
        assert "NO POSTS" in text_of(await page_at(app, "3219811201")).upper()

    async def test_an_empty_archive_says_so_rather_than_showing_an_empty_menu(self) -> None:
        with Repository.in_memory() as empty:
            app = StardotApplication(repository=empty)
            assert "NO POSTS" in text_of(await page_at(app, "4")).upper()


class TestWhereTheKeysLead:
    async def test_zero_returns_to_the_index_from_everywhere(
        self, app: StardotApplication
    ) -> None:
        #  From everywhere a reader can get lost, which is everywhere except
        #  the two ends: the title frame, which is where they start and which
        #  offers one way on, and the page that rings off.
        ends = {app.home, app.address_for("logoff")}
        for digits in EVERY_PAGE:
            if PageAddress(digits) in ends:
                continue
            page = await page_at(app, digits)
            for page_frame in page.frames:
                assert page_frame.destination("0") == PageAddress("1")

    async def test_the_page_that_rings_off_offers_nothing(
        self, app: StardotApplication
    ) -> None:
        #  The one exception, and the reason for it: a key offering the index
        #  on a page there is no coming back from is a key that does nothing,
        #  and a frame names only the keys that do something.
        page = await page_at(app, "90")
        assert page.frames[0].choices == {}

    async def test_a_post_offers_its_forum_its_author_its_day_and_its_topic(
        self, app: StardotApplication
    ) -> None:
        page = await page_at(app, "82489000")
        first = page.frames[0]
        assert first.destination("1") == PageAddress("4253")
        assert first.destination("2") == PageAddress("5210058")
        assert first.destination("3") == PageAddress("3220260802")
        assert first.destination("4") == PageAddress("7233387")

    async def test_a_menu_offers_the_pages_it_lists(self, app: StardotApplication) -> None:
        page = await page_at(app, "8")
        assert page.destinations[0] == PageAddress("82489024")

    async def test_a_post_reached_by_number_offers_no_neighbours(
        self, app: StardotApplication
    ) -> None:
        page = await page_at(app, "82489001")
        assert page.frames[0].destination(keys.NEXT_ITEM) is None

    async def test_a_post_reached_through_a_menu_offers_them(
        self, app: StardotApplication
    ) -> None:
        page = await page_at(
            app,
            "82489001",
            Arrival(preceding=PageAddress("82489000"), following=PageAddress("82489002")),
        )
        assert page.frames[0].destination(keys.NEXT_ITEM) == PageAddress("82489002")
        assert page.frames[0].destination(keys.PREVIOUS_ITEM) == PageAddress("82489000")


class TestUtc:
    #  Days are London days, because that is where the board's readers are.
    async def test_a_post_is_filed_under_its_london_day(
        self, repository: Repository
    ) -> None:
        repository.add_post(
            make_post(500000, published=datetime(2026, 8, 2, 23, 30, tzinfo=UTC))
        )
        app = StardotApplication(repository=repository)
        page = await page_at(app, "82500000")
        assert page.frames[0].destination("3") == PageAddress("3220260803")


class TestTheServiceNamesItself:
    """The reader dialled Stardot, not the software that serves it.

    These read oddly until you know the history: this service and the framework
    beneath it were one program, so every page that had a name on it had the
    wrong one.
    """

    def test_the_service_knows_what_it_is_called(self, app: StardotApplication) -> None:
        assert app.name == "Stardot"

    async def test_the_index_is_headed_with_it(self, app: StardotApplication) -> None:
        assert "STARDOT" in text_of(await page_at(app, "1"))

    async def test_so_is_the_about_page(self, app: StardotApplication) -> None:
        assert "ABOUT STARDOT" in text_of(await page_at(app, "9"))

    async def test_the_goodbye_thanks_the_reader_for_calling_it(
        self, app: StardotApplication
    ) -> None:
        assert "calling Stardot" in text_of(await page_at(app, "90"))

    @pytest.mark.parametrize("digits", ["1", "9", "90", "82999999"])
    async def test_no_page_a_reader_sees_names_the_framework(
        self, digits: str, app: StardotApplication
    ) -> None:
        #  Except where it is genuinely the subject: the about page credits
        #  what serves it, which is a different thing from being called it.
        shown = text_of(await page_at(app, digits))
        assert "Sextile" not in shown or "Served by Sextile" in shown


class TestTheTitleFrame:
    """What the line opens on: what this is, and the one way in.

    Page 0, which cannot be keyed -- `*0#` is the back command -- so a caller
    arrives on it because the line opened and leaves it by pressing on.
    """

    def test_the_line_opens_on_it(self, app: StardotApplication) -> None:
        assert app.home == PageAddress("0")

    async def test_it_names_the_service(self, app: StardotApplication) -> None:
        assert "STARDOT" in text_of(await page_at(app, "0"))

    async def test_it_shows_no_page_number(self, app: StardotApplication) -> None:
        #  A number a reader cannot key is an instruction that misleads them.
        assert "0a" not in text_of(await page_at(app, "0"))

    async def test_hash_carries_on_to_the_index(self, app: StardotApplication) -> None:
        #  The one key a viewdata reader tries without being told.
        assert (await page_at(app, "0")).follows == PageAddress("1")

    async def test_so_does_the_first_digit(self, app: StardotApplication) -> None:
        page = await page_at(app, "0")
        assert page.frames[0].destination("1") == PageAddress("1")

    async def test_and_nothing_else_does(self, app: StardotApplication) -> None:
        #  There is one way on from here, which is the point of a title frame.
        page = await page_at(app, "0")
        assert set(page.frames[0].choices) == {"1"}

    async def test_it_leaves_the_bottom_rows_clear(self, app: StardotApplication) -> None:
        #  Room for the countdown bar, which has the footer row.
        page = await page_at(app, "0")
        assert page.frames[0].frame.last_written_row() < 22


class TestHowToGetAbout:
    async def test_it_has_a_number_in_the_system_namespace(
        self, app: StardotApplication
    ) -> None:
        assert app.address_for("help") == PageAddress("91")

    @pytest.mark.parametrize("keyword", ["HELP", "GUIDE", "KEYS"])
    def test_a_keyword_reaches_it(self, keyword: str, app: StardotApplication) -> None:
        assert app.resolve(keyword) == PageAddress("91")

    def test_about_is_still_its_own_page(self, app: StardotApplication) -> None:
        #  What the service is, as against how to work it.
        assert app.resolve("ABOUT") == PageAddress("9")

    async def test_the_main_index_offers_it(self, app: StardotApplication) -> None:
        assert PageAddress("91") in (await page_at(app, "1")).destinations

    async def test_it_runs_to_more_than_one_frame(self, app: StardotApplication) -> None:
        assert len((await page_at(app, "91")).frames) == 2

    @pytest.mark.parametrize(
        "keys", ["1-9", "0", "*nnn#", "W", "A", "*0#", "*00#", "*09#", "**", "*90#"]
    )
    async def test_it_names_the_keys_the_service_answers(
        self, keys: str, app: StardotApplication
    ) -> None:
        shown = text_of(await page_at(app, "91")) + text_of(await page_at(app, "91"), 1)
        #  `#` travels as 0x5F, which this grid shows as the `#` the SAA5050 draws.
        assert keys in shown

    async def test_it_points_at_the_generated_lists_rather_than_repeating_them(
        self, app: StardotApplication
    ) -> None:
        #  It used to name half a dozen keywords itself, which is a list that
        #  goes stale the first time one is added. The two pages it now points
        #  at are generated from the registrations and cannot.
        shown = text_of(await page_at(app, "91"), 1)
        assert "*93#" in shown
        assert "*94#" in shown


class TestThePagesSayWhatTheyAre:
    """The words live at the registration, and everything else reads them.

    Before this, a page was named in the menu, again wherever one was listed,
    and again in the guide. Three copies of a name do not stay in step.
    """

    def test_a_menu_item_is_taken_from_the_page_it_offers(
        self, app: StardotApplication
    ) -> None:
        item = MenuItem.for_page(app, "contributors")
        assert item.text == "By contributor"
        assert item.detail == "browse by poster"
        assert item.destination == PageAddress("5")

    def test_asking_for_a_page_that_says_nothing_about_itself(
        self, app: StardotApplication
    ) -> None:
        #  The title frame has no title, deliberately: it cannot be keyed.
        with pytest.raises(ValueError):
            MenuItem.for_page(app, "title")

    async def test_the_main_index_offers_what_the_pages_call_themselves(
        self, app: StardotApplication
    ) -> None:
        page = await page_at(app, "1")
        shown = "\n".join(text_of(page, index) for index in range(len(page.frames)))
        for title in ("Latest posts", "By topic", "By day", "By forum", "By contributor"):
            assert title in shown

    def test_a_page_with_no_field_is_described_by_its_title(
        self, app: StardotApplication
    ) -> None:
        assert app.describe(PageAddress("5")) == "By contributor"

    def test_one_with_a_field_says_which(self, app: StardotApplication) -> None:
        #  "One contributor" is the right title in a list of kinds of page and
        #  the wrong one in a list of pages a reader has been to.
        assert app.describe(PageAddress("5210058")) == "Contributor 10058"

    def test_a_day_is_described_as_a_reader_would_say_it(
        self, app: StardotApplication
    ) -> None:
        assert app.describe(PageAddress("3220260802")) == "SUN 02 AUG 2026"


class TestEveryPage:
    async def test_it_lists_the_pages_with_their_numbers(
        self, app: StardotApplication
    ) -> None:
        shown = text_of(await page_at(app, "93"))
        assert "*5#" in shown
        assert "By contributor" in shown

    async def test_a_number_with_a_field_is_shown_as_one(
        self, app: StardotApplication
    ) -> None:
        assert "*52<user-id>#" in text_of(await page_at(app, "93"))

    async def test_a_page_that_cannot_be_keyed_is_left_off(
        self, app: StardotApplication
    ) -> None:
        #  Only the title frame: `*0#` is the back command, so the number would
        #  be an instruction that misleads. Everything else shown here is
        #  keyable and does something, ringing off included -- this is a
        #  directory of numbers rather than a menu of places to go.
        assert "*0#" not in text_of(await page_at(app, "93"))

    async def test_ringing_off_is_listed_because_it_can_be_keyed(
        self, app: StardotApplication
    ) -> None:
        assert "*90#" in text_of(await page_at(app, "93"))

    @pytest.mark.parametrize("keyword", ["PAGES", "CONTENTS"])
    def test_a_keyword_reaches_it(self, keyword: str, app: StardotApplication) -> None:
        assert app.resolve(keyword) == PageAddress("93")

    def test_every_page_listed_can_be_reached(self, app: StardotApplication) -> None:
        #  A directory that has drifted from the thing it describes is worse
        #  than none, and this one is built from the registrations so it cannot.
        #  Parameterised numbers are shown as patterns, so only the plain ones
        #  can be built and looked up.
        for page in app.pages():
            if "<" not in page.keyed:
                assert app.route(PageAddress(page.keyed)) is not None
