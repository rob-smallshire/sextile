# Working on Sextile

A uv workspace holding a Viewdata application-server framework and the services
built on it.

```
packages/sextile/              the framework: connections, sessions, routing,
                               page numbering, frames on the wire
packages/stardot-viewdata/     the Stardot phpBB forum, as Viewdata
packages/calendar-viewdata/    a calendar; the framework's worked example
packages/weather-viewdata/     the weather, from met.no and a local gazetteer
```

Read [docs/architecture.md](docs/architecture.md) first; it maps the workspace
and says where the seams are. Then whichever of these you are working in — each
is written up as built:

- [sextile/docs/design.md](packages/sextile/docs/design.md)
- [stardot-viewdata/docs/design.md](packages/stardot-viewdata/docs/design.md)
- [calendar-viewdata/docs/design.md](packages/calendar-viewdata/docs/design.md)
- [weather-viewdata/docs/design.md](packages/weather-viewdata/docs/design.md)

[docs/target-architecture.md](docs/target-architecture.md) says where this is
going: a phpBB extension replacing the Atom feed. For writing a new service,
[writing-an-application.md](packages/sextile/docs/writing-an-application.md);
for the two end-to-end narratives,
[rendering.md](packages/sextile/docs/rendering.md) and
[navigation.md](packages/sextile/docs/navigation.md).

## The two invariants

They are the point of the whole arrangement, and both are checkable.

1. **Nothing in `packages/sextile/` may know about a forum, phpBB, Stardot, a
   calendar or the weather.**
   Not in the code, and preferably not in the comments — a framework that
   explains itself in terms of posts will grow a dependency on them sooner or
   later. `calendar-viewdata` and `weather-viewdata` exist to keep this honest: if a
   page there ever needs something the framework offers only because Stardot
   wanted it, the seam has moved.

   Note the difference between that and an application finding the framework
   *awkward*. `weather-viewdata` did, five times in a day, and each was a real
   framework defect rather than a seam moving. When something in `sextile` is
   awkward from an application, that is evidence: fix the framework and write
   down what it was, rather than working around it in the application.

2. **Nothing in an application may reach into the framework's internals.** The
   surface is a stated set of public submodules, each with a stated set of
   public names, written down in
   [public-surface.md](packages/sextile/docs/public-surface.md). A module not
   listed there is machinery.

   That document also lists the places where the line is currently crossed, and
   what has to happen before each can be deleted — nothing checks the surface
   yet, which is how it came to be crossed in six places unnoticed. Read it
   before adding an import to an application or moving a module in the
   framework.

## How this project is built

**Test-first, in small increments.** Name the next behaviour, write the failing
test, make it pass, tidy. The awkward parts here are nearly all pure functions
over values — transliteration, routing, HTML to blocks, layout, command parsing
— and the two impure edges, HTTP and sockets, sit behind narrow interfaces that
are easy to fake.

**Measure the BBC end; do not assume it.** Several things that a reasonable
reading of the documentation would get wrong were settled by driving real
Commstar under Beebium:

- attributes must travel as `ESC` + code + 0x40; the SAA5050's own 0x80-0x9F
  codes simply vanish on Prestel's 7E1 line;
- a frame is 24 rows of 40, column 40 wraps by itself, and the bottom-right cell
  wraps to the top-left rather than scrolling;
- `RETURN` transmits 0x5F, not 0x23;
- page numbers have no practical length limit.

The spikes that established these are in `docs/spikes/`. They need a local
Beebium checkout and are not part of the test suite. Findings are written up in
[viewdata-encoding.md](packages/sextile/docs/viewdata-encoding.md), which separates what was
verified from what was inferred. **Keep that distinction** in anything new.

Beebium's own source is a good oracle where a spike would be slow:
`~/Code/beebium/src/core/include/beebium/Saa5050.hpp` and
`docs/discussion/teletext-repertoire-choice.md` settled the per-row attribute
reset and corroborated the character set.

**Say so when something is missing.** An empty menu with no explanation looks
like a fault, and on a service that answers slowly by design a reader cannot
tell the difference. Pages with nothing to show say why. Note the difference
between that and a page that does not exist: a handler returns `None` for the
second, and the session says so without moving the reader.

**Record limitations as tests.** What the feed cannot tell us is pinned by tests
in `packages/stardot-viewdata/tests/`, so a change in the board's configuration
surfaces as a failure rather than going unnoticed. See
[feed-limitations.md](packages/stardot-viewdata/docs/feed-limitations.md).

**Keep the design documents as built.** Each package has one, and they describe
what is there rather than what was planned. A design that has drifted from the
code is worse than none, because it is believed.

## Conventions

- `uv` for everything: `uv run pytest`, `uv run ruff check .`, `uv run mypy`.
  All three run over the whole workspace, and all three must pass. `mypy` is
  `--strict`, including the tests.
- Path variables use the `_filepath`, `_dirpath` suffixes, not `_dir`/`_file`.
- Comments explain *why*, and are worth writing where a choice looks arbitrary
  but is not. There are many such choices here.
- Commit at each working increment. Do not push; that is the user's call.

**When code goes, its tests are sorted rather than rescued.** Each test that
fails belongs in one of three piles: it tests something that survives, it
duplicates a test somewhere else, or it tested only the thing being deleted.
The first is repointed, the second and third are deleted with the code.

Never reimplement deleted code in a test module to keep the suite green. A test
that verifies a copy verifies the copy, and the suite goes green while the
guarantee it stood for is gone. This has happened here: `typesetting` lost its
pagination and the two functions reappeared in `test_typesetting.py`, with a
justification in the commit message.

