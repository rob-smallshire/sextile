# The public surface

What an application may import from `sextile`, and what it may not.

**This document states the surface, and as of 2026-08-14 it is also the actual
one.** Nothing in the three services reaches past it, and
`test_public_surface.py` reads them and says so. [Where the line is
crossed](#where-the-line-is-crossed) records what it took to get there.

## The rule

The surface is **a stated set of public submodules**, each with a stated set of
public names. A module not listed here is machinery: it may be renamed, split,
merged or deleted without notice, and an application importing from it will
break.

A set of submodules rather than one flat namespace, because the framework is
large enough that a single top level would say nothing about what belongs with
what. `sextile.layout` and `sextile.viewdata` are the two an application
spends its time in, and they are different subjects.

Names beginning with an underscore are private everywhere, module and package
alike, and are not listed.

## The public modules

### `sextile` — the vocabulary

What a service is made of, and the types it hands about. Imported by every
application in its first few lines.

    Sextile  PageRoute  PageInfo  Handler
    Page  PageFrame  PageAddress  keyed
    PageRequest  Arrival  Parting  Held  GuideRow
    Middleware  Next
    Converter  UnknownPageError  NoSuchRouteError  RouteError
    Form  Suggest  draw_form
    page  routes_in  routes_on  transliterate
    keys  handlers  __version__

`keys` and `handlers` are modules, re-exported: `keys.BACK`,
`keys.with_arrows`, and the rest of
[`sextile.keys`](#sextilekeys--the-keys-a-reader-presses);
`handlers.history` and the rest of
[`sextile.handlers`](#sextilehandlers--the-frameworks-pages-as-handlers).

### `sextile.layout` — a page as furniture and parts

    PageLayout                            what a service constructs (.build)
    Part  Once  Every  Flowing  Break     a page's parts, and the four kinds
    Drawn                                  a part that draws itself, cell by cell
    Drawable  Room  Offer  Placement       what a part of your own must satisfy
    Edge  Summary  Furnishing             what furniture must satisfy
    Header  Rule  Prompt  DEFAULT_FURNITURE
    Shortcut  HOME_KEY                     a fixed key on every frame
    content_rows  CHOICES_PER_FRAME

### `sextile.formatting` — sequences laid out as parts

    Formatter  RowFormatter              to subclass
    Menu  Listing  Figures  Lines  Prose  the shapes
    Entry  MenuItem                       what a shape is given
    farewell_page                         the notice shown on the way out

### `sextile.viewdata.typesetting` — a document as rows

    Row  rows_for  TRUNCATION_NOTICE

For a page made of something richer than strings. `rows_for` wraps a
`Document`, colours quotations and listings, indents nesting, and breaks
over-long words rather than dropping them.

### `sextile.viewdata` — the drawing toolkit

For a page drawing something no layout has a shape for: a picture, a chart, a
masthead, a form's furniture. **Prefer a layout.** What is here is for drawing
*within* a page. A page that finds itself drawing chrome or composing a footer
has gone past the toolkit and is rebuilding the `sextile.layout` layer by hand.

Public submodules:

| Module | For |
|---|---|
| `canvas` | `Canvas`, `RowWriter`, `Run` — writing on a frame |
| `frame` | `Frame`, `ROWS`, `COLUMNS`, `FOOTER_ROW` — what a frame is |
| `controls` | `Colour`, `Control`, `is_control_code`, and the two colour encoders |
| `encoding` | `cell_count`, `fitted` — what fits in how many cells |
| `charset` | `G0_TO_UNICODE`, `mosaic_code`, `is_representable` |
| `drawing` | `rule`, `thin_rule`, `centred`, `key_row`, `bar` |
| `blocks` | mosaic pictures: `Icon`, `icon`, `block_runs`, `read_bitmap`, `BLOCKS_ACROSS`, `BLOCKS_DOWN` |
| `charting` | `curve`, `bars` |
| `composition` | `Composition`, `Panel`, `Align`, `Style`, `DoesNotFit`, `Where` — placing things relative to each other |
| `lettering` | outsized letters: `place`, `boxed`, `cells_for`, `width`, `rows_for`, `Spacing` |
| `font` | `Font`, `load_font`, `font_names`, `read_font`, `Glyph`, `FontError` |
| `footer` | `FooterItem`, `Priority`, `movement`, `render_footer`, `ROOM` — composing a prompt for a frame drawn by hand |
| `wrapping` | `wrap_text`, `wrap_within` |

Internal to the framework, and not to be imported: `command_line`,
`countdown`, `parting`, `repaint`, `ansi`. These are what the session is built
from, and it draws on a frame after a page has been built rather than while it
is being built.

**Some of this is offered rather than used.** `read_bitmap`, `boxed`,
`cells_for` and `is_control_code` have no caller among the three services here,
and that is not an argument against them. A framework's surface is justified by
being useful to a service, not by being used by the services that happen to
share a repository with it: a fourth service drawing its own icons wants
`read_bitmap`, and one setting a masthead in a box wants `boxed` and
`cells_for`. They are listed here so that a sweep for uncalled code finds the
reason rather than the absence.

That is a different thing from a duplicate implementation, which is what
`viewdata/chrome.py` turned out to be. It was deleted because `Header`, `Rule`
and `Prompt` do the job it did, and two implementations of one thing diverge —
not because nothing called it.

### `sextile.keys` — the keys a reader presses

The names and codes, and the four helpers that turn one form into another.

    PREVIOUS_FRAME  NEXT_FRAME  CONVENTIONAL_NEXT_FRAME
    PREVIOUS_ITEM  NEXT_ITEM  BACK
    REDISPLAY  REFRESH  CANCEL  RUB_OUT
    LEFT  RIGHT  UP  DOWN  ARROW_KEYS  ARROW_FOR  LETTER_FOR
    with_arrows  as_letter  arrows_lead_where  moving

### `sextile.content` — what is to be shown

The document vocabulary, for a service turning something richer than a string
into frames. `sextile.content.blocks`:

    Document  Paragraph  Quote  Code  ListItem  Image  Attachment  Link  Block

`transliterate` is at the top level, being the one thing every service needs of
this module.

### `sextile.forms` — a field on a frame

    Form  Field  Fields  Suggest  Complete  Note  Lookup  draw_form  SUGGESTIONS

`Form`, `Suggest` and `draw_form` are also at the top level, those three being
what a page with one field needs.

The colour constants are the defaults behind the parameters of the same name.
Pass a parameter rather than reading a constant.

### `sextile.pages` — the commonest pages, said in one call

    menu_page  notice_page

The one-call shapes, each building a `PageLayout` from the request the page
answers. Also at the top level, those being what most services reach for first.
`app.menu_item(name)` builds a menu entry from a registered page's own words.

### `sextile.handlers` — the framework's pages, as handlers

    history  contents  names

One line apiece in a service's routes. The pages behind them are
`sextile.builtin`, which is internal: a service reaches them through these
handlers or through the `Sextile` methods they call.

### `sextile.middleware` — what wraps every page

    log_pages  record_visits  held_in  Finder

### `sextile.visits` — the log of what has been read

    Visits  Visit  SqliteVisits  KEPT

`Visits` is the protocol, `SqliteVisits` the implementation that comes with the
framework. A service keeping its log elsewhere writes its own, and the pages
behave no differently.

### `sextile.testing` — driving a service the way a caller does

    calling  Caller  request_for

A service's own tests want to press keys and read the screen, which nothing
else stands in for: whether `*3#` reaches a handler, whether a field kept what
was typed, and what `0` does from three pages in are questions about the
session rather than about any one page.

### `sextile.cli` — building a service's command line

    run_service  render_page  add_listening_arguments  add_form_arguments
    ApplicationSpecError

### `sextile.compass` — the four keys that move about a page, drawn

    ROWS  compass

The picture of `W`/`A`/`S`/`D` is the framework's, not any one service's, so a
service drawing its own guide page reaches for the same one rather than
redrawing it. `ROWS` is how many rows it occupies.

## What is internal

Everything else, and specifically:

| Module | Why an application does not need it |
|---|---|
| `application`, `requests`, `declarations`, `held` | their public names are re-exported by `sextile` |
| `addressing`, `page` | likewise: `PageAddress`, `keyed`, `Page`, `PageFrame` |
| `routing` | a service declares routes; the router matches them. `Converter` is the extension point, and it and the two errors it raises are at the top level |
| `pages` | reached through `sextile.handlers` or the `Sextile` methods |
| `session`, `server` | how a call is answered, which no page takes part in |
| `viewdata.command_line`, `.countdown`, `.parting`, `.repaint` | what the session is built from |
| `viewdata.ansi` | for looking at a frame without a terminal |

## Where the line is crossed

Nowhere, as of 2026-08-14.

The last three crossings were `viewdata.chrome`, `viewdata.footer` and
`viewdata.typesetting`, all reached because a page had to draw its own
furniture. Splitting a page into furniture and parts closed them: `chrome` has
no reader outside the framework, and `footer` and `typesetting` turned out to
be public rather than crossed. A part says which keys to name, so a service
writing one needs `FooterItem`; a page made of a document needs `rows_for`.
Both are listed above.

*Kept as a record of what the surface was for, since a document showing only
its present state says nothing about which way it is moving.* Six crossings
were found when this was first written. Three were applications reaching past a
front door that was already open, and closed the same day. One was a name that
should have been exported and was not. One was API behind an internal path,
`guidance.Key`, now `GuideRow` and exported. The last was the interesting one
and took the longest: three services drawing chrome and composing footers by
hand, for want of any way to obtain the furniture of a page without also being
a formatter of a homogeneous sequence.

## How it is checked

`test_public_surface.py` reads the three services' syntax trees and asserts
that every `from sextile...` import names a module listed here — in the spirit
of the rest of this workspace, where what must not drift is pinned by a test
rather than by a rule somebody remembers. Its list of known crossings is empty,
and a second assertion fails if a line outlives the defect it names: a
known-crossing exception left in place reads as permission, so an empty list is
the only state that needs no watching.
