# Sextile

```{sextile-frame}
:page: "1"

from examples.hero import app
```

Viewdata or Videotex services, such as Prestel in Britain, were among the
earliest interactive services of the information age: a terminal dialled a
remote computer over a telephone line equipped with a modem, and the computer
answered with pages of text. The display was simple, twenty-four rows of forty
characters in seven colours with block mosaics, and the reader moved through the
pages by keying page numbers on a telephone keypad, a dedicated terminal or a
microcomputer. The BBC Micro and other home computers of the day ran software
that could dial and display such a service.

Sextile builds such services today, in Python. It is to a Viewdata service what
Flask or Starlette is to a web application: it manages the connection, the
caller's session, the page numbering and the frames of text and graphics. You
write what the pages say and how the reader interacts with them. Sextile is the
framework; the Viewdata services built on it are Sextile applications.

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
