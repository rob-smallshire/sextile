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

`packages/sextile/src/sextile/viewdata/fonts/acorn.font` is the Acorn 8x8 face
`ArcNormal`, from the font collection at `mdfs.net/Apps/Font/` maintained by
J.G.Harston, converted into this project's own format by
`tools/mdfs_font.py`. It is **free for public use**, and each file carries its
source and terms in its own header as well as here.

The fonts at `damieng.com/typography/zx-origins/` are deliberately **not**
included: they are offered for use "in exchange for a mention in the credits",
which is a permission rather than a licence. The importer for them, when there
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
