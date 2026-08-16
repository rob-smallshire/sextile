"""A field a reader types into, and the suggestions beneath it.

The one thing a viewdata page could not previously do: answer a keypress by
changing what is on screen without going anywhere. Everything about how much of
the screen may change, and how often, came off real Commstar in
`docs/spikes/spike_suggestion_block.py`.
"""

from collections.abc import Sequence

import pytest

from sextile import Page, PageAddress, PageFrame, PageRequest, PageRoute, Sextile, keys
from sextile.formatting import Entry, MenuItem
from sextile.forms import SUGGESTIONS, TypeAhead, draw_form
from sextile.forms.base import SUBMIT_MARK
from sextile.session.session import Session
from sextile.testing import text_of
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import Frame

FIELD_ROW = 2
FIRST_ROW = 4

PLACES = [
    ("TRONDHEIM", "NO"),
    ("TROMSO", "NO"),
    ("TRONDHEIMSFJORDEN", "NO"),
    ("TRONDENES", "NO"),
    ("YORK", "GB"),
    #  Appended rather than inserted: the addresses below are built from these
    #  positions, so a place added in the middle renumbers the lot.
    ("NEW YORK", "US"),
]


def _folded(text: str) -> str:
    """What the index matches against: letters only, as the real one folds."""
    return "".join(letter for letter in text.upper() if letter.isalpha())


async def lookup(typed: str) -> Sequence[Entry]:
    """A gazetteer small enough to reason about."""
    return [
        MenuItem(name.title(), country, PageAddress(f"32{1000 + n}"))
        for n, (name, country) in enumerate(PLACES)
        if _folded(name).startswith(_folded(typed))
    ]


def a_field(**wanted: object) -> TypeAhead:
    return TypeAhead(
        lookup=lookup,
        field_row=FIELD_ROW,
        suggestions_row=FIRST_ROW,
        label="PLACE:",
        **wanted,  # type: ignore[arg-type]
    )


async def typing(form: TypeAhead, letters: str) -> TypeAhead:
    for letter in letters:
        await form.typed(letter)
    return form


def field_value(frame: Frame, form: TypeAhead) -> str:
    """What is in the field, read from where the caret says it ends.

    Rather than by counting spaces: the label, the field's background and the
    text colour all occupy cells and all show as spaces, so a literal is three
    ways to be wrong when any of them changes.
    """
    row, column = form.caret
    return frame.text_at(row, column - len(form.value), len(form.value))


class TestTyping:
    async def test_a_letter_goes_into_the_field(self) -> None:
        assert (await typing(a_field(), "TRO")).value == "TRO"

    async def test_letters_are_shouted(self) -> None:
        #  The index they are matched against holds them that way, and a
        #  viewdata keypad has no case to speak of.
        assert (await typing(a_field(), "tro")).value == "TRO"

    async def test_rubbing_out_takes_the_last_one_back(self) -> None:
        form = await typing(a_field(), "TROM")
        await form.typed(keys.RUB_OUT)
        assert form.value == "TRO"

    async def test_rubbing_out_an_empty_field_is_harmless(self) -> None:
        form = a_field()
        await form.typed(keys.RUB_OUT)
        assert form.value == ""


class TestWhichKeysAreTyping:
    @pytest.mark.parametrize("key", ["A", "z", keys.RUB_OUT])
    def test_letters_and_the_rub_out(self, key: str) -> None:
        assert a_field().accepts(key)

    @pytest.mark.parametrize("key", ["1", "9", "0"])
    def test_but_never_a_digit(self, key: str) -> None:
        #  Digits are spoken for by the suggestions. A place whose name holds
        #  one cannot be keyed, which is the trade a numbered list costs.
        assert not a_field().accepts(key)


class TestWhatIsOffered:
    async def test_nothing_typed_offers_nothing(self) -> None:
        #  Rather than the whole gazetteer in whatever order it is held: a
        #  reader who has typed nothing has asked nothing.
        assert a_field().found == ()

    async def test_what_matches_is_offered(self) -> None:
        form = await typing(a_field(), "TROND")
        assert [entry.text for entry in form.found] == [
            "Trondheim",
            "Trondheimsfjorden",
            "Trondenes",
        ]

    async def test_the_digits_lead_to_them(self) -> None:
        form = await typing(a_field(), "YORK")
        assert form.choices() == {"1": PageAddress("321004")}

    async def test_and_no_further_than_the_wire_affords(self) -> None:
        #  Three, measured. A fourth would be a digit that draws a row nobody
        #  can afford to send.
        form = await typing(a_field(), "TRO")
        assert len(form.choices()) == SUGGESTIONS

    async def test_typing_on_narrows_them(self) -> None:
        form = await typing(a_field(), "TROM")
        assert [entry.text for entry in form.found] == ["Tromso"]

    async def test_and_rubbing_out_widens_them_again(self) -> None:
        form = await typing(a_field(), "TROM")
        await form.typed(keys.RUB_OUT)
        assert len(form.found) > 1


