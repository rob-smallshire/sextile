"""The warning that a silent line is about to be released.

A caller who has been reading one frame for ten minutes has no way of knowing
the service is about to ring off, and being disconnected without warning on a
service that answers slowly is indistinguishable from a fault.

So the footer row becomes a bar that drains, with an instruction. It is drawn
over that row alone, like the command line, and only when what it would say has
changed -- a bar of twenty-five cells over several minutes changes about twice a
minute, and at 1200 baud a row costs a third of a second.
"""

import pytest

from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.idle_warning import (
    BAR_CELLS,
    RESUME_HINT,
    idle_warning_bytes,
    lit_cells,
)


def printable(data: bytes) -> str:
    return "".join(chr(byte) for byte in data if 0x20 <= byte < 0x7F)


class TestTheBar:
    def test_a_full_bar_when_all_the_time_remains(self) -> None:
        assert lit_cells(1.0) == BAR_CELLS

    def test_an_empty_bar_when_none_does(self) -> None:
        assert lit_cells(0.0) == 0

    def test_half_the_bar_for_half_the_time(self) -> None:
        assert lit_cells(0.5) == BAR_CELLS // 2

    def test_the_bar_drains_rather_than_filling(self) -> None:
        assert lit_cells(0.9) > lit_cells(0.1)

    @pytest.mark.parametrize("fraction", [-1.0, 2.0])
    def test_a_fraction_outside_its_range_is_clamped(self, fraction: float) -> None:
        assert 0 <= lit_cells(fraction) <= BAR_CELLS

    def test_the_last_of_the_time_still_shows_something(self) -> None:
        #  A bar that empties before the line drops would say the service had
        #  already gone.
        assert lit_cells(0.01) >= 1


class TestTheRow:
    def test_it_says_what_to_do(self) -> None:
        assert RESUME_HINT in printable(idle_warning_bytes(0.5))

    def test_it_fits_the_row_exactly(self) -> None:
        #  Attributes occupy cells, so the arithmetic has to come out at forty.
        assert 1 + len(RESUME_HINT) + 2 + 1 + BAR_CELLS == COLUMNS

    def test_it_is_drawn_over_the_footer_row_alone(self) -> None:
        #  No clear-screen: the page beneath has to survive, or there was no
        #  point drawing a row.
        assert 0x0C not in idle_warning_bytes(0.5)

    def test_every_byte_survives_a_seven_bit_line(self) -> None:
        assert all(byte < 0x80 for byte in idle_warning_bytes(0.5))

    def test_a_fuller_bar_is_not_the_same_row_as_an_emptier_one(self) -> None:
        assert idle_warning_bytes(1.0) != idle_warning_bytes(0.2)

    def test_the_row_is_redrawn_in_full(self) -> None:
        #  Cells the bar has given up must be overwritten, not left lit.
        assert idle_warning_bytes(0.0).endswith(b" " * BAR_CELLS)
