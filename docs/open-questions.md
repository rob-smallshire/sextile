# Open questions and known gaps

Written down so they survive the session that found them. Nothing here is
blocking: the service works end to end.

## Needs a person, not a program

**Does an edited post change its `updated` timestamp?** Unknown, because it
needs someone to edit a post and a later poll to observe. The store handles
either answer — `add_post` replaces the content and preserves `first_seen` —
but if `updated` does not move, an edit will only be noticed while the post is
still inside the feed's ten-post window.

**Do the Stardot administrators want to fix the feed?**
[phpbb-feed-code-newlines.md](phpbb-feed-code-newlines.md) is written to be
handed over. It would make code listings legible, which on a board largely about
6502 assembler is the single biggest improvement available.

**Would they host a small read-only endpoint?** That is the seam
`feed/source.py` exists for. It would bring topic ids, and with them thread
browsing, which is the one obviously missing way to read a forum.

## Wanted, once a real screen has been watched

None of these can be judged from a test; they need someone reading Stardot on a
Beeb for half an hour.

- **Subjects and menu items truncate mid-word.** Wrapping to a second line or
  eliding would both cost rows. Which is better depends on how it reads.
- **Do the BBC's cursor keys reach us?** They transmit 0x88-0x8B, and at 7E1 the
  top bit is stripped, leaving 0x08-0x0B — precisely the viewdata cursor-control
  codes. If Commstar passes them through in Prestel chat mode rather than
  consuming them locally, arrows could work alongside WASD, and would be more
  authentic than either. Measurable with the existing spike harness.
- **Code listings now keep their line breaks**, since the board fixed its feed,
  but they are still not wrapped for forty columns. A listing indented to
  column eight has little room left.
- **A full frame is 960 cells, resent on every keypress.** At 1200 baud that is
  about eight seconds, which is authentic; at 9600 it is under a second.
  Differential update is possible but needs cursor positioning, which has not
  been measured, and nothing depends on it yet.
- **`sextile render --post` draws no chrome**, unlike `--page`. It predates the
  chrome and is now only useful for inspecting body layout in isolation.

## Wanted before it runs unattended

- **Pacing does not survive a restart.** `FeedClient` spaces requests within one
  process, so a supervisor restarting the poller would bypass the site's
  60-second crawl delay. The last-request time should be persisted in the
  archive. This matters as soon as anything but a human starts the poller.
- **The archive path is relative to the working directory.** `sextile.sqlite`
  by default, which means `serve` and `ingest` silently disagree if run from
  different directories — the first thing that went wrong in practice. A fixed
  location under `platformdirs` would be kinder.
- **No service file.** Running on a Raspberry Pi wants the poller and the server
  supervised, and a decision about whether they are one process or two. They are
  currently two, sharing only the SQLite file, which works and is simple.

## Deliberately not done

- **Emphasis is discarded.** `<strong>` and `<em>` occur twice in thirty posts,
  and on forty columns colour is better spent distinguishing a quotation from a
  listing from the author's own words.
- **Separated graphics render as contiguous** in the ANSI preview. Unicode has
  no separated variants and the difference is decorative.
- **Search is reserved but not built.** The numbering leaves `<root>1` free for
  it in every namespace.
- **Login and posting.** The whole design is read-only, and the feed offers no
  way to write. That would need the phpBB extension too.
