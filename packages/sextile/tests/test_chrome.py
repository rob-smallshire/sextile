"""The furniture every frame carries.

Four of the twenty-four rows go to chrome: a header naming the page and its
number, a rule beneath it, a rule above the footer, and the footer's navigation
prompt. That leaves twenty rows of content, which is the budget every page
builder works to.

The header is where a reader looks to know where they are, so the page number
must survive however long the title is.
"""

import pytest

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import (
    CONTENT_FIRST_ROW,
    CONTENT_ROWS,
    FOOTER_ROW,
    HEADER_ROW,
    SERVICE_NAME,
    draw_chrome,
)
from sextile.viewdata.frame import COLUMNS, ROWS


def rows_of(canvas: Canvas) -> list[str]:
    characters, _ = canvas.frame.to_grid()
    return characters


def attributes_of(canvas: Canvas) -> list[str]:
    _, attributes = canvas.frame.to_grid()
    return attributes


class TestGeometry:
    def test_content_occupies_twenty_rows(self) -> None:
        assert CONTENT_ROWS == 20

    def test_the_chrome_and_the_content_account_for_the_whole_frame(self) -> None:
        assert CONTENT_FIRST_ROW + CONTENT_ROWS + 2 == ROWS

    def test_the_footer_is_the_last_row(self) -> None:
        assert FOOTER_ROW == ROWS - 1


class TestHeader:
    def test_the_title_appears(self) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title="PROGRAMMING", page_number="4254", prompt="")
        assert "PROGRAMMING" in rows_of(canvas)[HEADER_ROW]

    def test_the_page_number_is_at_the_right(self) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title="PROGRAMMING", page_number="4254a", prompt="")
        assert rows_of(canvas)[HEADER_ROW].rstrip().endswith("4254a")

    def test_a_long_title_is_truncated_rather_than_pushing_out_the_number(self) -> None:
        #  Forum names on Stardot run to forty characters on their own.
        canvas = Canvas()
        draw_chrome(
            canvas,
            title="8-bit acorn software: games - high scores",
            page_number="82489493a",
            prompt="",
        )
        header = rows_of(canvas)[HEADER_ROW]
        assert header.rstrip().endswith("82489493a")
        assert len(header) == COLUMNS

    def test_a_frame_that_is_not_a_page_needs_no_number(self) -> None:
        #  Not everything on screen is a page. A notice drawn in reply to a
        #  keypress has no number, and inventing one would tell the reader to
        #  key something that fetches nothing.
        canvas = Canvas()
        draw_chrome(canvas, title="UNKNOWN PAGE", page_number="", prompt="")
        assert rows_of(canvas)[HEADER_ROW].rstrip().endswith("UNKNOWN PAGE")

    def test_the_title_and_the_number_never_collide(self) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title="X" * 60, page_number="123456789012", prompt="")
        header = rows_of(canvas)[HEADER_ROW]
        assert "X123456789012" not in header

    def test_the_service_is_named_when_a_page_has_no_title_of_its_own(self) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title="", page_number="1", prompt="")
        assert SERVICE_NAME in rows_of(canvas)[HEADER_ROW]


class TestRules:
    def test_rules_are_drawn_in_mosaic_graphics(self) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title="T", page_number="1", prompt="")
        attributes = attributes_of(canvas)
        #  Graphics colours travel as Q-W.
        assert any(cell in "QRSTUVW" for cell in attributes[HEADER_ROW + 1])
        assert any(cell in "QRSTUVW" for cell in attributes[FOOTER_ROW - 1])


class TestFooter:
    def test_the_prompt_appears(self) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title="T", page_number="1", prompt="Key 1-9, or *1# for index")
        assert "Key 1-9" in rows_of(canvas)[FOOTER_ROW]

    def test_an_over_long_prompt_is_truncated_to_the_row(self) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title="T", page_number="1", prompt="p" * 100)
        assert len(rows_of(canvas)[FOOTER_ROW]) == COLUMNS


class TestContentIsLeftAlone:
    def test_chrome_writes_nothing_into_the_content_rows(self) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title="T", page_number="1", prompt="P")
        content = rows_of(canvas)[CONTENT_FIRST_ROW : CONTENT_FIRST_ROW + CONTENT_ROWS]
        assert all(not row.strip() for row in content)


class TestSendability:
    @pytest.mark.parametrize(
        ("title", "number"),
        [("", "1"), ("PROGRAMMING", "4254"), ("£ ½ café", "82489493z")],
    )
    def test_every_byte_survives_a_seven_bit_line(self, title: str, number: str) -> None:
        canvas = Canvas()
        draw_chrome(canvas, title=title, page_number=number, prompt="Key # for more")
        assert all(byte < 0x80 for byte in canvas.frame.to_bytes())
