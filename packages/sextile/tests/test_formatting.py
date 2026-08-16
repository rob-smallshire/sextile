"""Sequences formatted as parts of a page.

What a formatter does with the room it is given: how many entries go in it,
which of them can be chosen, and what is left for the next frame.

See docs/design.md.
"""

from dataclasses import dataclass
from typing import ClassVar

from sextile.application import Sextile
from sextile.formatting import (
    Entry,
    Figures,
    Lines,
    Listing,
    Menu,
    MenuItem,
    Prose,
    SequencePart,
)
from sextile.layout import CHOICES_PER_FRAME, Flow, OnOneFrame, PageLayout, Space
from sextile.page import PageAddress
from sextile.testing import request_for, text_of
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import COLUMNS

CONTENT = range(2, 22)


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


_APP = Sextile()


def items(count: int) -> list[MenuItem]:
    return [
        MenuItem(text=f"Item {n}", detail=f"detail {n}", destination=at(f"8{n}"))
        for n in range(1, count + 1)
    ]


def said(canvas: Canvas) -> list[str]:
    characters, _ = canvas.frame.to_grid()
    return [row.strip() for row in characters if row.strip()]


def whole_frame() -> Space:
    return Space(first_row=CONTENT.start, rows=len(CONTENT), choices=CHOICES_PER_FRAME)


class TestAMenuAsAPart:
    def test_it_takes_nine_however_many_rows_are_free(self) -> None:
        #  Two rows an entry and twenty rows free would fit ten, but a reader
        #  chooses with one keypress.
        placed = Menu(entries=items(12)).place(Canvas(), whole_frame())
        assert placed.rows == CHOICES_PER_FRAME * 2
        assert len(placed.claim.choices) == CHOICES_PER_FRAME

    def test_and_hands_back_what_is_left(self) -> None:
        placed = Menu(entries=items(12)).place(Canvas(), whole_frame())
        #  The same shape, carrying what is left, so the next frame draws it
        #  the same way.
        assert isinstance(placed.remainder, Menu)
        assert list(placed.remainder.entries) == items(12)[9:]

    def test_it_takes_no_more_than_the_choices_it_is_given(self) -> None:
        placed = Menu(entries=items(12)).place(
            Canvas(), Space(first_row=2, rows=20, choices=4)
        )
        assert len(placed.claim.choices) == 4
        assert placed.rows == 8

    def test_the_digits_lead_where_the_entries_do(self) -> None:
        placed = Menu(entries=items(3)).place(Canvas(), whole_frame())
        assert placed.claim.choices == {"1": at("81"), "2": at("82"), "3": at("83")}

    def test_an_entry_leading_nowhere_takes_no_digit(self) -> None:
        entries = [MenuItem(text="Just words"), *items(1)]
        placed = Menu(entries=entries).place(Canvas(), whole_frame())
        assert placed.claim.choices == {"2": at("81")}

    def test_it_names_the_digits_a_full_frame_offers(self) -> None:
        placed = Menu(entries=items(12)).place(Canvas(), whole_frame())
        assert [one.key for one in placed.claim.named] == ["1-9"]

    def test_it_names_the_digits_a_short_frame_offers(self) -> None:
        #  Fewer than nine entries offer fewer than nine digits, and the prompt
        #  says the range a reader can actually key.
        placed = Menu(entries=items(3)).place(Canvas(), whole_frame())
        assert [one.key for one in placed.claim.named] == ["1-3"]

    def test_a_single_entry_names_the_one_digit(self) -> None:
        placed = Menu(entries=items(1)).place(Canvas(), whole_frame())
        assert [one.key for one in placed.claim.named] == ["1"]

    def test_it_names_the_digits_offered_when_the_first_leads_nowhere(self) -> None:
        entries = [MenuItem(text="Just words"), *items(1)]
        placed = Menu(entries=entries).place(Canvas(), whole_frame())
        assert placed.claim.choices == {"2": at("81")}
        assert [one.key for one in placed.claim.named] == ["2"]

    def test_nothing_to_show_says_so(self) -> None:
        placed = Menu(entries=[], empty="Nothing yet.").place(Canvas(), whole_frame())
        assert placed.rows == 1
        assert placed.remainder is None
        assert not placed.claim.named

    def test_and_nothing_to_say_about_it_takes_no_rows(self) -> None:
        assert Menu(entries=[]).place(Canvas(), whole_frame()).rows == 0

    def test_a_reason_of_several_lines_takes_a_row_each(self) -> None:
        canvas = Canvas()
        placed = Menu(entries=[], empty=["Nothing yet.", "", "Do call again."]).place(
            canvas, whole_frame()
        )
        assert placed.rows == 3
        assert placed.remainder is None
        assert said(canvas) == ["Nothing yet.", "Do call again."]

    def test_a_reason_of_lines_defers_where_the_frame_is_full(self) -> None:
        #  No room left is deferred whole, as a one-line reason is, so nothing of
        #  the message is drawn half onto a frame that cannot hold it.
        placed = Menu(entries=[], empty=["A", "B"]).place(
            Canvas(), Space(first_row=CONTENT.start, rows=0, choices=0)
        )
        assert placed.rows == 0
        assert placed.remainder is not None


