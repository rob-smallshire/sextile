# Working on Sextile

A uv workspace: a Viewdata application-server framework and the services built
on it. Start with [README](README.md) and
[docs/architecture.md](docs/architecture.md), which maps the workspace and says
where the seams are. [docs/target-architecture.md](docs/target-architecture.md)
is where the product is going;
[docs/plans/revealing-sextile.md](docs/plans/revealing-sextile.md) where the
rework is. Each package is written up as built in its own `docs/design.md`.

## The two invariants

Both are checkable; `test_public_surface.py` pins the second, and the calendar
and weather services keep the first honest.

1. **Nothing in `packages/sextile/` may know about a forum, phpBB, Stardot, a
   calendar or the weather** -- not in the code, and preferably not in the
   comments. `calendar-viewdata` and `weather-viewdata` exist to keep this
   honest. An application finding the framework *awkward* is a framework defect
   to fix and write down, not a seam moving.
2. **Nothing in an application may reach into the framework's internals.** The
   surface is a stated set of public submodules and names, in
   [public-surface.md](packages/sextile/docs/public-surface.md); a module not
   listed there is machinery. The test fails if an application imports past it.

## How this is built

- **Test-first, in small increments.** Name the next behaviour, write the
  failing test, make it pass, tidy. Commit at each working increment.
- **Measure the BBC end; do not assume it.** Retrocomputing facts are settled by
  driving real Commstar under Beebium, not by reading the documentation. The
  spikes are in `docs/spikes/`; findings, kept separate from what is inferred,
  in [viewdata-encoding.md](packages/sextile/docs/viewdata-encoding.md).
- **Say so when something is missing.** A page with nothing to show says why; a
  page that does not exist returns `None`, and the session says so without
  moving the reader.
- **When code goes, its tests are sorted, not rescued.** Each failing test tests
  something that survives (repoint it), duplicates another (delete it), or
  tested only the deleted thing (delete it). Never reimplement deleted code in a
  test to keep the suite green.
- **"Nothing calls it" is not a reason to delete framework code** -- the surface
  is justified by being useful to a service, not by being used by the three
  here. The reason to delete is a *duplicate* implementation.
- **A new `PageLayout` field needs a second caller, or the page wants a part of
  its own.** Look for the field it is a special case of first; content that is
  not a plain sequence is a `Part`, and a sequence drawn its own way a
  `SequencePart` subclass.

## Conventions

- `uv` for everything: `uv run pytest`, `uv run ruff check .`, `uv run mypy`
  (`--strict`, tests included). All three run over the workspace and must pass.
- Path variables use the `_filepath`/`_dirpath` suffixes, not `_dir`/`_file`.
- Comments explain *why*, beside the line that makes a choice. The why-comments
  in `routing.py` and `keys.py` are the model.
- Commit at each increment. Do not push; that is the user's call. No emoji in
  commit messages, and do not name the model or the assistant.

## Writing the documentation

Docstrings are the framework's primary documentation and what Sphinx/autodoc
renders. The `docs/*.md` are being rewritten under Sphinx; until then,
[glossary.md](packages/sextile/docs/glossary.md) is the rename ledger.

Google style, contract first (what it is, what goes in, what comes out, what a
subclass overrides); rationale after the sections and short, or in a `#`
comment. Sentence-level rules:

1. Name the identifier, do not paraphrase it.
2. Summary is one sentence: a finite verb for a function or method, a noun
   phrase for a property, a value or a type.
3. No anthropomorphism -- a class does not say, want, know, ask or decide.
4. One term, one meaning, fixed across the package.
5. `Example:` wherever the call sequence is not obvious -- anything constructed
   then built, anything subclassed.
6. `Attributes:` on a public class, the `ClassVar` knobs a subclass overrides in
   their own labelled block above it.
7. Count nothing you have not enumerated; better, do not count.
8. Cut ornament: em-dash asides, inversions, rhythm for its own sake.
9. No history ("used to", "since it was written"), no application concept even
   in an example, no "how it might have been worse".

Document-level rules, for the Markdown too:

- Declare the genre in line one.
- Code or a table first under any heading, then at most three sentences of
  contract, rationale last in a short Why note.
- Headings are tasks or nouns, never claims.
- No bold sentences.
- One home per idea; elsewhere a link.
- A doc that says it renders something pastes the render.
- Every API name backticked, spelled exactly, and present in the surface.

## Crawling Stardot

Stardot asks for a 60-second crawl delay and forbids several paths, including
`viewtopic.php?p=`; both are enforced in `stardot_viewdata/feed/`, whose
`robots.py` is hand-written because `urllib.robotparser` reads Stardot's file
wrongly and would permit what the board forbids. Prefer the captured fixtures
under `packages/stardot-viewdata/tests/data/` to fresh requests.

## Trying it

```sh
uv run sextile serve calendar_viewdata:app          # a whole service, no forum
uv run stardot-viewdata ingest --seed               # fill the archive first (an hour)
uv run stardot-viewdata serve                       # then answer calls on port 6850
uv run weather-viewdata import-places               # fill the gazetteer first (seconds)
uv run weather-viewdata render --page 3213133880    # then Trondheim's forecast
nc localhost 6850                                   # and call it
```

`ingest` and `import-places` default to SQLite files in the working directory,
so run them and `serve` from the same place.

[docs/open-questions.md](docs/open-questions.md) lists what is known to be
missing, and what is deliberately not done.
