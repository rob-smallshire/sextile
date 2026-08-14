# A container, its furniture, and its content

A design note. Nothing here is built. It proposes splitting `Template` into two
pieces, and exists to find out whether the seam holds before anything moves.

## The frame, and what each part is called

A frame is 24 rows of 40 cells. `viewdata/chrome.py` fixes the geometry:

    row  0        header        the page title, and the page number at the right
    row  1        rule
    rows 2-21     content       CONTENT_FIRST_ROW, CONTENT_ROWS = 20
    row  22       rule
    row  23       footer        FOOTER_ROW

**The bottom row is the footer.** That is the canonical term and it is already
settled by usage: "footer" appears 89 times in the framework, against 24 for
"prompt" and 19 for "command line", and it names the constant (`FOOTER_ROW`),
the module (`viewdata/footer.py`) and the two types that compose it
(`FooterItem`, `render_footer`).

Three different things occupy that row at different moments, and they are three
things rather than three names for one:

- the **prompt** — which keys work on this frame and what they do, composed
  from `FooterItem` values and shed in priority order when the row is tight;
- the **command line** — what the reader has keyed so far, while a request is
  being typed (`viewdata/command_line.py`);
- the **countdown** — a draining bar warning that a silent line is about to be
  released (`viewdata/countdown.py`), which covers whatever else wanted the
  row.

So no new term is needed for the row. "Navigation bar" would be a fourth name
for it, and would also be too narrow: two of the three things that appear there
are not navigation.

One open question the term "bar" does raise, and worth settling once: the
footer is exactly one row today, and `CONTENT_ROWS = 20` follows from that. A
two-row footer is possible, but every capacity calculation in the framework
derives from that constant, so it is a single decision with a wide blast
radius rather than a local one.

"Furniture" is the collective term for the header, the rules and the footer.
It is used loosely in the design documents already and is worth keeping: the
chrome is what draws it.

## The observation

`Template` does two separable jobs.

**The furniture.** Title and page number in the header, the two rules, the
prompt in the footer, the way home, the shortcuts, the keys that move between
frames, and assembling the `Page`.

**The content.** Everything in rows 2 to 21, and how much of it fits.

Today the only way to obtain the first is to be a formatter of a homogeneous
sequence. Content that is not a sequence has no route to the furniture at all.

## The evidence that these want separating

**Three pages in the workspace draw their own furniture** rather than accept
that constraint, and they are the last entries in
[public-surface.md](public-surface.md)'s list of crossings:

- `stardot_viewdata/post_page.py` — a repeating heading and a paginated
  document;
- `weather_viewdata/handlers.py` — two frames whose content is a field to type
  into;
- and until recently the calendar's two pages, which is how the crossing was
  found.

**One page pretends to be a sequence to get the furniture.** The calendar's
month page is now `Lines(entries=[], preamble=[Block(...)])`. A month grid is
not a collection of items. The furniture and the keys were what it wanted, and
being a formatter of nothing was the price.

**The optional fields divide cleanly along the same line.** Of the nine on
`Template`:

    furniture   title, home, shortcuts, item
    content     entries, preamble, headings, footnote, empty

Every field that has caused concern about knob growth is on the content side,
attached to a class that is mostly about furniture. `Figures` grew `footnote`
because a table of figures wants a note beneath it, which has nothing to do
with titles, rules or keys.

## The seam

A **container** holds furniture and content. It knows the title, the way home,
the shortcuts and what the items are called; it draws the header, the rules and
the prompt, wires the frame-movement keys, and returns a `Page`.

**Content** owns rows 2 to 21. Given the number of rows a frame offers, it
answers two questions: how many frames it needs, and what goes on frame *i*.

A **sequence formatter** is one kind of content: the one that lays out a
homogeneous sequence of items, owning `entries`, `preamble`, `headings`,
`footnote`, `empty` and the capacity arithmetic. `Menu`, `Listing`, `Figures`,
`Lines` and `Prose` become sequence formatters. A month grid, a form and a
post's heading-and-body become three other kinds of content, and get the
furniture without being sequences of anything.

## What content has to tell the furniture

This is the part to get right, and it is more than "draw some rows". Per frame,
content contributes three things upward:

- **choices** — keys that lead somewhere. A menu's digits are content's, not
  the container's, and they differ from frame to frame.
- **footer items** — what to name in the prompt. `1-9 select` on a menu,
  `A-Z type a name` and `TAB next field` on a form. The container adds the
  shortcuts, the movement keys and the way home, and `render_footer` sheds
  what will not fit across the whole set.
- **a form**, where the frame has one, since `PageFrame.form` is what makes a
  frame answer keys by redrawing rather than by going anywhere.

Sketched:

```python
class Content(Protocol):
    def frames(self, rows: int) -> int:
        """How many frames this needs, given `rows` rows on each of them."""

    def fill(self, canvas: Canvas, index: int, first_row: int, rows: int) -> Filling:
        """Draw frame `index`, and say what it claims."""


@dataclass(frozen=True)
class Filling:
    choices: Mapping[str, PageAddress] = ...
    named: Sequence[FooterItem] = ()
    form: Form | None = None
```

`Filling` is a placeholder name and wants a better one.

## This protocol already exists, in part

`Form` is most of it. It has `rows()`, `draw(canvas)`, `choices()` and
`accepts(key)`: it occupies a row range, draws itself, contributes keys that
lead somewhere, and answers keypresses. It reached that shape independently,
for a page that types rather than a page that lists.

That is the strongest evidence the seam is real. It also shows where the
current design put the join in the wrong place: a form hangs off `PageFrame`
as a special case, when it is one kind of content among several.

## The four cases, on both sides of the seam

| Page | Furniture | Content |
|---|---|---|
| Latest posts | title, home | sequence formatter over 60 posts, 9 a frame |
| Month grid | title, home, shortcuts for the months either side, `item="month"` | one frame, draws a grid of weeks |
| One post | title, home, shortcuts for the neighbouring posts | heading repeated on every frame, document paginated beneath it |
| Place search | title, home | a form, its suggestions, and the digits that choose one |

The post page is the one that stresses the design: its heading repeats on every
frame while a sequence formatter's preamble appears only on the first. Under
the split that stops being a special case — the content decides what it puts on
each frame, and repeating a heading is its business rather than a field on the
container.

## What it would cost

Two types where there is one. The 23 construction sites would change shape:

```python
Container(
    title=SERVICE_NAME,
    home=app.index,
    content=Menu(entries=items, empty="Nothing yet."),
).build(address)
```

The alternative is to keep `Menu(title=..., entries=..., home=...)` as it is
and have it construct both halves. That leaves the call sites alone and hides
the split, which defeats the purpose for anyone whose content is not a
sequence.

## Risks

**A protocol got wrong is worse than a class with too many knobs.** The three
things content contributes upward are known from the four cases above; a fifth
case may want a fourth, and each addition is a change to every implementation
rather than a default on one class.

**Capacity is shared knowledge.** The container knows the row range; content
knows how much it needs. The arithmetic that currently lives in one place
(`_capacity`, `_deal`) would be split across the seam, and off-by-one errors
there write over the bottom rule.

**Two of the five names are still open**: what the container is called, and
what the per-frame return value is called. `Container` is serviceable and
generic; `Filling` is a placeholder.

## What is settled and what is not

Settled by this note: the bottom row is the **footer**, and the prompt, the
command line and the countdown are three things that appear on it. The furniture
and the content are separable, and the evidence is four pages that either draw
their own furniture or pretend to be sequences.

Not settled: the exact content protocol, whether the call sites change, what
the container is called, and whether the footer may ever be more than one row.
