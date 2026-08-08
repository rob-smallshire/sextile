# Getting about

How a reader moves through Sextile, and why the controls are what they are.

Two rules run through all of it:

- **A frame names only the keys that do something on it.** An offer that goes
  nowhere is worse than no offer, and on a service that answers slowly a reader
  cannot tell a dead key from a slow one.
- **A reader must always be able to see where they are and get out.** Hence the
  page number on every frame, `0` for the menu on every frame, and a cancel that
  works from anywhere.

## The keys

```
        W                 W, S    up and down the frames of this item
   A    ·    D            A, D    back and forward through the items
        S                 #       the same as S, the conventional viewdata key
```

Vertical within an item, because a document reads top to bottom; horizontal
between items, because that is shuffling sideways through a drawer of them.

**The BBC's own cursor keys do the same four things.** They transmit 0x88-0x8B
and the 7E1 line takes the eighth bit, landing them on the viewdata
cursor-control codes 0x08-0x0B. So arrows and WASD are two spellings of one
compass, and `sextile/keys.py` is where it is spelled once.

`sextile/compass.py` draws that compass, for a page that would rather show a
reader which way is which than tell them. The arrows on it are mosaics because
the G0 set has left, right and up and **no down arrow** — those three are there
for BBC BASIC and the line editor rather than as a compass, so one of the four
would have had to be drawn whatever happened.

WASD is the project's one deliberate anachronism — it postdates viewdata by a
decade, where everything else here is period-correct to the byte. `#` therefore
keeps working alongside `S`, being the one key a viewdata reader will try
without being told, and there are tests to keep the two identical.

```
*<number># go to a page             1-9   select from the menu
*0#       back, through history     0     the main index
*00#      show this frame again     *     cancel a request being typed
*09#      fetch it afresh           DEL   rub out; over the star, cancel
**        cancel and begin again
```

Keyword jumps work too: `*MAIN#`, `*LATEST#`, `*DAYS#`, `*FORUMS#`, `*WHO#`,
`*ABOUT#`, `*BYE#`. Prestel was almost entirely numeric because its terminals
were keypads and its pages a numeric database; we own both ends and need not be.

## What "next item" means

`A` and `D` walk **the sequence the reader arrived through**. From a day's index
`D` walks that day; from a forum it walks that forum; from a topic it walks the
thread. A page reached by typing its number belongs to no sequence, so neither
key is offered there.

The sequence carries across a menu's own frames, so the ninth choice of frame a
is followed by the first of frame b. `Page.destinations` is where a page says
what it offers, in order, and `Session._Sequence` is where the reader's place in
it lives.

## Choices and moves are different things

`PageFrame` keeps two mappings, and the distinction is load-bearing:

- **`choices`** — keys that go to another page. Keyed by character, not digit,
  so a page can offer `R` for reply later without the type changing.
- **`moves`** — keys that move within this page, to another of its frames. They
  name no destination: the session stays on the page it is already showing.

Putting frame movement among the choices made a menu appear to offer eleven of
them, which two existing tests noticed immediately. The session consults `moves`
first, then `choices`, and does nothing at all with a key in neither.

## The footer

Forty cells is not many, and the prompt has to say what every available key
does. At its longest it fills the row exactly, so the next thing added will not
fit — and what gives should be decided by what a reader can least afford to
lose, not by what happens to sit at the end of the string.

So a prompt is **composed as items, not written as a string**:

```python
from sextile.viewdata.footer import ROOM, FooterItem, Priority, movement, render_footer

items = [FooterItem("1-9", "select", Priority.PRIMARY)]
items += movement(moving, item="post")
items.append(FooterItem(HOME_KEY, "index", Priority.ESSENTIAL))
prompt = render_footer(items, ROOM)
```

`movement` gives the framework's own words for the framework's own keys, so a
page built by a template and a page built by hand say the same thing about
`S`. Only the noun differs, and it comes from the service: a post, a month, a
day.

| key | full | brief |
|---|---|---|
| `W` | page up | up |
| `S` | page down | down |
| `A` | previous *noun* | prev |
| `D` | next *noun* | next |

