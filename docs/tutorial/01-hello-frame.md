# A first frame

A tutorial step: a one-page service that answers `*1#` with a
[frame](../reference/glossary.md), run at the terminal and dialled into.

## Install Sextile

```sh
uv sync
```

This tutorial works inside the Sextile workspace, where `uv sync` installs
everything the steps need. For a project of your own, once Sextile is published,
`uv add sextile` (or `pip install sextile`) is the same thing.

## Write a one-page service

Put this in `my_calendar.py`. The frame below it is the one this code draws — it
is rendered from the code, so the two cannot disagree:

```{sextile-frame}
:page: "1"
:show-code:

from sextile import Page, PageRequest, Sextile, notice_page

app = Sextile(name="CALENDAR")

@app.page("1")
async def main(request: PageRequest) -> Page:
    return notice_page(request, "A calendar, served as Viewdata.")
```

`Sextile` is the service. `@app.page("1")` registers a handler at the page number
`*1#`, and a handler is an `async` function of the `PageRequest` that returns a
[`Page`](../reference/glossary.md). `notice_page` is the one-call shape for a page
that simply says something. The types are not decoration: this workspace is
checked with `mypy --strict`, and so is anything you write in it.

## Draw it at the terminal

```sh
uv run sextile render my_calendar:app --page 1
```

`render` fetches the page and draws one frame to the terminal, without answering a
call — the quickest way to see what a change did:

```text
 *1#                                  1a
  ████████████████████████████████████
A calendar, served as Viewdata.



















  ████████████████████████████████████
 0 index
```

The top row is the page number and which frame of it this is; the bottom is the
footer, naming the one key the page answers. `0` goes to the index, which is page
1 until you give the service another.

## Answer a call

```sh
uv run sextile serve my_calendar:app
```

In another terminal, dial in the way a Viewdata terminal would, over a modem:

```sh
nc localhost 6850
```

You arrive on `*1#`. Key `0` to go to the index — the same page, for now — and
`Ctrl-C` to hang up. Menus, where a digit chooses, come next.
```
