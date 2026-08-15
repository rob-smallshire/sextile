"""Laying blocks out as frames.

A post rarely fits one screen, so this is where the awkward decisions live: how
much room the chrome takes, what happens when a block lands on a boundary, and
what to do with a quotation nested four deep inside eighteen usable rows.

Colour carries structure here. A reader on a monochrome screen would still
follow the text; a reader in colour can tell at a glance whose words they are.
"""

import pytest

from sextile.content.blocks import (
    Attachment,
    Code,
    Document,
    Image,
    Link,
    ListItem,
    Paragraph,
    Quote,
)
from sextile.formatting import Prose
from sextile.layout import Flow, fill
from sextile.testing import text_of
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS, FRAME_PREAMBLE, ROWS, Frame
from sextile.viewdata.typesetting import rows_for

#: A whole frame, this module being about typesetting rather than furniture.
WHOLE = range(0, ROWS)


def lay_out(content: Document) -> list[Frame]:
    """The document as bare frames, with no furniture round it.

    A lens rather than a copy: the rendering is `rows_for`'s and the division
    between frames is the layout's, and this only puts the two together so a
    test can look at the result. `typesetting` used to do the dividing as well,
    which is what these tests were written against and is why they read as they
    do.
    """
    return [
        one.canvas.frame for one in fill([Flow(Prose(entries=rows_for(content)))], WHOLE)
    ]


#: Rows a frame gives the content, there being no furniture round it here.
BODY_ROWS = ROWS


def _drawn(content: Document) -> None:
    """Draw a document through the real drawing path, and discard it.

    For the tests that ask only whether something can be drawn at all: three
    captions crashed the service once, and what they crashed was the arithmetic
    about how wide a row is.
    """
    fill([Flow(Prose(entries=rows_for(content)))], WHOLE)


def body_of(frame: Frame) -> list[str]:
    characters, _ = frame.to_grid()
    return [line.rstrip() for line in characters if line.strip()]


class TestFittingOnOneFrame:
    def test_the_text_appears(self) -> None:
        content = Document(blocks=(Paragraph(("Short and sweet.",)),))
        assert "Short and sweet." in text_of(lay_out(content)[0])

    def test_long_lines_are_wrapped_to_the_frame(self) -> None:
        content = Document(blocks=(Paragraph(("word " * 40,)),))
        for frame in lay_out(content):
            for line in body_of(frame):
                assert len(line) <= COLUMNS


class TestContinuation:
    """What survives a document being divided between frames.

    How many frames there are, and that a page stops at twenty-six and says so,
    are the layout's and are tested there. What is tested here is what only a
    real document can show: that dividing one neither loses a row nor draws one
    twice.
    """

    def test_no_text_is_lost_across_frames(self) -> None:
        content = Document(blocks=tuple(Paragraph((f"marker{n}",)) for n in range(30)))
        rendered = "\n".join(text_of(frame) for frame in lay_out(content))
        for n in range(30):
            assert f"marker{n}" in rendered

    def test_nothing_is_repeated_across_frames(self) -> None:
        content = Document(blocks=tuple(Paragraph((f"marker{n}",)) for n in range(30)))
        frames = lay_out(content)
        rendered = "\n".join(text_of(frame) for frame in frames)
        assert rendered.count("marker7") == 1

    def test_every_frame_covers_the_whole_screen(self) -> None:
        #  Trailing blanks are trimmed off the wire, but the grid behind them is
        #  always the full 24 by 40.
        content = Document(blocks=tuple(Paragraph((f"line {n}",)) for n in range(40)))
        for frame in lay_out(content):
            assert len(frame.to_bytes(trim=False)) == len(FRAME_PREAMBLE) + 24 * COLUMNS


class TestBlockKinds:
    def test_a_quotation_is_marked(self) -> None:
        content = Document(blocks=(Quote((Paragraph(("Someone else said this.",)),)),))
        assert "Someone else said this." in text_of(lay_out(content)[0])

    def test_a_nested_quotation_is_indented_further(self) -> None:
        content = Document(
            blocks=(Quote((Paragraph(("outer",)), Quote((Paragraph(("inner",)),)))),)
        )
        lines = body_of(lay_out(content)[0])
        outer = next(line for line in lines if "outer" in line)
        inner = next(line for line in lines if "inner" in line)
        assert _indent(inner) > _indent(outer)

    def test_deep_nesting_does_not_run_out_of_columns(self) -> None:
        content = Document(blocks=(_nested(8, Paragraph(("deep",))),))
        lines = body_of(lay_out(content)[0])
        assert any("deep" in line for line in lines)
        assert all(len(line) <= COLUMNS for line in lines)

    def test_code_is_shown(self) -> None:
        content = Document(blocks=(Code(("LDA #&19",)),))
        assert "LDA #&19" in text_of(lay_out(content)[0])

    def test_an_image_is_announced_rather_than_omitted(self) -> None:
        content = Document(blocks=(Image("cap1.png"),))
        rendered = text_of(lay_out(content)[0])
        assert "cap1.png" in rendered
        assert "IMAGE" in rendered.upper()

    def test_an_attachment_is_announced(self) -> None:
        content = Document(blocks=(Attachment("BtLoader 1.ssd"),))
        rendered = text_of(lay_out(content)[0])
        assert "BtLoader 1.ssd" in rendered

    def test_a_list_item_is_marked(self) -> None:
        content = Document(blocks=(ListItem("first"),))
        assert "first" in text_of(lay_out(content)[0])


