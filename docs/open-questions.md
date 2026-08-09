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
[phpbb-feed-code-newlines.md](../packages/stardot-viewdata/docs/phpbb-feed-code-newlines.md) is written to be
handed over. It would make code listings legible, which on a board largely about
6502 assembler is the single biggest improvement available.

**Would they host a small read-only endpoint?** They would: the administrator
has proposed a phpBB extension, which is better than the endpoint we were going
to ask for. See [target-architecture.md](target-architecture.md) for the shape
of it and the phases between here and there.

## Wanted, once a real screen has been watched

None of these can be judged from a test; they need someone reading Stardot on a
Beeb for half an hour.

- **Subjects and menu items truncate mid-word.** Wrapping to a second line or
  eliding would both cost rows. Which is better depends on how it reads.
- **Code listings now keep their line breaks**, since the board fixed its feed,
  but they are still not wrapped for forty columns. A listing indented to
  column eight has little room left.
- **Differential update** — sending only the cells that changed since the last
  frame. Trailing blanks are already trimmed, which takes a third to three
  quarters off; this would take most of the rest on a menu where only the middle
  rows differ. The cursor positioning it needs has now been measured and works;
  see `viewdata-encoding.md`.
- **`render --post` is gone.** It drew a post's body with no chrome, which was
  useful for inspecting layout in isolation, and it did not survive the split
  because it was a page-drawing command that bypassed pages. `lay_out` still
  does the same thing from a test.

## Wanted before it runs unattended

- **Pacing does not survive a restart.** `FeedClient` spaces requests within one
  process, so a supervisor restarting the poller would bypass the site's
  60-second crawl delay. The last-request time should be persisted in the
  archive. This matters as soon as anything but a human starts the poller.
- **The archive path is relative to the working directory.** `stardot.sqlite`
  by default, which means `stardot-viewdata serve` and `ingest` silently
  disagree if run from different directories — the first thing that went wrong in practice. A fixed
  location under `platformdirs` would be kinder.
- **No service file.** Running on a Raspberry Pi wants the poller and the server
  supervised, and a decision about whether they are one process or two. They are
  currently two, sharing only the SQLite file, which works and is simple.

## Raised by the framework extraction

- **Both applications write their own menu builder**, and the two are much
  alike: nine choices to a frame, a line of detail beneath each, the way back on
  0. That is a viewdata convention rather than either service's, so it belongs
  in the framework — but with two examples the shared shape is a guess, and with
  three it would be evidence.
- **Mounting is untested against a real second application.** `mount` gives the
  mounted application the whole address rather than stripping a prefix, because
  the application draws the page number into the frame itself. That is right,
  but nothing yet runs two applications behind one number space.
- **`sextile.viewdata` is a large surface for an application to reach into.**
  Chrome, canvas, colours, layout and the frame itself are all public, and an
  application needs most of them. Whether some of it should be a smaller,
  friendlier facade is a question for when there are more services.

## Raised by the weather service

- **GeoNames' alternate names carry no tag saying what they are.** The main
  dump's `alternatenames` column mixes genuine names with IATA airport codes
  and with romanised transliterations, and `weather-viewdata` tells them apart
  by capitalisation — measured against the real `cities500`, not documented
  anywhere. It works: `TRO` gives Tromsø rather than Taree, whose airport code
  it is. But it is a rule of thumb, and `alternateNamesV2` carries a proper
  language tag at a further 193M if it ever misleads.
- **A few nicknames still surface.** `PARIS` offers Warsaw second and `NEWYORK`
  offers Jakarta, both through multi-word alternates the places genuinely go
  by. Harmless in the second and third rows; it would matter if it reached the
  first.
- **Whose weather the service is about is a setting, not a fact.** `--prefer NO`
  weights Norwegian places, without which `BER` gives Berlin before Bergen.
  Which is right depends on who is dialling, and nobody has yet dialled.

## Next, and specified

- **Mosaic fonts** — large lettering drawn out of block graphics, for banners
  and title frames. The layer beneath it is built; the requirements, the source
  formats and the measurements are written up in
  [mosaic-fonts.md](../packages/sextile/docs/mosaic-fonts.md).

## Deliberately not done

- **Emphasis is discarded.** `<strong>` and `<em>` occur twice in thirty posts,
  and on forty columns colour is better spent distinguishing a quotation from a
  listing from the author's own words.
- **Separated graphics render as contiguous** in the ANSI preview. Unicode has
  no separated variants and the difference is decorative.
- **Double height renders as two identical rows** in the ANSI preview, which is
  what the frame actually holds and not what the screen shows. `--form grid` is
  the honest view; a terminal has no way to draw one line at twice the height.
- **Search is reserved but not built.** The numbering leaves `<root>1` free for
  it in every namespace.
- **Login and posting.** The whole design is read-only, and the feed offers no
  way to write. That would need the phpBB extension too.
