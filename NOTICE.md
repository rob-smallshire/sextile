# Third-party material

Sextile is MIT licensed (see [LICENSE](LICENSE)). Some material in this
repository is not ours to license, and is noted here.

## Forum posts used as test fixtures

`tests/data/board-feed.xml`, `forum-53-feed.xml` and `topic-28000-feed.xml` are
Atom documents captured verbatim from `stardot.org.uk`'s public syndication
feed. They contain **posts written by named members of that forum**, whose
words remain their own. They are included because the parsing, layout and
character-set work needed real input to be correct: several defects were found
only because these are genuine posts and not invented ones.

They are reproduced here for testing, in the quantity needed to test with, and
are **not covered by the MIT grant above**. Anyone redistributing this
repository should treat them as third-party content.

`tests/data/stardot-robots.txt` is likewise a copy of that site's robots.txt,
kept so that the rules Sextile obeys are tested against the real file rather
than a paraphrase.

Stardot's robots.txt carries `Content-Signal: search=yes, ai-train=no,
use=reference`. Sextile does not train anything.

## Spike scripts

The scripts in `docs/spikes/` drive the Beebium BBC Micro emulator, and their
navigation of Commstar follows the patterns in Beebium's own test suite.
Beebium is licensed GPL-3.0-or-later and is copyright Robert Smallshire, who is
also the author of Sextile and has licensed that material here under the MIT
terms above. No third-party GPL code is included.

## Quoted source

`docs/phpbb-feed-code-newlines.md` quotes two lines of phpBB
(GPL-2.0-or-later), for the purpose of identifying and reporting a defect.

## Conversation transcript

`docs/ChatGPT-phpBB-API-Integration.md` is an export of an early design
conversation, kept for the record. It contains quoted links and summaries of
third-party documentation.

## Dependencies

None are vendored. At the time of writing the runtime dependency tree is
`httpx`, `httpcore` and `idna` (BSD-3-Clause), `anyio`, `sniffio` and `h11`
(MIT), and `certifi` (MPL-2.0).
