"""Stardot as a Sextile application.

What the service has: a numbering that is not allowed to drift, a set of named
jumps, and a rule that a page with nothing to show says so rather than appearing
to be broken.

Nothing here is about frames, sessions or the wire. Those belong to the
framework, and the framework is tested against a service that is about nothing
in particular, so that neither can quietly come to depend on the other.
"""

from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest

from sextile import (
    Neighbours,
    Page,
    PageAddress,
    PageRoute,
    Sextile,
    UnknownPageError,
    keyed,
    keys,
)
from sextile.testing import request_for
from sextile.viewdata import lettering
from sextile.viewdata.blocks import BLOCKS_ACROSS, BLOCKS_DOWN
from sextile.viewdata.charset import mosaic_pattern
from sextile.viewdata.controls import Control
from sextile.viewdata.font import load_font
from sextile.viewdata.frame import COLUMNS, Frame
from sextile.viewdata.lettering import Spacing
from stardot_viewdata import PAGES, build_application
from stardot_viewdata.handlers import ARCHIVE, SERVICE_NAME
from stardot_viewdata.model import Post
from stardot_viewdata.post_page import CONVENTIONAL_NEXT_FRAME_KEY
from stardot_viewdata.store.repository import Repository
from stardot_viewdata.title_frame import (
    BANNER_FACE,
    BANNER_ROW,
    SERVICE_KIND,
    SUBTITLE_FACE,
    SUBTITLE_ROW,
)

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


def _blocks_of(frame: Frame, row: int, rows: int) -> list[list[bool]]:
    """The mosaic blocks a frame carries over some rows, as a bitmap."""
    picture = [[False] * (COLUMNS * BLOCKS_ACROSS) for _ in range(rows * BLOCKS_DOWN)]
    for offset in range(rows):
        for column in range(COLUMNS):
            if frame.is_attribute(row + offset, column):
                continue
            pattern = mosaic_pattern(frame.cell(row + offset, column))
            for bit, (across, down) in enumerate(
                ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2))
            ):
                if pattern >> bit & 1:
                    picture[offset * BLOCKS_DOWN + down][
                        column * BLOCKS_ACROSS + across
                    ] = True
    return picture


def _ink_of(picture: list[list[bool]]) -> list[list[bool]]:
    """The same bitmap cropped to what it lights, so two can be compared."""
    lit = [
        (y, x)
        for y, line in enumerate(picture)
        for x, block in enumerate(line)
        if block
    ]
    top, bottom = min(y for y, _ in lit), max(y for y, _ in lit)
    left, right = min(x for _, x in lit), max(x for _, x in lit)
    return [line[left : right + 1] for line in picture[top : bottom + 1]]


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
async def app(repository: Repository) -> AsyncIterator[Sextile]:
    service = build_application(repository=repository)
    await service.startup()
    yield service
    await service.shutdown()


def _moved(name: str, **changed: object) -> tuple[PageRoute, ...]:
    """The service's pages, with one of them declared differently.

    What the old tests did by subclassing and overriding a method. A service is
    a list, so a variant of one is a variant of the list.
    """
    return tuple(
        PageRoute(**{**vars(route), **changed}) if route.name == name else route
        for route in PAGES
    )


#: How a reader who keyed a number arrived: from nowhere in particular.
BY_NUMBER = Neighbours()


async def page_at(app: Sextile, digits: str, neighbours: Neighbours = BY_NUMBER) -> Page:
    """The page at a number, which for a number the service has is always one."""
    page = await app.ask(digits, neighbours=neighbours)
    assert page is not None, f"*{digits}# is not a page here"
    return page


async def what_a_reader_sees(app: Sextile, digits: str) -> Page:
    """The page, or the notice shown in its place -- as the session would."""
    page = await app.ask(digits)
    if page is not None:
        return page
    return await app.not_found(request_for(app, app.index), digits)


def bytes_of(page: Page) -> list[bytes]:
    return [page_frame.frame.to_bytes() for page_frame in page.frames]


def text_of(page: Page, index: int = 0) -> str:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


