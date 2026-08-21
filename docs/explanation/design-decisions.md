# Design decisions

Explanation: the load-bearing choices, each with the alternative it was made
against. One entry a decision, grouped by subject. Where a decision rests on a
wire measurement, the basis is in {doc}`../reference/viewdata-encoding` rather
than restated here.

## Addressing

### Page addresses are strings

Decision: `PageAddress` wraps a validated non-empty ASCII digit string, and is
the framework's only notion of what a page is called.
Because: the page number is the one name everyone shares — the reader keying it,
the terminal displaying it, the service answering it, and a note on paper.
Rejected: being generic over an application-supplied reference type, as the
original code was; a string makes history, the back key and cross-service links
ordinary operations on a value that carries nothing about what it names.

### A frame letter is not part of an address

Decision: the `b` in `82489493b` names a continuation frame and is not part of a
`PageAddress`.
Because: it appears only on screen, and a reader never keys it.
Rejected: folding the letter into the address; it would carry something no
request ever names.

## Routing

### Patterns, not a table of numbers

Decision: a route is a pattern of literal digits and named fields compiled to an
anchored regex, `82{post_id:int}`.
Because: a page number's fields are the service's own identifiers, and a service
has as many pages as it has posts.
Rejected: a dictionary of numbers; it cannot hold a page per post, and cannot be
read backwards by `address_for` to keep the numbering in one place.

### Distinct, not prefix-free

Decision: page numbers need only be distinct, so fields may vary in width and
stay short.
Because: a viewdata request is terminated — `*8#` and `*82489493#` are
unambiguously different — because the reader presses a terminator.
Rejected: requiring prefix-free numbers as a URL router must; the terminator
removes the ambiguity a URL has no way to.

### Most literal wins

Decision: candidates are tried by how many characters of the pattern are fixed
digits, most first, so `90` beats `9{n:int}`.
Because: a table whose meaning changed when someone reordered it would be no use.
Rejected: matching in registration order; the meaning would then shift whenever
someone tidied the list.

### Fields must be separable

Decision: all but the last of adjacent fields must have a width known in advance,
and two bare `int` fields adjacent are refused at registration.
Because: a page number has no separators, so adjacent fields can be told apart
only by a fixed width.
Rejected: matching adjacent variable-width fields; the split is unrecoverable at
match time, so it is refused when the route is declared instead.

## The session

### A missing page returns None

Decision: `respond` returns `None` for a page that is not there, rather than a
notice.
Because: a page that exists is somewhere the reader has gone and enters the
history; a page that does not is something said to a reader who has not moved.
Rejected: returning a notice page; it blurs "gone somewhere" into "told
something", which the session must tell apart.

### A raised handler costs its page, not the call

Decision: the session catches a handler's exception, logs it with its traceback,
and shows `Sextile.failed` without moving the reader.
Because: a session is a telephone call, and ending it over the service's own
fault means dialling back in over minutes of a slow line.
Rejected: letting the exception end the session; the fault was the service's, not
the reader's.

### Failed is not not-found

Decision: `Sextile.failed` is a page of its own, distinct from the not-found
notice.
Because: one says the reader asked for something not here, the other that the
service could not build something that is.
Rejected: reusing the not-found notice; it sends the reader away thinking they
mistyped and hides the fault from whoever could fix it.

### The board has a finite number of lines

Decision: `serve` caps live callers at `max_connections` (64 by default) and
turns a caller over the ceiling away with the application's busy frame — an
`on_busy` hook, like the not-found and timeout notices — rather than holding the
line.
Because: nothing else stops one caller opening connections without limit and
locking everyone out; the idle timeout releases a silent caller, not one who
keeps a line active.
Rejected: an unbounded server, or a silent TCP refusal; the first is a denial of
service anyone can mount, the second leaves a caller at a dead line rather than a
busy signal they can read.

## Pages and frames

### A page is a type, with choices per frame

