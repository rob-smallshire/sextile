# Font importers

A face is converted once in its life and the result is vendored, so these live
beside the framework rather than in it: `sextile` should carry no parser for a
format it reads once. They are held to the same `pytest`, `ruff` and `mypy` as
everything else.

```sh
uv run python tools/mdfs_font.py ~/fonts/ArcNormal Acorn \
    --from "MDFS ArcNormal (mdfs.net/Apps/Font/Fonts1.zip)" \
    --terms "Free for public use" > packages/sextile/src/sextile/viewdata/fonts/acorn.font

uv run python tools/more_fonts.py ~/more-fonts/fonts/BoldBash \
    > packages/sextile/src/sextile/viewdata/fonts/boldbash.font
```

| script | reads | metrics |
|---|---|---|
| `mdfs_font.py` | MDFS `VDU 23` sequences, ten bytes a glyph | derived: the ink is measured and the advance is the ink plus tracking |
| `more_fonts.py` | the Lua tables at `github.com/michielp1807/more-fonts` | in the file: `startX` and `lengthX` are the ink bounds |

Both trim each glyph to its ink, keep what they trimmed from the left as the
glyph's bearing, and convert only codes whose meaning is established — see the
scripts' own docstrings, which say what was measured and what was left out.

## Before vendoring a face

Read its licence. Three collections have been checked and **none was what a
summary of it said**: the "MIT fonts" at `github.com/michielp1807/more-fonts`
are MIT in their *source* only, each face carrying its own terms; two of them
state no licence at all; and the ZX Origins faces are offered "in exchange for
a mention in the credits", which is a permission and not a licence.

Then record it in three places, because each is read by someone different: the
converted file's own `terms:` line, the repository's [NOTICE.md](../NOTICE.md),
and — for an Open Font License face — the copyright block in
`packages/sextile/src/sextile/viewdata/fonts/OFL-1.1.txt`, which ships with the
faces because that licence requires a copy to travel with them.

**Converting a font is a Modified Version** under the OFL, which says so in as
many words: *"by changing formats"*. So a face whose licence reserves its name
gets a name of ours, with the original recorded in its `source:` line. There is
a test that no shipped face is called by a reserved name.

## Writing another importer

The target is `sextile.viewdata.font`: build a `Font` of `Glyph`s and hand it
to `write_font`. A glyph is a picture, an `advance` and a `bearing`; the face
carries a `height`, a `fixed` design width, a `source` and its `terms`. The
round trip through `read_font` is tested, so a converter that produces a `Font`
is a converter that produces a file.

What each importer has had to decide, and what a new one will:

- **the advance** — the ink plus tracking, unless the source gives one;
- **the width of a space**, which has no ink to measure and so cannot be
  derived;
- **which codes mean what their code point means** — every one of these formats
  holds glyphs above 127 in an encoding it does not state;
- **whether to drop rows blank in every glyph**, which costs rows of a
  twenty-four row screen. Blank in *every* glyph, never in each: trimming a
  glyph on its own stops the letters sitting on the same line.
