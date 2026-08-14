# The public surface

What an application may import from `sextile`, and what it may not.

**This document states the intended surface, which is not yet the actual one.**
Every place the two disagree is listed under [Where the line is
crossed](#where-the-line-is-crossed), with what has to happen before the entry
can be deleted. Until that list is empty this is a design being worked towards,
and it says so rather than pretending otherwise.

## The rule

The surface is **a stated set of public submodules**, each with a stated set of
public names. A module not listed here is machinery: it may be renamed, split,
merged or deleted without notice, and an application importing from it will
break.

A set of submodules rather than one flat namespace, because the framework is
large enough that a single top level would say nothing about what belongs with
what. `sextile.templates` and `sextile.viewdata` are the two an application
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

### `sextile.templates` — the shapes a page takes

The first place to look when a page is being written. A service that finds no
shape here fitting should subclass `Template` or `RowTemplate` rather than draw
a frame by hand; a frame drawn by hand is a frame that has to keep up with the
chrome on its own, and they do not.

    Template  RowTemplate           to subclass
    Menu  Listing  Figures  Prose   the shapes
    Entry  MenuItem                 what a shape is given
    Shortcut  Block  PreambleLine   what goes round the entries
    farewell_page                   the last frame of a call
    CHOICES_PER_FRAME  HOME_KEY     the two numbers a page may need

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
| `controls` | `Colour`, `Control`, and the two colour encoders |
| `encoding` | `cell_count`, `fitted` — what fits in how many cells |
| `charset` | the G0 set, `mosaic_code`, `is_representable` |
| `drawing` | `rule`, `thin_rule`, `centred`, `key_row`, `bar` |
| `blocks` | mosaic pictures: `Icon`, `icon`, `block_runs` |
| `charting` | `curve`, `bars` |
| `composition` | `Composition`, `Panel`, `Align` — placing things relative to each other |
| `lettering` | double-height and outsized letters |
| `font` | `Font`, `load_font`, `font_names` |
| `wrapping` | `wrap_text`, `wrap_within` |

Internal to the framework, and not to be imported: `chrome`, `footer`,
`layout`, `command_line`, `countdown`, `parting`, `repaint`, `ansi`. These are
what the templates and the session are built from. The frame geometry a page
legitimately needs to position something — `CONTENT_FIRST_ROW`, `CONTENT_ROWS`
— is the one part of `chrome` an application has a reason to know, and it is
listed as a gap below rather than blessed where it stands.

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

Two places, as of 2026-08-14. Both are the framework failing to offer
something and the application reaching in for it; the four crossings that were
merely applications reaching past an open front door are closed.

*Closed on 2026-08-14, and kept here because a surface document that shows only
its present state says nothing about which way it is moving:* `PageAddress`,
`Page`, `PageFrame`, `Sextile`, `Arrival`, `Parting` and `Converter` were being
imported by module path though all seven were top-level exports already, and
now come through `sextile`. `keyed`, `keys`, `Handler`, `routes_on` and
`GuideRow` have been added to `__all__`, which had been half of the declaring
vocabulary and none of the addressing. `sextile.forms` is listed above as
public, which settles `Field` and `Fields`. `NoSuchRouteError` and
`RouteError` are exported, a service's own converter being what raises the
first of them. `guidance.Key` is `GuideRow` and is
exported from `sextile`: it describes a service's own row in a table, and the
word `key` was already spoken for by the thing a reader presses.

**1. Chrome and footers drawn by hand.** All three services import
`viewdata.chrome` and `viewdata.footer`; Stardot imports `viewdata.layout` as
well. Two different things are going on, and they want different answers:

- *Geometry as a coordinate.* `weather_viewdata/search.py` uses
  `CONTENT_FIRST_ROW` to say where its field sits. That is a legitimate need
  and wants a public home — the frame's geometry, without the drawing.
- *Rebuilding the template layer.* `stardot_viewdata/post_page.py` paginates a
  document and draws its own chrome and footer;
  `stardot_viewdata/handlers.py` and `calendar_viewdata/application.py` draw
  chrome and compose footers for notice frames. This is the arrangement
  `Template` was extracted to end, and it is a missing shape rather than a
  missing export. A post is a heading and a body dealt into frames; the
  calendar's notices are a heading and some lines. Closing this closes most of
  the crossings by itself.

**2. No blessed way to drive a session in a test.**
`weather-viewdata/tests/test_weather_application.py` imports
`sextile.session.session.Session` to play keys at a service end to end. That is
a reasonable thing for a service's tests to want and there is no public path to
it.

## How it is checked

`test_public_surface.py` reads the three services' syntax trees and asserts
that every `from sextile...` import names a module listed here — in the spirit
of the rest of this workspace, where what must not drift is pinned by a test
rather than by a rule somebody remembers. The two crossings above are named in
that test as known exceptions, so closing one means deleting a line from it and
watching the suite stay green.
