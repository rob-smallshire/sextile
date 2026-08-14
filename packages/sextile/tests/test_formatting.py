"""Sequences formatted as parts of a page.

What a formatter does with the room it is given: how many entries go in it,
which of them can be chosen, and what is left for the next frame.

See docs/page-layout.md.
"""

from dataclasses import dataclass
from typing import ClassVar

from sextile.addressing import PageAddress
from sextile.formatting import (
    Entry,
    Figures,
    Formatter,
    Lines,
    Listing,
    Menu,
    MenuItem,
    Prose,
    farewell_page,
)
from sextile.layout import CHOICES_PER_FRAME, Flowing, Once, PageLayout, Room
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import COLUMNS

CONTENT = range(2, 22)


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


def items(count: int) -> list[MenuItem]:
    return [
        MenuItem(text=f"Item {n}", detail=f"detail {n}", destination=at(f"8{n}"))
        for n in range(1, count + 1)
    ]


def said(canvas: Canvas) -> list[str]:
    characters, _ = canvas.frame.to_grid()
    return [row.strip() for row in characters if row.strip()]


def whole_frame() -> Room:
    return Room(first_row=CONTENT.start, rows=len(CONTENT), choices=CHOICES_PER_FRAME)


class TestAMenuAsAPart:
    def test_it_takes_nine_however_many_rows_are_free(self) -> None:
        #  Two rows an entry and twenty rows free would fit ten, but a reader
        #  chooses with one keypress.
        placed = Menu(entries=items(12)).place(Canvas(), whole_frame())
        assert placed.rows == CHOICES_PER_FRAME * 2
        assert len(placed.offer.choices) == CHOICES_PER_FRAME

    def test_and_hands_back_what_is_left(self) -> None:
        placed = Menu(entries=items(12)).place(Canvas(), whole_frame())
        #  The same shape, carrying what is left, so the next frame draws it
        #  the same way.
        assert isinstance(placed.rest, Menu)
        assert list(placed.rest.entries) == items(12)[9:]

    def test_it_takes_no_more_than_the_choices_it_is_given(self) -> None:
        placed = Menu(entries=items(12)).place(
            Canvas(), Room(first_row=2, rows=20, choices=4)
        )
        assert len(placed.offer.choices) == 4
        assert placed.rows == 8

    def test_the_digits_lead_where_the_entries_do(self) -> None:
        placed = Menu(entries=items(3)).place(Canvas(), whole_frame())
        assert placed.offer.choices == {"1": at("81"), "2": at("82"), "3": at("83")}

    def test_an_entry_leading_nowhere_takes_no_digit(self) -> None:
        entries = [MenuItem(text="Just words"), *items(1)]
        placed = Menu(entries=entries).place(Canvas(), whole_frame())
        assert placed.offer.choices == {"2": at("81")}

    def test_it_says_it_offers_a_choice(self) -> None:
        placed = Menu(entries=items(3)).place(Canvas(), whole_frame())
        assert [one.key for one in placed.offer.named] == ["1-9"]

    def test_nothing_to_show_says_so(self) -> None:
        placed = Menu(entries=[], empty="Nothing yet.").place(Canvas(), whole_frame())
        assert placed.rows == 1
        assert placed.rest is None
        assert not placed.offer.named

    def test_and_nothing_to_say_about_it_takes_no_rows(self) -> None:
        assert Menu(entries=[]).place(Canvas(), whole_frame()).rows == 0


class TestAMenuInAPage:
    def test_twelve_entries_are_nine_and_three(self) -> None:
        page = PageLayout(
            title="ITEMS", home=at("1"), parts=[Flowing(Menu(entries=items(12)))]
        ).build(at("8"))
        assert len(page.frames) == 2
        first, second = page.frame(0), page.frame(1)
        assert first is not None and second is not None
        assert first.destination("9") == at("89")
        assert second.destination("1") == at("810")

    def test_a_lead_in_takes_room_from_the_first_frame_only(self) -> None:
        page = PageLayout(
            title="ITEMS",
            home=at("1"),
            parts=[
                Once(Lines(said=("A lead-in", "of four", "rows, which", "costs two"))),
                Flowing(Menu(entries=items(12))),
            ],
        ).build(at("8"))
        found = page.frame(0)
        assert found is not None
        #  Four rows gone of twenty, so eight two-row entries rather than nine.
        assert len(found.choices) == 8 + 1  # and the way home
        later = page.frame(1)
        assert later is not None
        assert later.destination("1") == at("89")


