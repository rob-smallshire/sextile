"""Sequences formatted as parts of a page.

What a formatter does with the room it is given: how many entries go in it,
which of them can be chosen, and what is left for the next frame.

See docs/page-layout.md.
"""

from sextile.addressing import PageAddress
from sextile.formatting import Lines, Menu, MenuItem
from sextile.layout import CHOICES_PER_FRAME, Flowing, Once, PageLayout, Room
from sextile.viewdata.canvas import Canvas

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