The failure mode either way is treating green as the goal rather than as
evidence. Deleting a test module wholesale with the module it tested is the
same mistake facing the other way: `test_templates.py` went with
`templates.py`, and took with it the only tests of `farewell_page`, of a
shortcut answering its arrow, and of what the footer calls the way home -- all
three of which survived the deletion under another name.

**A new field on `Template` needs a second caller, or it wants to be a
subclass.** The shapes are configured rather than composed, which is right for
a small closed vocabulary and turns into twenty knobs if nobody counts. Three
fields were added in a day, each for one page; one of them, `home_says`, would
have failed this test and was folded back into `home` the day after.

Before adding one, look for the field it is a special case of. `home` and
`shortcuts` were the same idea — a key on every frame leading to a fixed
address — spelled two ways, so the second way went. And check what a page
needing this could do instead: a service can subclass `Template` or
`RowTemplate` and supply its own drawing, which is what `weather-viewdata` does
for a forecast day four rows tall.

Note also that `preamble`, `headings` and `footnote` are one idea spelled three
times — rows around the entries, differing in whether they sit above or below
and whether they appear on the first frame or on all of them. They are left
alone deliberately: with one or two callers each there is not yet enough
evidence to say what the single field would look like. A third caller for any
of them is the moment to unify them, not to add a fourth.

## Writing the documentation

Docstrings here have drifted into essay: fluent, metaphorical, and about the
design rather than about the interface. The prose was pleasant enough to hide
mistakes in itself — a list of three introduced as "two shapes", "the six steps"
that are enumerated nowhere. Everything below is a correction to that, and
applies to new docstrings and to any old one being touched. Bring an old
docstring up to this standard rather than patching around it.

**Google style, and nothing else.** `Args:`, `Returns:`, `Yields:`, `Raises:`,
`Attributes:`, `Example:`, in that order. Every parameter appears under `Args:`.
Do not restate a type — `mypy --strict` has already said it; say what the value
*means* and what constrains it.

**Two jobs, and they do not share a paragraph.**

- The *contract*: what this is, what goes in, what comes out, what a subclass
  must override. It comes first, it is plain, and it is complete.
- The *rationale*: why this and not the obvious alternative. It comes after the
  sections, or better, goes in an inline `#` comment beside the line that makes
  the choice, or in the package's `design.md`. If the rationale is longer than
  the contract, it is in the wrong place.

The discursive register belongs in `#` comments, where there is no contract
competing for the space. The existing why-comments in `templates.py` are the
model; its class docstrings are not.

**The rules, in order of how often they are broken here.**

1. Name the identifier, do not paraphrase it. Write "`rows_per_entry` rows",
   not "how tall an entry is". Names are what a reader greps for, what
   autocomplete offers, and what a traceback prints; a paraphrase is a
   translation exercise set for the reader.
2. The summary line is one sentence with a finite verb, saying what the thing
   is or does. It is often the only line a tooltip shows. Not a bare noun
   phrase, not a metaphor, not the least informative sentence in the docstring.
3. No anthropomorphism. A class does not say, want, know, ask or decide. Name
   the actor — the caller, the subclass author, the session — or rewrite so
   none is needed.
4. One term, one meaning, fixed across the package. *Frame*, *entry*,
   *template*, *row*, *chrome* each have exactly one sense. Do not press a word
   into a second job because it sounds well (as *shape* was: subclass kind,
   visual layout, and goodness of fit, in one file).
5. Give an `Example:` wherever the call sequence is not obvious from the
   signature — anything constructed then built, anything subclassed. Six lines
   of real code outteach three paragraphs.
6. A public class gets `Attributes:`, covering every field a caller passes. Put
   the `ClassVar` knobs a subclass overrides in a block of their own above it,
   labelled as such: which of the two a reader is looking at is the most
   important thing about a base class here, and one merged list loses it.
7. Count nothing you have not enumerated, and enumerate nothing you have not
   counted. Better still, do not count: say "the shapes are" and list them.
8. Cut ornament. Em-dash asides, inversions, and rhythm for its own sake. If a
   sentence survives being said flatly, say it flatly. This is the rule that
   catches the error the others let through, because plain prose makes a wrong
   claim look wrong.

The same applies to Markdown in `docs/`, with the register loosened one notch:
a reader there has chosen to be reading, but still cannot act on a metaphor.

## Politeness is not optional

Stardot asks for a 60-second crawl delay and forbids several paths, including
`viewtopic.php?p=` — which is exactly the page that would reveal a post's topic
id. Both are enforced in `stardot_viewdata/feed/`, whose `robots.py` is
hand-written because Python's `urllib.robotparser` reads Stardot's file wrongly
and would permit what the board forbids.

Test fixtures under `packages/stardot-viewdata/tests/data/` were captured from
the live board. Prefer re-using them to making fresh requests.

## Trying it

```sh
uv run sextile render --demo                        # a frame, without a Beeb
uv run sextile serve calendar_viewdata:app          # a whole service, no forum
uv run stardot-viewdata render --page 1             # a page, plus where its keys lead
uv run stardot-viewdata ingest --seed               # fill a new archive (an hour or more)
uv run stardot-viewdata ingest                      # then poll every 5 minutes
uv run stardot-viewdata serve                       # answer calls on port 6850
uv run weather-viewdata import-places               # fill the gazetteer (11 seconds)
uv run weather-viewdata render --page 3213133880     # Trondheim's forecast
                                                    # *3# and *4# are typed into,
                                                    # so they want a real session
uv run weather-viewdata serve                       # or answer calls
nc localhost 6850                                   # and call it
```

`serve` and `ingest` both default to `stardot.sqlite` **in the working
directory**, so run them from the same place.

[docs/open-questions.md](docs/open-questions.md) lists what is known to be
missing, and what is deliberately not done.
