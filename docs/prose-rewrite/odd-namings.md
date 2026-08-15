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