class TestThePromptNamesTheDigitsOffered:
    @staticmethod
    def _choose(form: TypeAhead) -> list[str]:
        return [item.key for item in form.footer_items() if item.label == "choose one"]

    async def test_nothing_typed_names_the_field_capacity(self) -> None:
        #  The footer is drawn once, with the field empty, so it says how many
        #  the field can offer rather than nothing about the choice to come.
        assert self._choose(a_field()) == ["1-3"]

    async def test_one_match_names_the_one_digit(self) -> None:
        assert self._choose(await typing(a_field(), "TROM")) == ["1"]

    async def test_two_matches_name_two_digits(self) -> None:
        assert self._choose(await typing(a_field(), "TRONDH")) == ["1-2"]

    async def test_three_matches_name_three_digits(self) -> None:
        assert self._choose(await typing(a_field(), "TRO")) == ["1-3"]


class TestDrawing:
    async def test_the_field_shows_what_was_typed(self) -> None:
        frame = Frame()
        form = await typing(a_field(), "TROND")
        draw_form(frame, form)
        assert field_value(frame, form) == "TROND"
        assert "PLACE:" in text_of(frame)

    async def test_the_suggestions_are_numbered_beneath_it(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        rows = text_of(frame).splitlines()
        assert "1" in rows[FIRST_ROW] and "Trondheim" in rows[FIRST_ROW]
        assert "2" in rows[FIRST_ROW + 1]

    async def test_a_shorter_suggestion_covers_the_longer_one_it_replaces(self) -> None:
        #  Or a place the reader has typed past goes on offering itself under a
        #  digit that now means something else.
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        draw_form(frame, await typing(a_field(), "TROM"))
        assert "Trondheimsfjorden" not in text_of(frame)

    async def test_nothing_found_says_so(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(no_match="No such place."), "ZZZ"))
        assert "No such place." in text_of(frame)

    async def test_the_caret_sits_where_the_next_letter_lands(self) -> None:
        #  Attributes included: each occupies a cell, so counting only the
        #  characters puts the cursor two to the left of the truth.
        frame = Frame()
        form = await typing(a_field(), "TROND")
        draw_form(frame, form)
        row, column = form.caret
        assert frame.text_at(row, column - len("TROND"), len("TROND")) == "TROND"
        assert frame.text_at(row, column, 1) == " ", "and nothing is under it yet"

    async def test_the_page_around_it_is_left_alone(self) -> None:
        frame = Frame()
        Canvas(frame).row(0).text("FIND A PLACE")
        Canvas(frame).row(20).text("SOMETHING ELSE")
        draw_form(frame, await typing(a_field(), "TROND"))
        shown = text_of(frame).splitlines()
        assert "FIND A PLACE" in shown[0]
        assert "SOMETHING ELSE" in shown[20]


class TestThroughASession:
    """What a reader actually experiences, keystroke by keystroke."""

    async def _session(self) -> tuple[Session, TypeAhead]:
        form = a_field()

        async def search(request: PageRequest) -> Page:
            canvas = Canvas()
            canvas.row(0).text("FIND A PLACE")
            draw_form(canvas.frame, form)
            return Page(frames=(PageFrame(frame=canvas.frame, form=form),))

        app = Sextile(
            pages=[
                PageRoute("1", search, name="search"),
                PageRoute("32{n:int}", _somewhere, name="place"),
            ]
        )
        session = Session(app)
        await session.greeting()
        return session, form

    async def test_a_letter_repaints_rather_than_moving(self) -> None:
        session, _ = await self._session()
        before = session.address
        sent = await session.receive(b"T")
        assert session.address == before, "typing is not going anywhere"
        assert sent, "and something was sent"

    async def test_what_was_typed_reaches_the_screen(self) -> None:
        session, form = await self._session()
        await session.receive(b"TROND")
        frame = session.current_frame()
        assert frame is not None
        assert field_value(frame, form) == "TROND"

    async def test_a_digit_goes_to_what_it_is_offering(self) -> None:
        session, _ = await self._session()
        await session.receive(b"YORK")
        await session.receive(b"1")
        assert session.address == PageAddress("321004")

    async def test_rubbing_out_reaches_the_form(self) -> None:
        session, form = await self._session()
        await session.receive(b"TROM")
        await session.receive(b"\x7f")
        frame = session.current_frame()
        assert frame is not None
        assert field_value(frame, form) == "TRO"

    async def test_a_page_request_still_leaves_the_page(self) -> None:
        #  The star is untouched by any of this: a reader is never trapped in a
        #  field they cannot get out of.
        session, _ = await self._session()
        await session.receive(b"TROND")
        await session.receive(b"*321001#")
        assert session.address == PageAddress("321001")

    async def test_only_the_form_s_rows_are_sent(self) -> None:
        #  Not the whole frame, which is eight seconds at 1200 baud against
        #  one for the block.
        session, _ = await self._session()
        await session.receive(b"TRO")
        sent = b"".join(await session.receive(b"N"))
        assert len(sent) < 200, f"a keystroke cost {len(sent)} bytes"

    async def test_and_a_keystroke_that_settles_the_list_costs_less(self) -> None:
        #  Typing on into a list that has narrowed to one leaves the
        #  suggestions alone and repaints the field only.
        session, _ = await self._session()
        await session.receive(b"TROMS")
        settled = b"".join(await session.receive(b"O"))
        assert len(settled) < 60, f"the common keystroke cost {len(settled)} bytes"


