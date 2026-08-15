# Glossary

The framework's terms, each with its current name and a plain definition. When
Phase 2 of the comprehensibility rework renames one, the old name is kept here
as "was X" so a reader coming from older code or docs can find it.

- **page** — what a handler returns: one or more frames sharing a page number.
- **frame** — one screenful, 24 rows of 40 cells; a page too long for one has
  several, keyed `a` to `z`.
- **attribute** (was `Control`) — a teletext spacing attribute: a colour or
  character-set code that takes a cell of its own and shows as a blank.
  `controls.Attribute`; `is_attribute_code` (was `is_control_code`) tells one
  from a character. Not to be confused with `encoding.ScreenControl`, the C0
  cursor and screen controls.
- **part** — a piece of a page's body between the rules: a menu, some lines, a
  picture, a form. `layout.Part`. A part says which frames it appears on:
  `OnOneFrame` (was `Once`), `OnEveryFrame` (was `Every`), `Flow` (was
  `Flowing`, and what a bare drawable means), or `FrameBreak` (was `Break`).
- **sequence part** (was `Formatter`/`RowFormatter`) — a part that lays out a
  homogeneous sequence of entries: a menu, a listing, a table of figures.
  Subclass `formatting.SequencePart`, or `RowSequencePart` for one whose entries
  are written left-to-right along their rows.
- **entry** — one item in a sequence a sequence part lays out, such as a line of
  a menu. `formatting.Entry`. `Lines` takes its lines as `entries`, passed first
  and without a keyword (was the `said=` keyword).
- **Custom** (was `Drawn`) — a part of a stated height a page draws itself, cell
  by cell: a picture, a grid, a masthead. `layout.Custom(rows, draw)`.
- **place** — what a custom part does: `place(canvas, room) -> Placed`, drawing
  as much as fits and saying what is left. `Space` (was `Room`) is what the
  frame has left; `Placed` (was `Placement`) carries the rows used, a `Claim`
  (was `Offer`) of the keys claimed, and a `remainder` (was `rest`). Two claims
  merge with `Claim.merged_with` (was `Offer.and_then`).
- **furniture** — the fixed structure a page is drawn into, around its parts:
  a `Header`, `Rule`s and a `Footer` (was `Prompt`). `layout.Furnishing`,
  `DEFAULT_FURNITURE`. A furnishing is told a `FrameContext` (was `Summary`);
  its edge is `Edge.TOP`/`Edge.BOTTOM` (was `Edge.FOOT`).
- **route** — a pattern bound to a handler, carrying the page's name and
  keywords. `PageRoute`. `app.route(name)` (was `page_info`) is the declared
  route by name, `app.routes()` (was `pages()`) all of them, and
  `app.match(address)` (was `route(address)`) what a page number matched.
- **router** — collects the routes a module of handlers declares with
  `@router.page`, spread into a service as `Sextile(pages=[*router, ...])`.
  `PageRouter` (replaced the free `@page` decorator and `routes_in`).
- **pattern** — the page-number template a route matches: literal digits and
  named fields, such as `82{post_id:int}`.
- **address** — a page number a reader is at, resolved from a pattern.
  `PageAddress`.
- **keyword** — a word a reader keys in place of a number, `*MAIN#` for `*1#`;
  set by a route's `keywords=`.
- **choices vs moves** — choices are keys that lead somewhere, such as a menu's
  digits; moves are keys that page or step within where the reader already is,
  `W`/`A`/`S`/`D` and `#`.
- **sequence, neighbours** — the pages either side of this one in a run a menu
  offered, so a reader can step along without going back. `request.neighbours`
  is a `Neighbours(previous, next)` (was `Arrival(preceding, following)`).
- **next_page** (was `follows`) — where `#` leads once a page's frames have run
  out, so a title frame or the last frame of a guide answers the key a viewdata
  reader tries first. On `PageLayout` and `Page`.
- **shortcut** — a key present on every frame that leads to a fixed address.
  `layout.Shortcut`: `label` (was `says`) is how the footer names it,
  `with_arrow` (was `arrow`) whether the matching cursor key leads there too.
- **DEFAULT_HOME** (was `_DEFAULT_HOME`) — the sentinel a `PageLayout` or a
  one-call page uses for `home` when none is given: `0` leads to the service's
  index. Distinct from `home=None`, which offers no way home. `DefaultHome` is
  its type. Public because `sextile.pages` shares it with `sextile.layout`.
- **home vs index** — home is where a caller arrives when the line opens
  (`Sextile(home=...)`, page 1 by default; a service opening on a title frame
  sets its own). Index is where the `0` key goes from every frame
  (`Sextile(index=...)`, the same as home unless set apart). The footer word
  `index` is the label for that key.
- **CallNext** (was `Next`) — the middleware continuation: a piece of middleware
  is `async (request, build: CallNext) -> Page | None` and calls `build(request)`
  to reach the rest of the chain. Starlette's `call_next`; renamed off `Next` to
  stop it colliding with the `*#` `Next` command.
- **PageRequest** — the request a handler answers. Kept `PageRequest`, not
  renamed to `Request`: the `Page*` family (`PageRoute`, `PageRouter`,
  `PageAddress`, `PageFrame`, `PageLayout`) is consistent, and the prefix keeps
  it clear of httpx's `Request` in an app that imports both. Decided in Phase 2,
  not to be re-litigated.
- **fetch** (was `ask`) — `Sextile.fetch(target)` builds a request for a page
  and answers it in process, for a test, a renderer or a tool with no socket.
  "fetch" is what a browser calls it; there is no HTTP verb to borrow.
- **idle timeout** — an idle caller is released with `on_timed_out(request,
  frame_index)`: the request is the page they were on, `frame_index` which frame
  of it. There was a `Parting` dataclass here; since it held only the frame it
  was dropped for a bare `int`.
- **session vs service state** — session state is one caller's own, lasting as
  long as the line is up (`request.session`); service state is shared across
  callers for the life of the service. Service state is `request.state`, a
  read-only view of what the lifespan opened, keyed by `StateKey`.
- **connect** (was `calling`) — `sextile.testing.connect(app)` opens a service,
  rings it up and closes it, yielding a `Caller`. The caller presses keys with
  `caller.press(...)` (was `key`) and reads `caller.screen` (was `shown`).
- **form** — rows of a frame a reader types into, a field with furniture around
  it. `forms.Form`, `forms.Field`. `TypeAhead` (was `Suggest`) is a field with
  the best few matches beneath it, changing as the reader types; `FieldSet`
  (was `Fields`) is a form of several fields at once. Its `on_submit` (was
  `complete`), `footnote` (was `note`), `submit_label` (was `sends`) and
  `footer_items` (was `advice`) each say what they are; the handler types are
  `SubmitHandler` (was `Complete`) and `Footnote` (was `Note`). A `Form`
  subclass overrides `footer_items()` (was `named()`) and reads `top_row` (was
  `at`), the row the layout placed it on.
