"""Pages made of rows, dealt into frames.

Two shapes over one mechanism. What is worth testing is the mechanism -- the
pagination, the keys, the arithmetic that says how much fits -- since that is
what five hand-written copies had each got slightly differently.
"""


from sextile.addressing import PageAddress
from sextile.keys import with_arrows
from sextile.page import Page
from sextile.templates import CHOICES_PER_FRAME, Entry, Listing, Menu, MenuItem, Prose
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


def text_of(page: Page, index: int = 0) -> str:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


def items(count: int, *, detail: bool = True) -> list[MenuItem]:
    return [
        MenuItem(
            text=f"Item {number}",
            detail=f"detail {number}" if detail else "",
            destination=at(f"8{number}"),
        )
        for number in range(1, count + 1)
    ]


class TestAMenu:
    def test_it_numbers_its_entries(self) -> None:
        page = Menu(title="ITEMS", entries=items(3), home=at("1")).build(at("8"))
        assert page.frames[0].destination("1") == at("81")
        assert page.frames[0].destination("3") == at("83")

    def test_it_shows_the_text_and_the_detail(self) -> None:
        shown = text_of(Menu(title="ITEMS", entries=items(1), home=at("1")).build(at("8")))
        assert "Item 1" in shown
        assert "detail 1" in shown

    def test_nine_to_a_frame(self) -> None:
        entries = items(CHOICES_PER_FRAME)
        page = Menu(title="ITEMS", entries=entries, home=at("1")).build(at("8"))
        assert len(page.frames) == 1

    def test_the_tenth_starts_a_new_frame(self) -> None:
        entries = items(CHOICES_PER_FRAME + 1)
        page = Menu(title="ITEMS", entries=entries, home=at("1")).build(at("8"))
        assert len(page.frames) == 2

    def test_the_digits_begin_again_on_each_frame(self) -> None:
        page = Menu(title="ITEMS", entries=items(10), home=at("1")).build(at("8"))
        assert page.frames[1].destination("1") == at("810")

    def test_zero_goes_home_from_every_frame(self) -> None:
        page = Menu(title="ITEMS", entries=items(10), home=at("1")).build(at("8"))
        for frame in page.frames:
            assert frame.destination("0") == at("1")

    def test_a_menu_with_nowhere_to_go_home_to_offers_no_zero(self) -> None:
        page = Menu(title="ITEMS", entries=items(1)).build(at("8"))
        assert page.frames[0].destination("0") is None

    def test_an_entry_that_leads_nowhere_takes_no_digit(self) -> None:
        page = Menu(
            title="ITEMS", entries=[MenuItem(text="Just words")], home=at("1")
        ).build(at("8"))
        assert page.frames[0].destination("1") is None


class TestThePreamble:
    def test_it_appears_on_the_first_frame(self) -> None:
        page = Menu(
            title="ITEMS", entries=items(1), home=at("1"), preamble=["Some words."]
        ).build(at("8"))
        assert "Some words." in text_of(page)

    def test_and_not_on_the_others(self) -> None:
        page = Menu(
            title="ITEMS", entries=items(20), home=at("1"), preamble=["Some words."]
        ).build(at("8"))
        assert "Some words." not in text_of(page, 1)

    def test_it_costs_the_first_frame_some_entries(self) -> None:
        #  Two lines of lead-in and a blank row after them: three rows, so one
        #  entry fewer at two rows each.
        page = Menu(
            title="ITEMS", entries=items(20), home=at("1"), preamble=["One.", "Two."]
        ).build(at("8"))
        assert page.frames[0].destination("8") is not None
        assert page.frames[0].destination("9") is None

    def test_and_costs_the_later_frames_nothing(self) -> None:
        #  Where the five hand-written copies disagreed: they spent the
        #  preamble's rows on every frame, though it is only on the first.
        page = Menu(
            title="ITEMS", entries=items(20), home=at("1"), preamble=["One.", "Two."]
        ).build(at("8"))
        assert page.frames[1].destination("9") is not None


