# Prose rewrite tracker

Working file for the project-wide rewrite of English prose (Markdown docs,
module and class docstrings, inline comments). Not a design document; delete or
gitignore when the sweep is finished.

## Standard

Strict and plain, as stated in `CLAUDE.md`'s "Writing the documentation"
section, applied literally:

1. Name the identifier, do not paraphrase it.
2. Summary line is one sentence with a finite verb.
3. No anthropomorphism. A module, class, page or session does not know, want,
   ask, decide or need. Name the actor (the caller, the subclass author, the
   session's code) or rewrite so none is needed.
4. One term, one meaning, fixed across the package.
5. `Example:` wherever the call sequence is not obvious from the signature.
6. Public class gets `Attributes:`; `ClassVar` knobs in a labelled block above.
7. Count nothing not enumerated; enumerate nothing not counted.
8. Cut ornament: em-dash asides, inversions, rhythm for its own sake.

Markdown gets the same, register loosened one notch (a reader there chose to be
reading), but still no metaphor a reader cannot act on.

Odd names found along the way go in `odd-namings.md`, not fixed in passing.

## Order

Package by package. Within each: docs, then module/class docstrings, then
inline comments. `sextile` first (the framework), then the three applications,
then the workspace-level docs, then `CLAUDE.md` last.

Commit at each working increment. Run `uv run ruff check .`, `uv run mypy`,
`uv run pytest` before committing when code files (docstrings/comments) changed;
docs-only changes need no test run.

## Progress

Legend: `[ ]` not started · `[~]` in progress · `[x]` done

### Phase 1 — sextile (framework)

Docs:
- [x] docs/writing-an-application.md  (flagship; register sample for sign-off)
- [~] docs/design.md  (delegated to a fork; awaiting review)
- [x] docs/layout.md
- [ ] docs/page-layout.md
- [x] docs/navigation.md  (also fixed stale "template" reference)
- [x] docs/rendering.md  (also fixed stale chrome.py references)
- [x] docs/viewdata-encoding.md  (already exemplary; one idiom fixed)
- [x] docs/graphics.md
- [x] docs/mosaic-fonts.md  (fixed stale Template-base reference)
- [x] docs/public-surface.md  (prose only; module-table drift recorded, not fixed)
- [x] README.md  (fixed broken draw_chrome headline example)

Source docstrings + comments (src/sextile):
- [ ] __init__.py, __main__.py
- [ ] addressing.py
- [ ] application.py
- [ ] cli.py
- [ ] compass.py
- [ ] content/ (blocks.py, transliterate.py)
- [ ] declarations.py
- [ ] demo.py
- [ ] formatting.py
- [ ] forms.py
- [ ] handlers.py
- [ ] held.py
- [ ] keys.py
- [ ] layout.py
- [ ] middleware.py
- [ ] page.py
- [ ] pages/ (contents, guidance, history, names, readership)
- [ ] requests.py
- [ ] routing.py
- [ ] server.py
- [ ] session/ (commands.py, session.py)
- [ ] testing.py
- [ ] visits.py
- [ ] viewdata/ (ansi, blocks, canvas, charset, charting, command_line,
      composition, controls, countdown, drawing, encoding, font, fonts,
      footer, frame, lettering, parting, repaint, typesetting, wrapping)

### Phase 2 — applications

- [ ] calendar-viewdata (docs + src)
- [ ] stardot-viewdata (docs + src)
- [ ] weather-viewdata (docs + src)

### Phase 3 — workspace docs

- [ ] README.md (root)
- [ ] docs/architecture.md
- [ ] docs/target-architecture.md
- [ ] docs/open-questions.md
- [ ] NOTICE.md (only if it carries prose worth touching)

### Phase 4 — CLAUDE.md

- [ ] Root CLAUDE.md, especially the writing-standard section.
