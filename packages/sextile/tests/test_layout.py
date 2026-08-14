"""Parts laid out down the frames of a page.

The fill pass alone: what goes on which frame, and what each frame claims.
Nothing here draws furniture, which is the other pass and knows the count.

See docs/page-layout.md.
"""

from dataclasses import dataclass

import pytest

from sextile.addressing import PageAddress
from sextile.layout import Break, Every, Flowing, Offer, Once, Placement, Room, fill
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.footer import FooterItem, Priority

CONTENT = range(2, 22)


@dataclass(frozen=True)
class Says:
    """A fixed part of one row a frame, saying what it was told to say."""

    said: str
    rows: int = 1

    def place(self, canvas: Canvas, room: Room) -> Placement:
        if room.rows < self.rows:
            return Placement(rows=0, rest=self)
        for offset in range(self.rows):
            canvas.row(room.first_row + offset).text(self.said, Colour.WHITE)
        return Placement(rows=self.rows)


@dataclass(frozen=True)
class Counts:
    """A flowing part of one row an item, which claims a digit for each."""

    items: tuple[str, ...]

    def place(self, canvas: Canvas, room: Room) -> Placement:
        taken = min(room.rows, room.choices, len(self.items))
        for offset, item in enumerate(self.items[:taken]):
            canvas.row(room.first_row + offset).text(item, Colour.WHITE)
        rest = self.items[taken:]
        return Placement(
            rows=taken,
            offer=Offer(
                choices={str(n + 1): PageAddress(f"8{n}") for n in range(taken)},
                named=[FooterItem("1-9", "select", Priority.PRIMARY)] if taken else [],
            ),
            rest=Counts(rest) if rest else None,
        )


@dataclass(frozen=True)
class Recites:
    """A flowing part of one row a line, which chooses nothing.

    Bound by the rows rather than by the digits, where `Counts` is bound by
    both -- which is the difference between prose and a menu.
    """

    lines: tuple[str, ...]

    def place(self, canvas: Canvas, room: Room) -> Placement:
        taken = min(room.rows, len(self.lines))
        for offset, line in enumerate(self.lines[:taken]):
            canvas.row(room.first_row + offset).text(line, Colour.WHITE)
        rest = self.lines[taken:]
        return Placement(rows=taken, rest=Recites(rest) if rest else None)


def said_on(frames: list[Canvas], index: int) -> list[str]:
    characters, _ = frames[index].frame.to_grid()
    return [row.strip() for row in characters if row.strip()]


def items(count: int) -> Counts:
    return Counts(tuple(f"item {n}" for n in range(1, count + 1)))


def lines(count: int) -> Recites:
    return Recites(tuple(f"line {n}" for n in range(1, count + 1)))


class TestOnePartOnOneFrame:
    def test_a_part_that_fits_gives_one_frame(self) -> None:
        filled = fill([Once(Says("hello"))], CONTENT)
        assert len(filled) == 1
        assert said_on([one.canvas for one in filled], 0) == ["hello"]

    def test_nothing_at_all_is_still_one_frame(self) -> None:
        #  A page that answered with no frames could not be shown.
        assert len(fill([], CONTENT)) == 1

    def test_a_part_claims_what_it_offers(self) -> None:
        filled = fill([Flowing(items(3))], CONTENT)
        assert filled[0].offer.choices == {
            "1": PageAddress("80"),
            "2": PageAddress("81"),
            "3": PageAddress("82"),
        }


class TestAPartThatFlows:
    def test_it_goes_on_to_as_many_frames_as_it_takes(self) -> None:
        #  Twenty rows a frame, and the part claims a digit for each row, so
        #  nine to a frame is the choices talking rather than the rows.
        filled = fill([Flowing(items(20))], CONTENT)
        assert len(filled) == 3
        assert len(said_on([one.canvas for one in filled], 0)) == 9
        assert len(said_on([one.canvas for one in filled], 2)) == 2

    def test_the_digits_begin_again_on_each_frame(self) -> None:
        filled = fill([Flowing(items(12))], CONTENT)
        assert set(filled[0].offer.choices) == {str(n) for n in range(1, 10)}
        assert set(filled[1].offer.choices) == {"1", "2", "3"}

    def test_two_flowing_parts_follow_one_another(self) -> None:
        #  Concatenation: the second begins in the row after the first has
        #  finished, on whatever frame that is.
        filled = fill([Flowing(items(5)), Flowing(Counts(("and", "then")))], CONTENT)
        assert len(filled) == 1
        assert said_on([one.canvas for one in filled], 0)[-2:] == ["and", "then"]


class TestOnceAndEvery:
    def test_once_is_drawn_on_the_first_frame_only(self) -> None:
        filled = fill([Once(Says("lead-in")), Flowing(items(12))], CONTENT)
        assert said_on([one.canvas for one in filled], 0)[0] == "lead-in"
        assert "lead-in" not in said_on([one.canvas for one in filled], 1)

    def test_every_is_drawn_on_all_of_them(self) -> None:
        filled = fill([Every(Says("headings")), Flowing(items(12))], CONTENT)
        for index in range(len(filled)):
            assert said_on([one.canvas for one in filled], index)[0] == "headings"

    def test_a_trailing_every_keeps_its_rows_on_every_frame(self) -> None:
        #  Charged before the flowing part is asked, or the flow takes the rows
        #  the footnote needs and writes over it. A part bound by rows rather
        #  than by digits, since it is the rows that are at stake.
        without = fill([Flowing(lines(40))], CONTENT)
        with_note = fill([Flowing(lines(40)), Every(Says("a note", rows=3))], CONTENT)
        assert len(without) == 2
        assert len(with_note) == 3
        for index in range(len(with_note)):
            assert "a note" in said_on([one.canvas for one in with_note], index)

    def test_once_after_a_flow_lands_where_the_flow_finished(self) -> None:
        #  `once` means once, not first.
        filled = fill([Flowing(items(12)), Once(Says("and that is all"))], CONTENT)
        assert "and that is all" not in said_on([one.canvas for one in filled], 0)
        assert "and that is all" in said_on([one.canvas for one in filled], 1)


class TestABreak:
    def test_what_follows_begins_on_a_new_frame(self) -> None:
        filled = fill([Flowing(items(2)), Break(), Flowing(items(2))], CONTENT)
        assert len(filled) == 2
        assert len(said_on([one.canvas for one in filled], 0)) == 2

    def test_a_break_at_either_end_divides_nothing(self) -> None:
        assert len(fill([Break(), Flowing(items(2))], CONTENT)) == 1
        assert len(fill([Flowing(items(2)), Break()], CONTENT)) == 1

    def test_and_nor_do_two_together(self) -> None:
        filled = fill([Flowing(items(2)), Break(), Break(), Flowing(items(2))], CONTENT)
        assert len(filled) == 2


class TestAPartTooTallForWhatIsLeft:
    def test_it_begins_the_next_frame_rather_than_being_split(self) -> None:
        #  Eighteen rows gone of twenty, and four wanted: it goes over whole.
        filled = fill([Flowing(lines(18)), Once(Says("four rows", rows=4))], CONTENT)
        assert len(filled) == 2
        assert "four rows" not in said_on([one.canvas for one in filled], 0)
        assert "four rows" in said_on([one.canvas for one in filled], 1)

    def test_a_part_taller_than_a_frame_is_refused(self) -> None:
        with pytest.raises(ValueError, match="never be placed"):
            fill([Once(Says("far too tall", rows=30))], CONTENT)
