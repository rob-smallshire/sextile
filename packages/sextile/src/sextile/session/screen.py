"""What the terminal is showing, and the bytes that change it.

The session decides what should be on screen -- which frame, whether the reader
is mid-request, whether the idle bar is up -- and hands each to the screen to
render. The screen owns the little display state that byte-at-a-time updates
depend on: what the footer row is currently showing of a request being typed,
and how much of the idle-warning bar is lit. Neither is state about *where* the
reader is; both are about what the wire has most recently been told.
"""

import copy

from sextile.forms import draw_form
from sextile.page import Page, PageFrame
from sextile.viewdata.command_line import (
    command_line_bytes,
    footer_bytes,
    incremental_bytes,
)
from sextile.viewdata.frame import Frame
from sextile.viewdata.hangup import hangup_bytes
from sextile.viewdata.idle_warning import idle_warning_bytes, lit_cells
from sextile.viewdata.repaint import (
    NOTHING,
    caret_bytes,
    changed_rows,
    rows_bytes,
    typed_bytes,
)


class Screen:
    """The terminal's display, and the bytes that bring it up to date."""

    def __init__(self) -> None:
        #  What the footer row is currently showing of a request being typed,
        #  or "" when it is showing the page's own prompt. Kept so that a
        #  keystroke which merely extends it can be sent as one byte.
        self._displayed = ""
        #  How much of the idle-warning bar is lit, or None when it is not
        #  showing. Kept so an unchanged bar costs nothing on the wire.
        self._warning_cells: int | None = None
        #  The last whole frame the wire was told, which is not always the
        #  frame the reader is on: a not-found or failed notice is sent over
        #  the page they were left on. A form redraws its frame in place, so
        #  this holds the live frame their typing goes on rather than a copy.
        self._painted: Frame | None = None

    @property
    def painted(self) -> Frame | None:
        """The last whole frame sent to the terminal, or None before the first."""
        return self._painted

    # -- whole frames -------------------------------------------------------

    def full_frame(self, showing: PageFrame) -> bytes:
        """The whole of a frame, and the caret where a field wants it."""
        self._painted = showing.frame
        frame = showing.frame.to_bytes()
        if showing.form is None:
            return frame
        #  A frame begins by hiding the cursor, which is right everywhere but
        #  here: a reader who has arrived at a field needs to see where their
        #  typing will go before they have typed anything. Without this the
        #  caret appears only on the first repaint, which is to say only after
        #  the reader has guessed correctly.
        return frame + caret_bytes(*showing.form.caret)

    def first_frame(self, page: Page) -> bytes:
        """A page's first frame, sent without going to it: said, not gone to."""
        first = page.frame(0)
        assert first is not None, "a page must have at least one frame"
        self._painted = first.frame
        return first.frame.to_bytes()

    def handback(self, frame: Frame | None) -> bytes:
        """Hand the terminal back, after the last frame has gone.

        The reader is about to be talking to their modem again, and a terminal
        with the cursor hidden under a full screen of somebody else's frame
        gives them nothing to type at.
        """
        return hangup_bytes(frame) if frame is not None else b""

    # -- the idle warning ---------------------------------------------------

    @property
    def warning_showing(self) -> bool:
        return self._warning_cells is not None

    def warn(self, remaining: float) -> bytes | None:
        """Draw or update the warning bar, or None if the row would not change.

        ``remaining`` is the fraction of the warning period left.

        The bar covers a request being typed, which shares the row. Nothing is
        lost by that: what was keyed is held in the parser rather than on the
        screen, and comes back the moment the reader touches anything. Leaving
        them unwarned and then cutting them off mid-request would be the rudest
        thing this service could do.
        """
        cells = lit_cells(remaining)
        if cells == self._warning_cells:
            return None
        self._warning_cells = cells
        return idle_warning_bytes(remaining)

    def dismiss(self, entry: str, frame: Frame | None) -> bytes | None:
        """Put back whatever the row should show, or None if no bar was up.

        ``entry`` is what the reader has keyed of a request, which the parser
        holds; ``frame`` is the one currently showing, whose own footer the row
        returns to when nothing is being typed.
        """
        if self._warning_cells is None:
            return None
        self._warning_cells = None
        if entry:
            self._displayed = entry
            return command_line_bytes(entry)
        return footer_bytes(frame) if frame is not None else None

    # -- the command-line echo ----------------------------------------------

    def echo(self, entry: str, showing: PageFrame | None, responses: list[bytes]) -> None:
        """Keep the footer row showing whatever the reader is doing.

        A request being typed replaces the footer; finishing or cancelling one
        puts it back, and so does dismissing the idle warning. A whole frame
        going out has the page's own footer in it already, so nothing more is
        needed then.

        A keystroke that only adds or removes a character changes the row by
        a byte or three rather than repainting it, which is visible as a
        flicker once the cursor is on.
        """
        warned, self._warning_cells = self._warning_cells is not None, None
        if entry:
            #  A bar covering the command line makes the byte-at-a-time trick a
            #  lie: what is on the row is not what was displayed before.
            change = None if warned else incremental_bytes(entry, self._displayed)
            responses.append(change or command_line_bytes(entry))
        elif responses:
            #  A whole frame went out, and it carries the page's own footer.
            pass
        elif self._displayed or warned:
            if showing is not None:
                responses.append(footer_bytes(showing.frame))
                #  Putting the footer back begins by hiding the cursor, which
                #  is right -- something is about to be drawn over the row it
                #  was on. On a page with a field, it has to come back: a
                #  reader who thought better of a page number is otherwise left
                #  in a field with no cursor in it and nothing to say where
                #  their next letter would go.
                if showing.form is not None:
                    responses.append(caret_bytes(*showing.form.caret))
        self._displayed = entry

    # -- typing into a form -------------------------------------------------

    def repaint_form(self, showing: PageFrame) -> bytes:
        """Redraw a form's rows in place and put the cursor where it now belongs.

        For when RETURN kept the reader on the page -- a form of several fields
        finishes one and starts the next -- so the rows may not have changed at
        all, and the caret still has to move to the field now live.
        """
        form = showing.form
        assert form is not None, "only asked of a frame that has one"
        was = copy.deepcopy(showing.frame)
        draw_form(showing.frame, form)
        moved = changed_rows(was, showing.frame, form.rows)
        return rows_bytes(
            showing.frame, moved, was=was, caret=form.caret
        ) or caret_bytes(*form.caret)

    async def type_into(self, showing: PageFrame, key: str) -> bytes | None:
        """Let a form take a keypress, and send back only what it changed.

        The frame is redrawn **in place**, so what the terminal is showing and
        what the session holds stay the same thing: `*00#` sends the frame in
        hand, and it has to be the frame with the reader's typing on it.

        Only the form's own rows are compared, so a form cannot disturb the
        page around it however wrong it is about its own contents. And only the
        rows that differ are sent -- typing narrows a list of suggestions, so
        the common keystroke leaves the top of it alone and costs forty bytes
        rather than a hundred and twenty.
        """
        form = showing.form
        assert form is not None, "only asked of a frame that has one"
        was = copy.deepcopy(showing.frame)
        caret = form.caret
        await form.typed(key)
        draw_form(showing.frame, form)
        moved = changed_rows(was, showing.frame, form.rows)
        #  The cursor is still where the last repaint left it, which is where
        #  the next character goes. So if the only thing that changed is the
        #  cell under it -- which is every keystroke that does not change what
        #  is on offer, and most of them do not -- the whole repaint is that
        #  one character, and the cursor need not even be moved back.
        field = caret[0]
        if moved == [field]:
            typed = typed_bytes(was, showing.frame, field, at=caret[1])
            if typed is not None:
                return typed
        if not moved:
            #  A keystroke that draws nothing and still moves the cursor: a
            #  space is a blank cell over a blank cell, so the frame comes out
            #  identical and there are no rows to send. Sending nothing leaves
            #  the cursor a cell behind where the form now thinks it is, and
            #  every keystroke after it lands one cell out -- which is how
            #  `ULAN BATOR` came to be typed with its space in the wrong place
            #  and rubbed out leaving characters behind.
            return caret_bytes(*form.caret) if form.caret != caret else NOTHING
        return rows_bytes(showing.frame, moved, was=was, caret=form.caret)
