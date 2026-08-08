# Sextile

A framework for Prestel-style Viewdata services in Python, and the service it
was extracted from.

Named after the star key on a viewdata keypad.

```
packages/sextile/              the framework: connections, sessions, routing,
                               page numbering, frames on the wire
packages/stardot-viewdata/     an application: the Stardot forum, as Viewdata
```

Sextile is to a Viewdata service what Flask or Starlette is to a web
application. It owns everything whose natural lifetime is the call, and an
application says what the pages are:

```python
from sextile import Page, PageRequest, Sextile

app = Sextile()

@app.page("82{post_id:int}", name="post")
async def post(request: PageRequest, post_id: int) -> Page:
    ...
```

```sh
uv run sextile serve my_service:app     # answer calls on port 6850
nc localhost 6850                       # and call it
uv run sextile render --demo            # a frame, in colour, without a Beeb
```

`stardot-viewdata` is the first such application, and the one all of this was
learned from. To run it, and to dial it from a real BBC Micro, see
[its README](packages/stardot-viewdata/README.md):

```sh
uv run stardot-viewdata ingest --once   # fetch something to look at
uv run stardot-viewdata serve           # answer calls
```

## Why the split

The service began as one program that was both of these things at once.
Separating them was worth doing on its own, but the shape to separate into was
settled by a second question: how to integrate properly with the phpBB board
behind Stardot, rather than reconstructing it from an Atom feed.

The decisive point is a lifecycle mismatch. phpBB answers a request and forgets
it. A Viewdata session lasts until the caller rings off, and because the terminal
holds nothing but the frame on screen, the server holds all of it. So phpBB
provides resources, and Sextile provides conversations with them — and neither
has to adopt the other's execution model.

[docs/target-architecture.md](docs/target-architecture.md) has the whole picture
and the invariants that keep it honest.

## Where things are written up

Each package is documented as built:

| | |
|---|---|
| [sextile](packages/sextile/docs/design.md) | the seam, addressing, routing, the session, the wire |
| [stardot-viewdata](packages/stardot-viewdata/docs/design.md) | the numbering, the archive, the polite ingest, phpBB's HTML |
| [calendar-viewdata](packages/calendar-viewdata/docs/design.md) | the second application, and what it was for |

[docs/architecture.md](docs/architecture.md) maps the whole workspace, and
[writing-an-application.md](packages/sextile/docs/writing-an-application.md) is
the framework's front door.

## What was measured rather than assumed

Much of the design rests on facts established by driving real Commstar under an
emulator rather than on documentation:

- Attributes must be escape-encoded as `ESC` + code + 0x40. The SAA5050's own
  0x80-0x9F codes do not survive Prestel's 7E1 line.
- A frame is exactly 24 rows of 40 cells. Column 40 wraps by itself, and the
  bottom-right cell wraps back to the top left rather than scrolling.
- `RETURN` transmits 0x5F, not 0x23, so a page request ends with 0x5F.
- Page numbers have no practical length limit.

The scripts that settled each are in [docs/spikes/](docs/spikes/), and what they
established is written up in
[viewdata-encoding.md](packages/sextile/docs/viewdata-encoding.md), which distinguishes what
was verified from what was inferred. **Keep that distinction** in anything new.

## Working on it

```sh
uv run pytest        # both packages
uv run ruff check .
uv run mypy
```

All three must pass; `mypy` is `--strict`, including the tests.

MIT licensed. Some material in this repository is not ours to license — see
[NOTICE.md](NOTICE.md).
