"""Parts laid out down the frames of a page.

The fill pass alone: what goes on which frame, and what each frame claims.
Nothing here draws furniture, which is the other pass and knows the count.

See docs/design.md.
"""

from dataclasses import dataclass

import pytest

from sextile.addressing import FRAMES_PER_PAGE, PageAddress
from sextile.application import Neighbours, Sextile
from sextile.keys import CONVENTIONAL_NEXT_FRAME, DOWN, LEFT, NEXT_FRAME, RIGHT, UP
from sextile.layout import (
    DEFAULT_FURNITURE,
    HOME_KEY,
    Claim,
    Flow,
    Footer,
    FrameBreak,
    OnEveryFrame,
    OnFirstFrame,
    PageLayout,
    Placed,
    Shortcut,
    Space,
    content_rows,
    fill,
)
from sextile.page import Page
from sextile.testing import request_for
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.footer import FooterItem, Priority
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.typesetting import TRUNCATION_NOTICE

#: A bare service to answer the requests these layout tests build. What is on a
#: page rather than which service it belongs to is what they are about.
_APP = Sextile()

CONTENT = range(2, 22)


@dataclass(frozen=True)
class Says:
    """A fixed part of one row a frame, saying what it was told to say."""

    said: str
    rows: int = 1

    def place(self, canvas: Canvas, room: Space) -> Placed:
        if room.rows < self.rows:
            return Placed(rows=0, remainder=self)
        for offset in range(self.rows):
            canvas.row(room.first_row + offset).text(self.said, Colour.WHITE)
        return Placed(rows=self.rows)


@dataclass(frozen=True)
class Counts:
    """A flowing part of one row an item, which claims a digit for each."""

    items: tuple[str, ...]

    def place(self, canvas: Canvas, room: Space) -> Placed:
        taken = min(room.rows, room.choices, len(self.items))
        for offset, item in enumerate(self.items[:taken]):
            canvas.row(room.first_row + offset).text(item, Colour.WHITE)
        rest = self.items[taken:]
        return Placed(
            rows=taken,
            claim=Claim(
                choices={str(n + 1): PageAddress(f"8{n}") for n in range(taken)},
                named=[FooterItem("1-9", "select", Priority.PRIMARY)] if taken else [],
            ),
            remainder=Counts(rest) if rest else None,
        )


@dataclass(frozen=True)
class Recites:
    """A flowing part of one row a line, which chooses nothing.

    Bound by the rows rather than by the digits, where `Counts` is bound by
    both -- which is the difference between prose and a menu.
    """

    lines: tuple[str, ...]

    def place(self, canvas: Canvas, room: Space) -> Placed:
        taken = min(room.rows, len(self.lines))
        for offset, line in enumerate(self.lines[:taken]):
            canvas.row(room.first_row + offset).text(line, Colour.WHITE)
        rest = self.lines[taken:]
        return Placed(rows=taken, remainder=Recites(rest) if rest else None)


def at(digits: str) -> PageAddress:
    return PageAddress(digits)


def rows_of(page: Page, index: int = 0) -> list[str]:
    found = page.frame(index)
    assert found is not None
    characters, _ = found.frame.to_grid()
    return characters


def said_on(frames: list[Canvas], index: int) -> list[str]:
    characters, _ = frames[index].frame.to_grid()
    return [row.strip() for row in characters if row.strip()]


def items(count: int) -> Counts:
    return Counts(tuple(f"item {n}" for n in range(1, count + 1)))


def lines(count: int) -> Recites:
    return Recites(tuple(f"line {n}" for n in range(1, count + 1)))


class TestOnePartOnOneFrame:
    def test_a_part_that_fits_gives_one_frame(self) -> None:
        filled = fill([OnFirstFrame(Says("hello"))], CONTENT)
        assert len(filled) == 1
        assert said_on([one.canvas for one in filled], 0) == ["hello"]

    def test_nothing_at_all_is_still_one_frame(self) -> None:
        #  A page that answered with no frames could not be shown.
        assert len(fill([], CONTENT)) == 1

    def test_a_part_claims_what_it_offers(self) -> None:
        filled = fill([Flow(items(3))], CONTENT)
        assert filled[0].claim.choices == {
            "1": PageAddress("80"),
            "2": PageAddress("81"),
            "3": PageAddress("82"),
        }


