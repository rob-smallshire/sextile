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
9. Cut the "how it might have been worse" narrative. Three forms of it, all to
   go: tours of other named systems and their failure modes (InDesign, LaTeX,
   CSS Regions, Textual); counterfactual justifications ("a framework that knew
   X would be a framework with an opinion", "would be one more thing that could
   disagree"); and speculative future-guards ("three things would show it had
   overreached"). State the design fact and, briefly, why it fits *this*
   problem. A framework the project deliberately models (Starlette) or the
   actual protocol (Prestel, viewdata) named in passing is fine; the digression
   built around it is not.

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
- [x] docs/design.md  (fork rewrite, reviewed; diagram/code verified intact)
- [x] docs/layout.md
- [x] docs/page-layout.md  (DELETED; rationale folded into design.md, links repointed)
- [x] docs/navigation.md  (also fixed stale "template" reference)
- [x] docs/rendering.md  (also fixed stale chrome.py references)
- [x] docs/viewdata-encoding.md  (already exemplary; one idiom fixed)
- [x] docs/graphics.md
- [x] docs/mosaic-fonts.md  (fixed stale Template-base reference)
- [x] docs/public-surface.md  (prose only; module-table drift recorded, not fixed)
- [x] README.md  (fixed broken draw_chrome headline example)

Source docstrings + comments (src/sextile):
- [ ] __init__.py, __main__.py
- [x] addressing.py
- [x] application.py
- [ ] cli.py
- [ ] compass.py
- [ ] content/ (blocks.py, transliterate.py)
- [x] declarations.py
- [ ] demo.py
- [x] formatting.py  (fixed several Invariant-1 leaks)
- [x] forms.py  (fixed several Invariant-1 leaks)
- [x] handlers.py
- [x] held.py
- [x] keys.py
- [x] layout.py  (fixed Shortcut Invariant-1 leak)
- [x] middleware.py  (already at target; left unchanged)
- [x] page.py  (source-docstring register sample)
- [x] pages/ (contents, guidance, history, names, readership)  (fixed Invariant-1 leaks)
- [x] requests.py
- [x] routing.py
- [x] server.py
- [x] session/ (commands.py, session.py)  (fixed 2 Invariant-1 comment leaks)
- [ ] testing.py
- [ ] visits.py
- [~] viewdata/  (Batch E done: canvas, drawing, composition rewritten;
      ansi, charset, controls, encoding, frame already at target. Remaining:
      blocks, charting, command_line, countdown, font, fonts, footer,
      lettering, parting, repaint, typesetting, wrapping)

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