class TestLinesAsAPart:
    def test_each_line_is_drawn_where_it_was_put(self) -> None:
        canvas = Canvas()
        placed = Lines(said=("first", "", "third")).place(canvas, whole_frame())
        assert placed.rows == 3
        assert said(canvas) == ["first", "third"]

    def test_it_chooses_nothing(self) -> None:
        placed = Lines(said=("first",)).place(Canvas(), whole_frame())
        assert not placed.offer.choices

    def test_more_lines_than_rows_go_on_to_the_next_frame(self) -> None:
        placed = Lines(said=tuple(f"line {n}" for n in range(30))).place(
            Canvas(), whole_frame()
        )
        assert placed.rows == 20
        assert isinstance(placed.rest, Lines)
        assert len(placed.rest.said) == 10


class TestAListing:
    WIDE = [
        MenuItem(text="*3#", detail="Forecast by name"),
        MenuItem(text="*321<geoname-id>#", detail="One place"),
    ]

    def test_two_columns_and_nothing_to_choose(self) -> None:
        canvas = Canvas()
        placed = Listing(entries=self.WIDE).place(canvas, whole_frame())
        assert not placed.offer.choices
        assert "*3#" in said(canvas)[0]
        assert "Forecast by name" in said(canvas)[0]

    def test_the_column_is_set_once_and_carried(self) -> None:
        #  Or the second frame would set its own from the entries left on it,
        #  and a table would step sideways part way down.
        listing = Listing(entries=self.WIDE * 15)
        placed = listing.place(Canvas(), whole_frame())
        assert isinstance(placed.rest, Listing)
        assert placed.rest.column == listing.column

    def test_a_detail_too_long_for_its_room_is_carried_on(self) -> None:
        canvas = Canvas()
        Listing(
            entries=[MenuItem(text="*321<geoname-id>#", detail="Forecast by lat/lon position")]
        ).place(canvas, whole_frame())
        assert len(said(canvas)) == 2

    def test_and_the_widest_the_left_column_may_be_is_said_once(self) -> None:
        assert Listing.widest() == COLUMNS // 2


class TestFigures:
    def counts(self) -> list[MenuItem]:
        return [
            MenuItem(text="Last 24 hours", detail="4"),
            MenuItem(text="Last 30 days", detail="1908"),
        ]

    def test_the_figures_end_in_the_same_column(self) -> None:
        canvas = Canvas()
        Figures(entries=self.counts()).place(canvas, whole_frame())
        characters, _ = canvas.frame.to_grid()
        written = [row for row in characters if row.strip()]
        assert len({len(row.rstrip()) for row in written}) == 1

    def test_the_columns_are_set_once_and_carried(self) -> None:
        figures = Figures(entries=self.counts() * 15)
        placed = figures.place(Canvas(), whole_frame())
        assert isinstance(placed.rest, Figures)
        assert (placed.rest.label, placed.rest.figure) == (figures.label, figures.figure)


class TestProse:
    def test_it_wraps_what_it_is_given(self) -> None:
        canvas = Canvas()
        Prose.of("A sentence long enough to need more than one row of forty cells.").place(
            canvas, whole_frame()
        )
        assert len(said(canvas)) == 2

    def test_a_blank_row_divides_one_paragraph_from_the_next(self) -> None:
        canvas = Canvas()
        Prose.of("First.", "Second.").place(canvas, whole_frame())
        characters, _ = canvas.frame.to_grid()
        assert characters[2].strip() == "First."
        assert characters[3].strip() == ""
        assert characters[4].strip() == "Second."

    def test_it_goes_on_to_as_many_frames_as_it_takes(self) -> None:
        long = Prose.of(*(f"Paragraph {n} of some length." for n in range(20)))
        placed = long.place(Canvas(), whole_frame())
        assert isinstance(placed.rest, Prose)