Everything else a page offers is a `FooterItem` of its own: the key, what it
does in words, a priority, and optionally a **brief** way of saying the same
thing for when the row is tight.

### What gives, and in what order

The renderer takes the fullest wording that fits, giving up in this order:

1. **the long wording**, where there is a short one — a *band* of keys at a
   time, since `W page up` beside a bare `S` reads as though the two were
   different sorts of thing when they are a pair;
2. **keys that are only another key said differently** — `#`, which `S`
   already does;
3. **the word beside the way out**, `0` being the one key every reader knows;
4. **the last word off everything else**, then whole items, then a cut.

```
S page down, # next frame, 0 index              a frame with room
1-9 select, W up, S down, #, 0 index            a menu in the middle of a run
W up, S down, A prev, D next, 0 index           everything a post can offer
0                                               a row of one cell
```

**Say it in full and let the renderer decide.** The prompt used to be written
for the busiest page — `←W―S→ frame`, a pair of keys packed into one item and
labelled with the noun they move through — and that wording was then used on
every page, including ones with fifteen cells going spare. Nothing was
contracting it: there was no middle setting between the sentence and the
letter, so whoever wrote the page had to choose, and chose the one that fits
everywhere.

## The command line

Commstar does not echo a `*123#` page request, so unless Sextile draws it the
reader is typing blind. While a request is being entered the footer becomes a
command line — white on blue for the buffer, yellow on black for a reminder that
`*` cancels — and goes away when the request is finished or abandoned.

It is drawn over row 23 alone. `CURSOR_HOME` then cursor up wraps to that row,
so the first draw costs about fifty bytes rather than the seven hundred a frame
would.

After that it is cheaper still, because the cursor is left exactly where the
next character goes:

| Keystroke | Cost |
|---|---|
| the first `*` | ~50 bytes, a row redraw |
| a character typed | **1 byte** — the cursor advances itself |
| a character rubbed out | **3 bytes** — cursor left, a space, cursor left |
| the buffer scrolling, or `*` cancelling | a redraw, everything having moved |

The space in a rub-out keeps the row's blue background, the attributes that set
it sitting earlier in the row and going untouched.

**The cursor is hidden everywhere else.** Every frame begins by turning it off,
so it does not trail across the screen as the frame paints; the command line
turns it back on, that being the one place it tells a reader anything.

## Cancelling

One rule: **a star while typing cancels.** The command line goes away, the footer
comes back, and a reader who changes their mind is never trapped in a buffer they
no longer want.

`**` is then simply cancel followed by begin, which leaves an empty buffer ready
for a new number — exactly what Prestel's `**` did, without the parser knowing
the sequence at all. `*824**456#` goes to page 456, as a reader with Prestel
habits would expect.

DELETE rubs out the last character, and rubbing out the star itself cancels, the
star being a character like any other. That is one rule fewer than treating the
boundary specially, and it makes DELETE do the obvious thing everywhere.

## Where the code is

| | |
|---|---|
| `sextile/keys.py` | the compass, and the arrow codes that spell it |
| `sextile/compass.py` | drawing it, for a page that shows rather than tells |
| `sextile/session/commands.py` | bytes to commands; syntax only, no meanings |
| `sextile/session/session.py` | where the reader is, where they have been, what to send |
| `sextile/page.py` | `Page` and `PageFrame`: frames, choices, moves |
| `sextile/routing.py` | which page number means which page |
| `sextile/application.py` | the seam an application answers across |
| `sextile/viewdata/footer.py` | fitting the prompt into a row |
| `sextile/viewdata/command_line.py` | drawing and editing the request being typed |

All of it is the framework's. What the pages actually *are* belongs to an
application: see [writing-an-application.md](writing-an-application.md).

The command parser recognises **syntax only**. Whether `MAIN` or `82489493`
names anything is the numbering layer's business, and whether `N` does anything
is the current frame's. That is what keeps viewdata's numeric keypad from being
baked in.