class TestAPartThatFlows:
    def test_it_goes_on_to_as_many_frames_as_it_takes(self) -> None:
        #  Twenty rows a frame, and the part claims a digit for each row, so
        #  nine to a frame is the choices talking rather than the rows.
        filled = fill([Flow(items(20))], CONTENT)
        assert len(filled) == 3
        assert len(said_on([one.canvas for one in filled], 0)) == 9
        assert len(said_on([one.canvas for one in filled], 2)) == 2

    def test_the_digits_begin_again_on_each_frame(self) -> None:
        filled = fill([Flow(items(12))], CONTENT)
        assert set(filled[0].claim.choices) == {str(n) for n in range(1, 10)}
        assert set(filled[1].claim.choices) == {"1", "2", "3"}

    def test_two_flowing_parts_follow_one_another(self) -> None:
        #  Concatenation: the second begins in the row after the first has
        #  finished, on whatever frame that is.
        filled = fill([Flow(items(5)), Flow(Counts(("and", "then")))], CONTENT)
        assert len(filled) == 1
        assert said_on([one.canvas for one in filled], 0)[-2:] == ["and", "then"]


class TestABareDrawableIsFlowing:
    """A `Drawable` in a parts list, wrapped in nothing, means `Flow`.

    Flowing across as many frames as it takes is what a part does unless it says
    otherwise, so the common case need not say it.
    """

    def test_it_flows_across_frames_like_an_explicit_flowing(self) -> None:
        bare = fill([items(20)], CONTENT)
        wrapped = fill([Flow(items(20))], CONTENT)
        assert len(bare) == len(wrapped) == 3
        assert [said_on([one.canvas for one in bare], f) for f in range(3)] == [
            said_on([one.canvas for one in wrapped], f) for f in range(3)
        ]

    def test_it_follows_a_once_the_way_a_flowing_would(self) -> None:
        filled = fill([OnFirstFrame(Says("lead-in")), items(12)], CONTENT)
        assert said_on([one.canvas for one in filled], 0)[0] == "lead-in"
        assert len(filled) == 2


class TestOnceAndEvery:
    def test_once_is_drawn_on_the_first_frame_only(self) -> None:
        filled = fill([OnFirstFrame(Says("lead-in")), Flow(items(12))], CONTENT)
        assert said_on([one.canvas for one in filled], 0)[0] == "lead-in"
        assert "lead-in" not in said_on([one.canvas for one in filled], 1)

    def test_every_is_drawn_on_all_of_them(self) -> None:
        filled = fill([OnEveryFrame(Says("headings")), Flow(items(12))], CONTENT)
        for index in range(len(filled)):
            assert said_on([one.canvas for one in filled], index)[0] == "headings"

    def test_a_trailing_every_keeps_its_rows_on_every_frame(self) -> None:
        #  Charged before the flowing part is asked, or the flow takes the rows
        #  the footnote needs and writes over it. A part bound by rows rather
        #  than by digits, since it is the rows that are at stake.
        without = fill([Flow(lines(40))], CONTENT)
        with_note = fill([Flow(lines(40)), OnEveryFrame(Says("a note", rows=3))], CONTENT)
        assert len(without) == 2
        assert len(with_note) == 3
        for index in range(len(with_note)):
            assert "a note" in said_on([one.canvas for one in with_note], index)

    def test_once_after_a_flow_lands_where_the_flow_finished(self) -> None:
        #  `once` means once, not first.
        filled = fill([Flow(items(12)), OnFirstFrame(Says("and that is all"))], CONTENT)
        assert "and that is all" not in said_on([one.canvas for one in filled], 0)
        assert "and that is all" in said_on([one.canvas for one in filled], 1)


class TestABreak:
    def test_what_follows_begins_on_a_new_frame(self) -> None:
        filled = fill([Flow(items(2)), FrameBreak(), Flow(items(2))], CONTENT)
        assert len(filled) == 2
        assert len(said_on([one.canvas for one in filled], 0)) == 2

    def test_a_break_at_either_end_divides_nothing(self) -> None:
        assert len(fill([FrameBreak(), Flow(items(2))], CONTENT)) == 1
        assert len(fill([Flow(items(2)), FrameBreak()], CONTENT)) == 1

    def test_and_nor_do_two_together(self) -> None:
        filled = fill([Flow(items(2)), FrameBreak(), FrameBreak(), Flow(items(2))], CONTENT)
        assert len(filled) == 2


