"""How to get about, generated from the keys the framework answers.

The fourth page the framework builds for a service, and here for the reason
the other three are: a guide that drifts from the thing it describes is worse
than none.
"""

from sextile.addressing import PageAddress
from sextile.application import Sextile
from sextile.builtin.guidance import GuideRow, guide_page
from sextile.page import Page
from sextile.testing import request_for

_APP = Sextile()


def text_of(page: Page, index: int = 0) -> str:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return "\n".join(characters)


def a_guide(**wanted: object) -> Page:
    return guide_page(request=request_for(_APP, PageAddress("91")), **wanted)  # type: ignore[arg-type]


class TestWhatTheFrameworkSaysForItself:
    def test_the_keys_it_answers_are_all_named(self) -> None:
        shown = text_of(a_guide())
        for key in ("1-9", "*<number>#", "*<keyword>#", "DEL"):
            assert key in shown, key

    def test_and_the_ones_that_ask_for_something_on_the_second_frame(self) -> None:
        shown = text_of(a_guide(), 1)
        for key in ("*0#", "*00#", "*09#"):
            assert key in shown, key

    def test_the_way_home_is_called_what_the_service_calls_it(self) -> None:
        #  "back to the main menu" on a service with a menu and "back to the
        #  main index" on one with an index: it is the page's own title, so the
        #  two cannot come to disagree.
        assert "back to the main menu" in text_of(a_guide(home_called="main menu"))
        assert "back to the main index" in text_of(a_guide(home_called="main index"))

    def test_the_compass_is_drawn_under_the_moving_keys(self) -> None:
        assert "page down" in text_of(a_guide())

    def test_and_dropped_where_a_service_has_filled_the_frame(self) -> None:
        #  A service with a great many keys of its own gets the keys, which are
        #  what it asked for.
        crowded = a_guide(moving=[GuideRow(f"K{n}", f"does {n}") for n in range(9)])
        #  `page down` is in the footer of every frame with a frame after it,
        #  so the compass is looked for by the word only it draws.
        assert "previous" not in text_of(crowded)
        assert "K8" in text_of(crowded)

    def test_and_kept_where_they_have_left_room(self) -> None:
        assert "previous" in text_of(a_guide(moving=[GuideRow("A-Z", "type")]))


class TestWhatAServiceAddsToIt:
    def test_its_own_moving_keys_join_the_first_frame(self) -> None:
        guide = a_guide(moving=[GuideRow("A-Z", "type into a search field")])
        assert "type into a search field" in text_of(guide)

    def test_and_its_own_pages_the_second(self) -> None:
        guide = a_guide(asking=[GuideRow("*95#", "what the pictures mean")])
        assert "what the pictures mean" in text_of(guide, 1)

    def test_the_column_is_one_width_for_the_whole_guide(self) -> None:
        #  Both frames of one table, set from the widest key in either, so the
        #  two line up with each other and neither is set by hand.
        guide = a_guide(asking=[GuideRow("*1234567890#", "a very long number")])
        first, second = (text_of(guide, index).splitlines() for index in (0, 1))
        assert first[2].index("choose from a menu") == second[2].index("back,")


class TestGettingAboutTheGuide:
    def test_the_first_frame_turns_to_the_second(self) -> None:
        page = a_guide()
        found = page.frame(0)
        assert found is not None
        assert "#" in found.moves

    def test_and_the_second_turns_back(self) -> None:
        page = a_guide()
        found = page.frame(1)
        assert found is not None
        assert "W" in found.moves

    def test_and_nought_goes_home_from_either(self) -> None:
        page = a_guide()
        for index in (0, 1):
            found = page.frame(index)
            assert found is not None
            assert found.destination("0") == PageAddress("1")
