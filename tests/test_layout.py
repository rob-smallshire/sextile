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
    Image,
    Link,
    ListItem,
    Paragraph,
    PostContent,
    Quote,
)
from sextile.viewdata.frame import COLUMNS, Frame
from sextile.viewdata.layout import BODY_ROWS, lay_out


def text_of(frame: Frame) -> str:
    characters, _ = frame.to_grid()
    return "\n".join(characters)


def body_of(frame: Frame) -> list[str]:
    characters, _ = frame.to_grid()
    return [line.rstrip() for line in characters[:BODY_ROWS] if line.strip()]


class TestFittingOnOneFrame:
    def test_a_short_post_makes_one_frame(self) -> None:
        content = PostContent(blocks=(Paragraph(("Short and sweet.",)),))
        assert len(lay_out(content)) == 1

    def test_the_text_appears(self) -> None:
        content = PostContent(blocks=(Paragraph(("Short and sweet.",)),))
        assert "Short and sweet." in text_of(lay_out(content)[0])

    def test_nothing_at_all_still_makes_one_frame(self) -> None:
        #  A frame that says nothing is better than no frame to send.
        assert len(lay_out(PostContent(blocks=()))) == 1

    def test_long_lines_are_wrapped_to_the_frame(self) -> None:
        content = PostContent(blocks=(Paragraph(("word " * 40,)),))
        for frame in lay_out(content):
            for line in body_of(frame):
                assert len(line) <= COLUMNS


class TestContinuation:
    def test_a_long_post_spills_onto_further_frames(self) -> None:
        content = PostContent(blocks=tuple(Paragraph((f"line {n}",)) for n in range(40)))
        assert len(lay_out(content)) > 1

    def test_no_text_is_lost_across_frames(self) -> None:
        content = PostContent(blocks=tuple(Paragraph((f"marker{n}",)) for n in range(30)))
        rendered = "\n".join(text_of(frame) for frame in lay_out(content))
        for n in range(30):
            assert f"marker{n}" in rendered

    def test_nothing_is_repeated_across_frames(self) -> None:
        content = PostContent(blocks=tuple(Paragraph((f"marker{n}",)) for n in range(30)))
        frames = lay_out(content)
        rendered = "\n".join(text_of(frame) for frame in frames)
        assert rendered.count("marker7") == 1

    def test_every_frame_covers_the_whole_screen(self) -> None:
        #  Trailing blanks are trimmed off the wire, but the grid behind them is
        #  always the full 24 by 40.
        content = PostContent(blocks=tuple(Paragraph((f"line {n}",)) for n in range(40)))
        for frame in lay_out(content):
            assert len(frame.to_bytes(trim=False)) == 2 + 24 * COLUMNS

    def test_a_post_needing_more_than_twenty_six_frames_is_truncated_visibly(self) -> None:
        #  A page has frames a-z and no more. Running out must be said, not
        #  silently swallowed.
        content = PostContent(blocks=tuple(Paragraph((f"line {n}",)) for n in range(2000)))
        frames = lay_out(content)
        assert len(frames) <= 26
        assert "TRUNCATED" in text_of(frames[-1]).upper()


class TestBlockKinds:
    def test_a_quotation_is_marked(self) -> None:
        content = PostContent(blocks=(Quote((Paragraph(("Someone else said this.",)),)),))
        assert "Someone else said this." in text_of(lay_out(content)[0])

    def test_a_nested_quotation_is_indented_further(self) -> None:
        content = PostContent(
            blocks=(Quote((Paragraph(("outer",)), Quote((Paragraph(("inner",)),)))),)
        )
        lines = body_of(lay_out(content)[0])
        outer = next(line for line in lines if "outer" in line)
        inner = next(line for line in lines if "inner" in line)
        assert _indent(inner) > _indent(outer)

    def test_deep_nesting_does_not_run_out_of_columns(self) -> None:
        content = PostContent(blocks=(_nested(8, Paragraph(("deep",))),))
        lines = body_of(lay_out(content)[0])
        assert any("deep" in line for line in lines)
        assert all(len(line) <= COLUMNS for line in lines)

    def test_code_is_shown(self) -> None:
        content = PostContent(blocks=(Code(("LDA #&19",)),))
        assert "LDA #&19" in text_of(lay_out(content)[0])

    def test_an_image_is_announced_rather_than_omitted(self) -> None:
        content = PostContent(blocks=(Image("cap1.png"),))
        rendered = text_of(lay_out(content)[0])
        assert "cap1.png" in rendered
        assert "IMAGE" in rendered.upper()

    def test_an_attachment_is_announced(self) -> None:
        content = PostContent(blocks=(Attachment("BtLoader 1.ssd"),))
        rendered = text_of(lay_out(content)[0])
        assert "BtLoader 1.ssd" in rendered

    def test_a_list_item_is_marked(self) -> None:
        content = PostContent(blocks=(ListItem("first"),))
        assert "first" in text_of(lay_out(content)[0])


class TestLinks:
    def test_links_are_listed_after_the_text(self) -> None:
        content = PostContent(
            blocks=(Paragraph(("See this [1].",)),),
            links=(Link(1, "", "https://stardot.org.uk/x"),),
        )
        rendered = "\n".join(text_of(frame) for frame in lay_out(content))
        assert "stardot.org.uk/x" in rendered

    def test_a_post_with_no_links_lists_none(self) -> None:
        content = PostContent(blocks=(Paragraph(("Nothing here.",)),))
        assert "[1]" not in text_of(lay_out(content)[0])


class TestEveryByteIsSendable:
    def test_no_frame_carries_an_eighth_bit(self) -> None:
        content = PostContent(
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
    content = PostContent(blocks=tuple(Paragraph((f"m{n}",)) for n in range(rows)))
    rendered = "\n".join(text_of(frame) for frame in lay_out(content))
    for n in range(rows):
        assert f"m{n}" in rendered
