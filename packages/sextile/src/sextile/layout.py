"""Parts laid out down the frames of a page.

A page's content is a short list of parts. Each is drawn once, drawn on every
frame, or broken across as many frames as it takes, and the order of the list
settles what sits above what. `fill` walks them and returns as many frames as
they needed, which is the first of the two passes that build a page: nothing
here knows how many frames there will be, and nothing here draws furniture.

See [page-layout.md](../../docs/page-layout.md) for the design this implements
and the reasoning behind it.

Example:
    A lead-in on the first frame, a heading on all of them, and a menu that
    goes on for as long as it goes on::

        fill(
            [Once(preamble), Every(headings), Flowing(Menu(items))],
            range(CONTENT_FIRST_ROW, CONTENT_FIRST_ROW + CONTENT_ROWS),
        )
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from sextile.addressing import FRAMES_PER_PAGE, PageAddress
from sextile.forms import Form
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.footer import FooterItem


@dataclass(frozen=True)
class Room:
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
class Offer:
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
    form: Form | None = None

    def and_then(self, other: "Offer") -> "Offer":
        """This offer and another, as one.

        Args:
            other: What a later part on the same frame claimed.

        Returns:
            The two merged. Where both claim the same key the later wins,
            which cannot arise between the digits of two flowing parts because
            the second is given only the choices the first left.

        Raises:
            ValueError: If both carry a form. A frame has one field to type
                into; `forms.Fields` is what composes several into one.
        """
        if self.form is not None and other.form is not None:
            raise ValueError("a frame can carry only one form")
        return Offer(
            choices={**self.choices, **other.choices},
            named=[*self.named, *other.named],
            form=self.form or other.form,
        )


@dataclass(frozen=True)
class Placement:
    """What placing a part on one frame came to.

    Attributes:
        rows: The rows it used, which is nought where it would not begin here.
        offer: What it claims on this frame.
        rest: What is left of it for the next frame, or None where it is
            finished. A part that returns nought rows and itself is asking for
            a frame of its own.
    """

    rows: int
    offer: Offer = Offer()
    rest: "Part | None" = None


@runtime_checkable
class Part(Protocol):
    """Something drawn between the rules.

    A part is a description rather than a position, so placing one does not
    change it and a layout may be built more than once. The exception is a
    form, which holds what has been typed.
    """

    def place(self, canvas: Canvas, room: Room) -> Placement:
        """Draw as much as `room` allows, and say what is left over.

        Args:
            canvas: The frame being filled.
            room: What the frame has left to give.

        Returns:
            The rows used, what they claim, and whatever remains for the next
            frame. Returning nought rows and `self` asks for a fresh frame,
            which is how a part too tall for what is left declines to be
            split.
        """
        ...


@dataclass(frozen=True)
class Once:
    """A part drawn one time, at its place in the order.

    On the first frame where nothing flowing comes before it, and otherwise on
    whichever frame the flow before it finished on.
    """

    part: Part


@dataclass(frozen=True)
class Every:
    """A part drawn on every frame, at its place in the order.

    Where it comes after any flowing part, its rows are kept back at the foot
    of every frame before that part is asked for its, since a flowing part
    takes the rows left to it and nothing after one would be drawn at all.
    Where it comes before them all, it is drawn where it stands. Several of
    either follow one another in the order the list gives them.
    """

    part: Part


@dataclass(frozen=True)
class Flowing:
    """A part broken across as many frames as it takes.

    Several may appear in one list, and they follow one another: the second
    begins in the row after the first has finished, on whatever frame that is.
    """

    part: Part


@dataclass(frozen=True)
class Break:
    """A division the page means, rather than one the rows forced.

    Whatever follows begins on a new frame. A break that would divide nothing
    is ignored: one at either end of the list, two together, or one on a frame
    with nothing yet drawn on it.
    """


#: One item of a page's content: a part, and which frames it appears on.
type Laid = Once | Every | Flowing | Break


@dataclass
class Filled:
    """One frame's content, before any furniture is drawn on it.

    Attributes:
        canvas: The frame, with the content drawn and the furniture rows left
            alone.
        offer: Everything the parts on this frame claimed, merged.
    """

    canvas: Canvas
    offer: Offer = field(default_factory=Offer)


#: The digits a frame can offer, a reader choosing with one keypress. Held here
#: rather than in the templates because it is a fact about the keypad and the
#: whole frame shares it, however many parts divide it up.
CHOICES_PER_FRAME = 9


def fill(parts: Sequence[Laid], rows: range) -> list[Filled]:
    """Draw the parts onto as many frames as they take.

    Args:
        parts: The page's content, in the order it is to appear.
        rows: The rows of a frame the content may use, the furniture having
            taken the rest.

    Returns:
        One `Filled` a frame, in order, and never none: a page that answered
        with no frames could not be shown. Stops at `FRAMES_PER_PAGE`, a page
        having frames `a` to `z` and no more.

    Raises:
        ValueError: If a part can never be placed, being taller than a whole
            frame, or if two parts on one frame both carry a form.
    """
    state = _State(parts)
    frames: list[Filled] = []
    while True:
        frames.append(_frame(state, rows))
        if state.finished or len(frames) == FRAMES_PER_PAGE:
            return frames


@dataclass
class _State:
    """How far through the list the filling has got.

    `pending` is what is left to draw of each item, by its position in the
    list: a `Once` that has been drawn and a `Flowing` that has run out are
    both absent from it.
    """

    parts: Sequence[Laid]
    pending: dict[int, Part] = field(default_factory=dict)
    broken: set[int] = field(default_factory=set)
    at_foot: dict[int, Part] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.pending = {
            index: laid.part
            for index, laid in enumerate(self.parts)
            if not isinstance(laid, Break)
        }
        self.at_foot = _at_foot(self.parts)

    @property
    def finished(self) -> bool:
        """Whether anything is left that is not drawn on every frame."""
        return not any(
            index in self.pending
            for index, laid in enumerate(self.parts)
            if not isinstance(laid, Every | Break)
        )


def _at_foot(parts: Sequence[Laid]) -> dict[int, Part]:
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
        (index for index, laid in enumerate(parts) if isinstance(laid, Flowing)),
        len(parts),
    )
    return {
        index: laid.part
        for index, laid in enumerate(parts)
        if index > flowing and isinstance(laid, Every)
    }


def _height(part: Part, rows: range) -> int:
    """How many rows a part takes on a whole frame.

    Measured by placing it on a canvas that is then thrown away. A part is a
    description and placing one does not change it, so the second placing --
    the one that counts -- draws the same thing in the row it belongs on. The
    alternative was a second method on every part, asked before every draw.
    """
    return part.place(
        Canvas(), Room(rows.start, len(rows), CHOICES_PER_FRAME)
    ).rows


def _frame(state: _State, rows: range) -> Filled:
    """Fill one frame, taking as much of what is pending as will go on it."""
    filled = Filled(canvas=Canvas())
    #  A part at the end of the list that is drawn on every frame is charged
    #  its rows before anything flowing is asked for its, or the flow takes
    #  them and the note beneath it is written over.
    reserved = _reserved(state, rows)
    at, left = rows.start, len(rows) - reserved
    choices = CHOICES_PER_FRAME
    drawn = False

    for index, laid in enumerate(state.parts):
        if isinstance(laid, Break):
            #  A break on a frame with nothing on it yet would make an empty
            #  one, and a break already honoured is not a second division.
            if drawn and index not in state.broken:
                state.broken.add(index)
                break
            continue
        if index in state.at_foot:
            continue
        part = state.pending.get(index)
        if part is None:
            continue
        placed = part.place(filled.canvas, Room(at, left, choices))
        if placed.rows == 0 and placed.rest is part:
            if not drawn:
                raise ValueError(f"{part!r} can never be placed: it is taller than a frame")
            break
        drawn = True
        filled.offer = filled.offer.and_then(placed.offer)
        at, left = at + placed.rows, left - placed.rows
        choices -= len(placed.offer.choices)
        if isinstance(laid, Every):
            continue
        if placed.rest is None:
            del state.pending[index]
        else:
            state.pending[index] = placed.rest
            break

    _draw_at_foot(state, filled, rows, reserved)
    return filled


def _reserved(state: _State, rows: range) -> int:
    """Rows kept back on every frame for the parts drawn at its foot."""
    total = 0
    for part in state.at_foot.values():
        rows_wanted = _height(part, rows)
        if rows_wanted == 0:
            #  It would decline a whole frame, so it would decline every frame,
            #  and reserving nothing for it would leave it silently undrawn.
            raise ValueError(f"{part!r} can never be placed: it is taller than a frame")
        total += rows_wanted
    return total


def _draw_at_foot(
    state: _State, filled: Filled, rows: range, reserved: int
) -> None:
    """Draw the parts at the foot, in the rows kept back for them."""
    at = rows.stop - reserved
    for part in state.at_foot.values():
        placed = part.place(filled.canvas, Room(at, rows.stop - at, CHOICES_PER_FRAME))
        filled.offer = filled.offer.and_then(placed.offer)
        at += placed.rows
