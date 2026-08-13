"""Pages made of rows, dealt into frames.

Two shapes over one mechanism. What is worth testing is the mechanism -- the
pagination, the keys, the arithmetic that says how much fits -- since that is
what five hand-written copies had each got slightly differently.
"""


from sextile.addressing import PageAddress
from sextile.keys import with_arrows
from sextile.page import Page
from sextile.templates import (
    CHOICES_PER_FRAME,
    Entry,
    Figures,
    Listing,
    Menu,
    MenuItem,
    Prose,
    farewell_page,
)
from sextile.viewdata.canvas import Run
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS
from sextile.viewdata.controls import Colour, Control


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


class TestAPreambleLineInMoreThanOneColour:
    """A lead-in is not always one thing said in one voice.

    A weather page's is: a clock in UTC and the same clock locally, which mean
    different things and are told apart by colour rather than by a label
    costing four cells to say `UTC` twice. So a preamble line may be given as
    runs instead of as a string, and the rows it costs are counted the same way.
    """

    def test_each_run_is_written_in_its_own_colour(self) -> None:
        page = Menu(
            title="ITEMS",
            entries=items(1),
            home=at("1"),
            preamble=[[Run("10:29", Colour.YELLOW), Run("12:29", Colour.CYAN)]],
        ).build(at("8"))
        found = page.frame(0)
        assert found is not None
        characters, attributes = found.frame.to_grid()
        written, marked = characters[CONTENT_FIRST_ROW], attributes[CONTENT_FIRST_ROW]
        assert "10:29 12:29" in written
        #  The attribute sits in the cell before the run it colours.
        assert marked[written.index("10:29") - 1] == chr(Control.ALPHA_YELLOW + 0x40)
        assert marked[written.index("12:29") - 1] == chr(Control.ALPHA_CYAN + 0x40)

    def test_it_costs_a_row_like_any_other_line(self) -> None:
        plain = Menu(
            title="ITEMS", entries=items(20), home=at("1"), preamble=["One.", "Two."]
        ).build(at("8"))
        coloured = Menu(
            title="ITEMS",
            entries=items(20),
            home=at("1"),
            preamble=[[Run("One.")], [Run("Two.", Colour.GREEN)]],
        ).build(at("8"))
        assert len(coloured.frames[0].choices) == len(plain.frames[0].choices)

    def test_and_a_line_too_long_for_the_row_is_trimmed_rather_than_refused(
        self,
    ) -> None:
        #  A preamble is drawn from whatever an application has to say, and a
        #  place name of forty letters must not take the frame down with it.
        page = Menu(
            title="ITEMS",
            entries=items(1),
            home=at("1"),
            preamble=[[Run("x" * 60, Colour.GREEN)]],
        ).build(at("8"))
        assert "Item 1" in text_of(page)


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


class TestAListingCarriesOnRatherThanCuts:
    """A second column too long for its room goes on to another row.

    A listing's second column gets what is left after the first, so how much
    room it has depends on the widest thing in the first: `*3#  Forecast by
    lat/lon position` fits, and the same title beside `*321<geoname-id>#` does
    not. Cut, it reads as a fault rather than as a shortage of room.
    """

    #  A wide first column, as a contents page has once a page number carries
    #  a field, and a title written for a menu where it had the whole row.
    WIDE = [
        MenuItem("*321<geoname-id>#", "One place"),
        MenuItem("*4#", "Forecast by lat/lon position"),
    ]

    def test_a_long_second_column_is_carried_on(self) -> None:
        shown = text_of(Listing(title="PAGES", entries=self.WIDE, home=at("1")).build(at("9")))
        assert "Forecast by lat/lon" in shown
        assert "position" in shown

    def test_and_the_carried_row_has_nothing_in_the_first_column(self) -> None:
        #  Which column a thing is in is what tells a page number from a title
        #  that has run on.
        rows = text_of(
            Listing(title="PAGES", entries=self.WIDE, home=at("1")).build(at("9"))
        ).splitlines()
        carried = next(row for row in rows if "position" in row and "*4#" not in row)
        assert carried.strip() == "position"

    def test_a_second_column_that_fits_is_left_where_it_was(self) -> None:
        rows = [
            row
            for row in text_of(
                Listing(title="PAGES", entries=self.WIDE, home=at("1")).build(at("9"))
            ).splitlines()
            if "One place" in row
        ]
        assert len(rows) == 1
        assert "*321<geoname-id>#" in rows[0]

    def test_and_the_carrying_costs_the_frame_its_rows(self) -> None:
        #  A wrapped entry is two rows, and the pagination has to know it: a
        #  listing that counted them as one would run off the bottom.
        long = [MenuItem("*321<geoname-id>#", "Forecast by lat/lon position")] * 11
        page = Listing(title="PAGES", entries=long, home=at("1")).build(at("9"))
        assert len(page.frames) == 2


