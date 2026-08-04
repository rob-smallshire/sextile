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

## Connecting a BBC Micro

Sextile is a plain TCP server. Everything between it and a Beeb is off-the-shelf:
[tcpser](https://github.com/go4retro/tcpser) presents a TCP service as an
emulated Hayes modem on an ip232 endpoint, and the emulator dials it. Four
processes, so four shells.

**1. Fetch Stardot's content into the archive**

```sh
cd sextile
uv run sextile ingest --once     # one request: the ten latest posts
```

That is enough to have something to look at. Later, `ingest --seed` sweeps every
route the board publishes — the latest posts, the newest and active topics, then
each forum and each topic it has just learned of — and `ingest` alone polls every
five minutes. (Seeding makes one request per route and the site asks for sixty
seconds between requests, so a first sweep takes about as many minutes as there
are routes: an hour or so for Stardot, and several for a re-sweep of a full
archive. Nothing is lost if it is interrupted; the archive keeps what it has.)

**2. Serve it**

```sh
cd sextile
uv run sextile serve             # answers on port 6850
```

**3. Bridge TCP to an emulated modem**

```sh
tcpser -v 25232 -s 9600 -l 4 -t sS -n 1=localhost:6850
```

`-n 1=…` puts Sextile in the modem's phonebook as number 1, so it can be dialled
without typing a hostname through an emulated keyboard. `-t sS` traces the bytes
in both directions, which is the best debugging tool in the whole arrangement.

**4. Point an emulator's serial port at it**

Here a Beebium instance named `Terminator`, with a Commstar ROM in a sideways
slot:

```sh
./beebium-model-b start \
    --sideways 13:rom:../../../roms/commstar_1_40_SN882A.rom \
    --ip232-serial host=localhost:port=25232 \
    --machine-name "Terminator" --advertise
```

Then in the Beebium front end, **File > Connect…** and choose `Terminator`.

BeebEm should work too, having its own IP232 support, though it has not been
tried here. So should a real BBC Micro with one of the ESP-based WiFi modems.

**5. Dial from Commstar**

```
*COMMSTAR         start the comms ROM
#                 switch to Prestel emulation
C                 enter chat mode
ATDT1  CTRL-M     dial phonebook entry 1
```

`CTRL-M` rather than `RETURN`, because in Prestel mode `RETURN` transmits the
viewdata `#` (0x5F) rather than a carriage return, and an AT command needs a
real one.

![Sextile page 1 on a BBC Micro](docs/images/sextile-page-1.png)

## Trying it without a Beeb

```sh
uv run sextile render --demo                # a frame, in colour
uv run sextile render --demo --form grid    # character and attribute layers
uv run sextile render --demo --form bytes   # the wire stream, as a hex dump

uv run sextile render --page 1              # the main index
uv run sextile render --page 8              # latest posts
uv run sextile render --page 82489493       # one post, by its Stardot id
uv run sextile render --page 8 --frame 1    # its second frame

uv run sextile archive                      # what the archive holds
nc localhost 6850                           # call the server from a terminal
```

`render --page` also prints, to standard error, where each key would lead —
the quickest way to check a menu is wired up correctly.

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
*09#      fetch it afresh           DEL   rub out; over the star, cancel
**        cancel and begin again
```

Commstar does not echo a page request, so Sextile draws it: while one is being
typed the footer becomes a command line, white on blue, with a reminder that `*`
cancels. It is drawn over that row alone rather than by redrawing the frame, and
the cursor is left where the next character goes — so a typed character costs
one byte and a rub-out three.

`**` is then simply cancel followed by begin, which leaves an empty buffer ready
for a new number — what Prestel's `**` did, for a reader who types it out of
habit.

[docs/navigation.md](docs/navigation.md) has the whole model and the reasoning
behind it.

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
`viewtopic.php?p=`. Sextile enforces both in code, with its own RFC 9309 matcher
because Python's `urllib.robotparser` reads the board's file wrongly and would
permit what it forbids.

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

Start with the architecture, then follow whichever narrative you need: one
takes a post from the archive to the wire, the other a keypress from the
terminal to a reply.

| | |
|---|---|
| [architecture.md](docs/architecture.md) | the module map, the seams, and where the awkwardness lives |
| [rendering.md](docs/rendering.md) | how a post becomes bytes, stage by stage |
| [navigation.md](docs/navigation.md) | how a reader moves about, and why the controls are what they are |
| [page-numbering.md](docs/page-numbering.md) | the numbering scheme and why it uses Stardot's own ids |
| [viewdata-encoding.md](docs/viewdata-encoding.md) | what the BBC end actually does, and how we know |
| [spikes/README.md](docs/spikes/README.md) | the eight questions measured on real hardware, and their answers |
| [feed-limitations.md](docs/feed-limitations.md) | what the Atom feed cannot tell us |
| [phpbb-feed-code-newlines.md](docs/phpbb-feed-code-newlines.md) | a defect in phpBB's feed, found here and since fixed |
| [open-questions.md](docs/open-questions.md) | known gaps, and what is deliberately not done |

`CLAUDE.md` records how the project is built, for anyone — human or otherwise —
picking it up.

## Licence

MIT — see [LICENSE](LICENSE).

The test fixtures under `tests/data/` are Atom documents captured from Stardot
and contain posts written by members of that forum. Those words are their
authors' own and are not covered by the grant; see [NOTICE.md](NOTICE.md).
