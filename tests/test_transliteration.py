"""Turning arbitrary Unicode from forum posts into characters G0 can display.

The rule is that transliteration is total: whatever goes in, what comes out is
displayable. Anything else defers a failure to the point where bytes reach the
wire, which is the worst place to discover it.
"""

import pytest

from sextile.content.transliterate import transliterate
from sextile.viewdata.charset import is_representable


def assert_displayable(text: str) -> None:
    unrepresentable = [character for character in text if not is_representable(character)]
    assert not unrepresentable, f"{unrepresentable!r} cannot be displayed"


class TestPassthrough:
    @pytest.mark.parametrize(
        "text",
        [
            "",
            "PLAIN TEXT",
            "the quick brown fox",
            "0123456789",
            "!\"$%&'()*+,-./:;<=>?@",
            "£5.00",
            "#p489493",
            "½ ¼ ¾ ÷ ← → ↑",
        ],
    )
    def test_already_displayable_text_is_unchanged(self, text: str) -> None:
        assert transliterate(text) == text


class TestPunctuation:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("\u201cquoted\u201d", '"quoted"'),  # curly double quotes
            ("\u2018quoted\u2019", "'quoted'"),  # curly single quotes
            ("a \u2013 b", "a - b"),  # en dash
            ("a \u2014 b", "a - b"),  # em dash
            ("wait\u2026", "wait..."),  # ellipsis
            ("\u2022 item", "* item"),  # bullet
            ("6502\u00a0CPU", "6502 CPU"),  # non-breaking space
            ("\u00d7", "x"),  # multiplication sign
            ("\u20ac20", "EUR20"),  # euro
            ("\u00a9 1981", "(c) 1981"),  # copyright
        ],
    )
    def test_punctuation_is_transliterated(self, source: str, expected: str) -> None:
        assert transliterate(source) == expected


class TestCharactersG0Lacks:
    """The ten ASCII characters with no G0 representation.

    Forum posts quote source code constantly, so these are not edge cases. The
    substitutions are chosen to stay readable as code: caret becomes an up arrow,
    which is what BBC BASIC itself uses for exponentiation, and the vertical bar
    becomes the double vertical line that G0 does provide.
    """

    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("[", "("),
            ("]", ")"),
            ("{", "("),
            ("}", ")"),
            ("\\", "/"),
            ("^", "↑"),
            ("_", "-"),
            ("`", "'"),
            ("|", "‖"),
            ("~", "-"),
        ],
    )
    def test_substitutions(self, source: str, expected: str) -> None:
        assert transliterate(source) == expected

    def test_a_line_of_c_survives_legibly(self) -> None:
        assert transliterate("if (a[i] > 0) { x |= 1 << i; }") == "if (a(i) > 0) ( x ‖= 1 << i; )"


class TestAccentedLetters:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("café", "cafe"),
            ("naïve", "naive"),
            ("Müller", "Muller"),
            ("Ångström", "Angstrom"),
            ("señor", "senor"),
            ("Łódź", "Lodz"),
            ("Straße", "Strasse"),
            ("Ærø", "Aero"),
        ],
    )
    def test_accents_are_stripped_to_base_letters(self, source: str, expected: str) -> None:
        assert transliterate(source) == expected


class TestWhitespace:
    @pytest.mark.parametrize("whitespace", ["\n", "\r", "\t", "\r\n", "\v"])
    def test_whitespace_becomes_a_space(self, whitespace: str) -> None:
        #  Line structure belongs to the block model, not to a run of text; by the
        #  time a run reaches here it is expected to be a single line.
        result = transliterate(f"a{whitespace}b")
        assert result.startswith("a")
        assert result.endswith("b")
        assert set(result[1:-1]) <= {" "}


class TestFallback:
    @pytest.mark.parametrize("source", ["日本語", "→\u0001←", "\U0001f600", "\u2603"])
    def test_anything_unmappable_becomes_a_question_mark(self, source: str) -> None:
        assert_displayable(transliterate(source))

    def test_emoji_becomes_a_question_mark(self) -> None:
        assert transliterate("nice \U0001f600") == "nice ?"


class TestTotality:
    @pytest.mark.parametrize(
        "text",
        [
            "".join(chr(code) for code in range(0x00, 0x0400)),
            "Posted by Iapetus — Sun Aug 02, 2026 9:20 pm",
            "“What a great project!” … £10 ½ way",
            "C:\\BEEB\\DISCS\\*.SSD",
        ],
    )
    def test_output_is_always_displayable(self, text: str) -> None:
        assert_displayable(transliterate(text))
