# Findings for later attention

Noticed during the prose rewrite. Recorded here rather than changed in passing;
a rename or an API correction is a separate, tested increment. Prose being
rewritten in place is corrected as it is touched, and noted here when it was.

## Odd or unclear names

| Location | Name | Note |
|----------|------|------|
| _(none yet)_ | | |

## Stale references (factual drift)

Docs or docstrings naming code that no longer exists. The prose rewrite must not
launder these into cleaner sentences; where a doc is being rewritten anyway, the
reference is corrected and marked "fixed here".

| Location | Stale reference | Reality | Status |
|----------|-----------------|---------|--------|
| writing-an-application.md, "Forty columns" | `draw_chrome` | Removed with `viewdata/chrome.py`. Standard furniture is now `PageLayout` + `DEFAULT_FURNITURE` (`Header`, `Rule`, `Prompt` in `layout.py`); a fully hand-drawn frame calls `rule()` and writes its own header/footer, as `demo.py` does. | fixed here |
| rendering.md, pipeline diagram + "Rows to a frame" | `chrome.py` | Same removal; furnishings live in `layout.py`. | fixing in rendering.md rewrite |
| application.py:821 (`_plain_notice` docstring) | `sextile.viewdata.chrome` | Module deleted. Refer to `layout.py` furnishings / `DEFAULT_FURNITURE`. | to fix in source-docstring pass |
| public-surface.md, design.md, page-layout.md | `chrome` / `draw_chrome` | Verify each against current `layout.py` when those docs are swept. | to check |
| sextile/README.md (headline example) | `from sextile.viewdata.chrome import CONTENT_FIRST_ROW, draw_chrome`; `draw_chrome(...)` | Module, function and `CONTENT_FIRST_ROW` all deleted, so the first example did not run. Rewrote it to the `PageLayout` + `Flowing(Lines(...))` form. | fixed here |
| public-surface.md, "What is internal" table (was line ~187) | `viewdata.chrome`, `.footer`, `.layout` "what a template is built from" | `viewdata.chrome` is deleted (the doc itself says so at the chrome paragraph); there is no `viewdata/layout.py` (the furniture layer is top-level `sextile.layout`); and `viewdata.footer` is described as *public* later in the same doc ("footer ... turned out to be public"). This row contradicted the rest and the enforced surface. **RESOLVED:** reconciled against `test_public_surface.py`'s `PUBLIC` set (the enforced truth, 26 modules) — `footer` added to the public viewdata table, and the stale `viewdata.chrome`/`.footer`/`.layout` internal row deleted. Test green (5 pass). | FIXED |
| mosaic-fonts.md, "What to build" item 5 | `Template` base | `Template` was replaced by `PageLayout`/`Part`/`Formatter`. Rephrased the not-yet-built `Banner` as a part built on `PageLayout`. | fixed here |
| design.md, architecture diagram | `chrome` under `viewdata/` | Deleted module; removed from the "its furniture" line (footer, command_line remain). | fixed here |
| design.md, name section | `draw_chrome` "has no fallback title" | Rephrased to the `Header` furniture drawing no fallback title. | fixed here |
| design.md, layout section | "What a template consumes is the `Entry` protocol" | `Template` deleted; `Formatter[E]` consumes `Entry`. Changed to `Formatter`. Also unified the live term to *furniture* where `chrome` was used as a noun. | fixed here |

## Invariant-1 leaks (framework naming application concepts)

CLAUDE.md invariant 1: nothing in `packages/sextile/` may know about a forum,
phpBB, Stardot, a calendar or the weather — "not in the code, and preferably not
in the comments". These were found in framework *comments* and genericised in
place during the docstring sweep. Worth a check that the same concepts have not
leaked into framework *code* (names, branches), which would be a seam defect
beyond prose.

| File | Leak | Fixed to |
|------|------|----------|
| session/commands.py | "the search page told readers there was no space bar"; "Place names hold spaces, hyphens and apostrophes" (weather concepts) | "a field appeared to have no space bar"; "Text a reader types may hold spaces, hyphens and apostrophes" — fixed here |
| session/session.py | "hanging up on somebody because one post has an awkward image caption" (Stardot concepts) | "ending it over one page's exception" — fixed here |
| viewdata/canvas.py | `RowWriter.runs` docstring: "a place name longer than anybody expected should cost the reader the end of a sentence" (weather concept) | "a value longer than anybody expected should cost the reader the end of a line" — fixed here |
| formatting.py | `Entry` "a post or a timestamp"; `Listing` weather page titles ("Forecast by lat/lon position"); `Prose` "a forum post" | genericised to neutral examples — fixed here |
| forms.py | `Suggest` "a place"; `accepts` "place names — NEW YORK, STRATFORD-UPON-AVON"; `Field.takes` "a latitude"; `Fields` "compass letters / West / South / coordinate" | genericised to entry/value/field and "the letters W and S as data" — fixed here |
| pages/__init__.py, history.py, guidance.py | "forum pages"; "forums or calendars"; guidance "a search field answers letters, a forecast answers F"; Stardot provenance of the guide | genericised; Stardot sentence cut — fixed here |
| application.py `guide()` | "a search field answers letters, a forecast answers F" (weather) — the same phrase, matched to guidance.py | genericised — fixed here |
| layout.py `Shortcut` | "a forecast returning to the search that found it, a post returning to the board it was on" (weather + Stardot) | "a page returning to the one that led to it" — fixed here |

