"""Redrawing part of a frame that is already on screen.

The rules here were measured against real Commstar rather than reasoned out;
`docs/spikes/spike_suggestion_block.py` is the record, and one of them would
never have been guessed.
"""

import pytest

from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import COLUMNS, Frame
from sextile.viewdata.repaint import changed_rows, rows_bytes, typed_bytes

HOME = bytes([ScreenControl.CURSOR_HOME])
DOWN = bytes([ScreenControl.LINE_FEED])
RETURN = bytes([ScreenControl.CARRIAGE_RETURN])
RIGHT = bytes([ScreenControl.CURSOR_RIGHT])
ON = bytes([ScreenControl.CURSOR_ON])
OFF = bytes([ScreenControl.CURSOR_OFF])
LEFT = bytes([ScreenControl.CURSOR_LEFT])


def frame_saying(**rows: str) -> Frame:
    frame = Frame()
    for name, text in rows.items():
        frame.write(int(name.removeprefix("row")), 0, text)
    return frame


class TestReachingARow:
    def test_the_first_row_is_reached_from_home(self) -> None:
        frame = frame_saying(row4="HELLO")
        assert rows_bytes(frame, [4]) == OFF + HOME + DOWN * 4 + b"HELLO"

    def test_the_next_is_a_return_and_a_step(self) -> None:
        frame = frame_saying(row4="ONE", row5="TWO")
        sent = rows_bytes(frame, [4, 5])
        assert sent == OFF + HOME + DOWN * 4 + b"ONE" + RETURN + DOWN + b"TWO"

    def test_and_a_row_stepped_over_costs_one_step_more(self) -> None:
        frame = frame_saying(row4="ONE", row6="THREE")
        sent = rows_bytes(frame, [4, 6])
        assert sent == OFF + HOME + DOWN * 4 + b"ONE" + RETURN + DOWN * 2 + b"THREE"

    def test_no_rows_is_no_bytes(self) -> None:
        assert rows_bytes(Frame(), []) == b""


class TestNotFillingARow:
    """The finding the spike existed to make.

    A row written to all forty columns wraps by itself, so a cursor down after
    it moves down a second row. A three-row block written full width lands on
    rows 4, 6 and 8.
    """

    def test_a_row_stops_at_what_is_written(self) -> None:
        frame = frame_saying(row4="HELLO")
        assert rows_bytes(frame, [4]).endswith(b"HELLO")

    def test_a_row_that_does_fill_the_line_is_accounted_for(self) -> None:
        #  Not refused: it is a legitimate row. The wrap has already put the
        #  cursor at column zero of the next row, so the step after it costs
        #  neither a carriage return nor a cursor down.
        frame = Frame()
        frame.write(4, 0, "A" * COLUMNS)
        frame.write(5, 0, "B")
        assert rows_bytes(frame, [4, 5]) == OFF + HOME + DOWN * 4 + b"A" * COLUMNS + b"B"

    def test_and_a_row_stepped_over_after_one_costs_one_step_fewer(self) -> None:
        frame = Frame()
        frame.write(4, 0, "A" * COLUMNS)
        frame.write(6, 0, "C")
        assert rows_bytes(frame, [4, 6]) == OFF + HOME + DOWN * 4 + b"A" * COLUMNS + DOWN + b"C"

    def test_a_blank_row_costs_only_the_move(self) -> None:
        assert rows_bytes(Frame(), [4]) == OFF + HOME + DOWN * 4


class TestBlankingWhatAShorterRowVacates:
    """A row that has grown shorter must cover what it used to say.

    On a suggestion list that is a place the reader has typed past, still
    offering itself under a digit that now means something else.
    """

    def test_the_tail_of_the_longer_thing_is_covered(self) -> None:
        was = frame_saying(row4="TRONDHEIMSFJORDEN")
        now = frame_saying(row4="TRONDHEIM")
        sent = rows_bytes(now, [4], was=was)
        assert sent == OFF + HOME + DOWN * 4 + b"TRONDHEIM" + b" " * len("SFJORDEN")

    def test_a_row_that_has_grown_is_sent_whole(self) -> None:
        was = frame_saying(row4="TRO")
        now = frame_saying(row4="TRONDHEIM")
        assert rows_bytes(now, [4], was=was).endswith(b"TRONDHEIM")

    def test_without_the_old_frame_nothing_is_blanked(self) -> None:
        #  Right for a first draw, where there is nothing on screen to cover.
        now = frame_saying(row4="TRONDHEIM")
        assert rows_bytes(now, [4]).endswith(b"TRONDHEIM")