class TestAMenuInAPage:
    def test_twelve_entries_are_nine_and_three(self) -> None:
        page = PageLayout(
            title="ITEMS", home=at("1"), parts=[Flow(Menu(entries=items(12)))]
        ).build(request_for(_APP, at("8")))
        assert len(page.frames) == 2
        first, second = page.frame(0), page.frame(1)
        assert first is not None and second is not None
        assert first.destination("9") == at("89")
        assert second.destination("1") == at("810")

    def test_each_frame_names_the_digits_it_offers(self) -> None:
        #  The full first frame offers nine, the second offers the last three,
        #  and each says so on its own prompt rather than both saying 1-9.
        page = PageLayout(
            title="ITEMS", home=at("1"), parts=[Flow(Menu(entries=items(12)))]
        ).build(request_for(_APP, at("8")))
        assert "1-9 select" in text_of(page, 0)
        assert "1-3 select" in text_of(page, 1)

    def test_a_lead_in_takes_room_from_the_first_frame_only(self) -> None:
        page = PageLayout(
            title="ITEMS",
            home=at("1"),
            parts=[
                OnOneFrame(Lines(("A lead-in", "of four", "rows, which", "costs two"))),
                Flow(Menu(entries=items(12))),
            ],
        ).build(request_for(_APP, at("8")))
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
        placed = Lines(("first", "", "third")).place(canvas, whole_frame())
        assert placed.rows == 3
        assert said(canvas) == ["first", "third"]

    def test_it_chooses_nothing(self) -> None:
        placed = Lines(("first",)).place(Canvas(), whole_frame())
        assert not placed.claim.choices

    def test_more_lines_than_rows_go_on_to_the_next_frame(self) -> None:
        placed = Lines(tuple(f"line {n}" for n in range(30))).place(
            Canvas(), whole_frame()
        )
        assert placed.rows == 20
        assert isinstance(placed.remainder, Lines)
        assert len(placed.remainder.entries) == 10


class TestAListing:
    WIDE = [
        MenuItem(text="*3#", detail="Forecast by name"),
        MenuItem(text="*321<geoname-id>#", detail="One place"),
    ]

    def test_two_columns_and_nothing_to_choose(self) -> None:
        canvas = Canvas()
        placed = Listing(entries=self.WIDE).place(canvas, whole_frame())
        assert not placed.claim.choices
        assert "*3#" in said(canvas)[0]
        assert "Forecast by name" in said(canvas)[0]

    def test_the_column_is_set_once_and_carried(self) -> None:
        #  Or the second frame would set its own from the entries left on it,
        #  and a table would step sideways part way down.
        listing = Listing(entries=self.WIDE * 15)
        placed = listing.place(Canvas(), whole_frame())
        assert isinstance(placed.remainder, Listing)
        assert placed.remainder.column == listing.column

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
        assert isinstance(placed.remainder, Figures)
        assert (placed.remainder.label_width, placed.remainder.figure_width) == (
            figures.label_width,
            figures.figure_width,
        )


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
        assert isinstance(placed.remainder, Prose)


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
        assert placed.claim.choices == {"1": at("82489493")}
        assert "Post 489493" in said(canvas)[0]

    def test_and_satisfies_the_protocol_at_runtime(self) -> None:
        assert isinstance(self.Post(1), Entry)


class TestAServiceWithItsOwnShape:
    """A formatter of its own, for content no shape here fits.

    What `weather-viewdata` does for a forecast day four rows tall with a
    picture in it: say how tall an entry is, and how to draw one.
    """

    @dataclass(frozen=True, kw_only=True)
    class Blocks(SequencePart[str]):
        rows_per_entry: ClassVar[int] = 3
        gap: ClassVar[int] = 1

        def draw_entry(
            self, canvas: Canvas, row: int, entry: str, digit: str | None = None
        ) -> None:
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
            Canvas(), Space(first_row=2, rows=10, choices=CHOICES_PER_FRAME)
        )
        #  Ten rows holds two whole entries and the blank between them.
        assert placed.rows == 7
        assert isinstance(placed.remainder, self.Blocks)
        assert list(placed.remainder.entries) == list("cdefg")
