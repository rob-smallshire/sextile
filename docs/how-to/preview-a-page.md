# Preview a page

A how-to guide: draw one frame of a service without ringing it up, at the
terminal or as a web page.

## At the terminal

```sh
uv run sextile render calendar_viewdata:app --page 3
```

`render` fetches the page and draws one frame of it to standard output, its keys
to standard error. `--page` is the number; `--frame` picks a later frame of a
page that runs to several (the first, `0`, by default). `--form` chooses how:

| `--form` | what it draws |
|---|---|
| `ansi` (default) | colour, as the Beeb would draw it, for a terminal |
| `grid` | the character and attribute layers, for a drawing fault |
| `bytes` | the wire stream, as a hex dump |
| `html` | a self-contained web page (below) |

## As a web page

```sh
uv run sextile render calendar_viewdata:app --page 3 --form html > month.html
```

`--form html` writes a whole page: the Bedstead font embedded, the stylesheet
inlined, and the frame. It opens from disk with no server, and names the page
number in its `<title>`. This is the same rendering the documentation uses, and a
page in its own right — for sending someone a frame to look at.

## In the documentation

A frame in a doc is drawn with the `sextile-frame` directive rather than pasted,
so it is the frame the code produces at build time. See {doc}`../contributing`
for its two forms.
