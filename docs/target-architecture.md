# Where this is going

Sextile began as one program that was two things at once: a Viewdata application
server, and the Stardot service running on it. This document records the
architecture it is moving towards, and why. [architecture.md](architecture.md)
describes what exists today.

## Four layers

```
   phpBB                          the system of record: posts, users,
     |                            permissions, attachments
     |  forum-native services
     v
   Stardot Content Provider API   a phpBB extension exposing forum concepts
     |                            over HTTP/JSON, for any front end
     |  HTTP/JSON, localhost
     v
   stardot-viewdata               a Sextile application: the Stardot
     |                            information architecture in Viewdata
     |  Sextile application interfaces
     v
   Sextile                        the framework: connections, sessions,
     |                            routing, protocol, frames
     |  Viewdata over TCP
     v
   Viewdata clients               a stateless display terminal
```

## Why the boundaries fall there

**The lifecycle mismatch is the decisive argument.** phpBB is built around a
short-lived request: bootstrap, authenticate, query, render, end. A Viewdata
service is the opposite shape — a connection opens, and the session lasts until
the caller rings off, holding the current page, the navigation history, entered
input and eventually authentication. A Viewdata terminal is a dumb display
holding nothing but the frame on screen, so *the server holds all of it*, and the
TCP connection is the session's container.

Making phpBB own that lifetime would mean writing a long-running PHP daemon that
happens to bootstrap phpBB — which is Sextile rewritten in PHP, and the wrong
consequence of accepting closer integration. Splitting it the other way turns the
mismatch into an advantage: **phpBB provides resources; Sextile provides
conversations with those resources.** Each call into phpBB stays an ordinary
phpBB request, answered and forgotten, while Sextile keeps a caller connected for
three hours with no phpBB request open between calls.

**Content adaptation and presentation adaptation are different jobs.** The
extension converts phpBB internals into clean forum-domain resources.
`stardot-viewdata` converts forum-domain resources into a Viewdata application.
Keeping those in separate components is what makes each replaceable.

## Two invariants

These are the falsifiable form of the design. If either fails, a boundary has
moved and should be moved back.

1. **It must be possible to write another consumer of the Stardot Content
   Provider API that knows nothing about Viewdata.** So no page numbers, frame
   sizes, control codes, 40-column wrapping or keypad conventions may appear in
   that API. If they do, the boundary has drifted into PHP.

2. **It must be possible to write another Sextile application that knows nothing
   about phpBB or Stardot.** So no `bbcode_uid`, ACL tables, database schema or
   forum vocabulary may appear in the framework. If they do, the boundary has
   drifted into Python.

The second invariant is checkable today, and the calendar and weather
applications exist to keep checking it.

## Phases

**1. Framework extraction** — separate Sextile from `stardot-viewdata`, leaving
the application working exactly as it does now, against the SQLite archive and
the Atom ingest. Nothing here depends on anyone else. *This is the phase in
progress.*

**2. A phpBB to develop against** — stand up a local vanilla phpBB, which is
what Stardot is said to be, so the extension can be built and tested without
touching the live board.

**3. The Stardot Content Provider API** — the phpBB extension itself: a
`composer.json`, services registered in phpBB's DI container, a controller and
routes, and later event listeners for changes. Small, in the end: a few thin
adapter classes. The interesting work is deciding which phpBB abstraction to
retrieve posts through, and how much interpretation belongs on the PHP side.

**4. `stardot-viewdata` onto the API** — replace the Atom source and the SQLite
archive with the content provider. The page numbering and the rendering should
not need to change, which is the point of doing phase 1 first.

Two questions are deliberately left until they are reached: who owns the mapping
between Viewdata page numbers and phpBB topic ids, and what becomes of the local
archive once the board can be asked directly.

## Names

**Sextile** — the Viewdata application-server framework.
**stardot-viewdata** — the Sextile application implementing the Stardot service.
**Stardot Content Provider API** — the phpBB extension exposing the source
material. Named for its responsibility rather than its current consumer, because
a Viewdata service is only the first front end it could serve.

The reasoning is recorded at length in
[discussions/ChatGPT-phpBB-extension-integration.md](discussions/ChatGPT-phpBB-extension-integration.md),
with a sketch of the same picture beside it.