class TestLinks:
    def test_links_are_listed_after_the_text(self) -> None:
        content = Document(
            blocks=(Paragraph(("See this [1].",)),),
            links=(Link(1, "", "https://stardot.org.uk/x"),),
        )
        rendered = "\n".join(text_of(frame) for frame in lay_out(content))
        assert "stardot.org.uk/x" in rendered

    def test_a_post_with_no_links_lists_none(self) -> None:
        content = Document(blocks=(Paragraph(("Nothing here.",)),))
        assert "[1]" not in text_of(lay_out(content)[0])


class TestEveryByteIsSendable:
    def test_no_frame_carries_an_eighth_bit(self) -> None:
        content = Document(
            blocks=(
                Paragraph(("Straße café — “quoted” … 100°C",)),
                Code(("if (a[i] > 0) { x |= 1 << i; }",)),
            )
        )
        for frame in lay_out(content):
            assert all(byte < 0x80 for byte in frame.to_bytes())


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip())


def _nested(depth: int, inner: Paragraph) -> Quote:
    block: Quote = Quote((inner,))
    for _ in range(depth - 1):
        block = Quote((block,))
    return block


@pytest.mark.parametrize("rows", [BODY_ROWS - 1, BODY_ROWS, BODY_ROWS + 1])
def test_a_post_landing_exactly_on_a_boundary_loses_nothing(rows: int) -> None:
    content = Document(blocks=tuple(Paragraph((f"m{n}",)) for n in range(rows)))
    rendered = "\n".join(text_of(frame) for frame in lay_out(content))
    for n in range(rows):
        assert f"m{n}" in rendered


class TestEveryBlockIsWrapped:
    """The frame is forty cells wide whatever the block is.

    Images and attachments were the two that built a row without wrapping it,
    so a photograph with a long caption crashed the page -- and took the
    caller's whole session with it, since the handler raised.
    """

    def test_a_long_image_description_is_wrapped(self) -> None:
        content = Document(
            blocks=(Image("New socket sitting waiting for the soldering iron"),)
        )
        rows = rows_for(content)
        assert all(cell_count(row.text) + row.indent < COLUMNS for row in rows)

    def test_and_says_what_it_is_on_the_first_row(self) -> None:
        content = Document(blocks=(Image("A very long description indeed " * 3),))
        assert rows_for(content)[0].text.startswith("[IMAGE:")

    def test_a_long_attachment_name_is_wrapped(self) -> None:
        content = Document(blocks=(Attachment("vlcsnap-2026-08-02-17h29m56s151.png"),))
        rows = rows_for(content)
        assert all(cell_count(row.text) + row.indent < COLUMNS for row in rows)

    def test_nothing_of_the_description_is_lost(self) -> None:
        description = "Screenshot 2026-08-03 164815.png"
        rows = rows_for(Document(blocks=(Image(description),)))
        assert description in " ".join(row.text for row in rows)

    def test_one_inside_a_quotation_is_wrapped_to_the_room_left(self) -> None:
        #  Where the indent has already taken some of the row.
        content = Document(
            blocks=(Quote((Quote((Image("A caption of some considerable length"),)),)),)
        )
        rows = rows_for(content)
        assert all(cell_count(row.text) + row.indent < COLUMNS for row in rows)


class TestDrawingWhatWasRendered:
    """The reported crash, reproduced.

    A post with a long image caption raised out of `draw_rows`, which took the
    caller's whole session with it. The rows a paginator hands back must always
    be drawable: that is the contract between the two halves.
    """

    def test_a_long_caption_can_be_drawn(self) -> None:
        content = Document(
            blocks=(Image("New socket sitting waiting for the soldering iron"),)
        )
        _drawn(content)

    def test_a_caption_with_a_character_that_widens_can_be_drawn(self) -> None:
        #  The second bug, from the same crash: `…` is drawn as three cells.
        content = Document(blocks=(Paragraph(("attribute keywords (L, W, R, WR, …)",)),))
        _drawn(content)

    @pytest.mark.parametrize(
        "description",
        [
            "Screenshot 2026-08-03 164815.png",
            "vlcsnap-2026-08-02-17h29m56s151.png",
            "Scherm\xadafbeelding 2026-07-21 om 14.27.11.png",
            "This has fought me to its dying breath",
            "New socket sitting waiting for the 'iron",
        ],
    )
    def test_the_captions_that_crashed_the_service(self, description: str) -> None:
        #  Taken from the archive, by rendering every post it holds and keeping
        #  the ones that raised.
        _drawn(Document(blocks=(Image(description),)))
