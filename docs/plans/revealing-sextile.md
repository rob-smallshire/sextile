# Revealing Sextile: the comprehensibility plan

Status: approved 2026-08-15. This file is the working reference for the rework;
the architect session owns it and the developer session executes against it.

**Documentation is deferred.** The Markdown docs will be rewritten from scratch
under Sphinx (with a Markdown extension). Until then: do not invest in the
legacy `docs/*.md` beyond keeping them from stating falsehoods about code that
has changed. Phase 4 below is therefore parked; phase 5's CLAUDE.md work still
applies.

## Diagnosis

The engine is good: routing, session, command parsing, wire encoding, the
attribute planner, the fill algorithm, mosaic fonts, forms at 1200 baud,
`testing.calling`. What stands between a newcomer and it:

1. A coined vocabulary about forty words long (`Held`, `Room`, `Offer`,
   `Placement`, `Once`, `Every`, `Flowing`, `Drawn`, `Arrival`, `Parting`,
   `Lines(said=)`, `Suggest(look_up=)`, ...), several used in two senses
   (`Run`, `rows_for`, `blocks`, `ROOM`/`Room`, `Control` meaning attribute).
2. One idea, several spellings: five ways to register a page; five ways to ask
   a page's title (`describe`, `heading`, `heading_for`, `page_info`,
   `on_describe`); six spellings for service state (`Held`, `.checking`,
   `.of`, `.found_in`, `.find`, `held_in`); three routes to centre text; two
   notice-page builders (`farewell_page`, `_plain_notice`).
3. A tax on every handler: `app = Sextile.of(request)`,
   `title=app.heading_for(request.address)`, `home=app.index`,
   `.build(request.address)`; plus `_menu`/`_notice` helpers, neighbour
   wiring, and the framework's own pages routed by hand, all repeated in every
   app.
4. Docs that argue instead of instruct (deferred: Sphinx rewrite).

## The target

```python
from sextile import Sextile, Request, Page, Menu, Notice

app = Sextile()

@app.page("1", title="Main menu")
async def main(request: Request) -> Page:
    return Menu(request, items=[app.item("news"), app.item("sport")])

@app.page("11", title="News")
async def news(request: Request) -> Page:
    return Notice(request, "Nothing yet.")
```

One import line; title, home key and page number defaulted from the
registration and the app. `PageLayout`, parts, furniture and custom drawables
remain underneath for the hard cases.

## Phases

| Phase | What | Size |
|---|---|---|
| 0 | Ground truth: stale claims fixed; name-level public-surface test via `__all__`; delete `docs/prose-rewrite/`; glossary stub | S |
| 1 | Make easy things easy (API) | L |
| 2 | Naming sweep, one family per commit, no shims | M |
| 3 | Module structure and duplicate implementations | M |
| 4 | Documentation (DEFERRED to Sphinx rewrite) | — |
| 5 | Docstrings contract-first; CLAUDE.md to ~100 lines with document-level rules | M |
| 6 | Applications converge; calendar becomes the canonical example | M |

Order: 0, then 1, then 2, then 3; 5 interleaves; 6 is partly forced by 1-2.

### Phase 0: ground truth

- Fix stale claims: `graphics.md` "lettering not built"; `rendering.md`
  pagination and NFKD; `writing-an-application.md` override-`describe`,
  "three pages come built", `sextile.compass` import; `open-questions.md`
  "both apps write their own menu builder"; `drawing.py:12-17` "when it
  comes"; `canvas.py:409` paginator; `CLAUDE.md` "nothing checks the surface";
  stardot README footer format and "eight questions"; sextile README "two
  applications" and `app.alias` example.
- `test_public_surface.py` checks names: every public module gets `__all__`;
  the test diffs `__all__` against `public-surface.md`. Missing today:
  `Shortcut`, `HOME_KEY`, `farewell_page`, `Spacing`, `Style`, `DoesNotFit`,
  `Where`, `BLOCKS_ACROSS/DOWN`, `read_font`, `FOOTER_ROW`.
- Delete `docs/prose-rewrite/`.
- Glossary stub: one line per term; renames recorded here.

### Phase 1: make easy things easy

1.1 One application class; `request.app: Sextile`; delete `Sextile.of`.
    Fold `Application` into `Sextile` (a small Protocol if a seam is wanted).