class TestAPartTooTallForWhatIsLeft:
    def test_it_begins_the_next_frame_rather_than_being_split(self) -> None:
        #  Eighteen rows gone of twenty, and four wanted: it goes over whole.
        filled = fill([Flow(lines(18)), OnFirstFrame(Says("four rows", rows=4))], CONTENT)
        assert len(filled) == 2
        assert "four rows" not in said_on([one.canvas for one in filled], 0)
        assert "four rows" in said_on([one.canvas for one in filled], 1)

    def test_a_part_taller_than_a_frame_is_refused(self) -> None:
        with pytest.raises(ValueError, match="never be placed"):
            fill([OnFirstFrame(Says("far too tall", rows=30))], CONTENT)


class TestSeveralPartsOnEveryFrame:
    """They follow one another in the order the list gives them.

    Two bands, and which one a part falls in is settled by the flowing parts:
    what comes before the first of them is drawn where it stands, and what
    comes after has its rows kept back at the foot, because a flowing part
    would otherwise take them.
    """

    def test_two_at_the_top_are_drawn_in_order(self) -> None:
        filled = fill(
            [OnEveryFrame(Says("first")), OnEveryFrame(Says("second")), Flow(items(12))],
            CONTENT,
        )
        for index in range(len(filled)):
            said = said_on([one.canvas for one in filled], index)
            assert said[:2] == ["first", "second"]

    def test_two_at_the_foot_are_drawn_in_order(self) -> None:
        filled = fill(
            [Flow(lines(30)), OnEveryFrame(Says("penultimate")), OnEveryFrame(Says("last"))],
            CONTENT,
        )
        for index in range(len(filled)):
            said = said_on([one.canvas for one in filled], index)
            assert said[-2:] == ["penultimate", "last"]

    def test_one_between_two_flows_is_still_drawn_on_every_frame(self) -> None:
        #  It falls in the band at the foot: anything after a flowing part has
        #  to have its rows kept back, or the flow takes them and it is never
        #  drawn at all.
        filled = fill(
            [Flow(lines(30)), OnEveryFrame(Says("throughout")), Flow(lines(4))],
            CONTENT,
        )
        assert len(filled) > 1
        for index in range(len(filled)):
            assert "throughout" in said_on([one.canvas for one in filled], index)


class TestTheFurniture:
    """The second pass: what goes round the content once the count is known."""

    def test_the_default_leaves_the_content_rows_it_always_had(self) -> None:
        assert content_rows(DEFAULT_FURNITURE) == range(2, 22)

    def test_and_no_furniture_leaves_the_whole_frame(self) -> None:
        assert content_rows(()) == range(0, 24)

    def test_a_two_row_footer_costs_a_content_row(self) -> None:
        #  The arithmetic says so, rather than a constant needing to be edited.
        assert content_rows([*DEFAULT_FURNITURE, Footer()]) == range(2, 21)

    def test_the_header_carries_the_title_and_the_page_number(self) -> None:
        layout = PageLayout(title="ITEMS", parts=[OnFirstFrame(Says("x"))])
        shown = rows_of(layout.build(request_for(_APP, at("8"))))
        assert shown[0].strip().startswith("ITEMS")
        assert shown[0].strip().endswith("8a")

    def test_a_page_with_no_number_gives_the_title_the_row(self) -> None:
        shown = rows_of(
            PageLayout(title="UNKNOWN PAGE", numbered=False).build(request_for(_APP, at("8")))
        )
        assert shown[0].strip() == "UNKNOWN PAGE"

    def test_a_page_may_do_without_furniture_altogether(self) -> None:
        shown = rows_of(
            PageLayout(title="STARDOT", furniture=(), parts=[OnFirstFrame(Says("masthead"))])
            .build(request_for(_APP, at("8")))
        )
        assert shown[0].strip() == "masthead"
        assert all("STARDOT" not in row for row in shown)


