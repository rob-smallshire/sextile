# The forum

A worked example: the Stardot BBC Micro forum, served as Viewdata. It is the
service the framework was extracted from, so its numbering, its archive, its
polite crawl and its reading of phpBB's HTML are its own; the framework holds
only the connection, the session and the wire.

## The numbering

Every identifier in it is the board's own — a post, forum, topic or contributor
id — so a page number means the same thing on the web forum as on a BBC Micro:

```{literalinclude} ../../packages/stardot-viewdata/docs/page-numbering.md
:language: text
:lines: 6-18
```

## Running it

```sh
uv run stardot-viewdata ingest --seed    # fill the archive first (about an hour)
uv run stardot-viewdata serve            # then answer calls on port 16650
uv run stardot-viewdata render --page 8  # or just draw a page
```

## The latest posts

The service takes an open archive, so a handful of posts held in memory draws a
real page offline:

```{sextile-frame}
:page: "8"
:show-code:

from datetime import datetime, timedelta, timezone

from stardot_viewdata import build_application
from stardot_viewdata.model import Post
from stardot_viewdata.store.repository import Repository

BST = timezone(timedelta(hours=1))
archive = Repository.in_memory()
for offset in range(6):
    archive.add_post(
        Post(
            post_id=489000 + offset,
            forum_id=53,
            forum_name="new projects in development: games",
            topic_id=33387,
            author_id=10058,
            author_name="Iapetus",
            subject=f"Re: Head over Heels, part {offset + 1}",
            published=datetime(2026, 8, 2, 9, 0, tzinfo=BST) + timedelta(minutes=offset),
            updated=datetime(2026, 8, 2, 9, 0, tzinfo=BST) + timedelta(minutes=offset),
            url=f"https://stardot.org.uk/forums/viewtopic.php?p={489000 + offset}",
            content_html="<p>What a great project!</p>",
        )
    )

app = build_application(repository=archive)
```

Everything above the session deals in `Post` and `Feed` and has never heard of
phpBB or HTTP: the Atom adapter is the first `PostSource`, and the board
administrator's phpBB extension is the intended second, arriving without
disturbing the numbering, the renderer or the session. The full design is in the
package's own `docs/design.md`.
