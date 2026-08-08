# stardot-viewdata, as built

The Stardot forum as a Viewdata service. This is a Sextile application: it says
which page numbers exist, what each shows and where the keys lead, and it holds
the archive those pages are drawn from. Connections, sessions, frames, control
codes and routing all belong to [the framework](../../sextile/docs/design.md).

## The shape of the thing

```
   Stardot's Atom feed
        |  feed/   client, robots, atom, source, ingest    fetching, politely
        v
   model      Post, Feed                                   the domain
        |
        v
   store/     repository, schema.sql                       the archive
        |
        v
   html       phpBB's post HTML into blocks                a post's shape
        |
        v
   application  routes, handlers, menus, notices           what a page shows
        |
        v
   Sextile
```

`__main__.py` carries the commands that are this application's own: `ingest`,
`archive`, and defaulted `serve`/`render`.

Two things here are **provisional by design**. The Atom feed and the local
archive both exist because the board offered nothing better at the time; the
administrator has since proposed a phpBB extension, which would replace both.
See [target-architecture.md](../../../docs/target-architecture.md). The seams
that make that replaceable are `feed/source.py` and the fact that no page
handler touches HTTP.

## Numbering

The scheme is documented in full in [page-numbering.md](page-numbering.md). Its
two load-bearing properties:

**Every identifier is the board's own.** Post, forum, topic and contributor ids
come from Stardot. Nothing here allocates a number, so nothing can renumber, and
`*82489493#` on a BBC Micro is post 489493 on the web forum. A page number
written down in 2026 will still fetch that page.

**The first digit names a namespace, the second says what kind of page within
it**, so the scheme has room to grow without renumbering anything.

```
0     title frame                        9     about
1     service root                       91    how to get about
                                         92    where you have been
                                         93    every page
                                         94    words you can key
3     days index    32<YYYYMMDD>         90    logoff
4     forums index  42<forum>            <root>1   search, reserved throughout
5     contributors  52<user>             2, 6      reserved
7     topics        72<topic>
8     latest posts  82<post>
```

Three deliberate irregularities. A namespace's index is the bare root and never
`<root>0`, because accepting both would give one page two numbers. `9` is the
system namespace, where the second digit is a system function rather than a
content operation, so that `*90#` keeps its conventional Prestel meaning. And
page 0, the title frame, cannot be keyed at all — `*0#` is the back command — so
it displays no number and is reached only by the line opening.

There is no conventional number for a help page; viewdata's conventions are about
commands rather than about where a service files its own pages. `91` is this
scheme's choice. The keyword is the conventional part, and `*HELP#` reaches it.

Registered as framework routes, with the handler names that `address_for` uses,
so no page spells another's number:

```python
self.page("82{post_id:int}", name="post")(self._post)
self.address_for("post", post_id=post.post_id)
```

Seventeen keywords — `*MAIN#`, `*LATEST#`, `*HELP#`, `*BYE#` and the rest — are
aliases onto those same routes rather than onto literal numbers.

## The pages

| | |
|---|---|
| `0` | the title frame the line opens on; `#` carries on to the index |
| `1` | the index, with a count of what is held |
| `8`, `82<post>` | latest posts; one post, in as many frames as it takes |
| `7`, `72<topic>` | topics; a topic's posts, oldest first |
| `3`, `32<date>` | days held; a day's posts |
| `4`, `42<forum>` | forums; a forum's posts |
| `5`, `52<user>` | contributors; one contributor's posts |
| `9` | about the service |
| `91` | how to get about: the keys, in two frames. `*HELP#` |
| `92` | where you have been: the framework's page, mapped in here. `*HISTORY#` |
| `93` | every page and its number, built from the registrations. `*PAGES#` |
| `94` | every word you can key, built from the aliases. `*KEYWORDS#` |
| `90` | goodbye, which sets `hang_up` |

A post page offers its forum, its author, its day and its topic on `1`–`4`, and
the posts either side of it on the horizontal keys when the reader arrived
through a menu. Menus deal nine to a frame with a line of detail beneath each.

**Pages with nothing to show say why.** An empty menu with no explanation looks
like a fault, and on a service that answers slowly by design a reader cannot
tell the difference. A topic index with nothing in it explains that topic ids
are only known for posts seen since the board's feed began carrying them; a post
not held explains that the archive reaches back only a little way.

That is distinct from a page that does not exist, which returns `None` and lets
the session say so without moving the reader.

## The archive

SQLite, one `posts` table, five indexes. It exists because **the board-wide feed
is a window ten posts wide** which drains in about two and a half hours, so
without accumulation the service could offer only what Stardot happened to be
syndicating at that moment.

Two decisions are baked into the schema rather than repeated at call sites:

- **Instants are stored in UTC**, so ordering by text is ordering by time. A
  local offset would not sort across a daylight-saving boundary.
- **A post's London calendar date is computed once, on the way in.** Days are
  London days because that is where the board's readers are, and deriving that
  in SQL on every query would be both slow and obscure.

