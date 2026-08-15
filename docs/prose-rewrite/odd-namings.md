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
| public-surface.md, "What is internal" table (was line ~187) | `viewdata.chrome`, `.footer`, `.layout` "what a template is built from" | `viewdata.chrome` is deleted (the doc itself says so at the chrome paragraph); there is no `viewdata/layout.py` (the furniture layer is top-level `sextile.layout`); and `viewdata.footer` is described as *public* later in the same doc ("footer ... turned out to be public"). This row contradicts the rest and needs reconciling against `test_public_surface.py`. Left the module membership unchanged; only the surrounding prose was touched. | NEEDS TESTED FIX — do not guess |
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

