# Sextile

Viewdata — Prestel in Britain — was the interactive information service of the
early 1980s: a terminal dialled a computer over the telephone line, and the
computer answered with pages of text, twenty-four rows of forty characters in
seven colours and block mosaics, that the reader moved through by keying page
numbers. The BBC Micro and other home computers of the day spoke it.

Sextile builds such services today, in Python. It is to a Viewdata service what
Flask or Starlette is to a web application: it owns the connection, the session,
the page numbering and the frames on the wire, and you write what the pages say.

```python
from sextile import Page, PageRequest, Sextile, notice_page

app = Sextile(name="My service")

@app.page("1", name="main", keywords=("MAIN",))
async def main(request: PageRequest) -> Page:
    return notice_page(request, "Hello, 1981.")
```

Page 1, as a caller sees it — drawn from that code at build time, not a
screenshot:

```{sextile-frame}
from sextile import Sextile, notice_page

app = Sextile(name="My service")

@app.page("1")
async def main(request):
    return notice_page(request, "Hello, 1981.")

frame = fetch(app, "1")
```

The documentation is in five parts. The **tutorial** teaches the framework by
building one service; the **how-to** guides answer particular questions; the
**reference** states the surface, the glossary and the wire; the **explanation**
says why the framework is shaped as it is; and the **applications** are the three
services built on it, worked through. **Contributing** covers the gate and the
two invariants.

```{toctree}
:maxdepth: 2
:hidden:

tutorial/index
how-to/index
reference/index
explanation/index
applications/index
contributing
```
