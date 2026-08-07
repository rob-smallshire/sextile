"""Breaking text into lines that fit a viewdata frame.

Forty columns is narrow, and forum posts contain URLs, hex dumps and assembler
listings that no amount of politeness will fit. So the hard cases -- a word
longer than the whole line -- are the point rather than the exception.
"""

import pytest

from sextile.viewdata.wrapping import wrap_text


class TestOrdinaryWrapping:
    def test_short_text_is_one_line(self) -> None:
        assert wrap_text("STARDOT", 40) == ["STARDOT"]

    def test_empty_text_is_no_lines(self) -> None:
        assert wrap_text("", 40) == []

    def test_whitespace_only_is_no_lines(self) -> None:
        assert wrap_text("   \t  ", 40) == []

    def test_text_breaks_at_a_space(self) -> None:
        assert wrap_text("the quick brown fox", 10) == ["the quick", "brown fox"]

    def test_a_line_may_fill_the_width_exactly(self) -> None:
        assert wrap_text("abcde fghij", 5) == ["abcde", "fghij"]

    def test_runs_of_whitespace_collapse(self) -> None:
        assert wrap_text("one    two", 20) == ["one two"]

    def test_no_line_has_leading_or_trailing_space(self) -> None:
        lines = wrap_text("  the   quick brown   fox  ", 10)
        assert all(line == line.strip() for line in lines)

    @pytest.mark.parametrize("width", [1, 2, 5, 10, 39, 40])
    def test_no_line_exceeds_the_width(self, width: int) -> None:
        text = "The Acorn NS32016 second processor board runs at 8MHz nominally"
        assert all(len(line) <= width for line in wrap_text(text, width))

    def test_every_word_survives(self) -> None:
        text = "the quick brown fox jumps over the lazy dog"
        assert " ".join(wrap_text(text, 12)).split() == text.split()


class TestUnbreakableWords:
    def test_a_word_longer_than_the_width_is_split(self) -> None:
        assert wrap_text("ABCDEFGHIJ", 4) == ["ABCD", "EFGH", "IJ"]

    def test_a_long_word_starts_on_its_own_line(self) -> None:
        assert wrap_text("hi ABCDEFGHIJ", 5) == ["hi", "ABCDE", "FGHIJ"]

    def test_a_url_is_split_rather_than_lost(self) -> None:
        url = "https://stardot.org.uk/forums/viewtopic.php?p=489493"
        lines = wrap_text(url, 40)
        assert "".join(lines) == url
        assert all(len(line) <= 40 for line in lines)

    def test_text_continues_after_a_split_word(self) -> None:
        assert wrap_text("ABCDEFGH then more", 4) == ["ABCD", "EFGH", "then", "more"]


class TestInvalidWidths:
    @pytest.mark.parametrize("width", [0, -1])
    def test_a_width_of_less_than_one_is_rejected(self, width: int) -> None:
        with pytest.raises(ValueError, match="width"):
            wrap_text("text", width)