Decision: a handler returns a `Page` of `PageFrame`s, each carrying its own
`choices`, not bare frames.
Because: frame b of a listing offers a different nine destinations from frame a,
and the session consults the showing frame and nothing else.
Rejected: bare frames with the choices on the page; the choices differ frame to
frame, so they belong to the frame.

### Choices are kept apart from moves

Decision: a `PageFrame` keeps `choices` and `moves` as two mappings.
Because: a move names no destination — it steps between frames of the page
already showing.
Rejected: putting frame movement among the choices; a menu then appeared to
offer eleven, which two existing tests caught at once.

### A service is a list of routes

Decision: a service is `Sextile(pages=[...])`, given as data.
Because: it makes registration order unobservable, which was the root of four
separate defects.
Rejected: registering pages imperatively through decorators and constructor
order; each defect was that order showing through.

### Listing words are stated once

Decision: a page's title, detail, label and keywords sit on its `PageRoute`, and
a page given no title is not advertised.
Because: a service naming each page in its menu, again where listed, and again in
its guide keeps three copies that drift.
Rejected: naming a page separately in each place it appears; the copies go out of
step, as an earlier service's did.

## Layout

### Furniture is separate from parts

Decision: `PageLayout` splits a page into furniture round the edge and a list of
parts down the middle.
Because: the earlier shape coupled the furniture to being a homogeneous sequence,
so a grid, form or masthead had to draw its own.
Rejected: the coupled template; six pages had come to redraw furniture by hand.

### A frame break divides at a chosen point

Decision: `FrameBreak` divides a page where the author places it, not where the
rows run out.
Because: two frames may be two lists split by what a reader is doing.
Rejected: breaking only when rows fill; it cannot divide a page at a meaningful
point.

### Custom for what is not a sequence

Decision: `Custom(rows, draw)` is a part of stated height drawn cell by cell.
Because: a picture, grid or masthead is not a homogeneous sequence.
Rejected: forcing all content through a sequence part; it is the wrong shape for
a placed drawing.

## Navigation

### The parser does not translate the cursor keys

Decision: the parser reports which key was pressed; `keys.ARROW_FOR` and
`with_arrows` offer the letter each arrow stands for and a page decides.
Because: translating arrows to WASD in the parser makes a fact about the hardware
into an opinion imposed on every service.
Rejected: turning arrows into WASD before any page sees them; on a coordinate
form `W` is West, and the up arrow would silently type a letter into a number.

### The prompt is composed and shed by priority

Decision: the footer is prioritised `FooterItem`s, and `render_footer` sheds
words in a fixed order, keeping the way home last.
Because: what gives should be what a reader can least afford to lose, not what
happens to sit at the end of a string.
Rejected: one prompt string sized for the busiest page; there was no setting
between the sentence and the letter, so it wasted room on roomy pages.

## Drawing

### The drawing operations are free functions

Decision: `fitted`, `centred`, `rule` and `bar` take a canvas and a row, and are
functions rather than methods.
Because: a service can write its own beside them and reach for either without
minding which is which.
Rejected: methods on a canvas or page; a service could not then place its own
operations on equal footing.

### A frame is a fixed grid

Decision: `Frame` is a fixed 24 × 40 grid, not a stream of writes.
Because: Commstar wraps from the bottom-right cell back to the top-left instead
of scrolling ({doc}`../reference/viewdata-encoding`), so a serialiser one cell
over would overwrite the frame it just drew.
Rejected: a stream of writes; one cell too many corrupts the frame.

### Colour was built in from the start

Decision: `Canvas` accounts for a colour attribute occupying a character cell, so
no layer above it counts columns.
Because: a colour attribute costs one of the forty columns
({doc}`../reference/viewdata-encoding`), and deferring colour would have forced
the typesetting to be rewritten around it.
Rejected: adding colour later; the cell arithmetic reaches every layer that
places text.

## Forms

### A form is a menu whose choices change