class TestAFarewell:
    """The last thing a caller sees, drawn the same way by every service.

    No chrome, and the lower rows left blank: the reader is about to be
    talking to their modem, and the cursor needs somewhere to be left.
    """

    def test_the_title_heads_the_frame_and_the_lines_follow(self) -> None:
        page = farewell_page("GOODBYE", "Thank you for calling.", "", "Ring off.")
        rows = text_of(page).splitlines()
        assert rows[0].startswith(" GOODBYE")
        assert "Thank you for calling." in rows[2]
        assert rows[3].strip() == ""
        assert "Ring off." in rows[4]

    def test_it_ends_the_call(self) -> None:
        assert farewell_page("GOODBYE").hang_up

    def test_a_ringing_off_page_may_be_shown_without_dropping_the_line(self) -> None:
        #  The involuntary parting: the session drops the line itself, so the
        #  page need not insist.
        assert not farewell_page("RINGING OFF", hang_up=False).hang_up


class TestFigures:
    """A label and a figure a row, for a page that reports rather than offers.

    The figures line up in a column of their own, because a column of numbers
    that does not line up is a column a reader has to check twice.
    """

    def figures(self, *pairs: tuple[str, int]) -> list[MenuItem]:
        return [MenuItem(text=label, detail=str(count)) for label, count in pairs]

    def test_the_label_and_the_figure_are_both_shown(self) -> None:
        shown = text_of(
            Figures(
                title="CALLERS",
                entries=self.figures(("Last 24 hours", 4), ("Last 7 days", 19)),
                home=at("1"),
            ).build(at("98"))
        )
        assert "Last 24 hours" in shown
        assert "Last 7 days" in shown
        assert "4" in shown
        assert "19" in shown

    def test_the_figures_end_in_the_same_column(self) -> None:
        rows = text_of(
            Figures(
                title="CALLERS",
                entries=self.figures(("One", 4), ("A much longer label", 1908)),
                home=at("1"),
            ).build(at("98"))
        ).splitlines()
        written = [row for row in rows if "One" in row or "1908" in row]
        assert len(written) == 2
        ends = {len(row.rstrip()) for row in written}
        assert len(ends) == 1, f"figures do not end in one column: {written}"

    def test_nothing_to_report_says_so(self) -> None:
        shown = text_of(
            Figures(
                title="CALLERS", entries=[], home=at("1"), empty="Nobody has called yet."
            ).build(at("98"))
        )
        assert "Nobody has called yet." in shown

    def test_a_figure_is_not_something_to_choose(self) -> None:
        page = Figures(
            title="CALLERS", entries=self.figures(("Last 7 days", 19)), home=at("1")
        ).build(at("98"))
        found = page.frame(0)
        assert found is not None
        assert found.destination("1") is None


class TestAFootnote:
    """What the entries above mean, said beneath them on every frame.

    The same argument as the headings: a reader on frame c looking at a column
    of figures has no way back to the words that say what they are.
    """

    NOTE = "A caller is one connection, counted once however long they stay."

    def test_it_is_drawn_beneath_the_entries(self) -> None:
        rows = text_of(
            Menu(title="ITEMS", entries=items(2), home=at("1"), footnote=self.NOTE)
            .build(at("8"))
        ).splitlines()
        said = next(number for number, row in enumerate(rows) if "A caller is one" in row)
        last = max(number for number, row in enumerate(rows) if "Item 2" in row)
        assert said > last

    def test_it_is_on_every_frame(self) -> None:
        page = Menu(
            title="ITEMS", entries=items(12), home=at("1"), footnote=self.NOTE
        ).build(at("8"))
        assert len(page.frames) > 1
        for index in range(len(page.frames)):
            assert "A caller is one" in text_of(page, index)

    def test_it_takes_its_room_from_the_entries(self) -> None:
        #  Counted like the headings and not like the preamble: a footnote on
        #  every frame costs its rows on every frame, and an entry written over
        #  it would be an entry written over the rule at the foot as well. A
        #  listing rather than a menu, a menu being capped at nine by the
        #  digits before the rows ever come into it.
        without = Listing(title="PAGES", entries=items(40), home=at("1")).build(at("9"))
        with_note = Listing(
            title="PAGES", entries=items(40), home=at("1"), footnote=self.NOTE
        ).build(at("9"))
        assert len(with_note.frames) > len(without.frames)

    def test_it_is_said_even_where_there_is_nothing_to_say_it_about(self) -> None:
        shown = text_of(
            Menu(
                title="ITEMS", entries=[], home=at("1"),
                empty="Nothing yet.", footnote=self.NOTE,
            ).build(at("8"))
        )
        assert "Nothing yet." in shown
        assert "A caller is one" in shown