class TestWhatAFrameAnswers:
    def test_the_parts_claims_and_the_way_home_together(self) -> None:
        page = PageLayout(
            title="ITEMS", home=at("1"), parts=[Flow(items(3))]
        ).build(request_for(_APP, at("8")))
        found = page.frame(0)
        assert found is not None
        assert found.destination("1") == PageAddress("80")
        assert found.destination("0") == at("1")

    def test_a_shortcut_leads_from_every_frame(self) -> None:
        page = PageLayout(
            title="POSTS",
            home=at("1"),
            shortcuts=[Shortcut(key="R", destination=at("7"), says="reply")],
            parts=[Flow(items(12))],
        ).build(request_for(_APP, at("8")))
        for index in range(len(page.frames)):
            found = page.frame(index)
            assert found is not None
            assert found.destination("R") == at("7")

    def test_the_prompt_names_the_keys_that_work_here(self) -> None:
        page = PageLayout(
            title="ITEMS", home=at("1"), parts=[Flow(items(12))]
        ).build(request_for(_APP, at("8")))
        first = rows_of(page, 0)[-1]
        second = rows_of(page, 1)[-1]
        assert "1-9 select" in first
        assert "S page down" in first and "W page up" not in first
        assert "W page up" in second and "S page down" not in second

    def test_and_a_page_of_one_frame_names_no_movement(self) -> None:
        layout = PageLayout(title="ITEMS", home=at("1"), parts=[Flow(items(3))])
        page = layout.build(request_for(_APP, at("8")))
        assert "page down" not in rows_of(page, 0)[-1]


class TestWhereAPageLeads:
    def test_follows_brings_the_key_that_reaches_it(self) -> None:
        #  The session tries the next frame and falls through to `follows`, so
        #  the key has to be answered for that to happen at all.
        page = PageLayout(
            title="STARDOT", furniture=(), parts=[OnFirstFrame(Says("masthead"))], follows=at("1")
        ).build(request_for(_APP, at("8")))
        found = page.frame(0)
        assert found is not None
        assert page.follows == at("1")
        assert NEXT_FRAME in found.moves
        assert CONVENTIONAL_NEXT_FRAME in found.moves

    def test_ringing_off_is_said_by_the_page(self) -> None:
        assert PageLayout(title="GOODBYE", hang_up=True).build(request_for(_APP, at("1"))).hang_up


class TestAPageTooLongForItsFrames:
    def test_it_stops_and_says_so(self) -> None:
        layout = PageLayout(title="PAGES", parts=[Flow(lines(1000))])
        page = layout.build(request_for(_APP, at("9")))
        assert len(page.frames) == FRAMES_PER_PAGE
        assert TRUNCATION_NOTICE in rows_of(page, FRAMES_PER_PAGE - 1)[-3]


class TestTheWayHomeIsAShortcutLikeAnyOther:
    """An address for the usual case, a `Shortcut` where a page wants more.

    `home` and `shortcuts` are the same idea -- a key on every frame leading to
    a fixed address -- so a page that wants the footer to call the way home
    something else says it the way it would for any other key.
    """

    def a_page(self, home: PageAddress | Shortcut | None = None) -> Page:
        return PageLayout(
            title="NOTICE", home=home, parts=[OnFirstFrame(Says("Said."))]
        ).build(request_for(_APP, at("2")))

    def test_an_address_puts_it_on_nought_and_calls_it_the_index(self) -> None:
        page = self.a_page(at("1"))
        found = page.frame(0)
        assert found is not None
        assert found.destination(HOME_KEY) == at("1")
        assert "0 index" in rows_of(page)[-1]

    def test_a_shortcut_is_taken_as_given(self) -> None:
        page = self.a_page(Shortcut(key="9", destination=at("1"), says="back to the top"))
        found = page.frame(0)
        assert found is not None
        assert found.destination("9") == at("1")
        assert found.destination(HOME_KEY) is None
        assert "9 back to the top" in rows_of(page)[-1]

    def test_the_short_form_is_what_stands_before_the_comma(self) -> None:
        #  Rather than a second field saying it twice. The footer sheds words
        #  from the end when the row is tight.
        page = self.a_page(Shortcut(HOME_KEY, at("1"), says="index, or key another page"))
        assert "0 index, or key another page" in rows_of(page)[-1]

    def test_no_way_home_at_all_names_no_key(self) -> None:
        page = self.a_page()
        found = page.frame(0)
        assert found is not None
        assert found.destination(HOME_KEY) is None
        assert "index" not in rows_of(page)[-1]


