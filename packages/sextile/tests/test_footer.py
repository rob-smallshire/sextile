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

from sextile.viewdata.footer import FooterItem, Priority, movement, render_footer

#  The sort of items a page really offers, so the tests read as a page
#  would be written rather than as the renderer's own vocabulary.
MENU = FooterItem("0", "index", Priority.ESSENTIAL)
SELECT = FooterItem("1-9", "select", Priority.PRIMARY)
FRAME = FooterItem("S", "page down", Priority.SECONDARY, brief="down")
POST = FooterItem("D", "next post", Priority.SECONDARY, brief="next")
NEXT = FooterItem("#", "next frame", Priority.ALIAS)


class TestWhenItAllFits:
    def test_every_item_is_named_in_full(self) -> None:
        assert render_footer([SELECT, FRAME, MENU], 40) == "1-9 select, S page down, 0 index"

    def test_items_keep_the_order_they_were_given(self) -> None:
        #  Priority decides what is shed, never where things sit.
        assert render_footer([MENU, SELECT], 40) == "0 index, 1-9 select"

    def test_nothing_at_all_renders_as_nothing(self) -> None:
        assert render_footer([], 40) == ""

    def test_an_item_with_no_label_shows_only_its_key(self) -> None:
        assert render_footer([FooterItem("0", "")], 40) == "0"


class TestSheddingLabels:
    def test_the_least_important_label_goes_first(self) -> None:
        rendered = render_footer([SELECT, FRAME, NEXT, MENU], 38)
        assert "# next frame" not in rendered
        assert "#" in rendered
        assert "1-9 select" in rendered

    def test_more_labels_go_as_the_row_narrows(self) -> None:
        wide = render_footer([SELECT, FRAME, NEXT, MENU], 40)
        narrow = render_footer([SELECT, FRAME, NEXT, MENU], 30)
        assert narrow.count(" ") < wide.count(" ")

    def test_the_most_important_label_is_the_last_to_go(self) -> None:
        rendered = render_footer([SELECT, FRAME, NEXT, MENU], 26)
        assert "0 index" in rendered

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
        assert render_footer([FooterItem("0", "index…")], 40) == "0 index…"


class TestPriorityOrder:
    def test_the_priorities_run_from_essential_downwards(self) -> None:
        assert Priority.ESSENTIAL > Priority.PRIMARY > Priority.SECONDARY > Priority.ALIAS

    def test_equal_priorities_give_up_their_words_together(self) -> None:
        #  They are the same sort of thing -- a pair of movement keys, say --
        #  and a row that labelled one and not the other would read as though
        #  they were not.
        left = FooterItem("A", "alpha", Priority.SECONDARY)
        right = FooterItem("B", "beta", Priority.SECONDARY)
        rendered = render_footer([left, right, MENU], 20)
        assert "alpha" not in rendered and "beta" not in rendered
        assert "A" in rendered and "B" in rendered

    def test_but_when_one_must_go_it_is_the_later(self) -> None:
        #  Nothing distinguishes them, so the later one goes first, which keeps
        #  what the reader met earliest.
        left = FooterItem("A", "alpha", Priority.SECONDARY)
        right = FooterItem("B", "beta", Priority.SECONDARY)
        rendered = render_footer([left, right, MENU], 5)
        assert "A" in rendered
        assert "B" not in rendered


class TestSayingItMoreBriefly:
    """An item may offer a short wording as well as a full one.

    Without that, a row too tight for the sentence had to fall back to the
    key alone -- so whoever wrote the page wrote for the worst case and every
    page got the terse version, including the ones with a row to spare.
    """

    def test_the_full_wording_is_used_when_it_fits(self) -> None:
        item = FooterItem("S", "page down", Priority.SECONDARY, brief="down")
        assert render_footer([item, MENU], 40) == "S page down, 0 index"

    def test_the_brief_one_when_it_does_not(self) -> None:
        item = FooterItem("S", "page down", Priority.SECONDARY, brief="down")
        assert render_footer([item, MENU], 15) == "S down, 0 index"

    def test_the_way_out_gives_up_its_word_before_a_mover_gives_up_its_last(
        self,
    ) -> None:
        #  Every reader knows what 0 does; nobody is born knowing what S does.
        item = FooterItem("S", "page down", Priority.SECONDARY, brief="down")
        assert render_footer([item, MENU], 10) == "S down, 0"

    def test_and_the_key_alone_when_even_that_will_not_fit(self) -> None:
        item = FooterItem("S", "page down", Priority.SECONDARY, brief="down")
        assert render_footer([item, MENU], 8) == "S, 0"

    def test_an_item_with_no_brief_goes_straight_to_its_key(self) -> None:
        item = FooterItem("S", "page down", Priority.SECONDARY)
        assert render_footer([item, MENU], 15) == "S, 0 index"


class TestWhatGoesBeforeWhat:
    def test_an_alias_leaves_before_the_way_out_loses_its_word(self) -> None:
        #  A row that shows a key which is another key said differently, and
        #  does not say where the way out goes, has kept the wrong thing.
        items = [
            FooterItem("S", "page down", Priority.SECONDARY, brief="down"),
            FooterItem("#", "next frame", Priority.ALIAS),
            MENU,
        ]
        rendered = render_footer(items, 16)
        assert "#" not in rendered
        assert "0 index" in rendered


class TestTheWordsForTheMovementKeys:
    """One set of words, so two pages of a service describe a key alike.

    They were named in three places -- the templates, and each application's
    own prompt builder -- and had drifted: a page built by a template said one
    thing about `S` and a page built by hand said another.
    """

    def test_each_key_is_named(self) -> None:
        from sextile import keys

        said = {item.key: item.label for item in movement(keys.ARROW_FOR)}
        assert said == {
            keys.PREVIOUS_FRAME: "page up",
            keys.NEXT_FRAME: "page down",
            keys.PREVIOUS_ITEM: "previous item",
            keys.NEXT_ITEM: "next item",
        }

    def test_and_only_the_keys_that_do_something(self) -> None:
        from sextile import keys

        assert [item.key for item in movement([keys.NEXT_FRAME])] == [keys.NEXT_FRAME]

    def test_the_item_axis_takes_the_service_s_own_noun(self) -> None:
        #  A service moves between posts, or days, or whatever it is made of.
        from sextile import keys

        said = [item.label for item in movement([keys.NEXT_ITEM], item="post")]
        assert said == ["next post"]

    def test_they_come_out_in_the_order_they_are_pressed_in(self) -> None:
        from sextile import keys

        assert [item.key for item in movement(keys.ARROW_FOR)] == [
            keys.PREVIOUS_FRAME,
            keys.NEXT_FRAME,
            keys.PREVIOUS_ITEM,
            keys.NEXT_ITEM,
        ]