class TestAListing:
    def test_it_numbers_nothing(self) -> None:
        page = Listing(title="PAGES", entries=items(3), home=at("1")).build(at("9"))
        assert page.frames[0].destination("1") is None

    def test_it_shows_both_columns(self) -> None:
        shown = text_of(Listing(title="PAGES", entries=items(1), home=at("1")).build(at("9")))
        assert "Item 1" in shown
        assert "detail 1" in shown

    def test_the_columns_line_up(self) -> None:
        entries = [MenuItem("*1#", "Short"), MenuItem("*82<post_id>#", "Long one")]
        rows = text_of(Listing(title="PAGES", entries=entries, home=at("1")).build(at("9")))
        lines = [line for line in rows.splitlines() if "Short" in line or "Long one" in line]
        assert lines[0].index("Short") == lines[1].index("Long one")

    def test_twenty_to_a_frame(self) -> None:
        entries = items(CONTENT_ROWS)
        page = Listing(title="PAGES", entries=entries, home=at("1")).build(at("9"))
        assert len(page.frames) == 1

    def test_the_twenty_first_starts_a_new_frame(self) -> None:
        entries = items(CONTENT_ROWS + 1)
        page = Listing(title="PAGES", entries=entries, home=at("1")).build(at("9"))
        assert len(page.frames) == 2


class TestTheKeysAFrameOffers:
    """A frame names only the keys that do something on it."""

    def test_one_frame_offers_no_movement(self) -> None:
        page = Menu(title="ITEMS", entries=items(1), home=at("1")).build(at("8"))
        assert page.frames[0].moves == frozenset()

    def test_the_first_of_several_offers_forward_only(self) -> None:
        page = Menu(title="ITEMS", entries=items(10), home=at("1")).build(at("8"))
        assert page.frames[0].moves == with_arrows({"S", "#"})

    def test_the_last_offers_back_only(self) -> None:
        page = Menu(title="ITEMS", entries=items(10), home=at("1")).build(at("8"))
        assert page.frames[-1].moves == with_arrows({"W"})

    def test_the_prompt_names_selecting_only_where_there_is_a_choice(self) -> None:
        with_items = text_of(Menu(title="ITEMS", entries=items(1), home=at("1")).build(at("8")))
        without = text_of(
            Menu(title="ITEMS", entries=[], home=at("1"), empty="Nothing.").build(at("8"))
        )
        assert "1-9 select" in with_items
        assert "1-9 select" not in without

    def test_a_listing_never_names_selecting(self) -> None:
        shown = text_of(Listing(title="PAGES", entries=items(3), home=at("1")).build(at("9")))
        assert "1-9" not in shown


class TestNothingToShow:
    def test_a_template_with_no_entries_still_makes_a_page(self) -> None:
        page = Menu(title="ITEMS", entries=[], home=at("1")).build(at("8"))
        assert len(page.frames) == 1

    def test_and_says_why_if_it_was_told_what_to_say(self) -> None:
        page = Menu(
            title="ITEMS", entries=[], home=at("1"), empty="NO ITEMS held yet."
        ).build(at("8"))
        assert "NO ITEMS held yet." in text_of(page)


class TestSubstitutingYourOwnEntry:
    """The point of the protocol: a service keeps its own richer type."""

    def test_anything_with_the_three_attributes_will_do(self) -> None:
        class Mine:
            def __init__(self, post_id: int) -> None:
                self.post_id = post_id

            @property
            def text(self) -> str:
                return f"Post {self.post_id}"

            @property
            def detail(self) -> str:
                return "by somebody"

            @property
            def destination(self) -> PageAddress:
                return at(f"82{self.post_id}")

        page = Menu(title="POSTS", entries=[Mine(489493)], home=at("1")).build(at("8"))
        assert "Post 489493" in text_of(page)
        assert page.frames[0].destination("1") == at("82489493")

    def test_and_it_is_recognised_as_an_entry(self) -> None:
        assert isinstance(MenuItem("a"), Entry)


class TestAnApplicationsOwnShape:
    """A third shape is a subclass, not another copy of the six steps."""

    def test_a_template_can_be_written_from_scratch(self) -> None:
        class Roomy(Menu):
            rows_per_entry = 4

        page = Roomy(title="ROOMY", entries=items(20), home=at("1")).build(at("8"))
        assert page.frames[0].destination("5") is not None
        assert page.frames[0].destination("6") is None


