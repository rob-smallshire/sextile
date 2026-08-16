# Sextile

[![CI](https://github.com/rob-smallshire/sextile/actions/workflows/ci.yml/badge.svg)](https://github.com/rob-smallshire/sextile/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sextile.svg)](https://pypi.org/project/sextile/)
[![Python](https://img.shields.io/pypi/pyversions/sextile.svg)](https://pypi.org/project/sextile/)
[![Licence](https://img.shields.io/pypi/l/sextile.svg)](https://github.com/rob-smallshire/sextile/blob/master/LICENSE)
[![Docs](https://img.shields.io/badge/docs-github.io-blue)](https://rob-smallshire.github.io/sextile/)

A framework for Prestel-style Viewdata services in Python, and the services built
on it. Named after the star key on a viewdata keypad.

Viewdata was the interactive information service of the early 1980s: a terminal
dialled a computer over the telephone line, and the computer answered with pages
of text — twenty-four rows of forty characters in seven colours and block mosaics
— keyed by page number. The [documentation](docs/index.md) opens with the whole
of that story.

```
packages/sextile/              the framework: connections, sessions, routing,
                               page numbering, frames on the wire
packages/stardot-viewdata/     the Stardot phpBB forum, as Viewdata
packages/calendar-viewdata/    a calendar; the framework's worked example
packages/weather-viewdata/     the weather, from met.no and a local gazetteer
```

Sextile is to a Viewdata service what Flask or Starlette is to a web application.
It owns everything whose natural lifetime is the call, and an application says
what the pages are:

```sh
pip install sextile
```

```python
from sextile import Page, PageRequest, Sextile, notice_page

app = Sextile(name="My service")

@app.page("1", name="main", keywords=("MAIN",))
async def main(request: PageRequest) -> Page:
    return notice_page(request, "Hello, 1981.")
```

```sh
uv run sextile serve my_service:app                 # answer calls on port 6850
nc localhost 6850                                   # and call it
uv run sextile render my_service:app --page 1       # or draw a page without a Beeb
```

`render` draws a frame as the Beeb would (`--form ansi`), as its character and
attribute layers (`grid`), as the wire stream (`bytes`), or as a self-contained
web page with the font embedded (`--form html`).

## Documentation

Built with Sphinx from [`docs/`](docs/index.md), in five parts: a **tutorial**
that builds one service, **how-to** guides, a **reference** for the surface, the
glossary and the wire, an **explanation** of why it is shaped as it is, and the
three **applications** worked through.

```sh
uv run --group docs sphinx-build -n -W --keep-going -b html docs docs/_build/html
```

## Working on it

```sh
uv run pytest        # the whole workspace
uv run ruff check .
uv run mypy          # --strict, including the tests
```

All four — the three above and the docs build — must pass. MIT licensed; some
material in this repository is not ours to license, see [NOTICE.md](NOTICE.md).
