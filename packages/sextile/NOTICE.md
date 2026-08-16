# Third-party material

Sextile is MIT licensed (see [LICENSE](LICENSE)). The mosaic font faces and the
Bedstead font it ships are not ours to license, and are noted here. Each face
also carries its source and terms in its own header, and the conversion to this
project's format changes the format and nothing else about the design.

## Fonts

`sextile/viewdata/fonts/` holds bitmap faces converted into this project's own
format. None is covered by the MIT grant above.

### Free for public use

| face | from |
|---|---|
| `acorn` | MDFS ArcNormal (mdfs.net/Apps/Font/Fonts1.zip), by J.G.Harston |

### Public domain (Creative Commons Zero v1.0)

`3x3-mono` (GGBotNet), `boldbash` (Michiel), `lilliputsteps` (Raymond Larabie),
`pixeloperator` and its variants (Jayvee Enaguas / HarvettFox96), `pixelplace`
(Michiel), `publicpixel` (GGBotNet).

### SIL Open Font License, Version 1.1

The licence text and copyright notices are in `sextile/viewdata/fonts/OFL-1.1.txt`,
which ships with the faces because the licence requires it. Converting a font to
another format makes a Modified Version, which may not use a reserved font name,
so several carry a name of ours instead; the original is named in each file's
`source:` line, and the mapping is in the licence file.

`arcade` (QuinqueFive, GGBotNet), `console` and `console-bold` (Dogica, Roberto
Mocci), `garland` (Birch Leaf, solirides), `grotesque` and `grotesque-bold`
(Pixeloid Sans, GGBotNet), `roman` (Times9k, Sammy L. Koch), `scientifica` and
its variants (Akshay Oppiliappan), `silkscreen` and `silkscreen-bold` (Jason
Kottke).

The CC0 and Open Font faces come from `github.com/michielp1807/more-fonts`, whose
own MIT licence covers its source and not the faces it collects.

## Bedstead

`sextile/viewdata/static/bedstead.woff2` is Bedstead, the Mullard SAA5050
teletext character generator recreated as an OpenType font by bjh21 (Ben
Harris), which draws Viewdata frames as HTML — `sextile render --form html`
ships it. The program that generates Bedstead and its newly-designed glyphs are
released into the public domain (CC0-1.0); the original SAA5050 bitmap is stated
to be public domain in the United Kingdom under Section 55 of the Copyright,
Designs and Patents Act 1988. Vendored from `https://bjh21.me.uk/bedstead/bedstead.otf`
and converted to WOFF2 with fontTools; the design is unchanged.
