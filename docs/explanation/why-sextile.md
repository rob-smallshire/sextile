# Why Sextile

Explanation: why a framework for Viewdata takes the shape it does. The argument is
one lifecycle fact and its consequences, stated once here; the rest of the design
follows from it.

## The terminal holds only the screen

A Viewdata terminal is a display and nothing more. It holds the frame on screen
and not the page it came from, the menu that led there, or who is connected. All
of that is held at the server, for as long as the line is up. This is the reverse
of the web, where the client carries a cookie and the server may forget between
requests.

## A request comes from a session

Three shapes follow, and they are where the framework departs from a web
framework:

- **The connection is the session.** There is no session store, identifier or
  expiry: `PageRequest.session` is a writable `State`, keyed by `StateKey`, that
  lives exactly as long as the socket and is gone when the caller rings off.
  Keeping something for one caller across their pages is
  {doc}`../how-to/remember-a-caller`.
- **A handler is a function of a request, not of a page number.** Two callers
  keying the same number may be shown different things — the menu they arrived
  through, and later who they are — so a `PageRequest` carries the address, the
  `Neighbours` either side, the history and the session, and the handler reads
  what it needs.
- **Everything is async.** Not for scale — a board serves a handful of callers —
  but because a handler that goes to a database or an HTTP service would
  otherwise stop every other caller while it waited.

## A page is built when reached, and kept

Because the session holds the page the reader is on, redrawing it costs nothing
sent to a handler: `*00#` (`REDISPLAY`) re-sends the frame already in hand, while
`*09#` (`REFRESH`) rebuilds the page from its handler. They are two keys because
the difference is real — one is a repaint, the other a rebuild. The measured wire
economy that makes a repaint cheap is in {doc}`../reference/viewdata-encoding`.

## Resources, and conversations with them

The same lifecycle fact settles the larger boundaries. A phpBB request
bootstraps, queries, renders and ends; a Viewdata session lasts until the caller
rings off, holding the current page, the history and any typing. Making phpBB own
that lifetime would be Sextile rewritten as a long-running PHP daemon. Split the
other way, the mismatch becomes an advantage: phpBB provides resources, Sextile
provides conversations with them, and each call into phpBB stays an ordinary
request, answered and forgotten. {doc}`../reference/public-surface` states the
seam the split is enforced across.
