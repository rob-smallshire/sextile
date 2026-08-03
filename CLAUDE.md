# Working on Sextile

A Prestel-style Viewdata service presenting the Stardot phpBB forum to 1980s
Acorn hardware. Read [docs/architecture.md](docs/architecture.md) first; it
explains the layering and, more usefully, where the seams are and why.

## How this project is built

**Test-first, in small increments.** Name the next behaviour, write the failing
test, make it pass, tidy. The awkward parts here are nearly all pure functions
over values — transliteration, page numbers, HTML to blocks, layout, command
parsing — and the two impure edges, HTTP and sockets, sit behind narrow
interfaces that are easy to fake.

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
[docs/viewdata-encoding.md](docs/viewdata-encoding.md), which separates what was
verified from what was inferred. **Keep that distinction** in anything new.

Beebium's own source is a good oracle where a spike would be slow:
`~/Code/beebium/src/core/include/beebium/Saa5050.hpp` and
`docs/discussion/teletext-repertoire-choice.md` settled the per-row attribute
reset and corroborated the character set.

**Say so when something is missing.** An empty menu with no explanation looks
like a fault, and on a service that answers slowly by design a reader cannot
tell the difference. Pages with nothing to show say why. The same applies to
feed entries that fail to parse: they are reported, not silently dropped.

**Record limitations as tests.** What the feed cannot tell us is pinned by tests
in `tests/test_html.py` and `tests/test_atom.py`, so a change in the board's
configuration surfaces as a failure rather than going unnoticed. See
[docs/feed-limitations.md](docs/feed-limitations.md).

## Conventions

- `uv` for everything: `uv run pytest`, `uv run ruff check .`, `uv run mypy`.
- All three must pass. `mypy` is `--strict`, including the tests.
- Path variables use the `_filepath`, `_dirpath` suffixes, not `_dir`/`_file`.
- Comments explain *why*, and are worth writing where a choice looks arbitrary
  but is not. There are many such choices here.
- Commit at each working increment. Do not push; that is the user's call.

## Politeness is not optional

Stardot asks for a 60-second crawl delay and forbids several paths, including
`viewtopic.php?p=` — which is exactly the page that would reveal a post's topic
id. Both are enforced in `feed/`. `feed/robots.py` is hand-written because
Python's `urllib.robotparser` reads Stardot's file wrongly and would permit what
the board forbids.

Test fixtures under `tests/data/` were captured from the live board. Prefer
re-using them to making fresh requests.

## Trying it

```sh
uv run sextile render --demo            # a frame, in colour, without a Beeb
uv run sextile render --page 1          # any page, plus where each key leads
uv run sextile ingest --seed            # fill a new archive (~20 minutes)
uv run sextile ingest                   # then poll every 5 minutes
uv run sextile serve                    # answer calls on port 6850
nc localhost 6850                       # and call it
```

`serve` and `ingest` both default to `sextile.sqlite` **in the working
directory**, so run them from the same place.

[docs/open-questions.md](docs/open-questions.md) lists what is known to be
missing, and what is deliberately not done.
