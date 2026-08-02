# What the Atom feed cannot tell us

Sextile reads Stardot through phpBB's syndication feed. That is enough for a
great deal, but not for everything, and the gaps are worth naming because each
one is an argument for a different data source later — most plausibly a small
read-only phpBB extension.

Each limitation below is pinned by a test, so if the board's configuration ever
changes we find out from a failure rather than by chance.

## Code listings arrive without line breaks

Every `<pre><code>` block in the captured feeds contains **zero newlines**. A
listing that was written as

```
;; Step 2: Test if that pre-existing rom image is SWMMFS
;; so we re-use the same slot again and again
        lda     &b5fe
        cmp     #MAGIC0
```

arrives as one run-on line, its original breaks recoverable only by eye, from
the `;;` comment markers. This is phpBB's feed generation, not our parsing: the
web page for the same post keeps its line breaks.

It is a defect rather than a design choice, and it is fixable. See
[phpbb-feed-code-newlines.md](phpbb-feed-code-newlines.md) for the evidence, the
cause and a one-line patch.

Sextile renders what it is given. Inventing line breaks — splitting before `;;`,
or on runs of spaces — would fabricate structure that might be wrong, and being
confidently wrong about someone's assembler is worse than being awkward.

On a board about 6502 programming this is the most costly limitation of the
three.

## Posts do not know their topic

A feed entry links only to `viewtopic.php?p=<post>`. There is no topic id
anywhere in the entry, and `robots.txt` forbids `/forums/viewtopic.php?p=`,
which is the page that would reveal it.

Per-topic feeds do exist and work — `app.php/feed/topic/<t>` returns a topic's
ten most recent posts — so thread browsing is possible for any topic whose id we
already know. We simply have no legitimate way to learn an id from the feed.

This is why the page numbering reserves `72<topic>` rather than using it.

## Per-topic feeds do not name their forum

Board-wide and per-forum feeds carry a `<category>` naming the forum. Per-topic
feeds carry none, and their entry titles are the bare subject with no forum name
prepended. So a post first seen through a topic feed has no `forum_id`.

## Smaller things

- The feed window is **ten posts** board-wide, fifteen for topic listings. At
  the observed rate of roughly four posts an hour that is about two and a half
  hours of cover, so a poller that stops for an afternoon misses posts
  permanently.
- Emphasis (`<strong>`, `<em>`) is present but rare — two occurrences in thirty
  posts — and Sextile discards it. Colour on forty columns is better spent
  distinguishing a quotation from a listing from the author's own words.
- Attachments are named but cannot be fetched: `robots.txt` disallows
  `/forums/download/file.php`, and a BBC Micro could do little with the file.
