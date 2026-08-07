# Test fixtures

Captured verbatim from the live board, because the parsing and layout work
needed real input to be correct. Several things were found only because these
are genuine posts rather than invented ones:

- per-topic feeds carry no `<category>`, so a post read from one does not know
  its forum;
- a post id can be recovered from `<id>` when the link is unusable;
- phpBB's feed strips the newlines from code listings.

| File | Source |
|---|---|
| `board-feed.xml` | `app.php/feed` |
| `forum-53-feed.xml` | `app.php/feed/forum/53` |
| `topic-28000-feed.xml` | `app.php/feed/topic/28000` |
| `stardot-robots.txt` | `/robots.txt` |

The feeds contain posts written by members of stardot.org.uk. Those words are
their authors' own and are **not covered by this project's MIT licence**. See
[NOTICE.md](../../NOTICE.md).

Prefer re-using these to making fresh requests: the site asks for sixty seconds
between them.
