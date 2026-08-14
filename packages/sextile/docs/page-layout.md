# A page layout: its furniture, and the parts between

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

A **page layout** holds the furniture and the content. It knows the title, the way home,
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
  the layout's, and they differ from frame to frame.
- **footer items** — what to name in the prompt. `1-9 select` on a menu,
  `A-Z type a name` and `TAB next field` on a form. The layout adds the
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
layout.

## What it would cost

Two types where there is one. The 23 construction sites would change shape:

```python
PageLayout(
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

**Capacity is shared knowledge.** The layout knows the row range; content
knows how much it needs. The arithmetic that currently lives in one place
(`_capacity`, `_deal`) would be split across the seam, and off-by-one errors
there write over the bottom rule.

**One name is still open**: the per-frame return value, sketched above as
`Filling`, which is a placeholder.

## Parts laid out down a frame

The seam above splits furniture from content and leaves content as one thing.
It does not have to be. The content of a page is a short list of parts arranged
down the frame, and giving each part a rule about which frames it appears on
covers every case in the workspace.

Four kinds of part are enough:

    once      drawn one time, at its place in the order
    every     drawn on every frame, at the position the list gives it
    flowing   broken across as many frames as it takes
    break     whatever follows begins on a new frame

List order settles what sits above what. That is the whole vocabulary.

### It removes the fields rather than adding to them

`preamble`, `headings` and `footnote` are the same idea spelled three times:
rows around the entries, differing in whether they sit above or below and
whether they appear once or on every frame. As parts, the difference is
position in the list and one word:

    [ Once(preamble), Every(headings), Flowing(Menu(items)), Every(footnote) ]

Above-versus-below falls out of the ordering. First-frame-versus-every falls
out of the rule. Three fields, and the knob-counting problem they represent,
stop existing.

### The six pages

| Page | Parts |
|---|---|
| Latest posts | `[Once(preamble), Flowing(Menu(posts))]` |
| Forecast | `[Once(preamble), Every(headings), Flowing(days)]` |
| One post | `[Every(heading), Flowing(document)]` |
| Month grid | `[Once(grid)]` |
| Place search | `[Once(instructions), Once(form)]` |
| The guide | `[Flowing(moving_keys), Break(), Flowing(asking_keys)]` |

Three of those are the pages with no answer today. The post's subject and
byline repeat on every frame, which is why it draws its own furniture; as a
part with the `every` rule it stops being a special case. The month grid needs
no flowing part at all, so it no longer has to be a sequence of nothing to
obtain a title and a way home. The guide divides where it means to rather than
where the rows run out, which is what a break says.

### Several flowing parts simply follow one another

A part that flows takes the rows left to it and continues on the next frame.
Where a second flowing part follows, it begins in the row after the first has
finished, on whatever frame that is. Concatenation, and nothing more.

That is the same decision `typesetting.rows_for` already made: a post's body and
its list of links are two streams, and it joins them into one before anything
is dealt into frames.

    rows = list(_rows_for(content.blocks, depth=0))
    rows.extend(_link_rows(content))

The alternative is to let two streams compete for the space on a frame, which
is what InDesign and LaTeX do, and neither is worth inheriting here.

InDesign threads a story through a chain of frames a person has drawn and
linked: a feature starting on page 12 and continuing on page 78 is two frames
of one chain, and three articles on a newspaper page are three chains that
cannot spill into each other. The placement question is answered by whoever
draws the rectangles, not by the software.

LaTeX has three streams competing for every page -- the running text, floats,
and footnotes -- and a parameter set that exists to referee them:
`\topfraction`, `\bottomfraction`, `\textfraction`, `\floatpagefraction`,
`\topnumber`, `\bottomnumber`, `\totalnumber`. The familiar failures follow
from allowing it at all. A footnote takes room on the page carrying its
reference, so a footnote that will not fit moves the reference to the next
page, which moves the footnote. Floats that cannot be placed are deferred, and
deferred often enough they drift to the end of the chapter.

CSS Regions offered the same thing for the web, shipped in Blink, and was
removed. CSS Paged Media kept the safe parts: running heads, which are the
`every` rule, and `break-inside: avoid`.

A viewdata frame is twenty rows of forty cells with no floats, no columns and
no images to place. Concatenation answers every case here, and it means there
is no rule about how many parts may flow.

### What concatenation still has to settle

**A part that does not flow is drawn whole or moved on.** Where a fixed part
does not fit in the rows left on a frame, it begins the next one rather than
being split. A part taller than a whole frame can never be placed and is an
error at build time rather than a silent truncation.

**Choices are a frame's budget, not a part's.** A reader chooses with one
keypress, so nine is the most any frame can offer whatever it is divided
between. Two flowing menus on a frame might show five entries and four. So a
flowing part is asked how much of itself fits in the rows *and* the choices
that are left, and `CHOICES_PER_FRAME` stops being a fact about a template and
becomes part of what the layout hands down.

**`once` means once, not first.** A fixed part before any flowing part lands on
the first frame, which is what `preamble` does today. A fixed part after a
flowing part lands on whichever frame that flow finished on. Both are the same
rule -- drawn exactly one time, at its place in the order -- and the second
falls out of concatenation rather than needing its own definition.

**`every` parts are placed against the frame, not the stream.** Those before
the flowing parts reserve rows at the top of every frame; those after reserve
rows at the bottom. What is left between them is what the flowing parts
divide.

### A break where a page divides for a reason of its own

Concatenation answers what happens when one flowing part runs out and another
follows. A page may want the opposite: a division that has nothing to do with
what fits.

    [ Flowing(moving_keys), Break(), Flowing(asking_keys) ]

That is the guide. `pages/guidance.py` builds two lists -- the keys for moving
about, and the keys for asking for something -- and renders exactly two frames.
Its docstring gives that as the reason it cannot be a template:

> A template divides one list between as many frames as it takes; these two
> frames are two different lists, split by what a reader is doing rather than
> by what will fit.

A break says so directly, and the objection goes.

It also removes a silent cap. The guide draws `rows[:CONTENT_ROWS]`, so a
service with more than twenty keys of its own loses the surplus without being
told. As flowing parts they would be dealt onto a third frame, which is what
the reader asked for and what the rest of the framework does.

**A break that would divide nothing is not a break.** One at the start or the
end of the parts, two together, or one on a frame with nothing drawn on it yet:
each is ignored. Otherwise a stray break produces a frame carrying furniture
and no content.

**What a break does not settle** is the rest of the guide. Its compass is drawn
at the *foot* of the first frame where the rows above leave room for it. A part
placed after the first flowing part would be drawn immediately below the last
key row instead. Anchoring a part to the foot of its frame is a separate
question, and a smaller one than the division was.

### What this is not

**Not a widget toolkit.** A frame is a still picture plus a mapping from keys
to addresses, computed once and sent down a 1200-baud line. There is nothing
for per-widget event handling to attach to, and the session already owns what
happens when a key arrives.

**Not a second placement engine.** `viewdata/composition.py` places things
*within* a frame and knows what attributes cost in cells. Parts are stacked
down the frame and nothing here arranges anything side by side.

**Not borrowed from terminal UI frameworks.** Textual and its relatives lay out
into one continuous viewport and scroll it. The problem here is the opposite:
break into discrete frames of twenty rows, each carrying its own furniture and
its own keys, with no scrolling anywhere. What does transfer is one idea --
docking a header and a footer and giving the rest to content -- which is the
furniture-and-content split already.

The nearer prior art is paged media: CSS `@page` with running heads,
InDesign's threaded text frames, LaTeX's output routine. All of them answer the
same question, which is how a stream of material breaks across pages and what
repeats on each.

One constraint none of them has: **a menu holds nine items to a frame because a
reader chooses with one keypress**, not because of how tall an item is. So a
flowing part is asked how many of itself fit in the rows available, rather than
being measured and divided by a parent.

### What it would replace

`viewdata/typesetting.py` breaks rendered rows into frames; `Template` breaks
entries into frames. Both are the flowing rule, written twice, and they had
diverged: one stopped at twenty-six frames and said so, the other built a
twenty-seventh and raised `ValueError` out of `frame_letter`. That is fixed,
but two implementations of one idea will diverge again.

### Risks

**A layout engine is a large thing to build for twenty-five pages.** The
version worth having is the smallest one this evidence demands: three rules,
concatenation where parts flow, no side-by-side arrangement, no styling
language, no units. If it grows a second axis, a way of expressing proportions,
or a parameter deciding how much of a frame one part may take, it has gone
wrong -- that last is where LaTeX's float parameters came from.

**Capacity becomes shared knowledge.** Today `_capacity` and `_deal` hold the
arithmetic in one place. Split across parts, an off-by-one writes over the rule
at the foot of the frame.

**`Flowing`, `Once`, `Every` and `Break` are placeholder names**, as is
`Filling`.

## What is settled and what is not

Settled by this note: the bottom row is the **footer**, and the prompt, the
command line and the countdown are three things that appear on it. The furniture
and the content are separable, and the evidence is four pages that either draw
their own furniture or pretend to be sequences.

Also settled: where several parts flow, they follow one another and nothing
arbitrates between them. The models that do arbitrate were examined and are not
worth inheriting for a frame of twenty rows.

Not settled: the exact content protocol, whether the call sites change, whether
the footer may ever be more than one row, how a part is anchored to the foot of
a frame, and five names -- the per-frame return value, and the four kinds of
part.
