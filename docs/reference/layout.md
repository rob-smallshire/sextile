# Layout

Reference: the pieces a page is built from, as a map from what a page looks like
to the type that draws it. A service constructs a `PageLayout` and calls
`.build(request)`; the rest is what goes in its fields. The commonest shapes are
re-exported from `sextile`; the full sets are in {py:mod}`sextile.layout` and
{py:mod}`sextile.formatting`.

## The page

`PageLayout` is the whole of a page, laid out down as many frames as it takes.

| Field | What it is |
|---|---|
| `title` | what the header calls the page; `None` takes the registered title |
| `parts` | the content, in the order it appears down the frames |
| `home` | where `0` leads; unset is the service's index, `None` offers no way home |
| `numbered` | whether the header shows the page number |
| `shortcuts` | `Shortcut` keys offered on every frame besides the digits and `0` |
| `item_noun` | what `A` and `D` move between, as the footer says it |
| `furniture` | the bands round the content |
| `next_page` | where `#` leads once the frames have run out |
| `hang_up` | whether the line drops once the page has been shown |

## Parts: which frames content appears on

| To draw | Use |
|---|---|
| a part on the first frame with room before it | `OnOneFrame(drawable)` |
| a part on every frame | `OnEveryFrame(drawable)` |
| a part broken across as many frames as it takes | `Flow(drawable)` |
| a picture positioned cell by cell | `Custom(rows=, draw=)` |
| a forced break between two parts | `FrameBreak` |

Each wraps a `Drawable`. `Part` is the four wrappers together, which the layout
walks onto frames itself.

## Content shapes: what a part draws

| To show | Use |
|---|---|
| numbered choices, chosen by a digit | `Menu` of `MenuItem` |
| lines exactly as given | `Lines` |
| a two-column reference | `Listing` |
| rows of figures | `Figures` |
| running text, wrapped | `Prose` |
| a sequence drawn your own way | a `SequencePart` subclass |

`RowSequencePart` writes each entry along its rows; `NumberedRowSequencePart`
draws the digit column too, for entries a reader chooses. `Entry` and `MenuItem`
are what a shape is given.

## Furniture: the bands round the content

| Band | Type |
|---|---|
| the header row | `Header` |
| a rule | `Rule` |
| the prompt row | `Footer` |
| a band of your own | any `Furnishing` |

`DEFAULT_FURNITURE` is the header, two rules and the footer; `content_rows`
is the rows they leave a page. A `Furnishing` satisfies the protocol drawn with a
`FrameContext` and docked to an `Edge`.

## A part of your own

A `Drawable` implements `place(canvas, space) -> Placed`. `Space` is the room
offered — its `first_row`, `rows` and `choices` — `Claim` is what the part took
(its `choices`, what it `named` in the prompt, and any `form`), and `Placed`
carries the rows drawn and the remainder for the next frame.
`CHOICES_PER_FRAME` is nine, the digits a frame has.

## A prompt drawn by hand

`render_footer(items, FOOTER_WIDTH)` composes the prompt row from `FooterItem`s,
shedding what will not fit in `Priority` order; `movement(available, item=)`
gives the `FooterItem`s for the movement keys a frame answers.

Why one import: `PageLayout`, the parts and the shapes come from `sextile.layout`
and `sextile.formatting`, but the commonest are re-exported from `sextile`, so a
plain page needs no second import line and the package split stays invisible.