class TestAShortcutThatAnswersAnArrowToo:
    """`A` and `D` move between items, and so do the left and right arrows.

    Whether an arrow means what its letter means is the page's business: on a
    page with a coordinate field it does not, `W` being West. So a shortcut
    answers its arrow only where the page has said it should.
    """

    def a_page(self, *, arrow: bool = False) -> Page:
        return PageLayout(
            title="ONE DAY",
            home=at("1"),
            parts=[OnFirstFrame(Says("Saturday."))],
            shortcuts=[
                Shortcut(key="A", destination=at("41"), says="prev", arrow=arrow),
                Shortcut(key="D", destination=at("43"), says="next", arrow=arrow),
            ],
        ).build(request_for(_APP, at("42")))

    def test_the_letter_leads_where_it_always_did(self) -> None:
        found = self.a_page().frame(0)
        assert found is not None
        assert (found.destination("A"), found.destination("D")) == (at("41"), at("43"))

    def test_and_the_arrow_does_not_unless_it_was_asked_for(self) -> None:
        found = self.a_page().frame(0)
        assert found is not None
        assert found.destination(LEFT) is None
        assert found.destination(RIGHT) is None

    def test_asked_for_the_arrow_leads_where_the_letter_does(self) -> None:
        found = self.a_page(arrow=True).frame(0)
        assert found is not None
        assert found.destination(LEFT) == at("41")
        assert found.destination(RIGHT) == at("43")

    def test_a_key_with_no_arrow_is_unmoved_by_asking(self) -> None:
        #  Only the four movement letters have arrows. Asking on any other is
        #  answered by there being nothing to add, rather than by an error.
        page = PageLayout(
            title="POST",
            home=at("1"),
            parts=[OnFirstFrame(Says("A post."))],
            shortcuts=[Shortcut(key="R", destination=at("7"), says="reply", arrow=True)],
        ).build(request_for(_APP, at("8")))
        found = page.frame(0)
        assert found is not None
        assert found.destination("R") == at("7")
        assert not [key for key in (LEFT, RIGHT, UP, DOWN) if found.destination(key)]


class TestWhatTheItemsAreCalled:
    """The movement keys name what they move between, and the page says what.

    The words come from `viewdata.footer` either way, so a page built here and
    a page drawn by hand describe the same key the same way. What the page
    supplies is the noun.
    """

    def footer_of(self, item: str = "item") -> str:
        return rows_of(
            PageLayout(
                title="ONE DAY",
                home=at("1"),
                item_noun=item,
                parts=[OnFirstFrame(Says("Saturday."))],
                shortcuts=[
                    Shortcut(key="A", destination=at("41"), arrow=True),
                    Shortcut(key="D", destination=at("43"), arrow=True),
                ],
            ).build(request_for(_APP, at("42")))
        )[-1]

    def test_an_item_by_default(self) -> None:
        assert "previous item" in self.footer_of()

    def test_or_whatever_the_page_moves_between(self) -> None:
        footer = self.footer_of("day")
        assert "previous day" in footer
        assert "next day" in footer

    def _by_neighbours(self, neighbours: Neighbours) -> Page:
        return PageLayout(
            title="ONE DAY",
            home=at("1"),
            neighbours=neighbours,
            item_noun="day",
            parts=[OnFirstFrame(Says("Saturday."))],
        ).build(request_for(_APP, at("42")))

    def test_neighbours_wire_the_item_keys_with_their_arrows(self) -> None:
        page = self._by_neighbours(Neighbours(previous=at("41"), next=at("43")))
        found = page.frame(0)
        assert found is not None
        assert found.destination("A") == at("41")
        assert found.destination("D") == at("43")
        assert found.destination(LEFT) == at("41")
        footer = rows_of(page)[-1]
        assert "previous day" in footer
        assert "next day" in footer

    def test_a_neighbour_that_is_not_there_is_neither_wired_nor_named(self) -> None:
        page = self._by_neighbours(Neighbours(next=at("43")))
        found = page.frame(0)
        assert found is not None
        assert found.destination("A") is None
        assert found.destination("D") == at("43")
        footer = rows_of(page)[-1]
        assert "previous" not in footer
        assert "next day" in footer

    def test_a_shortcut_that_is_not_a_movement_key_says_its_own_words(self) -> None:
        footer = rows_of(
            PageLayout(
                title="ONE DAY",
                home=at("1"),
                item_noun="day",
                parts=[OnFirstFrame(Says("Saturday."))],
                shortcuts=[Shortcut(key="1", destination=at("32"), says="month")],
            ).build(request_for(_APP, at("42")))
        )[-1]
        assert "1 month" in footer

    def test_the_frame_keys_are_not_named_for_the_item(self) -> None:
        #  `W` and `S` move between the frames of one item, and a page of many
        #  frames is still one day.
        footer = rows_of(
            PageLayout(
                title="A LONG NOTICE",
                home=at("1"),
                item_noun="day",
                parts=[Flow(lines(30))],
            ).build(request_for(_APP, at("42")))
        )[-1]
        assert "page down" in footer
        assert "day" not in footer


