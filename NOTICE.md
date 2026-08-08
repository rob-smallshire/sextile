# Third-party material

Sextile is MIT licensed (see [LICENSE](LICENSE)). Some material in this
repository is not ours to license, and is noted here.

## Forum posts used as test fixtures

In `packages/stardot-viewdata/tests/data/`, the files `board-feed.xml`,
`forum-53-feed.xml` and `topic-28000-feed.xml` are
Atom documents captured verbatim from `stardot.org.uk`'s public syndication
feed. They contain **posts written by named members of that forum**, whose
words remain their own. They are included because the parsing, layout and
character-set work needed real input to be correct: several defects were found
only because these are genuine posts and not invented ones.

They are reproduced here for testing, in the quantity needed to test with, and
are **not covered by the MIT grant above**. Anyone redistributing this
repository should treat them as third-party content.

`stardot-robots.txt` beside them is likewise a copy of that site's robots.txt,
kept so that the rules obeyed are tested against the real file rather than a
paraphrase.

Stardot's robots.txt carries `Content-Signal: search=yes, ai-train=no,
use=reference`. Sextile does not train anything.

## Fonts

`packages/sextile/src/sextile/viewdata/fonts/` holds bitmap faces converted
into this project's own format by the scripts in `tools/`. **None of them is
covered by the MIT grant above**; each carries its source and its terms in its
own header as well as here, and the conversion changes the format and nothing
else about the design.

### Free for public use

| face | blocks tall | from |
|---|---|---|
| `acorn` | 8 | MDFS ArcNormal (mdfs.net/Apps/Font/Fonts1.zip), by J.G.Harston |

From the font collection at `mdfs.net/Apps/Font/` maintained by J.G.Harston.

### Public domain (Creative Commons Zero v1.0)

| face | blocks tall | from |
|---|---|---|
| `3x3-mono` | 3 | 3x3 Mono Font by GGBotNet |
| `boldbash` | 9 | BoldBash by Michiel |
| `lilliputsteps` | 8 | Lilliput Steps by Raymond Larabie |
| `pixeloperator-bold` | 13 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixeloperator-hb` | 13 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixeloperator-sc-bold` | 13 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixeloperator-sc-hb` | 13 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixeloperator-sc` | 13 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixeloperator` | 13 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixeloperator8-bold` | 8 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixeloperator8-hb` | 8 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixeloperator8` | 8 | Pixel Operator by Jayvee Enaguas (HarvettFox96) |
| `pixelplace` | 6 | PixelPlace by Michiel |
| `publicpixel` | 7 | Public Pixel by GGBotNet |

### SIL Open Font License, Version 1.1

The licence text and the copyright notices are in
`packages/sextile/src/sextile/viewdata/fonts/OFL-1.1.txt`, which ships with the
faces because the licence requires it to. Converting a font to another format
makes a Modified Version, which may not use a reserved font name, so seven of
these carry a name of ours instead; the original is named in each file's
`source:` line, and the mapping is in that licence file.

| face | blocks tall | from |
|---|---|---|
| `arcade` | 5 | QuinqueFive by GGBotNet |
| `console-bold` | 8 | Dogica by Roberto Mocci |
| `console` | 8 | Dogica by Roberto Mocci |
| `garland` | 17 | Birch Leaf by solirides |
| `grotesque-bold` | 11 | Pixeloid Sans by GGBotNet |
| `grotesque` | 11 | Pixeloid Sans by GGBotNet |
| `roman` | 9 | Times9k by Sammy L. Koch |
| `scientifica-bold` | 10 | Scientifica by Akshay Oppiliappan |
| `scientifica-italic` | 10 | Scientifica by Akshay Oppiliappan |
| `scientifica` | 10 | Scientifica by Akshay Oppiliappan |
| `silkscreen-bold` | 9 | Silkscreen by Jason Kottke |
| `silkscreen` | 9 | Silkscreen by Jason Kottke |

The CC0 and Open Font faces above come from `github.com/michielp1807/more-fonts`,
whose own MIT licence covers its source and not the faces it collects. Two
fonts in that collection, `hdfont` and `hdfont-outline`, state no licence and
are **not** included.

The fonts at `damieng.com/typography/zx-origins/` are likewise **not**
included: they are offered for use "in exchange for a mention in the credits",
which is a permission rather than a licence. An importer for them, when there
is one, is for pointing at your own copy.

## Spike scripts

The scripts in `docs/spikes/` drive the Beebium BBC Micro emulator, and their
navigation of Commstar follows the patterns in Beebium's own test suite.
Beebium is licensed GPL-3.0-or-later and is copyright Robert Smallshire, who is
also the author of Sextile and has licensed that material here under the MIT
terms above. No third-party GPL code is included.

## Quoted source

`docs/phpbb-feed-code-newlines.md` quotes two lines of phpBB
(GPL-2.0-or-later), for the purpose of identifying and reporting a defect.

## Conversation transcripts

`docs/discussions/` holds exports of design conversations, kept for the record.
They contain quoted links and summaries of third-party documentation.

## Dependencies

None are vendored. At the time of writing the runtime dependency tree is
`httpx`, `httpcore` and `idna` (BSD-3-Clause), `anyio`, `sniffio` and `h11`
(MIT), and `certifi` (MPL-2.0).
