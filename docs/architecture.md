# How this is put together

Two kinds of thing live here: a framework, and services built on it.

```
packages/sextile/              the framework: connections, sessions, routing,
                               page numbering, frames on the wire
packages/stardot-viewdata/     the Stardot phpBB forum, as Viewdata
packages/calendar-viewdata/    a calendar; the framework's worked example
```

The framework depends on nothing at all; the applications depend on it and not
on each other. That is stated in the packaging rather than left as a convention,
so an import in the wrong direction fails at build time rather than being left
to convention.

Each is written up as built, and those are the documents to read:

The framework's own design is written up here — its choices in
{doc}`explanation/design-decisions`, its surface in
{doc}`reference/public-surface`, its layout in {doc}`reference/layout`, its wire
in {doc}`reference/viewdata-encoding`. Each in-tree application keeps its own
design note beside its code, at `packages/stardot-viewdata/docs/design.md` and
`packages/calendar-viewdata/docs/design.md`; the weather service keeps its own in
its repository.

{doc}`target-architecture` says where all this is going and why — the phpBB
extension, and the phases between here and it. {doc}`open-questions` lists what is
known to be missing and what is deliberately not done.

## The seams

Three boundaries do the load-bearing work. Each exists because something on one
side is expected to be replaced.

**`sextile/application.py` — `Sextile.respond`.** An application answers
`respond(request) -> Page | None`, and everything about connections, sessions,
protocol and routing is on the other side of it. The framework has no way to
reach into an application and no vocabulary for what one might be about.

**`stardot_viewdata/feed/source.py` — the `PostSource` port.** Everything above
it deals in `Post` and `Feed` and has never heard of Atom, phpBB or HTTP. The
Atom adapter is the first implementation; the phpBB Content Provider extension
is the intended second, and should arrive without disturbing the numbering, the
renderer or the session.

**`ForecastSource`, in the weather service — the same seam again.** It shows the
port is a shape rather than a coincidence: everything above it deals in `Forecast`
and `Moment` and has never heard of met.no, JSON or HTTP. The weather service now
lives in its own repository, depending on the framework as a published library.

**`sextile/visits.py` — the `Visits` port.** The third time the same shape has
been wanted, and the first time in the framework rather than an application: a
log of what has been read, with one SQLite implementation and a protocol narrow
enough to fake. The middleware that writes it and the pages that read it talk to
the protocol, so a service keeping its log elsewhere writes an adapter rather
than going without the pages.

**`sextile/server.py` — no transport knowledge.** A plain TCP server. tcpser is
already the ip232 endpoint an emulator connects to, so a service is dialled
exactly as any other viewdata board is and needs no ip232 code at all. Speaking
ip232 or a real serial port directly would be a new module beside this one, not
a change to it.

## Where to start reading

{doc}`explanation/rendering-pipeline` follows one document from its source to the
wire. To write a service of your own, the {doc}`tutorial/index` builds one step
by step and the {doc}`how-to/index` answers particular questions.

## What was measured rather than assumed

Much of the design rests on facts established by driving real Commstar under
Beebium rather than on documentation: attributes must travel escaped, a frame is
24 × 40 and wraps rather than scrolling, `RETURN` transmits 0x5F, page numbers
have no practical length limit.

The scripts that settled each question are indexed in {doc}`spikes/README`; they
need a local Beebium checkout and are not part of the test suite. What they
established is written up in {doc}`reference/viewdata-encoding`, which
distinguishes what was verified from what was inferred. Keep that distinction in
anything new.

## Testing

Unit tests throughout, written first. Each package's tests live with it, which
is the part that matters: the framework's suite cannot reach a forum fixture
even by accident, and it drives a made-up service rather than a real one so that
it cannot come to depend on what a real one happens to be about.

Test module names are unique across the workspace. Two members may both have a
`tests/` directory, but two modules called `test_store` may not, and `mypy`
says so rather than one shadowing the other.

Real data wherever the real data has a shape worth respecting, and limitations
recorded as tests so that a change at the board's end surfaces as a failure. See
each package's design document for the detail.