class TestTheHeader:
    """The title, and the page number at the right of the same row."""

    def a_frame(self, title: str, address: PageAddress) -> Page:
        layout = PageLayout(title=title, parts=[OnFirstFrame(Says("x"))])
        return layout.build(request_for(_APP, address))

    def test_the_title_appears(self) -> None:
        assert "PROGRAMMING" in rows_of(self.a_frame("PROGRAMMING", at("4254")))[0]

    def test_the_page_number_is_at_the_right(self) -> None:
        header = rows_of(self.a_frame("PROGRAMMING", at("4254")))[0]
        assert header.rstrip().endswith("4254a")

    def test_a_long_title_is_cut_rather_than_pushing_out_the_number(self) -> None:
        #  Forum names on Stardot run to forty characters on their own.
        header = rows_of(
            self.a_frame("8-bit acorn software: games - high scores", at("82489493"))
        )[0]
        assert header.rstrip().endswith("82489493a")
        assert len(header) == COLUMNS

    def test_the_title_and_the_number_never_collide(self) -> None:
        header = rows_of(self.a_frame("X" * 60, at("123456789012")))[0]
        assert "X123456789012" not in header

    def test_a_page_with_no_title_of_its_own_gets_none(self) -> None:
        #  The framework does not name the service. A title across the top of
        #  somebody else's service would be naming the machinery.
        assert rows_of(self.a_frame("", at("4254")))[0].strip() == "4254a"

    def test_every_byte_survives_a_seven_bit_line(self) -> None:
        for title, number in [("", "1"), ("PROGRAMMING", "4254"), ("£ ½ café", "82489493")]:
            page = self.a_frame(title, at(number))
            found = page.frame(0)
            assert found is not None
            assert all(byte < 0x80 for byte in found.frame.to_bytes())


class TestTheRulesAndThePrompt:
    def a_frame(self, prompt_from: str = "reply") -> Page:
        return PageLayout(
            title="T",
            home=at("1"),
            shortcuts=[Shortcut(key="R", destination=at("7"), says=prompt_from)],
            parts=[OnFirstFrame(Says("x"))],
        ).build(request_for(_APP, at("1")))

    def test_the_rules_are_drawn_in_mosaic_graphics(self) -> None:
        found = self.a_frame().frame(0)
        assert found is not None
        _, attributes = found.frame.to_grid()
        #  Graphics colours travel as Q-W.
        assert any(cell in "QRSTUVW" for cell in attributes[1])
        assert any(cell in "QRSTUVW" for cell in attributes[22])

    def test_the_prompt_names_the_keys(self) -> None:
        assert "R reply" in rows_of(self.a_frame())[-1]

    def test_an_over_long_prompt_is_cut_to_the_row(self) -> None:
        assert len(rows_of(self.a_frame("p" * 100))[-1]) == COLUMNS

    def test_the_furniture_writes_nothing_into_the_content_rows(self) -> None:
        page = PageLayout(title="T", home=at("1")).build(request_for(_APP, at("1")))
        content = rows_of(page)[2:22]
        assert all(not row.strip() for row in content)