1.2 `PageLayout(...).build(request)`: defaults title (registered, upper),
    home (`app.index`), page number. Masthead pages pass `address=None`.
1.3 First-class page shapes on top of the parts model: `Menu(request, items=,
    preamble=, title=, home=, empty=)`, `Notice(request, *lines, ...)`,
    `Prose(request, *paragraphs)`, one farewell/notice implementation,
    `app.item(name)` replacing `MenuItem.for_page(app, name)`.
1.4 `request.neighbours.previous/next`; `PageLayout(neighbours=,
    item_noun=)`; `standard_pages(history="92", contents="93",
    keywords="94")`; readership pages as routable handlers taking the visits
    log from state.
1.5 One state mechanism: `KEY = StateKey[T]("name")`, `request.state[KEY]`,
    lifespan yields `{KEY: value}`; `request.service` -> `request.state`.
    Spike the Protocol-vs-class runtime check; if not uniform, drop it.
1.6 Two registration forms: `Sextile(pages=[PageRoute(...)])` and
    `@app.page`; an APIRouter-style collector (`pages = Pages();
    @pages.page(...)`) replaces `@page` + `routes_in`; retire `routes_on`,
    subclass style, and post-construction duplicates; merge `PageInfo` into
    `PageRoute`.
1.7 Titles: `title_for(address)` and `label_for(address)` with one hook;
    per-route `label=`.
1.8 Small: done — `testing.text_of(page, index)` (one helper, all local
    reimplementations gone); flowing as the default (a bare `Drawable` in
    `parts` means `Flowing`). Deferred: `RowWriter` column offset and run
    trimming to a budget -> Phase 3 (with the drawing-triplicate collapse);
    drop `digit` from non-numbering formatters -> Phase 2 (with the formatter
    renames).

### Phase 2: names (recommendations; "your call" items settled by the user)

| Family | Now | Proposed |
|---|---|---|
| Layout wrappers | `Once` `Every` `Flowing` `Break` | `OnFirstFrame` `OnEveryFrame` (default) `FrameBreak` |
| Layout values | `Room` `Offer` `Placement` `Filled` `Summary` `Edge.FOOT` | `Space` `Claim` `Placed` `FilledFrame` (private) `FrameContext` `Edge.BOTTOM` |
| Furniture | `Prompt`; "chrome" | `Footer`; "furniture" |
| Custom part | `Drawn` | `Custom` |
| Shortcut | `says` `arrow` | `label` `with_arrow` |
| PageLayout | `follows` `item` | `next_page` `item_noun` |
| Formatters | `Lines(said=)` `Formatter`/`RowFormatter` `Figures` | `Lines(entries)` positional; `SequencePart`/`RowPart`; `KeyValues` |

Deferred from 1.8: drop the `digit` parameter from formatters that do not
number their rows, folded in with the formatter renames above.
| Forms | `Suggest(look_up=, field=, typing=, empty=)` `Fields(complete=, note=, sends=, advice=)` `Field.takes` | `TypeAhead(lookup=, field_colour=, text_colour=, no_match=)` `FieldSet(on_submit=, footnote=, submit_label=, footer_items=)` `Field.accepts` |
| Request | `Arrival(preceding, following)` `Parting` `service` | `Neighbours(previous, next)` `IdleTimeout` `state` |
| Application | `lately_read`/`most_read`/`who_has_called` `ask()` `advertised()`/`pages()` | `recent_page`/`popular_page`/`callers_page` `request_page()` `routes()` |
| Wire | `Control` `is_control_code` | `Attribute` `is_attribute_code` |
| Two senses | `canvas.Run`/`composition.Run`; `lettering.rows_for`/`cells_for`; `Style.held` | `Span`/`Run`; `rows_needed`/`cells_needed`; `hold_graphics` |
| Modules | `parting.py` `countdown.py` `lettering.py` | `hangup.py` `idle_warning.py` `mosaic_text.py` |
| Testing | `calling` `Caller.key` `Caller.shown` | `connect` `press` `screen` |
| Keys | `CONVENTIONAL_NEXT_FRAME` `moving(back=, on=)` `arrows_lead_where` `keys.BACK` vs `HOME_KEY` | `HASH` `frame_move_keys(has_previous=, has_next=)` `with_arrow_aliases`; one constant per meaning |

### Phase 3: modules and duplicates -- DONE

