"""Parts laid out down the frames of a page.

A page's content is a short list of parts. Each is drawn once, drawn on every
frame, or broken across as many frames as it takes, and the order of the list
settles what sits above what. `fill` walks them and returns as many frames as
they needed. This is the first of the two passes that build a page: it does not
decide the frame count in advance and draws no furniture; the second pass does
both, once the count is known.

See [design.md](../../docs/design.md#laying-out-a-page) for the design this
implements and the reasoning behind it.

Example:
    A lead-in on the first frame, a heading on all of them, and a menu that
    goes on for as long as it goes on::

        fill(
            [OnOneFrame(preamble), OnEveryFrame(headings), Flow(Menu(items))],
            content_rows(DEFAULT_FURNITURE),
        )
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from sextile.layout.footer import FooterItem
from sextile.page import FRAMES_PER_PAGE, PageAddress
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import ROWS
from sextile.viewdata.typesetting import TRUNCATION_NOTICE

if TYPE_CHECKING:
    from sextile.forms import Form


@dataclass(frozen=True)
class Space:
    """What is left of a frame when a part is asked to draw on it.

    Attributes:
        first_row: The row the part would begin on.
        rows: How many rows are left, which may be nought.
        choices: How many of the digits `1-9` are still unclaimed on this
            frame. A reader chooses with one keypress, so this is a budget the
            whole frame shares however it is divided between parts.
    """

    first_row: int
    rows: int
    choices: int


@dataclass(frozen=True)
class Claim:
    """What a part claims on the frame it has drawn on.

    Attributes:
        choices: Keys that lead somewhere, which for a menu are its digits and
            differ from frame to frame.
        named: What to name in the prompt, such as `1-9 select`. The layout
            adds the shortcuts, the movement keys and the way home.
        form: A field the reader types into, where this part is one.
    """

    choices: Mapping[str, PageAddress] = field(default_factory=dict)
    named: Sequence[FooterItem] = ()
    form: "Form | None" = None

    def merged_with(self, other: "Claim") -> "Claim":
        """This claim and another, as one.

        Args:
            other: What a later part on the same frame claimed.

        Returns:
            The two merged. Where both claim the same key the later wins,
            which cannot arise between the digits of two flowing parts because
            the second is given only the choices the first left.

        Raises:
            ValueError: If both carry a form. A frame has one field to type
                into; `forms.FieldSet` is what composes several into one.
        """
        if self.form is not None and other.form is not None:
            raise ValueError("a frame can carry only one form")
        return Claim(
            choices={**self.choices, **other.choices},
            named=[*self.named, *other.named],
            form=self.form or other.form,
        )


@dataclass(frozen=True)
class Placed:
    """What placing a drawable on one frame came to.

    Attributes:
        rows: The rows it used, which is nought where it would not begin here.
        claim: What it claims on this frame.
        remainder: What is left of it for the next frame, or None where it is
            finished. A drawable that returns nought rows and itself is asking
            for a frame of its own.
    """

    rows: int
    claim: Claim = Claim()
    remainder: "Drawable | None" = None


@runtime_checkable
class Drawable(Protocol):
    """Something drawn between the rules: a menu, some lines, a picture, a form.

    A drawable is a description rather than a position, so placing one does not
    change it and a layout may be built more than once. The exception is a
    form, which holds what has been typed.
    """

    def place(self, canvas: Canvas, room: Space) -> Placed:
        """Draw as much as `room` allows, and say what is left over.

        Args:
            canvas: The frame being filled.
            room: What the frame has left to give.

        Returns:
            The rows used, what they claim, and whatever remains for the next
            frame. Returning nought rows and `self` asks for a fresh frame,
            which is how a drawable too tall for what is left is carried whole
            to the next frame rather than split.
        """
        ...


@dataclass(frozen=True)
class Custom:
    """A part of a stated height, drawn cell by cell by the page itself.

    A picture is positioned at a cell and may be several rows tall, which suits
    a strip of mosaics or a grid of figures and does not suit a line of text.

    Attributes:
        rows: How many rows of the frame it occupies.
        draw: Called with the canvas and the row it begins on.

    Example:
        A month as a grid of weeks, which is the whole of a page's content::

            OnOneFrame(Custom(rows=1 + len(weeks), draw=lambda canvas, row: ...))
    """

    rows: int
    draw: "Callable[[Canvas, int], None]"

    def place(self, canvas: Canvas, room: Space) -> Placed:
        if room.rows < self.rows:
            return Placed(rows=0, remainder=self)
        self.draw(canvas, room.first_row)
        return Placed(rows=self.rows)


@dataclass(frozen=True)
class OnOneFrame:
    """A drawable drawn one time, at its place in the order.

    On the first frame where nothing flowing comes before it, and otherwise on
    whichever frame the flow before it finished on.
    """

    drawable: Drawable


@dataclass(frozen=True)
class OnEveryFrame:
    """A drawable drawn on every frame, at its place in the order.

    Where it comes after any flowing part, its rows are kept back at the foot
    of every frame before the flowing part is placed, since a flowing part
    takes the rows left to it and nothing after one would be drawn at all.
    Where it comes before them all, it is drawn where it stands. Several of
    either follow one another in the order the list gives them.
    """

    drawable: Drawable


@dataclass(frozen=True)
class Flow:
    """A drawable broken across as many frames as it takes.

    Several may appear in one list, and they follow one another: the second
    begins in the row after the first has finished, on whatever frame that is.
    """

    drawable: Drawable


@dataclass(frozen=True)
class FrameBreak:
    """A division the page means, rather than one the rows forced.

    Whatever follows begins on a new frame. A break that would divide nothing
    is ignored: one at either end of the list, two together, or one on a frame
    with nothing yet drawn on it.
    """


#: One of a page's parts: a `Drawable` with the frames it appears on
#: (`OnOneFrame`, `OnEveryFrame` or `Flow`), a `FrameBreak`, or a bare `Drawable`, which means
#: `Flow` -- flowing across as many frames as it takes is what a part does
#: unless it says otherwise, and it is the only sensible reading of one given
#: without a wrapper.
type Part = OnOneFrame | OnEveryFrame | Flow | FrameBreak | Drawable

#: A part once a bare drawable has been read as `Flow`: what the filling
#: works in, every part carrying its own `drawable`.
_Placed = OnOneFrame | OnEveryFrame | Flow | FrameBreak


def _placed(part: Part) -> _Placed:
    """Read a bare drawable in a parts list as a flowing part."""
    if isinstance(part, OnOneFrame | OnEveryFrame | Flow | FrameBreak):
        return part
    return Flow(part)


@dataclass
class _FilledFrame:
    """One frame's content, before any furniture is drawn on it.

    Attributes:
        canvas: The frame, with the content drawn and the furniture rows left
            alone.
        claim: Everything the parts on this frame claimed, merged.
    """

    canvas: Canvas
    claim: Claim = field(default_factory=Claim)


#: The digits a frame can offer, a reader choosing with one keypress. Held here
#: rather than in a sequence part because it is a fact about the keypad and the
#: whole frame shares it, however many parts divide it up.
CHOICES_PER_FRAME = 9


def fill(parts: Sequence[Part], rows: range) -> list[_FilledFrame]:
    """Draw the parts onto as many frames as they take.

    Args:
        parts: The page's content, in the order it is to appear.
        rows: The rows of a frame the content may use, the furniture having
            taken the rest.

    Returns:
        One `_FilledFrame` a frame, in order, and never none: a page that answered
        with no frames could not be shown. Stops at `FRAMES_PER_PAGE`, a page
        having frames `a` to `z` and no more, and says so on the last row of
        the last of them rather than ending without explanation.

    Raises:
        ValueError: If a part can never be placed, being taller than a whole
            frame, or if two parts on one frame both carry a form.
    """
    state = _State([_placed(part) for part in parts])
    frames: list[_FilledFrame] = []
    while True:
        frames.append(_frame(state, rows))
        if state.finished:
            return frames
        if len(frames) == FRAMES_PER_PAGE:
            #  A page has frames a to z and no more. A reader who has reached
            #  the end of what there is should not be left wondering whether
            #  that was all of it, so the last row says what happened.
            frames[-1].canvas.row(rows.stop - 1).text(TRUNCATION_NOTICE, Colour.RED)
            return frames


@dataclass
class _State:
    """How far through the list the filling has got.

    `pending` is what is left to draw of each item, by its position in the
    list: a `OnOneFrame` that has been drawn and a `Flow` that has run out are
    both absent from it.
    """

    parts: Sequence[_Placed]
    pending: dict[int, Drawable] = field(default_factory=dict)
    broken: set[int] = field(default_factory=set)
    at_foot: dict[int, Drawable] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.pending = {
            index: part.drawable
            for index, part in enumerate(self.parts)
            if not isinstance(part, FrameBreak)
        }
        self.at_foot = _at_foot(self.parts)

    @property
    def finished(self) -> bool:
        """Whether anything is left that is not drawn on every frame."""
        return not any(
            index in self.pending
            for index, part in enumerate(self.parts)
            if not isinstance(part, OnEveryFrame | FrameBreak)
        )


def _at_foot(parts: Sequence[_Placed]) -> dict[int, Drawable]:
    """Which parts drawn on every frame have their rows kept back at the foot.

    Those that come after the first flowing part, in the order the list gives
    them. A flowing part takes the rows left to it, so anything after one that
    waited its turn would find them gone -- and would not merely be pushed
    down, but never drawn at all, since the frame ends when a flowing part
    still has more to give.

    Those before the first flowing part need none of this. Nothing above them
    can take their rows, so they are drawn where they stand.
    """
    flowing = next(
        (index for index, part in enumerate(parts) if isinstance(part, Flow)),
        len(parts),
    )
    return {
        index: part.drawable
        for index, part in enumerate(parts)
        if index > flowing and isinstance(part, OnEveryFrame)
    }


def _height(drawable: Drawable, rows: range) -> int:
    """How many rows a drawable takes on a whole frame.

    Measured by placing it on a canvas that is then thrown away. A drawable is
    a description and placing one does not change it, so the second placing --
    the one that counts -- draws the same thing in the row it belongs on.
    """
    return drawable.place(
        Canvas(), Space(rows.start, len(rows), CHOICES_PER_FRAME)
    ).rows


def _frame(state: _State, rows: range) -> _FilledFrame:
    """Fill one frame, taking as much of what is pending as will go on it."""
    filled = _FilledFrame(canvas=Canvas())
    #  A part at the end of the list that is drawn on every frame is charged
    #  its rows before anything flowing is asked for its, or the flow takes
    #  them and the note beneath it is written over.
    reserved = _reserved(state, rows)
    at, left = rows.start, len(rows) - reserved
    choices = CHOICES_PER_FRAME
    drawn = False

    for index, part in enumerate(state.parts):
        if isinstance(part, FrameBreak):
            #  A break on a frame with nothing on it yet would make an empty
            #  one, and a break already honoured is not a second division.
            if drawn and index not in state.broken:
                state.broken.add(index)
                break
            continue
        if index in state.at_foot:
            continue
        drawable = state.pending.get(index)
        if drawable is None:
            continue
        placed = drawable.place(filled.canvas, Space(at, left, choices))
        if placed.rows == 0 and placed.remainder is drawable:
            if not drawn:
                raise ValueError(f"{drawable!r} can never be placed: it is taller than a frame")
            break
        drawn = True
        filled.claim = filled.claim.merged_with(placed.claim)
        at, left = at + placed.rows, left - placed.rows
        choices -= len(placed.claim.choices)
        if isinstance(part, OnEveryFrame):
            continue
        if placed.remainder is None:
            del state.pending[index]
        else:
            state.pending[index] = placed.remainder
            break

    _draw_kept_back(state, filled, at)
    return filled


def _reserved(state: _State, rows: range) -> int:
    """Rows kept back on every frame for the parts drawn at its foot."""
    total = 0
    for drawable in state.at_foot.values():
        rows_wanted = _height(drawable, rows)
        if rows_wanted == 0:
            #  It would decline a whole frame, so it would decline every frame,
            #  and reserving nothing for it would leave it silently undrawn.
            raise ValueError(f"{drawable!r} can never be placed: it is taller than a frame")
        total += rows_wanted
    return total


def _draw_kept_back(state: _State, filled: _FilledFrame, at: int) -> None:
    """Draw the parts whose rows were kept back, under what they follow.

    Kept back from the foot so that a flowing part cannot take them, but drawn
    where the content ended rather than at the foot itself. On a full frame the
    two are the same row; on a short one, a note that explains a table of four
    figures belongs under the table and not thirteen rows beneath it.
    """
    for drawable in state.at_foot.values():
        placed = drawable.place(filled.canvas, Space(at, ROWS - at, CHOICES_PER_FRAME))
        filled.claim = filled.claim.merged_with(placed.claim)
        at += placed.rows