Decision: a form is built on `PageFrame.choices`; type-ahead is a menu whose
numbered choices change as the reader types.
Because: `choices` already means what the digits do on a frame, so history,
sequences and the back key keep working with nothing added.
Rejected: Prestel's response frames bolted on beside the numbering; a form needs
little once choices mean what the digits do.

### Three suggestions, not nine

Decision: `TypeAhead` offers three matches beneath the field.
Because: nine rows would cost nearly three seconds a keystroke at 1200 baud where
a reader types two characters a second; three costs about one
({doc}`../reference/viewdata-encoding`).
Rejected: a full menu of nine; the wire cannot keep up with the typing.

### Digits choose, letters type

Decision: a digit always selects a suggestion and a letter always types; an entry
whose text holds a digit is found by the letters around it.
Because: a digit is data or it is a choice, never both, and the session consults
`choices` first.
Rejected: typing digits into the field; a digit that led nowhere would do nothing
the reader could see.

## Middleware and the visits log

### record_visits takes the key, not the log

Decision: `record_visits(VISITS)` is handed the `StateKey` the log sits under and
reads `request.state` per page.
Because: the middleware is built before the service's lifespan has opened
anything.
Rejected: handing it the log object; the log does not exist when the middleware
is constructed.

### The log is a file of its own

Decision: `SqliteVisits` keeps its own file, and trims once a day rather than
once a page.
Because: a service's own database is often derived and rebuilt, whereas the log
is the only copy of what it holds.
Rejected: a table in the service's database trimmed on every fetch; a rebuild
would lose the log, and a per-fetch delete is a write nobody asked for.

## The public surface

### The surface is a stated set of submodules

Decision: the public surface is a list of submodules with stated names; anything
unlisted is machinery, pinned by `test_public_surface.py`.
Because: an unlisted module may be renamed, split or deleted without notice, and
what must not drift is pinned by a test rather than a rule someone remembers.
Rejected: one flat namespace; the framework is large enough that a single top
level says nothing about what belongs with what.

### Uncalled is not a reason to delete

Decision: framework surface goes only when it duplicates another implementation,
never because nothing in the repository calls it.
Because: the surface is justified by being useful to a service — a fourth service
wants `read_bitmap` and `boxed` — not by the three that share the repo.
Rejected: deleting uncalled surface code; a since-removed furniture module went
because two implementations of one thing diverge, which is a different reason.

## Packaging

### Click, not argparse, for the command line

Decision: the command line is built on `click`, the framework's second
dependency, and a service extends it by adding the framework's `render` and
`serve` commands to its own `click.Group`.
Because: a service's command line is the framework's two commands plus its own,
and Click composes groups and commands as values a service adds to, where
argparse subparsers are assembled by mutating a parser through a `configure`
callback run against each; argparse also expands a help string as a printf
template, so a formatted percent sign in one crashed `serve --help` (issue #1).
Rejected: staying on the standard library's argparse; it held the dependency
count at one, but the service-extension seam and the help-string trap cost more
than a second, small, widely-used dependency does.

### No mounting

Decision: a service is one flat namespace; sub-application mounting was removed.
Because: it had no user, and it obliged routing, keywords, contents, state and
history to see through the seam for a scalability no service needs.
Rejected: web-framework mounting on a number prefix; the prefix cannot be
stripped — a drawn page number must be keyable back — which forces a
merged-and-disjoint numbering and pervasive accounting.

### Lifespan is one context manager

Decision: a service opens its resources in one async context manager, writing
them into `app.state` under `StateKey` keys.
Because: two halves of one function cannot drift, and the resource is an ordinary
local held across the `yield`.
Rejected: separate startup and shutdown handlers; they must be kept in step by
hand and must stash what they open where both reach it.

### Deployed services live in their own repository

Decision: a deployed service lives in its own repository and depends on the
published `sextile`; the in-tree applications keep the framework honest.
Because: one workspace has one lockfile, and a library must not commit one while
a deployment must — and a service on its own is exercised as a consumer would be.
Rejected: keeping the service in-tree with an ignored lock, or committing the
lock and pinning the library to it.
