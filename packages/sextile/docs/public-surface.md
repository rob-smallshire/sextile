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

    Application  Sextile  PageRoute  PageInfo  Handler
    Page  PageFrame  PageAddress  keyed
    PageRequest  Arrival  Parting  Held  GuideRow
    Middleware  Next
    Converter  UnknownPageError  NoSuchRouteError  RouteError
    Form  Suggest  draw_form
    page  routes_in  routes_on  transliterate
    keys  __version__

`keys` is the module, re-exported: `keys.BACK`, `keys.with_arrows`, and the
rest of [`sextile.keys`](#sextilekeys--the-keys-a-reader-presses).

### `sextile.layout` — a page as furniture and parts

    PageLayout  build                     what a service constructs
    Once  Every  Flowing  Break  Drawn    the kinds of part
    Part  Room  Offer  Placement          what a part of its own must satisfy
    Edge  Summary  Furnishing             what furniture must satisfy
    Header  Rule  Prompt  DEFAULT_FURNITURE
    content_rows  CHOICES_PER_FRAME

### `sextile.formatting` — sequences laid out as parts

    Formatter  RowFormatter              to subclass
    Menu  Listing  Figures  Lines  Prose  the shapes
    Entry  MenuItem                       what a shape is given

### `sextile.viewdata.typesetting` — a document as rows

    Row  rows_for  TRUNCATION_NOTICE

For a page made of something richer than strings. `rows_for` wraps a
`Document`, colours quotations and listings, indents nesting, and breaks
over-long words rather than dropping them.

### `sextile.viewdata` — the drawing toolkit

For a page drawing something no template has a shape for: a picture, a chart, a
masthead, a form's furniture. **Prefer a template.** What is here is for
drawing *within* a page, and a page that finds itself drawing chrome or
composing a footer has gone past the toolkit and is rebuilding the template
layer by hand.

Public submodules:

| Module | For |
|---|---|
| `canvas` | `Canvas`, `RowWriter`, `Run` — writing on a frame |
| `frame` | `Frame`, `ROWS`, `COLUMNS` — what a frame is |
| `controls` | `Colour`, `Control`, `is_control_code`, and the two colour encoders |
| `encoding` | `cell_count`, `fitted` — what fits in how many cells |
| `charset` | the G0 set, `mosaic_code`, `is_representable` |
| `drawing` | `rule`, `thin_rule`, `centred`, `key_row`, `bar` |
| `blocks` | mosaic pictures: `Icon`, `icon`, `block_runs`, `read_bitmap` |
| `charting` | `curve`, `bars` |
| `composition` | `Composition`, `Panel`, `Align` — placing things relative to each other |
| `lettering` | outsized letters: `place`, `boxed`, `cells_for`, `width`, `rows_for` |
| `font` | `Font`, `load_font`, `font_names` |
| `wrapping` | `wrap_text`, `wrap_within` |

Internal to the framework, and not to be imported: `command_line`,
`countdown`, `parting`, `repaint`, `ansi`. These are what the session is built
from, and it draws on a frame after a page has been built rather than while it
is being.

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

### `sextile.handlers` — the framework's pages, as handlers

    history  contents  names

One line apiece in a service's routes. The pages behind them are
`sextile.pages`, which is internal: a service reaches them through these
handlers or through the `Sextile` methods they call.

### `sextile.middleware` — what wraps every page

    log_pages  record_visits  held_in  Finder

### `sextile.visits` — the log of what has been read

    Visits  Visit  SqliteVisits  KEPT

`Visits` is the protocol, `SqliteVisits` the implementation that comes with the
framework. A service keeping its log elsewhere writes its own and the pages do
not notice.

### `sextile.testing` — driving a service the way a caller does

    calling  Caller

A service's own tests want to press keys and read the screen, which nothing
else stands in for: whether `*3#` reaches a handler, whether a field kept what
was typed, and what `0` does from three pages in are questions about the
session rather than about any one page.

### `sextile.cli` — building a service's command line

    run_service  render_page  add_listening_arguments  add_form_arguments
    ApplicationSpecError

## What is internal

Everything else, and specifically:

| Module | Why an application does not need it |
|---|---|
| `application`, `requests`, `declarations`, `held` | their public names are re-exported by `sextile` |
| `addressing`, `page` | likewise: `PageAddress`, `keyed`, `Page`, `PageFrame` |
| `routing` | a service declares routes; the router matches them. `Converter` is the extension point, and it and the two errors it raises are at the top level |
| `pages` | reached through `sextile.handlers` or the `Sextile` methods |
| `session`, `server` | how a call is answered, which no page is party to |
| `compass`, `demo` | drawn by the framework's own pages |
| `viewdata.chrome`, `.footer`, `.layout` | what a template is built from |
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
and a second assertion fails if a line outlives the defect it names -- an
exception left lying about reads as permission, so an empty list is the only
one that needs no watching.
