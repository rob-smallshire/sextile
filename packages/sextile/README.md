# Sextile

![Sextile](https://raw.githubusercontent.com/rob-smallshire/sextile/master/docs/images/sextile-hero.png)

[![CI](https://github.com/rob-smallshire/sextile/actions/workflows/ci.yml/badge.svg)](https://github.com/rob-smallshire/sextile/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/sextile.svg)](https://pypi.org/project/sextile/)
[![Python](https://img.shields.io/pypi/pyversions/sextile.svg)](https://pypi.org/project/sextile/)
[![Licence](https://img.shields.io/pypi/l/sextile.svg)](https://github.com/rob-smallshire/sextile/blob/master/LICENSE)
[![Docs](https://img.shields.io/badge/docs-github.io-blue)](https://rob-smallshire.github.io/sextile/)

A framework for Viewdata services, in Python. Sextile is to a Prestel-style
service what Flask or Starlette is to a web application: it owns the connection,
the session, the page numbering and the frames on the wire, and you write what
the pages say. The [documentation](https://rob-smallshire.github.io/sextile/)
opens with what Viewdata is.

```sh
uv add sextile          # or pip install sextile
```

```python
from sextile import Page, PageRequest, Sextile, notice_page

app = Sextile(name="My service")

@app.page("1", name="main", keywords=("MAIN",))
async def main(request: PageRequest) -> Page:
    return notice_page(request, "Hello, 1981.")
```

```sh
sextile serve my_service:app     # answer calls on port 6850
nc localhost 6850                # and call it
```

## What it gives you

**Routing by page number.** Patterns of literal digits and named fields, so
`82{post_id:int}` answers every page beginning 82 and hands the rest to the
handler already read as an integer. `app.address_for("post", post_id=...)` reads
the same pattern backwards, so a page linking to another does not respell the
numbering. Keywords — `*MAIN#` for `*1#` — are the route's `keywords=`.

**Sessions that last as long as the line.** A Viewdata terminal is a display and
nothing more: it holds the frame on screen and nothing else. So the server holds
where the reader is, what they have seen, and the menu they came through, and a
handler is a function of a request rather than of a number. The reasoning is in
[the explanation](https://rob-smallshire.github.io/sextile/explanation/why-sextile.html).

**The wire, measured rather than assumed.** Attributes travel as `ESC` + code +
0x40, a frame is 24 rows of 40 that wraps at the bottom-right back to the top
left, `RETURN` transmits 0x5F. Those were settled by driving real Commstar under
an emulator, and are written up in
[the encoding reference](https://rob-smallshire.github.io/sextile/reference/viewdata-encoding.html).

**Nobody is cut off without warning.** After half the idle timeout a silent
caller's footer becomes a bar that drains, reading `Press a key`. The first key
dismisses it and does nothing else, so it is safe to press whatever comes to
hand. Every service gets this without writing anything.

**Forty columns, accounted for.** A colour attribute occupies a character cell,
so a row that changes colour twice has thirty-eight columns for text. `Canvas`
does that arithmetic so nothing above it has to.

**Drawable without a Beeb.** `sextile render` draws any page four ways: `ansi`
colour as the Beeb would draw it, `grid` for the character and attribute layers,
`bytes` for the wire stream, and `html` for a self-contained web page with the
Bedstead font embedded, opening from disk with no server.

## Documentation

The full documentation is at
[rob-smallshire.github.io/sextile](https://rob-smallshire.github.io/sextile/):
[the tutorial](https://rob-smallshire.github.io/sextile/tutorial/index.html)
builds a service step by step, the
[how-to guides](https://rob-smallshire.github.io/sextile/how-to/index.html)
answer particular questions, the
[reference](https://rob-smallshire.github.io/sextile/reference/index.html) states
the surface, the glossary and the wire, and the
[explanation](https://rob-smallshire.github.io/sextile/explanation/index.html)
says why the framework is shaped as it is.

## Status

Young, and extracted from a working service rather than designed in the abstract.
Three applications use it in the
[source repository](https://github.com/rob-smallshire/sextile): a real Stardot
forum reader, a weather service, and a calendar written to be read.

MIT licensed. The bundled font faces and the Bedstead font are third-party
material; see
[NOTICE.md](https://github.com/rob-smallshire/sextile/blob/master/packages/sextile/NOTICE.md).
