# What the Atom feed cannot tell us

Sextile reads Stardot through phpBB's syndication feed. That is enough for a
great deal, but not for everything, and the gaps are worth naming because each
one is an argument for a different data source later — most plausibly a small
read-only phpBB extension.

Each limitation below is pinned by a test, so if the board's configuration ever
changes we find out from a failure rather than by chance.

## Fixed: code listings used to arrive without line breaks

phpBB's feed stripped every character below 0x20 from a post body, so listings
arrived as a single run-on line. Reported to the Stardot administrators, who
narrowed the sanitiser to the characters XML actually forbids. Listings now
arrive with their line breaks and tabs intact, and Sextile needed no change:
the parser split on newlines all along.

See [phpbb-feed-code-newlines.md](phpbb-feed-code-newlines.md) for the
investigation, kept because the method of finding it is worth remembering.

## Posts do not know their topic

A feed entry links only to `viewtopic.php?p=<post>`. There is no topic id
anywhere in the entry, and `robots.txt` forbids `/forums/viewtopic.php?p=`,
which is the page that would reveal it.

Per-topic feeds do exist and work — `app.php/feed/topic/<t>` returns a topic's
ten most recent posts — so thread browsing is possible for any topic whose id we
already know. We simply have no legitimate way to learn an id from the feed.

This is why the page numbering reserves `72<topic>` rather than using it.

## Mostly fixed: per-topic feeds and their forum

Board-wide and per-forum feeds carry a `<category>` naming the forum. Per-topic
feeds carry none, so a post first seen through one used to have no `forum_id`
at all.

Every entry now also has a `<link rel="up">` pointing at its forum, which fills
that gap. One rough edge remains: in a topic feed that link's `title` attribute
is empty, so the forum's *id* arrives but its *name* does not. The archive keeps
whichever name any post supplies, so a forum picks up its name as soon as it is
seen from another route.

## Smaller things

- The feed window is **ten posts** board-wide, fifteen for topic listings. At
  the observed rate of roughly four posts an hour that is about two and a half
  hours of cover, so a poller that stops for an afternoon misses posts
  permanently.
- Emphasis (`<strong>`, `<em>`) is present but rare, and Sextile discards it.
  Colour on forty columns is better spent distinguishing a quotation from a
  listing from the author's own words.
- Attachments are named but cannot be fetched: `robots.txt` disallows
  `/forums/download/file.php`, and a BBC Micro could do little with the file.
