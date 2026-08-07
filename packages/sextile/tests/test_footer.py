"""Fitting the navigation prompt into one row.

Forty cells is not many, and the prompt has to say what every available key
does. When it will not fit, something must give -- but *what* gives should be
decided by what the reader can least afford to lose, not by what happens to be
at the end of the string.

So each item carries a priority, and the renderer sheds in a fixed order:
labels first, from the least important upward, and only then whole items. The
key itself is the last thing to go, because the key is what the reader presses;
the label only teaches it.
"""

import pytest

from sextile.viewdata.footer import FooterItem, Priority, render_footer

MENU = FooterItem("0", "menu", Priority.ESSENTIAL)
SELECT = FooterItem("1-9", "select", Priority.PRIMARY)
FRAME = FooterItem("←W―S→", "frame", Priority.SECONDARY)
POST = FooterItem("←A―D→", "post", Priority.SECONDARY)
NEXT = FooterItem("#", "next", Priority.REDUNDANT)


class TestWhenItAllFits:
    def test_every_item_is_named_in_full(self) -> None:
        assert render_footer([SELECT, FRAME, MENU], 40) == "1-9 select, ←W―S→ frame, 0 menu"

    def test_items_keep_the_order_they_were_given(self) -> None:
        #  Priority decides what is shed, never where things sit.
        assert render_footer([MENU, SELECT], 40) == "0 menu, 1-9 select"

    def test_nothing_at_all_renders_as_nothing(self) -> None:
        assert render_footer([], 40) == ""

    def test_an_item_with_no_label_shows_only_its_key(self) -> None:
        assert render_footer([FooterItem("0", "")], 40) == "0"


class TestSheddingLabels:
    def test_the_least_important_label_goes_first(self) -> None:
        rendered = render_footer([SELECT, FRAME, NEXT, MENU], 38)
        assert "# next" not in rendered
        assert "#" in rendered
        assert "1-9 select" in rendered

    def test_more_labels_go_as_the_row_narrows(self) -> None:
        wide = render_footer([SELECT, FRAME, NEXT, MENU], 40)
        narrow = render_footer([SELECT, FRAME, NEXT, MENU], 30)
        assert narrow.count(" ") < wide.count(" ")

    def test_the_most_important_label_is_the_last_to_go(self) -> None:
        rendered = render_footer([SELECT, FRAME, NEXT, MENU], 26)
        assert "0 menu" in rendered

    def test_a_key_is_never_dropped_to_keep_a_label(self) -> None:
        rendered = render_footer([SELECT, FRAME, NEXT, MENU], 24)
        for item in (SELECT, FRAME, NEXT, MENU):
            assert item.key in rendered


class TestSheddingItems:
    def test_whole_items_go_only_once_every_label_has(self) -> None:
        rendered = render_footer([SELECT, FRAME, POST, NEXT, MENU], 18)
        assert "select" not in rendered
        assert "menu" not in rendered

    def test_the_least_important_item_goes_first(self) -> None:
        rendered = render_footer([SELECT, FRAME, POST, NEXT, MENU], 18)
        assert "#" not in rendered

    def test_the_essential_item_survives_everything(self) -> None:
        assert render_footer([SELECT, FRAME, POST, NEXT, MENU], 3) == "0"

    def test_the_way_out_is_kept_over_the_way_on(self) -> None:
        #  A reader who cannot read the screen still needs to leave it.
        rendered = render_footer([FRAME, POST, NEXT, MENU], 8)
        assert "0" in rendered


class TestNeverOverflowing:
    @pytest.mark.parametrize("width", range(0, 45))
    def test_the_result_never_exceeds_the_width(self, width: int) -> None:
        rendered = render_footer([SELECT, FRAME, POST, NEXT, MENU], width)
        assert len(rendered) <= width

    def test_a_width_of_nothing_yields_nothing(self) -> None:
        assert render_footer([SELECT, MENU], 0) == ""

    def test_a_key_wider_than_the_row_is_cut_rather_than_overflowing(self) -> None:
        assert render_footer([FooterItem("←A―D→", "post")], 3) == "←A―"

    def test_measurement_is_in_cells_not_characters(self) -> None:
        #  Transliteration can lengthen a label -- an ellipsis becomes three
        #  characters -- so a naive len() would let the row overflow. This label
        #  is five characters and fifteen cells, and must be shed accordingly.
        assert render_footer([FooterItem("0", "…" * 5)], 8) == "0"
        assert render_footer([FooterItem("0", "abcde")], 8) == "0 abcde"

    def test_the_text_is_left_untransliterated(self) -> None:
        #  The canvas transliterates when it writes; doing it here as well would
        #  be doing it twice.
        assert render_footer([FooterItem("0", "menu…")], 40) == "0 menu…"


class TestPriorityOrder:
    def test_the_priorities_run_from_essential_downwards(self) -> None:
        assert Priority.ESSENTIAL > Priority.PRIMARY > Priority.SECONDARY > Priority.REDUNDANT

    def test_equal_priorities_shed_from_the_right(self) -> None:
        #  Nothing distinguishes them, so the later one goes first, which keeps
        #  what the reader met earliest.
        left = FooterItem("A", "alpha", Priority.SECONDARY)
        right = FooterItem("B", "beta", Priority.SECONDARY)
        rendered = render_footer([left, right, MENU], 20)
        assert "alpha" in rendered
        assert "beta" not in rendered
