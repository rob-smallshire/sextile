# Contributing

How to work on Sextile. The authority is `CLAUDE.md` at the repository root; this
page gathers the parts a human contributor needs and points there for the rest.

## The gate

Four commands must pass over the whole workspace, at every commit — the last
builds the documentation with warnings treated as errors, so a docstring autodoc
cannot render stays broken no longer than the commit that breaks it:

```sh
uv run pytest
uv run ruff check .
uv run mypy
uv run --group docs sphinx-build -n -W --keep-going -b html docs docs/_build/html
```

## The two invariants

1. Nothing in `packages/sextile/` may know about any particular service — not a
   forum, a calendar or the weather. The applications exist to keep this honest.
2. Nothing in an application may reach past the framework's public surface. The
   surface is the set of modules and names in {doc}`reference/public-surface`,
   and `test_public_surface.py` fails if an application imports past it.

## The method

Test-first, in small increments: name the next behaviour, write the failing
test, make it pass, tidy, commit. Retrocomputing facts are settled by driving the
real emulator, not by reading the documentation. When code goes, its tests are
sorted — repointed or deleted — not reimplemented to keep the suite green. The
full method and the conventions are in `CLAUDE.md`.

## Building the documentation

```sh
uv run --group docs sphinx-build -n -W --keep-going -b html docs docs/_build/html
```

The output is written to `docs/_build/html`, which is git-ignored.

## Documentation conventions

- MyST Markdown for every page.
- Cross-reference the API with the `{py:class}`, `{py:func}` and `{py:mod}`
  roles; cross-reference a page with `{doc}`.
- Code fences carry their language.
- A heading is a task or a noun, never a claim.
- Line one of a page declares its genre.
- API names are backticked and spelled exactly as the surface spells them.
- No bold sentences. The full docstring and document rules are in `CLAUDE.md`.

## Showing a frame

A doc that shows a Viewdata frame draws it with the `sextile-frame` directive, so
the frame is the one the code produces at build time, not a screenshot that goes
stale. A frame that stops rendering stops the build. Two forms:

Fetch a page from a service by its `module:name`:

````md
```{sextile-frame}
:app: calendar_viewdata:app
:page: "3"
```
````

Or run a snippet that leaves a `frame` (a `Frame`) or a `page` (a `Page`), with
`fetch(app, number)` in scope — the form for anything that needs a fixed clock or
a hand-built frame. `:frame:` picks a later frame, `:keys:` presses keys from the
page first, and `:show-code:` shows the snippet:

````md
```{sextile-frame}
:show-code:

from datetime import UTC, datetime
from calendar_viewdata import build_application
app = build_application(now=lambda: datetime(2026, 8, 1, tzinfo=UTC))
frame = fetch(app, "3")
```
````

The directive is `docs/_ext/sextile_frames.py`; it draws the frame as
`render --form html` does, and registers the stylesheet and the Bedstead font
from the package.

```{toctree}
:hidden:

open-questions
spikes/README
/plans/revealing-sextile
```