Splits landed: `application.py` -- middleware types to `middleware.py`, the
seven built-in page methods to free functions in `sextile.handlers` (gathering
from `request.app`), which kept `builtin/` free of the application object;
`layout.py` -> a `layout/` package of `parts`, `furniture`, `page` with
`viewdata/footer.py` moved in as `layout/footer.py`; `forms.py` ->
`forms/{base,type_ahead,fields}.py`; `session/session.py` -> `navigation`,
`screen` and the coordinator; `composition.py` -> the attribute planner into
`viewdata/attributes.py`; `encoding.py` -> the wire half (kept, now internal)
and `viewdata/measure.py` (`cell_count`, `fitted`).
Merges landed: `addressing` -> `page`; `declarations` -> `routing`; `compass`
-> `viewdata/compass.py`. `requests` stayed (Starlette name); `held` was
already gone. `__init__.py` now exports the commonest layout and formatting
shapes, so hello world and a menu import from `sextile` in one line.
Duplicates collapsed: the centring and double-height twins deleted (the
Composition-based `drawing.centred`/`centred_double` survive), the mosaic twin
resolved by `bar` drawing through `RowWriter.mosaic`; `footer._cut`≡`fitted`;
the two `_to_footer_row` and `repaint._to_row` unified as `repaint.to_row` with
the last-row wrap as its edge case; `incremental_bytes` expressed through
`typed_bytes`; the two `Frame` escape loops into `_encoded_cells`; the colour
ranges owned by `controls` (`colour_of`); `drawing.SOLID` dropped for
`SOLID_BLOCKS`. (`charting.ACROSS_A_CELL/DOWN_A_CELL` had already gone in phase
2 batch 5.)
Deferred items resolved: `RowWriter` column offset became `starting_at`, which
reads the colour and mode in force; run trimming to a budget became
`RowWriter.runs(cells=)`. The `place(canvas, room: Space)` parameter is now
`space`, the int `room` split into `cells`/`extent`/`width` first.
`composition.Align.LEFT`/`RIGHT` became `Align.START`/`END`, axis-neutral,
rather than a separate `VAlign`, because `Where` is `int | Align` on both axes.
The `digit` parameter moved to `NumberedRowSequencePart`, drawn for a numbered
part through a private hook, so every other part lost it.

Not done, by decision: the page methods went to `sextile.handlers` functions
rather than a `pages/` package, and the `not_found`/`timed_out`/`failed`
notices stayed in `application.py` -- they are the application's own words, and
480 lines and one class is fine. `handlers.py` stayed rather than merging into
`pages/`.

### Phase 5: docstrings and CLAUDE.md

Contract first; rationale to a `#` comment or the design doc; no history in
docstrings; no application concept even in examples. Worst lists: core:
`Middleware` type, `Application.respond`, `index`, `Arrival`, `forms.py`
module/`Form`, `layout.Drawn`, `held.py`, `formatting.Lines`; rendering:
`canvas.Run`, `composition.py` module/`Align`, `wrap_within`,
`RowWriter.background`/`.plain`, `drawing.py` module, `countdown.py` module,
`repaint.typed_bytes`. Models: `routing.Converter`, `layout.fill`,
`charset.py`, `blocks.read_bitmap`, `encoding.ScreenControl`,
`Frame.row_bytes`.
CLAUDE.md to ~100 lines; add document-level rules (genre first; code before
prose; headings are tasks or nouns; no bold sentences; one home per idea;
API names backticked and present in the surface).

### Phase 6: applications

Calendar = canonical example (~180 lines); one factory shape; one home/index
convention; a `TitleFrame` helper; shared `render`/`serve` CLI assembly.

## Decisions (recommendation first)

1. Handlers keep returning `Page`; layouts take the request.
2. Keep typed state keys, one constructor.
3. Teach decorators first; the `PAGES` table shown as the same thing.
4. Wrapper names: `OnFirstFrame`/`OnEveryFrame`; flow the default.
5. The `Canvas` twins of `Composition` features are duplicates: delete.
6. Docs tooling: Sphinx (decided by the user).
7. Design rationale becomes a decision log, not ADRs.

## Guardrails

Do not touch routing, session command handling, wire encoding, the attribute
planner, the fill algorithm or the fonts except to rename. No new features. Do
not delete framework code because nothing calls it; only because something
else does the same job. Two invariants and the surface test gate every commit.
`uv run pytest`, `uv run ruff check .`, `uv run mypy` green at every commit.
