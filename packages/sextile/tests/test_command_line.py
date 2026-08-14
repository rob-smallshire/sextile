"""The command line a reader types a page request into.

Commstar does not echo `*123#`, so a reader cannot see what they have typed
unless Sextile draws it. It replaces the footer while a request is being
entered, which makes the mode change visible and gives `**` somewhere to be
explained -- there being nowhere in the ordinary footer to say so.
"""

import pytest

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.command_line import (
    BUFFER_CELLS,
    CANCEL_HINT,
    command_line_bytes,
    draw_command_line,
)
from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import COLUMNS, FOOTER_ROW


def drawn(entry: str) -> tuple[str, str]:
    canvas = Canvas()
    draw_command_line(canvas, entry)
    characters, attributes = canvas.frame.to_grid()
    return characters[FOOTER_ROW], attributes[FOOTER_ROW]


class TestWhatIsShown:
    def test_the_entry_appears(self) -> None:
        characters, _ = drawn("*123")
        assert "*123" in characters

    def test_the_cancel_hint_is_at_the_right(self) -> None:
        characters, _ = drawn("*123")
        assert characters.rstrip().endswith(CANCEL_HINT)

    def test_a_bare_star_shows_an_empty_buffer(self) -> None:
        characters, _ = drawn("*")
        assert characters.startswith("   *")
        assert CANCEL_HINT in characters

    def test_the_row_is_filled_to_its_width(self) -> None:
        characters, _ = drawn("*1")
        assert len(characters) == COLUMNS


class TestColour:
    def test_the_buffer_is_white_on_blue(self) -> None:
        _, attributes = drawn("*123")
        #  Alpha blue, then new background, then alpha white: three cells to say
        #  white on blue, since a background can only be taken from a foreground.
        assert attributes[:3] == "D]G"

    def test_the_hint_is_yellow_on_black(self) -> None:
        _, attributes = drawn("*123")
        assert "\\C" in attributes.replace("]", "]")  # black background, then yellow

    def test_the_hint_returns_the_background_to_black(self) -> None:
        _, attributes = drawn("*123")
        #  0x1C travels as backslash; it must come before the yellow.
        assert attributes.index("\\") < attributes.index("C")


class TestABufferThatWillNotFit:
    def test_the_buffer_area_is_what_is_left_after_the_hint(self) -> None:
        assert COLUMNS - 3 - 2 - len(CANCEL_HINT) == BUFFER_CELLS

    def test_an_over_long_entry_shows_its_tail(self) -> None:
        #  What was typed most recently is what a reader is checking.
        entry = "*" + "9" * 40
        characters, _ = drawn(entry)
        assert entry[-BUFFER_CELLS:] in characters

    def test_an_over_long_entry_does_not_disturb_the_hint(self) -> None:
        characters, _ = drawn("*" + "9" * 40)
        assert characters.rstrip().endswith(CANCEL_HINT)

    def test_the_row_never_overflows(self) -> None:
        for length in range(0, 60):
            characters, _ = drawn("*" + "9" * length)
            assert len(characters) == COLUMNS


class TestTheBytesSent:
    def test_it_goes_to_the_footer_row_in_two_bytes(self) -> None:
        #  Home, then cursor up, which wraps to the bottom. Measured; see
        #  docs/viewdata-encoding.md.
        sent = command_line_bytes("*1")
        assert sent[:2] == bytes([ScreenControl.CURSOR_HOME, ScreenControl.CURSOR_UP])

    def test_it_leaves_the_cursor_on(self) -> None:
        #  The one place in the service a cursor tells a reader anything: it
        #  marks where the next character will land.
        assert command_line_bytes("*1").endswith(bytes([ScreenControl.CURSOR_ON]))

    def test_it_does_not_clear_the_screen(self) -> None:
        #  The page beneath must survive: that is the whole point.
        assert ScreenControl.CLEAR_SCREEN not in command_line_bytes("*1")

    def test_every_byte_survives_a_seven_bit_line(self) -> None:
        assert all(byte < 0x80 for byte in command_line_bytes("*123456"))

    @pytest.mark.parametrize("entry", ["*", "*1", "*82489493", "*" + "9" * 40])
    def test_it_is_small_enough_to_send_on_every_keystroke(self, entry: str) -> None:
        #  About fifty bytes: a few milliseconds at 9600 baud, and under half a
        #  second even at 1200.
        assert len(command_line_bytes(entry)) < 100