`first_seen` is preserved when a post is replaced, so an edit does not move a
post in any ordering that matters.

The repository is **deliberately synchronous**. The queries are small and
indexed, and wrapping SQLite in an async facade would buy nothing but
indirection. `StardotApplication` reaches it through `asyncio.to_thread`, which
keeps the blocking explicit and in one place — and means the connection is used
from whichever worker thread is picked, hence `check_same_thread=False` and a
lock around every statement.

## Fetching, politely

**Stardot asks for a 60-second crawl delay and forbids several paths.** Both are
enforced in `feed/`, and this is not optional.

`feed/robots.py` is hand-written because Python's `urllib.robotparser` returns
the *first* matching rule, so Stardot's `Allow: /` masks every `Disallow` below
it and it wrongly permits `viewtopic.php?p=` — which is exactly the page that
would reveal a post's topic id. RFC 9309 requires longest-match-wins, and that
is what is implemented.

`feed/source.py` is **the seam**. Everything above it deals in `Post` and `Feed`
and has never heard of Atom, phpBB or HTTP. The `PostSource` protocol offers
five routes because those are the five phpBB actually publishes: the board's
latest, the newest topics, the active topics, a forum's posts, a topic's posts.
Notably it cannot resolve a post to its topic, since the feed never says and
robots.txt forbids the page that would.

**Ingest** has two modes. Polling fetches the board feed every five minutes; the
number worth reporting is how many posts were *new*, because if that ever equals
how many were offered, the window drained between polls and something was
missed. Seeding sweeps every route — latest, newest topics, active topics, then
each forum it has just learned of, then each topic — which gathers far more in
one pass than a single windowful, and gathers it as threads rather than as a
scatter of unrelated replies. At 60 seconds a request that takes an hour or so.

Neither gives up on a failure. A board briefly unreachable, or a route this
board has not enabled, is ordinary; stopping would mean a restart every time
Stardot reboots.

## phpBB's HTML

`html.py`, built on the standard library's parser: a survey of thirty captured
posts found fourteen distinct tags, all from phpBB's own templates, so a
dependency would buy nothing.

The output is a `Document` of framework blocks — `Paragraph`, `Quote` (which
nests), `Code`, `ListItem`, `Image`, `Attachment` — **structural, not
typographic**. Emphasis is discarded: on forty columns colour is better spent
telling a quotation from a listing from the author's own words than rendering an
italic.

Three details are specific to this board:

- Every body ends with a `Statistics: Posted by …` paragraph, which is stripped
  — but only after `feed/atom.py` has mined it for the author's numeric id,
  which appears nowhere else.
- A quotation arrives as `<blockquote class="uncited"><div>`, and nests.
- A listing arrives inside `<div class="codebox">`, whose `Code: ` label is
  furniture rather than content.

Links keep their text in place and collect their target as a numbered reference
listed after the body. Two are deliberately not offered: the footer's author
link is phpBB's own plumbing, and attachment downloads are forbidden by
robots.txt and unusable on a Beeb anyway.

**Titles and author names need separate care.** phpBB marks them `type="html"`
and puts them inside CDATA, which the XML parser takes literally, so `&amp;`
arrives as five characters — unlike the body, which an HTML parser sees
afterwards. `feed/atom.py` unescapes them exactly once: a poster who typed
`&amp;` literally sends `&amp;amp;`, and going twice would silently rewrite what
they wrote.

## What the feed cannot tell us

Recorded as tests, so a change in the board's configuration surfaces as a
failure rather than going unnoticed. See [feed-limitations.md](feed-limitations.md).

Two such tests have already inverted — one asserting listings arrive without
line breaks, one asserting no post carries a topic id — the administrators
having fixed the feed. That is the mechanism working, and it is why the
limitations are tests rather than prose.

[phpbb-feed-code-newlines.md](phpbb-feed-code-newlines.md) is the defect report
written to be handed to them.

## Fixtures

`tests/data/` holds feeds and a `robots.txt` captured from the live board.
Prefer re-using them to making fresh requests.

Real data has repeatedly found things invented data would not: per-topic feeds
carrying no `<category>`, a post id recoverable from `<id>` when the link is
unusable, and phpBB stripping newlines from code listings.

One lesson about fixtures, learned three refetches in. A test asserting the
first post's author is `komadori` pins today's feed, not the parser. Concrete
values belong on `topic-28000-feed.xml`, a closed thread from 2023 that does not
move; tests over the board feed should assert *shape*.

## Known rough edges

- The archive path is relative to the working directory, so `serve` and `ingest`
  silently disagree if run from different places. This was the first thing that
  went wrong in practice.
- `FeedClient` spaces requests within one process, so a supervisor restarting
  the poller would bypass the crawl delay. The last-request time should be
  persisted. This matters as soon as anything but a person starts the poller.
- Subjects and menu items truncate mid-word.

The rest are in [open-questions.md](../../../docs/open-questions.md).