async def _somewhere(request: PageRequest, n: int) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))


class TestTheSecondColumn:
    async def test_the_detail_sits_in_a_column_of_its_own(self) -> None:
        #  Names vary in length, so a detail written straight after one puts
        #  the second column somewhere different on every row. A fixed column
        #  reads as a column -- and a *fixed* one rather than one fitted to the
        #  widest name showing, which would move as the reader types and turn
        #  every keystroke into a repaint of all three rows.
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TRO"))
        rows = text_of(frame).splitlines()
        ends = {row.rstrip().rfind("NO") for row in rows[FIRST_ROW : FIRST_ROW + 3]}
        assert len(ends) == 1, "the countries do not line up"

    async def test_a_long_name_is_shortened_rather_than_the_detail(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TRONDHEIMS"))
        row = text_of(frame).splitlines()[FIRST_ROW]
        assert "NO" in row, "the detail survives"
        assert "Trondheims" in row, "and as much of the name as fits"


class TestSending:
    """What RETURN does, which a reader will press without being told.

    It takes the first suggestion -- the same as pressing 1. A reader can *see*
    the list, so refusing something visibly on offer because it is not
    character-for-character what they typed would be perverse; and nobody types
    a name in full once three letters have found it.
    """

    async def test_it_takes_the_first_suggestion(self) -> None:
        form = await typing(a_field(), "TROND")
        assert form.submit() == form.choices()["1"]

    async def test_which_is_what_pressing_one_would_have_done(self) -> None:
        session, _ = await self._session()
        await session.receive(b"YORK")
        await session.receive(b"\x5f")
        assert session.address == PageAddress("321004")

    async def test_a_partial_word_still_sends(self) -> None:
        #  TRO is not a place; Trondheim is, and it is the one on offer.
        session, _ = await self._session()
        await session.receive(b"TRO")
        await session.receive(b"\x5f")
        assert session.address != PageAddress("1"), "it went somewhere"

    async def test_hash_does_the_same(self) -> None:
        #  The conventional viewdata key, and the one most readers try first.
        session, _ = await self._session()
        await session.receive(b"YORK")
        await session.receive(b"#")
        assert session.address == PageAddress("321004")

    async def test_sending_nothing_goes_nowhere(self) -> None:
        session, _ = await self._session()
        await session.receive(b"\x5f")
        assert session.address == PageAddress("1")

    async def test_and_nor_does_a_word_that_matches_nothing(self) -> None:
        #  The page already says so where the suggestions would be; taking the
        #  reader somewhere would be worse than leaving them to correct it.
        session, _ = await self._session()
        await session.receive(b"ZZZZ")
        await session.receive(b"\x5f")
        assert session.address == PageAddress("1")

    async def _session(self) -> tuple[Session, TypeAhead]:
        form = a_field()

        async def search(request: PageRequest) -> Page:
            canvas = Canvas()
            draw_form(canvas.frame, form)
            return Page(frames=(PageFrame(frame=canvas.frame, form=form),))

        app = Sextile(
            pages=[
                PageRoute("1", search, name="search"),
                PageRoute("32{n:int}", _somewhere, name="place"),
            ]
        )
        session = Session(app)
        await session.greeting()
        return session, form


class TestMarkingWhatReturnWouldTake:
    """A key that does something invisible is a key nobody presses.

    A browser's address bar marks the row ENTER would choose. This does the
    same with the key's own character, beside the digit it does the same thing
    as.
    """

    async def test_the_first_suggestion_is_marked(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        assert text_of(frame).splitlines()[FIRST_ROW].rstrip().endswith(SUBMIT_MARK)

    async def test_and_the_others_are_not(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        rows = text_of(frame).splitlines()
        assert SUBMIT_MARK not in rows[FIRST_ROW + 1]
        assert SUBMIT_MARK not in rows[FIRST_ROW + 2]

    async def test_it_does_not_run_into_the_digit(self) -> None:
        #  In front of the digit it abutted it, and "#1" reads as "number 1"
        #  rather than as two keys that do the same thing.
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        assert f"{SUBMIT_MARK}1" not in text_of(frame)

    async def test_the_digits_still_line_up(self) -> None:
        #  A mark that shifted the first row would make the list read as two.
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        rows = text_of(frame).splitlines()[FIRST_ROW : FIRST_ROW + 3]
        columns = {row.index(digit) for row, digit in zip(rows, "123", strict=True)}
        assert len(columns) == 1

    async def test_it_marks_what_return_actually_takes(self) -> None:
        form = await typing(a_field(), "TROND")
        frame = Frame()
        draw_form(frame, form)
        assert text_of(frame).splitlines()[FIRST_ROW].rstrip().endswith(SUBMIT_MARK)
        assert form.submit() == form.choices()["1"]

    async def test_nothing_on_offer_is_nothing_marked(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(no_match="No such place."), "ZZZ"))
        assert SUBMIT_MARK not in text_of(frame)


class TestTypingANameAsItIsWritten:
    """Place names hold spaces and hyphens, so a reader should be able to.

    The search page used to tell them there was no space bar. There is; it
    transmits 0x20 like anything else, measured in `spike_editing_keys.py`.
    What was dropping it was this framework's own command parser.
    """

    async def test_a_space_goes_into_the_field(self) -> None:
        assert (await typing(a_field(), "NEW YORK")).value == "NEW YORK"

    async def test_and_finds_the_place_all_the_same(self) -> None:
        #  What the field is matched against folds spaces out, so the reader
        #  may type it either way.
        spaced = await typing(a_field(), "NEW YORK")
        joined = await typing(a_field(), "NEWYORK")
        assert [entry.text for entry in spaced.found] == [
            entry.text for entry in joined.found
        ]

    async def test_a_hyphen_too(self) -> None:
        assert (await typing(a_field(), "STRATFORD-UPON")).value == "STRATFORD-UPON"

    async def test_but_a_digit_is_still_a_choice(self) -> None:
        assert not a_field().accepts("1")

    async def test_a_space_reaches_the_field_through_a_session(self) -> None:
        session, form = await self._session()
        await session.receive(b"NEW YORK")
        assert form.value == "NEW YORK"

    async def _session(self) -> tuple[Session, TypeAhead]:
        form = a_field()

        async def search(request: PageRequest) -> Page:
            canvas = Canvas()
            draw_form(canvas.frame, form)
            return Page(frames=(PageFrame(frame=canvas.frame, form=form),))

        app = Sextile(pages=[PageRoute("1", search, name="search")])
        session = Session(app)
        await session.greeting()
        return session, form


class TestWhatAKeystrokeCosts:
    """The wire is the whole constraint, so this is a test and not a note.

    At 1200 baud a whole frame is eight seconds. A reader typing into a field
    changes one cell, and the difference between sending that cell and sending
    the rows around it is the difference between a search that keeps up and one
    that does not.
    """

    async def _session(self) -> tuple[Session, TypeAhead]:
        form = a_field()

        async def search(request: PageRequest) -> Page:
            canvas = Canvas()
            draw_form(canvas.frame, form)
            return Page(frames=(PageFrame(frame=canvas.frame, form=form),))

        app = Sextile(pages=[PageRoute("1", search, name="search")])
        session = Session(app)
        await session.greeting()
        return session, form

    async def test_a_letter_that_changes_nothing_else_costs_one_byte(self) -> None:
        #  TROM and TROMS offer the same one place, so only the field moves --
        #  and the cursor is already sitting where the S goes.
        session, _ = await self._session()
        await session.receive(b"TROM")
        assert b"".join(await session.receive(b"S")) == b"S"

    async def test_rubbing_one_out_costs_three(self) -> None:
        session, _ = await self._session()
        await session.receive(b"TROMS")
        assert len(b"".join(await session.receive(b"\x7f"))) == 3

    async def test_a_letter_that_changes_the_list_costs_the_rows_it_changed(
        self,
    ) -> None:
        #  Unavoidable, and the design working: the reader is being shown
        #  something new.
        session, _ = await self._session()
        await session.receive(b"TRO")
        churning = b"".join(await session.receive(b"M"))
        assert len(churning) > 3
        assert len(churning) < 200

    async def test_the_cursor_is_hidden_while_the_list_repaints(self) -> None:
        session, _ = await self._session()
        await session.receive(b"TRO")
        churning = b"".join(await session.receive(b"M"))
        assert churning.startswith(bytes([ScreenControl.CURSOR_OFF]))
        assert churning.endswith(bytes([ScreenControl.CURSOR_ON]))