def all_text_of(page: Page) -> str:
    """Every frame of a page, for something said on whichever frame has room."""
    return "\n".join(text_of(page, index) for index in range(len(page.frames)))


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
        self, digits: str, app: Sextile
    ) -> None:
        assert await app.ask(digits) is not None

    def test_a_page_number_is_built_from_the_board_s_own_identifier(
        self, app: Sextile
    ) -> None:
        assert app.address_for("post", post_id=489493) == PageAddress("82489493")
        assert app.address_for("forum", forum_id=53) == PageAddress("4253")
        assert app.address_for("topic", topic_id=33387) == PageAddress("7233387")
        assert app.address_for("contributor", user_id=10058) == PageAddress("5210058")
        assert app.address_for("day", day=datetime(2026, 8, 2).date()) == PageAddress("3220260802")

    @pytest.mark.parametrize("digits", ["2", "6", "11", "40", "9999"])
    async def test_a_reserved_or_unallocated_number_says_so(
        self, digits: str, app: Sextile
    ) -> None:
        assert "NOT a page here" in text_of(await what_a_reader_sees(app, digits))

    @pytest.mark.parametrize("digits", ["8201", "42053"])
    async def test_a_leading_zero_names_no_page(
        self, digits: str, app: Sextile
    ) -> None:
        #  Accepting one would give a single page two different numbers.
        assert "NOT a page here" in text_of(await what_a_reader_sees(app, digits))

    def test_the_index_has_one_number_and_not_two(self, app: Sextile) -> None:
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
        self, keyword: str, digits: str, app: Sextile
    ) -> None:
        assert app.resolve(keyword) == PageAddress(digits)

    def test_a_word_that_is_no_keyword_names_nothing(self, app: Sextile) -> None:
        with pytest.raises(UnknownPageError):
            app.resolve("BANANA")


class TestRingingOff:
    async def test_the_logoff_page_drops_the_line(self, app: Sextile) -> None:
        assert (await page_at(app, "90")).hang_up

    async def test_every_other_page_does_not(self, app: Sextile) -> None:
        assert not (await page_at(app, "1")).hang_up


class TestTheArchiveIsOpenedWhenTheServiceStarts:
    """Whose archive it is, said once in the lifespan rather than by a flag.

    It used to be two booleans on the application. Now the lifespan either
    opens one and closes it, or is handed one and leaves it alone, and the
    difference is a branch you can read.
    """

    async def test_an_archive_passed_in_is_not_closed(self, repository: Repository) -> None:
        service = build_application(repository=repository)
        await service.startup()
        await service.shutdown()
        assert repository.count_posts() == 25

    async def test_an_archive_of_its_own_is_opened_and_closed(
        self, tmp_path: Path
    ) -> None:
        service = build_application(tmp_path / "archive.sqlite")
        await service.startup()
        held = service.state[ARCHIVE]
        assert held.count_posts() == 0
        await service.shutdown()
        assert ARCHIVE not in service.state

    async def test_asking_before_starting_says_so_rather_than_failing_obscurely(
        self,
    ) -> None:
        #  A page reached before the lifespan has run says which thing is
        #  missing, rather than failing somewhere inside SQLite.
        service = build_application()
        with pytest.raises(KeyError, match="archive"):
            await service.ask("1")


class TestSayingWhatIsMissing:
    async def test_a_post_not_held_says_so(self, app: Sextile) -> None:
        assert "NOT in the archive" in text_of(await page_at(app, "82999999"))

    async def test_a_day_with_no_posts_says_so(self, app: Sextile) -> None:
        assert "NO POSTS" in text_of(await page_at(app, "3219811201")).upper()

    async def test_an_empty_archive_says_so_rather_than_showing_an_empty_menu(self) -> None:
        with Repository.in_memory() as empty:
            service = build_application(repository=empty)
            await service.startup()
            assert "NO POSTS" in text_of(await page_at(service, "4")).upper()


