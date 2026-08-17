# Examples

Runnable single-file services built on Sextile.

## `hero.py` — the title frame

Sextile's own title frame: a large mosaic sextile glyph, the name in outsized
lettering, and a strapline, all drawn from block graphics and the shipped fonts —
so it renders the same on a BBC Micro as in the browser. It is the picture at the
top of the READMEs.

```sh
uv run sextile render examples.hero:app --page 1                # draw it to a terminal
uv run sextile render examples.hero:app --page 1 --form html    # a self-contained web page
uv run sextile serve examples.hero:app                          # or serve it and dial in
```

### Capturing it on a real Beeb

The picture in the READMEs is a browser render of this frame. To photograph it on
a real BBC Micro teletext chip instead — the same page, drawn by the hardware —
serve the hero and bridge it to an emulated modem, then dial in from Commstar and
photograph the screen. The whole procedure is in the how-to guide
[Connect a BBC Micro](../docs/how-to/connect-a-bbc.md); `capture-hero.sh` does the
serving and bridging for you:

```sh
examples/capture-hero.sh
```

It serves the hero on port 16650 with the line held open (so the frame stays up
for the photo) and starts `tcpser`, then prints the emulator and Commstar steps.
Photograph the emulator window, crop to the screen, and save it as
`docs/images/sextile-hero.png` — the READMEs already point at that path.

The emulator's capture API reads the screen back as character cells, not pixels,
so the PNG is a photograph of the rendered display rather than something this
repository can generate headlessly.
