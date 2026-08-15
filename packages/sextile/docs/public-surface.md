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

    Sextile  PageRoute  PageRouter  Handler
    Page  PageFrame  PageAddress  keyed
    PageRequest  Neighbours  StateKey  GuideRow
    Middleware  CallNext
    Converter  UnknownPageError  NoSuchRouteError  RouteError
    Form  TypeAhead  draw_form
    PageLayout  Flow  Custom  OnOneFrame  Shortcut
    Lines  Prose  MenuItem
    menu_page  notice_page  prose_page  farewell_page  title_page
    standard_pages  transliterate
    keys  handlers  __version__

The commonest `layout` and `formatting` shapes are re-exported here too, so a
plain page needs no second import line: `PageLayout` and the parts a service
reaches for first (`Flow`, `Custom`, `OnOneFrame`, `Shortcut`), and the plain
`formatting` shapes (`Lines`, `Prose`, `MenuItem`). The full sets, and the
subclassing machinery, stay in [`sextile.layout`](#sextilelayout--a-page-as-furniture-and-parts)
and [`sextile.formatting`](#sextileformatting--sequences-laid-out-as-parts).

`keys` and `handlers` are modules, re-exported: `keys.BACK`,
`keys.with_arrows`, and the rest of
[`sextile.keys`](#sextilekeys--the-keys-a-reader-presses);
`handlers.history` and the rest of
[`sextile.handlers`](#sextilehandlers--the-frameworks-pages-as-handlers).

### `sextile.layout` — a page as furniture and parts

    PageLayout                            what a service constructs (.build)
    Part  OnOneFrame  OnEveryFrame  Flow  FrameBreak   a page's parts, and the four kinds
    Custom                                 a part that draws itself, cell by cell
    Drawable  Space  Claim  Placed         what a part of your own must satisfy
    Edge  FrameContext  Furnishing         what furniture must satisfy
    Header  Rule  Footer  DEFAULT_FURNITURE
    Shortcut  HOME_KEY                     a fixed key on every frame
    DEFAULT_HOME  DefaultHome              home unset: the service's index
    content_rows  CHOICES_PER_FRAME
    FooterItem  Priority  movement  render_footer  FOOTER_WIDTH   composing a prompt for a frame drawn by hand

A package of three modules -- `parts`, `furniture`, `page` -- with the prompt
composer in `layout.footer`; all re-exported here, so a service imports from
`sextile.layout` and the split is invisible. The footer names were
`sextile.viewdata.footer` before: a prompt is layout, not a frame or a byte.

### `sextile.formatting` — sequences laid out as parts

    SequencePart  RowSequencePart  NumberedRowSequencePart   to subclass
    Menu  Listing  Figures  Lines  Prose  the shapes
    Entry  MenuItem                       what a shape is given

`NumberedRowSequencePart` is `RowSequencePart` with a digit column drawn for it;
a service numbering its own entries subclasses it, and every other part is spared
the digit. `Menu` is the one shape the framework builds on it.

### `sextile.viewdata.typesetting` — a document as rows

    Row  rows_for  TRUNCATION_NOTICE

For a page made of something richer than strings. `rows_for` wraps a
`Document`, colours quotations and listings, indents nesting, and breaks
over-long words rather than dropping them.

### `sextile.viewdata` — the drawing toolkit

For a page drawing something no layout has a shape for: a picture, a chart, a
masthead, a form's furniture. **Prefer a layout.** What is here is for drawing
*within* a page. A page that finds itself drawing furniture or composing a footer
has gone past the toolkit and is rebuilding the `sextile.layout` layer by hand.

Public submodules:

| Module | For |
|---|---|
| `canvas` | `Canvas`, `RowWriter`, `Span` — writing on a frame |
| `frame` | `Frame`, `ROWS`, `COLUMNS`, `FOOTER_ROW` — what a frame is |
| `controls` | `Colour`, `Attribute`, `is_attribute_code`, the two colour encoders and `colour_of` reading one back |
| `measure` | `cell_count`, `fitted` — what fits in how many cells |
| `charset` | `G0_TO_UNICODE`, `mosaic_code`, `is_representable` |
| `drawing` | `rule`, `thin_rule`, `centred`, `centred_double`, `key_row`, `bar` |
| `blocks` | mosaic pictures: `Icon`, `icon`, `block_runs`, `read_bitmap`, `BLOCKS_ACROSS`, `BLOCKS_DOWN` |
| `charting` | `curve`, `bars` |
| `composition` | `Composition`, `Panel`, `Align`, `Style`, `DoesNotFit`, `Where` — placing things relative to each other |
| `lettering` | outsized letters: `place`, `boxed`, `cells_needed`, `width`, `rows_needed`, `Spacing` |
| `font` | `Font`, `load_font`, `font_names`, `read_font`, `Glyph`, `FontError` |
| `wrapping` | `wrap_text`, `wrap_within` |
| `compass` | `ROWS`, `compass` — `W`/`A`/`S`/`D` drawn, for a guide page |

Internal to the framework, and not to be imported: `encoding`, `command_line`,
`idle_warning`, `hangup`, `repaint`, `ansi`. `encoding` is the wire half --
`ScreenControl`, `encode_attribute`, `encode_text` -- which a page never touches;
the rest are what the session is built from, and it draws on a frame after a
page has been built rather than while it is being built.

**Some of this is offered rather than used.** `read_bitmap`, `boxed`,
`cells_needed` and `is_attribute_code` have no caller among the three services here,
and that is not an argument against them. A framework's surface is justified by
being useful to a service, not by being used by the services that happen to
share a repository with it: a fourth service drawing its own icons wants
`read_bitmap`, and one setting a masthead in a box wants `boxed` and
`cells_needed`. They are listed here so that a sweep for uncalled code finds the
reason rather than the absence.

That is a different thing from a duplicate implementation, which is what
a since-deleted furniture module turned out to be. It went because `Header`,
`Rule` and `Footer` do the job it did, and two implementations of one thing diverge —
not because nothing called it.

### `sextile.keys` — the keys a reader presses

The names and codes, and the four helpers that turn one form into another.

    PREVIOUS_FRAME  NEXT_FRAME  HASH
    PREVIOUS_ITEM  NEXT_ITEM  BACK
    REDISPLAY  REFRESH  CANCEL  RUB_OUT
    LEFT  RIGHT  UP  DOWN  ARROW_KEYS  ARROW_FOR  LETTER_FOR
    with_arrows  as_letter  with_arrow_choices  frame_moves

### `sextile.content` — what is to be shown

The document vocabulary, for a service turning something richer than a string
into frames. `sextile.content.blocks`:

    Document  Paragraph  Quote  Code  ListItem  Image  Attachment  Link  Block

`transliterate` is at the top level, being the one thing every service needs of
this module.

### `sextile.forms` — a field on a frame

    Form  Field  FieldSet  TypeAhead  SubmitHandler  Footnote  Lookup  draw_form  SUGGESTIONS

`Form`, `TypeAhead` and `draw_form` are also at the top level, those three being
what a page with one field needs.

The colour constants are the defaults behind the parameters of the same name.
Pass a parameter rather than reading a constant.

### `sextile.pages` — the commonest pages, said in one call

    menu_page  notice_page  prose_page  farewell_page  title_page

The one-call shapes, each building a `PageLayout` from the request the page
answers. Also at the top level, those being what most services reach for first.
`app.menu_item(name)` builds a menu entry from a registered page's own words.

### `sextile.handlers` — the framework's pages, as handlers

    standard_pages
    history  contents  keywords
    recent  popular  callers
    guide_page
    history_page  contents_page  keywords_page
    recent_page  popular_page  callers_page

`standard_pages(history="92", ...)` is the one line most services want: it
returns the routes for whichever pages a service gives a number, carrying the
framework's own title, detail and keywords. It is also at the top level. The
individual handlers are there for a service that wants finer control; the
readership three (`recent`, `popular`, `callers`) take the `StateKey` the visit
log is held under.

The `*_page` functions build one framework page each from `request.app`, and
were methods on `Sextile`. `guide_page` is the one a service calls itself, since
only the service knows the rows to add to a guide; the rest are what the routed
handlers above delegate to, exposed for a service routing one at a number of its
own. The pure builders behind them are `sextile.builtin`, which is internal.

### `sextile.state` — what a service holds while it runs

    StateKey  State  StateReader

`StateKey[T]("name")` is a typed key into what the lifespan opened; also at the
top level. `app.state[KEY] = value` writes it, `request.state[KEY]` reads it
back typed. `State` is what `app.state` is, `StateReader` the read-only view a
page is given.

### `sextile.middleware` — what wraps every page

    Middleware  CallNext
    log_pages  record_visits

`Middleware` and `CallNext` are the type a service writes and the rest of the
chain it is handed; both are re-exported at the top level. `log_pages` and
`record_visits` are the two the framework ships.

### `sextile.visits` — the log of what has been read

    Visits  Visit  SqliteVisits  RETENTION

`Visits` is the protocol, `SqliteVisits` the implementation that comes with the
framework. A service keeping its log elsewhere writes its own, and the pages
behave no differently.

### `sextile.testing` — driving a service the way a caller does

    connect  Caller  fetch  request_for  text_of

A service's own tests want to press keys and read the screen, which nothing
else stands in for: whether `*3#` reaches a handler, whether a field kept what
was typed, and what `0` does from three pages in are questions about the
session rather than about any one page. `text_of(page, index=0)` reads the
characters of a built page's frame back, the one extraction a test would
otherwise write for itself; it takes a `Frame` too, for a drawing test working
below the page. `fetch(app, "3")` is `Sextile.fetch` with the `None` asserted
away, so a test naming a page it registered reads it back typed as present.

### `sextile.cli` — building a service's command line

    run_service  render_page  add_listening_arguments  add_form_arguments
    add_standard_subcommands  run_standard  ApplicationSpecError

### `sextile.viewdata.compass` — the four keys that move about a page, drawn

    ROWS  compass

The picture of `W`/`A`/`S`/`D` is the framework's, not any one service's, so a
service drawing its own guide page reaches for the same one rather than
redrawing it. `ROWS` is how many rows it occupies. It is a drawing on the block
grid like the rest of `viewdata`, which is where it now lives.

## What is internal

Everything else, and specifically:

| Module | Why an application does not need it |
|---|---|
| `application`, `requests` | their public names are re-exported by `sextile` |
| `page` | likewise: `PageAddress`, `keyed`, `UnknownPageError`, `Page`, `PageFrame` |
| `routing` | a service declares routes; the router matches them. `PageRoute`, `PageRouter` and `Handler` are declared here and re-exported by `sextile`; `Converter` is the extension point, and it and the two errors it raises are at the top level |
| `pages` | reached through `sextile.handlers` or the `Sextile` methods |
| `session`, `server` | how a call is answered, which no page takes part in |
| `viewdata.encoding` | the wire half: `ScreenControl`, `encode_attribute`, `encode_text` |
| `viewdata.attributes` | the style model and the plan of attributes a row needs, which `composition` drives |
| `viewdata.command_line`, `.idle_warning`, `.hangup`, `.repaint` | what the session is built from |
| `viewdata.ansi` | for looking at a frame without a terminal |

## Where the line is crossed

Nowhere, as of 2026-08-14.

The last three crossings were a furniture module, `viewdata.footer` and
`viewdata.typesetting`, all reached because a page had to draw its own
furniture. Splitting a page into furniture and parts closed them: the furniture
module had no reader outside the framework, and `footer` and `typesetting` turned out to
be public rather than crossed. A part says which keys to name, so a service
writing one needs `FooterItem`; a page made of a document needs `rows_for`.
Both are listed above.

*Kept as a record of what the surface was for, since a document showing only
its present state says nothing about which way it is moving.* Six crossings
were found when this was first written. Three were applications reaching past a
front door that was already open, and closed the same day. One was a name that
should have been exported and was not. One was API behind an internal path,
`guidance.Key`, now `GuideRow` and exported. The last was the interesting one
and took the longest: three services drawing furniture and composing footers by
hand, for want of any way to obtain the furniture of a page without also being
a sequence part of a homogeneous sequence.

## How it is checked

`test_public_surface.py` reads the three services' syntax trees and asserts
that every `from sextile...` import names a module listed here — in the spirit
of the rest of this workspace, where what must not drift is pinned by a test
rather than by a rule somebody remembers. Its list of known crossings is empty,
and a second assertion fails if a line outlives the defect it names: a
known-crossing exception left in place reads as permission, so an empty list is
the only state that needs no watching.
