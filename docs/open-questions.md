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
`packages/stardot-viewdata/docs/phpbb-feed-code-newlines.md` is written to be
handed over. It would make code listings legible, which on a board largely about
6502 assembler is the single biggest improvement available.

**Would they host a small read-only endpoint?** They would: the administrator
has proposed a phpBB extension, which is better than the endpoint we were going
to ask for. See {doc}`target-architecture` for the shape
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
- **`render --post` is gone.** It drew a post's body with no furniture, which
  was useful for inspecting layout in isolation, and it did not survive the
  split because it was a page-drawing command that bypassed pages.

## Wanted before it runs unattended

- **The place index is derived data whose rules live in code**, so changing
  them does nothing until somebody re-imports. It now records which rules built
  it and the service refuses to start on a stale one, saying what to run —
  because the failure mode is not a crash but a wrong answer given confidently.
  Raise `store.RULES` whenever the folding or the ranking changes; nothing
  checks that you remembered.

- **Pacing does not survive a restart.** `FeedClient` spaces requests within one
  process, so a supervisor restarting the poller would bypass the site's
  60-second crawl delay. The last-request time should be persisted in the
  archive. This matters as soon as anything but a human starts the poller.
- **The archive path is relative to the working directory.** `stardot.sqlite`
  by default, which means `stardot-viewdata serve` and `ingest` silently
  disagree if run from different directories. A fixed location under
  `platformdirs` would be kinder.
- **No service file.** Running on a Raspberry Pi wants the poller and the server
  supervised, and a decision about whether they are one process or two. They are
  currently two, sharing only the SQLite file, which works and is simple.

## Raised by the framework extraction

- **Mounting is gone.** It let one application answer a prefix of another's
  numbering, and no service ever used it. Removing it took with it everything
  the rest of the framework had to know about the seam. Written up in
  {doc}`explanation/design-decisions`; if a service ever genuinely needs to be
  assembled from parts, that is the place to start reading and the reasons will
  still be there.
- **`sextile.viewdata` is a large surface for an application to reach into.**
  Canvas, colours, drawing, composition and the frame itself are all public, and
  an application needs most of them. Whether some of it should be a smaller,
  friendlier facade is a question for when there are more services.

## Raised by the weather service

- **Alternate names are not indexed, and one thing is lost with them.** The
  main dump's `alternatenames` column mixes genuine names with IATA airport
  codes, romanisations from other scripts and outright data errors, and carries
  no tag saying which is which. Three rounds of filtering made it less wrong
  without making it right — keying `A` still offered Oslo, one of whose
  alternates is `Asloa` — so what a reader types is now honoured as a prefix of
  the place's own name and nothing else.

  What that costs is smaller than it sounds, because GeoNames' own `name` is
  already the name an English reader knows: Munich, Vienna, Prague, Rome,
  Moscow, Tokyo and Beijing are all filed under exactly those. Köln is the
  exception — `COLOGNE` finds nothing — and `MUNCHEN` now finds Münchenstein
  rather than Munich, since Munich is not spelled that way in the dump.

  Doing it properly needs `alternateNamesV2`, whose entries say which language
  they are in: index the English and local-language ones and neither problem
  arises. A further 193M, and the obvious next step if anybody misses Cologne.
- **Whose weather the service is about is a setting, not a fact.** `--prefer NO`
  weights Norwegian places, without which `BER` gives Berlin before Bergen.
  Which is right depends on who is dialling, and nobody has yet dialled.
- **Nine is the ceiling on a suggestion list, and 470 names are past it.** Santa
  Cruz is sixty-nine places, San Isidro sixty-eight. Past nine there is no digit
  left to choose with, and typing more letters does not help — the names are
  identical. The country and the division within it tell most of them apart;
  4,857 name-and-country-and-division groups are still ambiguous, and those want
  `admin2`, which is another column and another download.
- **Sleet with thunder is drawn as rain with thunder.** The bottom band of a
  symbol holds two things and sleet already spends both, so six of the 41 codes
  are drawn identically to six others and only the words tell them apart. It
  errs towards wet, which is the safer way to be wrong.
- **`322<geoname-id>` is reserved and empty.** The presentation digit was put in
  so a forecast could be a graph as well as a table, and then the charts went
  into the table instead. Either the graph arrives or the digit should be
  reconsidered — a numbering that reserves what nobody builds is a numbering
  with a hole in it.
- **The visits log has no command that reads it.** `*2#`, `*96#`, `*97#` and
  `*98#` show it to a reader, but somebody running the service has no way to ask
  it anything without opening SQLite.
- **A period longer than the log is kept for reads low, and silently.** `*98#`
  asks for thirty days and the log keeps thirty days, so they agree today; a
  service that trims sooner would be quietly understating its longest window.
  The page cannot tell, `Visits` having no way to say how far back it goes.

## Raised by the forms

- **Repainting is row-granular.** `changed_rows` finds which rows differ and
  each is sent whole, so flipping one attribute cell in a thirty-seven-cell row
  costs thirty-seven bytes. The one exception is a character typed at the
  cursor, which costs one. A cell-level diff would make several things cheaper
  — a TAB between fields is 79 bytes of which most is unchanged — and would make
  `CONCEAL` usable for showing one field's advice at a time, which is otherwise
  dearer than showing both.
- **`CONCEAL` is unmeasured.** `Attribute.CONCEAL` exists and `Composition` emits
  it, but nothing has established whether Commstar honours it, and REVEAL is a
  viewer-side toggle in any case: concealed text is a suggestion to the terminal
  rather than a guarantee. `screen_text()` reads the rendered framebuffer and
  would settle it.

## Next, and specified

- **Mosaic fonts** — large lettering drawn out of block graphics, for banners
  and title frames. The layer beneath it is built; the requirements, the source
  formats and the measurements are written up in {doc}`explanation/mosaic-fonts`.

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