| viewdata/footer.py | `_MOVEMENT` comment "a service moves between posts, or days" (Stardot/calendar) | "whatever the service's items are" — fixed here |
| viewdata/repaint.py | `rows_bytes` "a place the reader has typed past" (weather) | "an entry the reader has typed past" — fixed here |
| visits.py | `KEPT` "a month of weather and a month of posts"; address example `321<geoname-id>`; `SqliteVisits` "the weather rebuilds its place index from a GeoNames dump" | genericised to "what 'lately' means", `52<id>`, "a service's own database is often derived and rebuilt" — fixed here |
| testing.py | module/`key` example "TROND"/"Trondheim" (weather place) | "ABC" — fixed here |
| content/blocks.py | module docstring "That is how phpBB's HTML reads -- one `<br>` is a new line, two are a new paragraph" (phpBB/forum) | general "different things that can arrive looking the same" — fixed here |
| content/transliterate.py, wrapping.py, typesetting.py | "a post with three emoji"; "a crash on a real post"; "Real posts carry captions" (forum) | "a line", "on real text", "A caption can be as long as a filename" — fixed here |
| viewdata/charting.py | `curve`/`bars` "a forecast with an hour missing"; "quantity per hour" (weather) | "a series with a value missing"; "per interval" — fixed here |

**Summary:** the docstring sweep found Invariant-1 (framework-must-not-know-applications) violated in framework *comments/docstrings* across ~11 files. All fixed in place.

### Code-level Invariant-1 audit — DONE, CLEAN

Checked framework `src` for identifiers, branches, runtime strings and imports naming an application concept:

- **No framework class/function/variable is named after an app concept.** Scan hits (`Board`, `contributors`, `post`, `feed`) are docstring examples or generic — `feed` is `CommandParser.feed(bytes)` and "line feed"; `place`/`Placement` are layout.
- **No branch** compares to an app-concept string (`== "weather"` etc.).
- **The framework imports no application package** (also enforced by packaging).
- Fixed 3 residual docstring leaks the prose sweep missed: "a weather service can ask for the forecasts" → generic; "a post's forum, a month's name" → generic; "One post" → "One item" (all in application.py).

**Judgment calls:**
1. The **`contributor` / "By contributor" / "poster"** running example — **RESOLVED:** genericised to **`user`** / "By user" / "browse by name" throughout the framework (src docstrings in contents.py, declarations.py, application.py; the design.md and writing-an-application.md examples; and the test fixtures in test_contents.py, test_application.py, kept green). `packages/sextile` is now clean of `contributor`/`poster`. "user" was chosen as neutral and already matched the `<user-id>` field in the example.
2. `demo._SAMPLE_BODY` — **RESOLVED by removing `demo.py` entirely.** A canned demonstration frame did not belong in a framework. Deleted `sextile/demo.py` and the `sextile render --demo` CLI flag; moved the frame construction into a self-contained frame-engine smoke test (`tests/test_frame_engine.py`, renamed from `test_demo_page.py`); updated the READMEs, CLAUDE.md, writing-an-application.md and public-surface.md; and fixed the already-broken `sextile.pages.demo` import in `docs/spikes/spike_trimmed_frames.py` to build its own frame. Gate green.

## Invariant-2 concern (application reaching past the public surface)

CLAUDE.md invariant 2: nothing in an application may reach into the framework's
internals; the surface is stated in public-surface.md.

| Finding | Detail |
|---------|--------|
| `weather-viewdata/forecast_page.py` imports `Laid` from `sextile.layout` | **RESOLVED with a rename.** `Laid` was the false-erudite name (past participle of "lay out") for the element type of `PageLayout.parts`, while the inner drawable protocol held the name `Part` — the inversion `parts: Sequence[Laid]`. Renamed the union `Laid` → **`Part`** (so `parts: Sequence[Part]`) and the protocol `Part` → **`Drawable`** (`place()`; implemented by Menu/Lines/Drawn/Form), with the wrapper field `part` → `drawable`. Both `Part` and `Drawable` are now documented in public-surface.md's `sextile.layout` block. The test checks module membership only (`sextile.layout` is public), so it was always green; now the doc lists the names too. mypy clean, 3044 tests pass. |

Also, `handlers.py` (weather) carried a dead `#:` doc-comment describing a
removed constant (nothing followed it); removed as prose cruft.

## Structural drift needing a decision

### page-layout.md — a pre-build proposal, now mostly believed-false

The header says "Built, as of 2026-08-14 … kept because the reasoning is the
part that does not survive in the code — marked where what was built differs
from what was proposed." But the body was never converted from proposal tense,
so it now describes the shipped design as a future and names deleted code as
present:

- Proposal framing throughout: "The two jobs" / "23 construction sites change
  shape" / "## What it would cost" / "## What can be deleted afterwards".
- Deleted code as present: `Template` ("does both", "`Template._divide` already
  works this way", "`Template` guarantees this today"), `templates.py` ("which
  is 907 lines"), `viewdata/chrome.py`, `draw_chrome`, `CONTENT_FIRST_ROW`,
  `CONTENT_ROWS` — all gone.
- "**Names.** `Part`, `Room`, `Placement`, `Offer`, `Summary`, `Furnishing`,
  `Edge` … are all proposals" and "Not settled: the names above" — these names
  are the shipped public surface (see public-surface.md `sextile.layout`).

Much of it also duplicates design.md's "Laying out a page" section, which is
the authoritative as-built account.

Left untouched pending a decision: (a) reframe fully as-built + rationale, or
(b) relabel clearly as "the original proposal, preserved as written" with a
one-line note that Template/chrome are gone and the names are now settled, or
(c) delete it and fold any surviving rationale into design.md / page-layout in
layout.md. This is a content decision, not a prose one.

