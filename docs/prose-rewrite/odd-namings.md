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