class TestProse:
    """Running text, wrapped here rather than by whoever wrote it."""

    def test_it_wraps_to_the_frame(self) -> None:
        page = Prose.of(
            "A Viewdata service carrying posts from stardot.org.uk, for users "
            "of Acorn computers and emulators.",
            title="ABOUT",
            home=at("1"),
        ).build(at("9"))
        rows = [row for row in text_of(page).splitlines() if row.strip()]
        assert all(len(row) <= 40 for row in rows)
        assert "stardot.org.uk" in text_of(page)

    def test_a_paragraph_break_costs_a_row(self) -> None:
        page = Prose.of("First.", "Second.", title="ABOUT", home=at("1")).build(at("9"))
        rows = text_of(page).splitlines()
        first = next(index for index, row in enumerate(rows) if "First." in row)
        second = next(index for index, row in enumerate(rows) if "Second." in row)
        assert second == first + 2

    def test_nothing_is_numbered(self) -> None:
        page = Prose.of("Words.", title="ABOUT", home=at("1")).build(at("9"))
        assert page.frames[0].destination("1") is None

    def test_zero_still_goes_home(self) -> None:
        page = Prose.of("Words.", title="ABOUT", home=at("1")).build(at("9"))
        assert page.frames[0].destination("0") == at("1")

    def test_long_text_runs_on_to_another_frame(self) -> None:
        page = Prose.of(*(f"Paragraph {n} of some length." for n in range(20)),
                        title="ABOUT", home=at("1")).build(at("9"))
        assert len(page.frames) > 1
        assert "S" in page.frames[0].moves

    def test_a_word_too_long_for_a_row_is_split_rather_than_lost(self) -> None:
        #  Losing part of a link address is worse than an ugly break. Counted
        #  over the content rows alone: the footer says "0 index".
        page = Prose.of("See " + "x" * 60, title="ABOUT", home=at("1")).build(at("9"))
        body = text_of(page).splitlines()[CONTENT_FIRST_ROW:CONTENT_FIRST_ROW + CONTENT_ROWS]
        assert sum(row.count("x") for row in body) == 60

    def test_it_takes_rendered_rows_as_readily_as_paragraphs(self) -> None:
        #  Which is what lets a notice have a quotation or a listing in it,
        #  rendered exactly as a post's would be.
        from sextile.content.blocks import Code, Document
        from sextile.viewdata.layout import rows_for

        page = Prose(
            title="ABOUT",
            entries=rows_for(Document(blocks=(Code(("LDA &FE",)),))),
            home=at("1"),
        ).build(at("9"))
        assert "LDA &FE" in text_of(page)


class TestColumnHeadings:
    """A table dealt across frames needs its headings on each of them.

    A preamble is a lead-in and belongs on the first frame only. Headings are
    not a lead-in: they say what the columns beneath them mean, and a reader on
    frame c looking at a column of numbers has no way back to the words.
    """

    def _table(self, count: int) -> Listing:
        return Listing(
            title="A TABLE",
            entries=[MenuItem(f"row {n}", f"detail {n}") for n in range(count)],
            headings="WHAT      AND WHAT ELSE",
        )

    def test_the_headings_are_drawn(self) -> None:
        page = self._table(3).build(PageAddress("1"))
        assert "WHAT      AND WHAT ELSE" in text_of(page, 0)

    def test_on_every_frame_and_not_just_the_first(self) -> None:
        page = self._table(60).build(PageAddress("1"))
        assert len(page.frames) > 1
        for index in range(len(page.frames)):
            assert "AND WHAT ELSE" in text_of(page, index), f"frame {index} lost them"

    def test_they_sit_immediately_above_the_entries(self) -> None:
        rows = text_of(self._table(3).build(PageAddress("1")), 0).splitlines()
        headings = next(n for n, row in enumerate(rows) if "AND WHAT ELSE" in row)
        assert "row 0" in rows[headings + 1]

    def test_they_cost_a_row_on_every_frame(self) -> None:
        #  Not just the first, or the last entry of each later frame would be
        #  written over the rule at the bottom.
        without = Listing(
            title="A TABLE",
            entries=[MenuItem(f"row {n}") for n in range(60)],
        ).build(PageAddress("1"))
        with_them = self._table(60).build(PageAddress("1"))
        assert len(with_them.frames) > len(without.frames)

    def test_a_table_without_them_is_unchanged(self) -> None:
        page = Listing(
            title="A TABLE", entries=[MenuItem("row 0")]
        ).build(PageAddress("1"))
        rows = text_of(page, 0).splitlines()
        assert "row 0" in rows[CONTENT_FIRST_ROW]

    def test_a_preamble_and_headings_together(self) -> None:
        page = Listing(
            title="A TABLE",
            entries=[MenuItem("row 0")],
            preamble=["what this is"],
            headings="WHAT",
        ).build(PageAddress("1"))
        shown = text_of(page, 0)
        assert "what this is" in shown
        assert "WHAT" in shown
        assert "row 0" in shown
