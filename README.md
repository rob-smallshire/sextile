# Sextile

A Prestel-style Viewdata service presenting the [Stardot](https://stardot.org.uk)
forum to 1980s Acorn computers.

Named after the star key on a viewdata keypad.

Stardot is a phpBB board for Acorn enthusiasts. Sextile reads its Atom feed and
serves the result as 40x24 teletext frames over a serial line, so it can be read
on a real BBC Micro running period comms software.

## State

Read-only and feed-driven, and it answers calls: the whole path from Stardot's
Atom feed to frames on a terminal is built and tested.

```
Atom feed  --> ingest --> SQLite --> content blocks --> frames --> session --> transport --> BBC
             (polite)    (archive)    (semantic)       (40x24)    (Prestel)     (TCP)
                done        done         done            done       done        done
```

A poller keeps the archive fed. What remains is the presentation work that only
watching a real screen can settle — see
[docs/open-questions.md](docs/open-questions.md).

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

```sh
uv run sextile serve                        # answer calls on port 6850
nc localhost 6850                           # and call it
```

Port 6850 is the Motorola MC6850 ACIA, which drives the BBC Micro's serial
port.

## Connecting a BBC Micro

Sextile is a plain TCP server, reached exactly as any other viewdata board is:
[tcpser](https://github.com/go4retro/tcpser) provides the ip232 endpoint the
emulator connects to, and the guest dials out through it.

```sh
tcpser -v 25232 -s 9600 -l 4 -t sS -n 1=localhost:6850
```

Then, in Commstar's Prestel mode, enter chat with `<C>`, type `ATDT1` and press
`CTRL-M`. `-t sS` traces the bytes, which is the best debugging tool available.

## Getting about

Moving about is two-dimensional, and the keys say so:

```
        W                 W, S    up and down the frames of this item
   A    ·    D            A, D    back and forward through the items
        S                 #       the same as S, the conventional viewdata key
```

**The BBC's own cursor keys do the same four things.** They transmit 0x88-0x8B,
and the 7E1 line takes the eighth bit, landing them on the viewdata
cursor-control codes 0x08-0x0B — so arrows and WASD are two spellings of one
compass. Measured, not assumed: `docs/spikes/spike_cursor_keys.py`.

Vertical within an item, because a document reads top to bottom; horizontal
between items, because that is shuffling sideways through a drawer of them.

```
*nnn#     go to a page              1-9   select from the menu
*0#       back, through history     0     the main index
*00#      show this frame again     *     cancel a request being typed
*09#      fetch it afresh           DEL   rub out the last character
**        cancel and begin again
```

Commstar does not echo a page request, so Sextile draws it: while one is being
typed the footer becomes a command line, white on blue, with a reminder that `*`
cancels. It is drawn over that row alone rather than by redrawing the frame, so
it costs about fifty bytes a keystroke and the page beneath survives.

`**` is then simply cancel followed by begin, which leaves an empty buffer ready
for a new number — what Prestel's `**` did, for a reader who types it out of
habit.

**A frame names only the keys that do something on it**, in a footer that says
so compactly:

```
1-9 select, ←W―S→ frame, # next, 0 menu     a menu with frames either side
S→ frame, ←A―D→ post, # next, 0 menu        a post reached through a sequence
0 menu                                      a page reached by typing its number
```

The G0 set has left, right and up arrows but no down arrow — those three are
there for BBC BASIC and the line editor, not as a compass — so the two
horizontal arrows do duty as `previous` and `next` on both axes. At its longest
the footer is exactly forty cells including its colour attribute, which is a
whole row, and there is a test to keep it that way.

WASD is deliberately anachronistic: it postdates viewdata by a decade, where
everything else here is period-correct to the byte. `#` therefore keeps working
alongside `S`, because it is the one key a viewdata reader will try without
being told.

Keyword jumps work too: `*MAIN#`, `*LATEST#`, `*DAYS#`, `*FORUMS#`, `*WHO#`,
`*ABOUT#`, `*BYE#`.

Page numbers follow the board's own identifiers, so `*82489493#` here is post
489493 there. See [docs/page-numbering.md](docs/page-numbering.md).

## How it is put together

[docs/architecture.md](docs/architecture.md) has the module map and, more
usefully, an account of the three seams and why they are where they are: the
`PostSource` port that a phpBB extension would slot into, the `Page`/`PageFrame`
pair that lets a frame decide what its keys do, and the server's deliberate
ignorance of ip232.

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

## Reading further

| | |
|---|---|
| [architecture.md](docs/architecture.md) | the module map and the seams |
| [viewdata-encoding.md](docs/viewdata-encoding.md) | what the BBC end actually does, and how we know |
| [page-numbering.md](docs/page-numbering.md) | the numbering scheme and why it uses Stardot's own ids |
| [feed-limitations.md](docs/feed-limitations.md) | what the Atom feed cannot tell us |
| [phpbb-feed-code-newlines.md](docs/phpbb-feed-code-newlines.md) | a defect in phpBB's feed, written up to hand over |
| [open-questions.md](docs/open-questions.md) | known gaps, and what is deliberately not done |

`CLAUDE.md` records how the project is built, for anyone — human or otherwise —
picking it up.

## Licence

MIT — see [LICENSE](LICENSE).

The test fixtures under `tests/data/` are Atom documents captured from Stardot
and contain posts written by members of that forum. Those words are their
authors' own and are not covered by the grant; see [NOTICE.md](NOTICE.md).
