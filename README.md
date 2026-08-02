# Sextile

A Prestel-style Viewdata service presenting the [Stardot](https://stardot.org.uk)
forum to 1980s Acorn computers.

Named after the star key on a viewdata keypad.

Stardot is a phpBB board for Acorn enthusiasts. Sextile reads its Atom feed and
serves the result as 40x24 teletext frames over a serial line, so it can be read
on a real BBC Micro running period comms software.

## State

Read-only and feed-driven. Everything from the feed to a renderable page is
built and tested; the server that would send those pages to a terminal is not.

```
Atom feed  --> ingest --> SQLite --> content blocks --> frames --> session --> transport --> BBC
             (polite)    (archive)    (semantic)       (40x24)    (Prestel)     (TCP)
                done        done         done            done       next        next
```

## Trying it

```sh
uv run sextile render --demo                # a frame, in colour, without a Beeb
uv run sextile render --demo --form grid    # character and attribute layers
uv run sextile render --demo --form bytes   # the wire stream

uv run sextile ingest --once                # fetch the feed into the archive
uv run sextile archive                      # what the archive holds

uv run sextile render --page 1              # the main index
uv run sextile render --page 8              # latest posts
uv run sextile render --page 82489493       # one post, by its Stardot id
uv run sextile render --page 8 --frame 1    # its second frame
```

`render --page` also prints, to standard error, where each digit key would
lead — which is the quickest way to check a menu is wired up correctly.

## Connecting a BBC Micro

Sextile is a plain TCP server, reached exactly as any other viewdata board is:
[tcpser](https://github.com/go4retro/tcpser) provides the ip232 endpoint the
emulator connects to, and the guest dials out through it.

```sh
tcpser -v 25232 -s 9600 -l 4 -t sS -n 1=localhost:6502
```

Then, in Commstar's Prestel mode, enter chat with `<C>`, type `ATDT1` and press
`CTRL-M`. `-t sS` traces the bytes, which is the best debugging tool available.

## What was measured rather than assumed

Much of the design rests on facts established against real software rather than
on documentation:

- Attributes must be escape-encoded as `ESC` + code + 0x40. The SAA5050's own
  0x80-0x9F codes do not survive Prestel's 7E1 line.
- A frame is exactly 24 rows of 40 cells. Column 40 wraps by itself, and the
  bottom right cell wraps back to the top left rather than scrolling.
- `RETURN` transmits 0x5F, not 0x23, so a page request ends with 0x5F.
- Page numbers have no practical length limit; the nine-digit Prestel maximum
  was a property of Prestel's database, not of any terminal.
- Python's `urllib.robotparser` reads Stardot's robots.txt incorrectly, so
  Sextile implements RFC 9309 matching itself.

See `docs/viewdata-encoding.md` and `docs/page-numbering.md`, and the spikes in
`docs/spikes/` that settled each question.

## Politeness

Stardot asks for a 60-second crawl delay and forbids several paths, including
the one that would reveal a post's topic id. Sextile enforces both in code.

## Development

```sh
uv run pytest
uv run ruff check .
uv run mypy
```

The spikes under `docs/spikes/` need a local Beebium checkout and are not part
of the test suite; they are kept as the record of how each question was
answered.