class TestPuttingTheCursorBack:
    def test_the_caret_goes_where_it_is_asked(self) -> None:
        frame = frame_saying(row4="HELLO")
        sent = rows_bytes(frame, [4], caret=(2, 13))
        assert sent.endswith(HOME + DOWN * 2 + RIGHT * 13 + ON)

    def test_and_is_turned_on(self) -> None:
        #  Every frame begins by hiding it; a field is the one place a reader
        #  needs to see where the next letter lands.
        assert rows_bytes(frame_saying(row4="X"), [4], caret=(0, 0)).endswith(ON)

    def test_none_asked_for_leaves_it_alone(self) -> None:
        assert not rows_bytes(frame_saying(row4="X"), [4]).endswith(ON)

    def test_a_column_off_the_row_is_refused(self) -> None:
        with pytest.raises(ValueError):
            rows_bytes(frame_saying(row4="X"), [4], caret=(0, COLUMNS + 1))


class TestOnlyWhatChanged:
    def test_a_row_that_is_the_same_is_not_listed(self) -> None:
        was = frame_saying(row4="ONE", row5="TWO")
        now = frame_saying(row4="ONE", row5="THREE")
        assert changed_rows(was, now, range(4, 6)) == [5]

    def test_a_row_outside_the_region_is_not_looked_at(self) -> None:
        was = frame_saying(row4="ONE", row9="NINE")
        now = frame_saying(row4="ONE")
        assert changed_rows(was, now, range(4, 6)) == []

    def test_they_come_back_in_order(self) -> None:
        was = Frame()
        now = frame_saying(row6="SIX", row4="FOUR")
        assert changed_rows(was, now, {6, 4}) == [4, 6]

    def test_nothing_changed_is_nothing_to_send(self) -> None:
        same = frame_saying(row4="ONE")
        assert rows_bytes(same, changed_rows(same, same, range(4, 6))) == b""


class TestHidingTheCursorWhileRowsPaint:
    """A cursor left on while several rows redraw trails across them.

    Every whole frame begins by hiding it, for the same reason. A block repaint
    is smaller but no less visible: it is the part of the screen the reader is
    looking at.
    """

    def test_a_repaint_hides_it_first(self) -> None:
        sent = rows_bytes(frame_saying(row4="HELLO"), [4])
        assert sent.startswith(OFF)

    def test_and_the_caret_turns_it_back_on(self) -> None:
        sent = rows_bytes(frame_saying(row4="HELLO"), [4], caret=(2, 3))
        assert sent.startswith(OFF)
        assert sent.endswith(ON)

    def test_painting_nothing_touches_nothing(self) -> None:
        assert rows_bytes(Frame(), []) == b""


class TestOneCharacterTyped:
    """What the command line has done since it was written.

    A reader typing into a field changes one cell. Repainting the row costs
    thirty-odd bytes and a visible flicker; sending the character costs one,
    because the cursor is already where it goes.
    """

    def test_a_character_appended_costs_one_byte(self) -> None:
        was = frame_saying(row4="TRO")
        now = frame_saying(row4="TROM")
        assert typed_bytes(was, now, 4, at=3) == b"M"

    def test_a_character_rubbed_out_costs_three(self) -> None:
        #  Cursor left, a space over what was there, cursor left again. The
        #  space takes the row's background, the attribute that set it sitting
        #  earlier in the row and going untouched.
        was = frame_saying(row4="TROM")
        now = frame_saying(row4="TRO")
        assert typed_bytes(was, now, 4, at=4) == LEFT + b" " + LEFT

    def test_a_row_that_changed_some_other_way_is_not_a_keystroke(self) -> None:
        was = frame_saying(row4="TROM")
        now = frame_saying(row4="OSLO")
        assert typed_bytes(was, now, 4, at=4) is None

    def test_nor_is_a_change_away_from_the_cursor(self) -> None:
        #  The trick works only because the cursor is already there. Anywhere
        #  else and the character would land in the wrong place.
        was = frame_saying(row4="TRO")
        now = frame_saying(row4="TROM")
        assert typed_bytes(was, now, 4, at=9) is None

    def test_an_unchanged_row_is_nothing_to_send(self) -> None:
        same = frame_saying(row4="TRO")
        assert typed_bytes(same, same, 4, at=3) == b""