class TestAFarewell:
    """The last thing a caller sees, drawn the same way by every service.

    No furniture, and the lower rows left blank: the reader is about to be
    talking to their modem, and the cursor needs somewhere to be left.
    """

    def test_the_title_heads_the_frame_and_the_lines_follow(self) -> None:
        page = farewell_page("GOODBYE", "Thank you for calling.", "", "Ring off.")
        found = page.frame(0)
        assert found is not None
        rows, _ = found.frame.to_grid()
        assert rows[0].strip() == "GOODBYE"
        assert "Thank you for calling." in rows[2]
        assert rows[3].strip() == ""
        assert "Ring off." in rows[4]

    def test_it_offers_no_keys_at_all(self) -> None:
        #  A footer naming the index would be a lie on a page there is no
        #  coming back from.
        found = farewell_page("GOODBYE", "Thank you.").frame(0)
        assert found is not None
        assert not found.choices
        assert not found.moves

    def test_it_ends_the_call(self) -> None:
        assert farewell_page("GOODBYE").hang_up

    def test_but_may_be_shown_without_dropping_the_line(self) -> None:
        #  The involuntary parting: the session drops the line itself, so the
        #  page need not insist.
        assert not farewell_page("RINGING OFF", hang_up=False).hang_up


class TestAServiceWithItsOwnIdeaOfAnEntry:
    """`Entry` is a protocol, so a service passes what it already has.

    A menu carrying a post, a place or a timestamp hands that value over
    rather than copying it into a dataclass belonging to the framework, and
    gets it back where it draws one.
    """

    @dataclass(frozen=True)
    class Post:
        post_id: int

        @property
        def text(self) -> str:
            return f"Post {self.post_id}"

        @property
        def detail(self) -> str:
            return "a post of its own"

        @property
        def destination(self) -> PageAddress:
            return PageAddress(f"82{self.post_id}")

    def test_it_needs_no_conversion(self) -> None:
        canvas = Canvas()
        placed = Menu(entries=[self.Post(489493)]).place(canvas, whole_frame())
        assert placed.offer.choices == {"1": at("82489493")}
        assert "Post 489493" in said(canvas)[0]

    def test_and_satisfies_the_protocol_at_runtime(self) -> None:
        assert isinstance(self.Post(1), Entry)


class TestAServiceWithItsOwnShape:
    """A formatter of its own, for content no shape here fits.

    What `weather-viewdata` does for a forecast day four rows tall with a
    picture in it: say how tall an entry is, and how to draw one.
    """

    @dataclass(frozen=True, kw_only=True)
    class Blocks(Formatter[str]):
        rows_per_entry: ClassVar[int] = 3
        separation: ClassVar[int] = 1

        def draw_entry(
            self, canvas: Canvas, row: int, entry: str, digit: str | None
        ) -> None:
            del digit
            for offset in range(self.rows_per_entry):
                canvas.row(row + offset).text(f"{entry}{offset}", Colour.WHITE)

    def test_the_rows_it_asks_for_are_the_rows_it_gets(self) -> None:
        canvas = Canvas()
        placed = self.Blocks(entries=["a", "b"]).place(canvas, whole_frame())
        #  Three rows each and a blank between, and none after the last.
        assert placed.rows == 7
        assert said(canvas) == ["a0", "a1", "a2", "b0", "b1", "b2"]

    def test_and_what_will_not_fit_is_handed_back(self) -> None:
        placed = self.Blocks(entries=list("abcdefg")).place(
            Canvas(), Room(first_row=2, rows=10, choices=CHOICES_PER_FRAME)
        )
        #  Ten rows holds two whole entries and the blank between them.
        assert placed.rows == 7
        assert isinstance(placed.rest, self.Blocks)
        assert list(placed.rest.entries) == list("cdefg")