class TestWhereTheKeysLead:
    async def test_zero_returns_to_the_index_from_everywhere(
        self, app: Sextile
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
        self, app: Sextile
    ) -> None:
        #  The one exception, and the reason for it: a key offering the index
        #  on a page there is no coming back from is a key that does nothing,
        #  and a frame names only the keys that do something.
        page = await page_at(app, "90")
        assert page.frames[0].choices == {}

    async def test_a_post_offers_its_forum_its_author_its_day_and_its_topic(
        self, app: Sextile
    ) -> None:
        page = await page_at(app, "82489000")
        first = page.frames[0]
        assert first.destination("1") == PageAddress("4253")
        assert first.destination("2") == PageAddress("5210058")
        assert first.destination("3") == PageAddress("3220260802")
        assert first.destination("4") == PageAddress("7233387")

    async def test_a_menu_offers_the_pages_it_lists(self, app: Sextile) -> None:
        page = await page_at(app, "8")
        assert page.destinations[0] == PageAddress("82489024")

    async def test_a_post_reached_by_number_offers_no_neighbours(
        self, app: Sextile
    ) -> None:
        page = await page_at(app, "82489001")
        assert page.frames[0].destination(keys.NEXT_ITEM) is None

    async def test_a_post_reached_through_a_menu_offers_them(
        self, app: Sextile
    ) -> None:
        page = await page_at(
            app,
            "82489001",
            Neighbours(previous=PageAddress("82489000"), next=PageAddress("82489002")),
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
        service = build_application(repository=repository)
        await service.startup()
        page = await page_at(service, "82500000")
        assert page.frames[0].destination("3") == PageAddress("3220260803")


class TestTheServiceNamesItself:
    """The reader dialled Stardot, not the software that serves it.

    These read oddly until you know the history: this service and the framework
    beneath it were one program, so every page that had a name on it had the
    wrong one.
    """

    def test_the_service_knows_what_it_is_called(self, app: Sextile) -> None:
        assert app.name == "Stardot"

    async def test_the_index_is_headed_with_it(self, app: Sextile) -> None:
        assert "STARDOT" in text_of(await page_at(app, "1"))

    async def test_so_is_the_about_page(self, app: Sextile) -> None:
        assert "ABOUT STARDOT" in text_of(await page_at(app, "9"))

    async def test_the_goodbye_thanks_the_reader_for_calling_it(
        self, app: Sextile
    ) -> None:
        assert "calling Stardot" in text_of(await page_at(app, "90"))

    @pytest.mark.parametrize("digits", ["1", "9", "90", "82999999"])
    async def test_no_page_a_reader_sees_names_the_framework(
        self, digits: str, app: Sextile
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

    def test_the_line_opens_on_it(self, app: Sextile) -> None:
        assert app.home == PageAddress("0")

    async def test_it_names_the_service_in_letters_made_of_blocks(
        self, app: Sextile
    ) -> None:
        #  Double height gave two rows and one size. The name is now set in a
        #  mosaic face, so what the frame carries is the same blocks the font
        #  produces -- compared against the font rather than a transcription of
        #  it, and by the shape of the ink rather than the cells it lands in,
        #  since where the letters sit is the composition's business.
        frame = (await page_at(app, "0")).frames[0].frame
        face = load_font(BANNER_FACE)
        wanted = lettering.bitmap(SERVICE_NAME, face, spacing=Spacing.KERNED)
        drawn = _blocks_of(frame, BANNER_ROW, lettering.rows_for(face))
        assert _ink_of(drawn) == _ink_of(wanted)

    async def test_on_a_stripe_of_colour_across_the_frame(
        self, app: Sextile
    ) -> None:
        #  Which the letters do not know about: the stripe is declared once and
        #  the lettering is drawn on it.
        frame = (await page_at(app, "0")).frames[0].frame
        rows = range(BANNER_ROW, BANNER_ROW + 3)
        assert all(
            any(frame.cell(row, column) == Control.NEW_BACKGROUND for column in range(4))
            for row in rows
        )
        #  Nothing turns it off again, so it runs to the end of every row.
        assert not any(
            frame.cell(row, column) == Control.BLACK_BACKGROUND
            for row in rows
            for column in range(COLUMNS)
        )

    async def test_and_says_what_it_is_underneath_in_the_same_way(
        self, app: Sextile
    ) -> None:
        frame = (await page_at(app, "0")).frames[0].frame
        face = load_font(SUBTITLE_FACE)
        wanted = lettering.bitmap(SERVICE_KIND, face, spacing=Spacing.KERNED)
        drawn = _blocks_of(frame, SUBTITLE_ROW, lettering.rows_for(face))
        assert _ink_of(drawn) == _ink_of(wanted)

    async def test_with_a_stripe_a_third_of_its_height_behind_it(
        self, app: Sextile
    ) -> None:
        #  A row of colour behind a word three rows tall, so the band runs
        #  through its waist and the rest of it is on the frame's own black.
        frame = (await page_at(app, "0")).frames[0].frame
        striped = [
            row
            for row in range(SUBTITLE_ROW, SUBTITLE_ROW + 3)
            if any(
                frame.cell(row, column) == Control.NEW_BACKGROUND
                for column in range(COLUMNS)
            )
        ]
        assert striped == [SUBTITLE_ROW + 1]

    async def test_and_the_stripe_is_no_wider_than_the_word(
        self, app: Sextile
    ) -> None:
        #  Unlike the name above it, which has a stripe across the frame: this
        #  one is fitted, which is what makes it read as a second line.
        frame = (await page_at(app, "0")).frames[0].frame
        row = SUBTITLE_ROW + 1
        assert any(
            frame.cell(row, column) == Control.BLACK_BACKGROUND
            for column in range(COLUMNS)
        )

    async def test_it_shows_no_page_number(self, app: Sextile) -> None:
        #  A number a reader cannot key is an instruction that misleads them.
        assert "0a" not in text_of(await page_at(app, "0"))

    async def test_hash_carries_on_to_the_index(self, app: Sextile) -> None:
        #  The one key a viewdata reader tries without being told.
        assert (await page_at(app, "0")).follows == PageAddress("1")

    async def test_so_does_the_first_digit(self, app: Sextile) -> None:
        page = await page_at(app, "0")
        assert page.frames[0].destination("1") == PageAddress("1")

    async def test_and_nothing_else_does(self, app: Sextile) -> None:
        #  There is one way on from here, which is the point of a title frame.
        page = await page_at(app, "0")
        assert set(page.frames[0].choices) == {"1"}

    async def test_it_leaves_the_bottom_rows_clear(self, app: Sextile) -> None:
        #  Room for the countdown bar, which has the footer row.
        page = await page_at(app, "0")
        assert page.frames[0].frame.last_written_row() < 22


class TestHowToGetAbout:
    async def test_it_has_a_number_in_the_system_namespace(
        self, app: Sextile
    ) -> None:
        assert app.address_for("help") == PageAddress("91")

    @pytest.mark.parametrize("keyword", ["HELP", "GUIDE", "KEYS"])
    def test_a_keyword_reaches_it(self, keyword: str, app: Sextile) -> None:
        assert app.resolve(keyword) == PageAddress("91")

    def test_about_is_still_its_own_page(self, app: Sextile) -> None:
        #  What the service is, as against how to work it.
        assert app.resolve("ABOUT") == PageAddress("9")

    async def test_the_main_index_offers_it(self, app: Sextile) -> None:
        assert PageAddress("91") in (await page_at(app, "1")).destinations

    async def test_it_runs_to_more_than_one_frame(self, app: Sextile) -> None:
        #  The keys with the compass under them, then the star requests.
        assert len((await page_at(app, "91")).frames) == 2

    async def test_the_first_frame_carries_the_compass_under_its_words(
        self, app: Sextile
    ) -> None:
        #  Drawn rather than described, and by the framework: the four keys it
        #  shows are the framework's, not this service's. Under the keys the
        #  frame lists, because the words are what a reader came for and the
        #  picture is what they will remember.
        page = await page_at(app, "91")
        rows = text_of(page).splitlines()
        assert any("choose from a menu" in row for row in rows)
        spoken = max(index for index, row in enumerate(rows) if "rub out" in row)
        drawn = min(index for index, row in enumerate(rows) if "page up" in row)
        #  Directly under them, rather than held to the foot of the frame. The
        #  compass is a part like any other now, and a rule about where one
        #  particular part sits is the beginning of a layout language.
        assert drawn == spoken + 1

    @pytest.mark.parametrize(
        "keys",
        ["1-9", "0", "*<number>#", "*<keyword>#", "W", "A", "*0#", "*00#", "*09#", "*90#"],
    )
    async def test_it_names_the_keys_the_service_answers(
        self, keys: str, app: Sextile
    ) -> None:
        #  `#` travels as 0x5F, which this grid shows as the `#` the SAA5050 draws.
        assert keys in all_text_of(await page_at(app, "91"))

    async def test_it_points_at_the_generated_lists_rather_than_repeating_them(
        self, app: Sextile
    ) -> None:
        #  It used to name half a dozen keywords itself, which is a list that
        #  goes stale the first time one is added. The two pages it now points
        #  at are generated from the registrations and cannot.
        shown = all_text_of(await page_at(app, "91"))
        assert "*93#" in shown
        assert "*94#" in shown


class TestThePagesSayWhatTheyAre:
    """The words live at the registration, and everything else reads them.

    Before this, a page was named in the menu, again wherever one was listed,
    and again in the guide. Three copies of a name do not stay in step.
    """

    def test_a_menu_item_is_taken_from_the_page_it_offers(
        self, app: Sextile
    ) -> None:
        item = app.menu_item("contributors")
        assert item.text == "By contributor"
        assert item.detail == "browse by poster"
        assert item.destination == PageAddress("5")

    def test_asking_for_a_page_that_says_nothing_about_itself(
        self, app: Sextile
    ) -> None:
        #  The title frame has no title, deliberately: it cannot be keyed.
        with pytest.raises(ValueError):
            app.menu_item("title")

    async def test_the_main_index_offers_what_the_pages_call_themselves(
        self, app: Sextile
    ) -> None:
        page = await page_at(app, "1")
        shown = "\n".join(text_of(page, index) for index in range(len(page.frames)))
        for title in ("Latest posts", "By topic", "By day", "By forum", "By contributor"):
            assert title in shown

    def test_a_page_with_no_field_is_described_by_its_title(
        self, app: Sextile
    ) -> None:
        assert app.label_for(PageAddress("5")) == "By contributor"

    def test_one_with_a_field_says_which(self, app: Sextile) -> None:
        #  "One contributor" is the right title in a list of kinds of page and
        #  the wrong one in a list of pages a reader has been to.
        assert app.label_for(PageAddress("5210058")) == "Contributor 10058"

    def test_a_day_is_described_as_a_reader_would_say_it(
        self, app: Sextile
    ) -> None:
        assert app.label_for(PageAddress("3220260802")) == "SUN 02 AUG 2026"


class TestEveryPage:
    async def test_it_lists_the_pages_with_their_numbers(
        self, app: Sextile
    ) -> None:
        shown = text_of(await page_at(app, "93"))
        assert "*5#" in shown
        assert "By contributor" in shown

    async def test_a_number_with_a_field_is_shown_as_one(
        self, app: Sextile
    ) -> None:
        assert "*52<user-id>#" in text_of(await page_at(app, "93"))

    async def test_a_page_that_cannot_be_keyed_is_left_off(
        self, app: Sextile
    ) -> None:
        #  Only the title frame: `*0#` is the back command, so the number would
        #  be an instruction that misleads. Everything else shown here is
        #  keyable and does something, ringing off included -- this is a
        #  directory of numbers rather than a menu of places to go.
        assert "*0#" not in text_of(await page_at(app, "93"))

    async def test_ringing_off_is_listed_because_it_can_be_keyed(
        self, app: Sextile
    ) -> None:
        assert "*90#" in text_of(await page_at(app, "93"))

    @pytest.mark.parametrize("keyword", ["PAGES", "CONTENTS"])
    def test_a_keyword_reaches_it(self, keyword: str, app: Sextile) -> None:
        assert app.resolve(keyword) == PageAddress("93")

    def test_every_page_listed_can_be_reached(self, app: Sextile) -> None:
        #  A directory that has drifted from the thing it describes is worse
        #  than none, and this one is built from the registrations so it cannot.
        #  Parameterised numbers are shown as patterns, so only the plain ones
        #  can be built and looked up.
        for about in app.pages():
            if "<" not in about.keyed:
                assert app.route(PageAddress(about.keyed)) is not None


class TestTheTitleFrameSaysWhatTheServiceDoes:
    """The two instructions on it are built, not written out.

    A frame that says "key *91# for how to get about" and a help page that has
    moved to another number is worse than no instruction: the reader does what
    they are told and it does not work. So the number, the words and the key
    all come from the service itself, and these tests fail if any of the three
    is written down twice instead.
    """

    async def test_the_number_it_names_is_the_one_the_router_builds(
        self, app: Sextile
    ) -> None:
        assert keyed(app.address_for("help")) in text_of(await page_at(app, "0"))

    async def test_the_words_are_the_ones_the_pages_were_registered_with(
        self, app: Sextile
    ) -> None:
        shown = text_of(await page_at(app, "0"))
        for name in ("main", "help"):
            about = app.page_info(name)
            assert about is not None
            assert about.title.lower() in shown

    async def test_and_the_key_it_says_to_press_is_one_the_frame_answers(
        self, app: Sextile
    ) -> None:
        page = await page_at(app, "0")
        assert CONVENTIONAL_NEXT_FRAME_KEY in page.frames[0].moves
        assert f"Key {CONVENTIONAL_NEXT_FRAME_KEY}" in text_of(page)

    async def test_moving_the_help_page_moves_what_the_title_frame_says(
        self, repository: Repository
    ) -> None:
        #  The test that would have caught the drift. A service whose guide is
        #  somewhere else says so on its title frame, without that frame being
        #  edited: nothing in it knows the number 91.
        moved = build_application(
            repository=repository, pages=_moved("help", pattern="95")
        )
        await moved.startup()
        shown = text_of(await page_at(moved, "0"))
        assert keyed(PageAddress("95")) in shown
        assert keyed(PageAddress("91")) not in shown


class TestAPageIsHeadedWithWhatItWasRegisteredAs:
    """The heading and the declaration are the same words, not two copies.

    A page called "By day" in its decorator and headed "BY DAY" in its own
    chrome has two of everything to keep in step -- and the decorator's copy is
    the one that shows in menus, contents pages and the history, so the two
    drift where nobody is looking at both at once.
    """

    @pytest.mark.parametrize("digits", ["3", "4", "5", "7", "8", "91"])
    async def test_the_heading_is_the_registered_title(
        self, digits: str, app: Sextile
    ) -> None:
        page = await page_at(app, digits)
        found = app.route(PageAddress(digits))
        assert found is not None and found.name is not None
        about = app.page_info(found.name)
        assert about is not None
        assert about.title.upper() in text_of(page)

    async def test_and_renaming_a_page_renames_its_heading(
        self, repository: Repository
    ) -> None:
        renamed = build_application(
            repository=repository, pages=_moved("days", title="Day by day")
        )
        await renamed.startup()
        assert "DAY BY DAY" in text_of(await page_at(renamed, "3"))

    async def test_a_page_whose_heading_is_not_its_name_still_says_so(
        self, app: Sextile
    ) -> None:
        #  A day's frames are headed with the date, not with "One day".
        shown = text_of(await page_at(app, "3220260802"))
        assert "ONE DAY" not in shown


class TestTheGuideDescribesTheServiceItIsPartOf:
    """Every key and number in the guide is one the service answers.

    This page is the one most able to lie: it is a table of keys, read by
    someone who cannot find their way, and nothing about it fails if it is
    wrong. So none of it is written out.
    """

    @pytest.mark.parametrize("name", ["logoff", "contents", "keywords"])
    async def test_the_numbers_it_gives_are_the_ones_the_router_builds(
        self, name: str, app: Sextile
    ) -> None:
        assert keyed(app.address_for(name)) in all_text_of(await page_at(app, "91"))

    @pytest.mark.parametrize(
        "key", [keys.PREVIOUS_FRAME, keys.NEXT_FRAME, keys.PREVIOUS_ITEM, keys.NEXT_ITEM]
    )
    async def test_and_the_keys_are_the_ones_the_framework_sends(
        self, key: str, app: Sextile
    ) -> None:
        assert key in all_text_of(await page_at(app, "91"))

    async def test_including_the_requests_the_session_answers_itself(
        self, app: Sextile
    ) -> None:
        shown = all_text_of(await page_at(app, "91"))
        for request in (keys.BACK, keys.REDISPLAY, keys.REFRESH):
            assert keyed(request) in shown

    async def test_moving_a_page_moves_what_the_guide_says_about_it(
        self, repository: Repository
    ) -> None:
        moved = build_application(
            repository=repository, pages=_moved("logoff", pattern="96")
        )
        await moved.startup()
        shown = all_text_of(await page_at(moved, "91"))
        assert keyed(PageAddress("96")) in shown
        assert keyed(PageAddress("90")) not in shown


class TestTheGuideSKeyColumn:
    async def test_the_two_frames_line_up_with_each_other(
        self, app: Sextile
    ) -> None:
        #  One column width for the whole guide, from the widest key in it, so
        #  neither frame is set by hand and a longer key widens both.
        page = await page_at(app, "91")
        starts = {
            row.index(word)
            for index in range(len(page.frames))
            for row in text_of(page, index).splitlines()
            for word in ("choose from", "back to the main", "show this frame")
            if word in row
        }
        assert len(starts) == 1

    async def test_and_nothing_runs_off_the_end_of_a_row(
        self, app: Sextile
    ) -> None:
        for row in all_text_of(await page_at(app, "91")).splitlines():
            assert len(row) <= COLUMNS


class TestHowThePlaceholdersAreWritten:
    async def test_a_field_a_reader_fills_in_is_written_the_same_way(
        self, app: Sextile
    ) -> None:
        #  As the contents page writes the ones inside a page number, so a
        #  reader meets one shape of placeholder and not two. The underscore
        #  of the route's own field name is not in the character set, so what
        #  reaches the screen is *82<post-id>#.
        guide = all_text_of(await page_at(app, "91"))
        assert "*<number>#" in guide and "*<keyword>#" in guide
        assert "*82<post-id>#" in all_text_of(await page_at(app, "93"))
