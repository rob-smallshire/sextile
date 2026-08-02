# Page numbering

The first digit names a namespace; the second says what kind of page within it.

```
<root>          the namespace's index
<root>1         search within it        (reserved, not yet built)
<root>2<id>     one member of it

1     service root        11  search everything
3     days index          32<YYYYMMDD>   3220260802
4     forums index    41 search   42<forum>  4253
5     contributors    51 search   52<user>   5210058
7     topics          71 search   72<topic>  7233387
8     latest posts    81 search   82<post>   82489493
9     system          90 logoff   91 status
0, 2, 6             reserved
```

## The shape

A namespace root does two jobs: alone it is that namespace's index, and with a
kind digit it introduces pages within it. Nothing is spent on separate index
pages, so every root stays one digit long, while the second digit leaves seven
unused slots per namespace for operations we have not thought of yet.

This works because **a page request is terminated by `#`**, so page numbers do
not have to be prefix-free — `*8#` and `*82489493#` are unambiguously different
pages. Only whole-number uniqueness matters, which is what lets the fields vary
in width and stay short.

Two deliberate irregularities:

- **A namespace's index is the bare root, never `<root>0`.** Accepting both
  spellings would give one page two numbers. The `0` slot documents the intent
  and stays free.
- **`9` is the system namespace**, where the second digit is a system function
  rather than a content operation, so that `*90#` keeps its conventional Prestel
  meaning as logoff.

## Why a second structural digit

Page numbers are the one thing that becomes hard to change once anyone has
bookmarked or quoted one; adding structure later would mean renumbering, which
is exactly what the rest of this design avoids. Reserving slots costs nothing,
while restructuring later would cost a great deal, and that asymmetry decides
it.

It also removed a wart rather than adding one. Under a flat `4<id>` scheme, `40`
had to be rejected by a special rule so it could not mean forum 0. With a fixed
two-digit prefix the split point never moves, so that rule falls out of the
structure instead of being patched on.

The cost is one digit on member pages — around 130ms of typing at 75 baud — and
a slight weakening of the correspondence with Stardot's own identifiers, since
`82489493` reads less obviously as `p=489493` than `8489493` would. The
identifier is still there, merely prefixed.

## Why Stardot's own identifiers

Every number here comes from upstream. Post, forum and contributor ids are all
present in the Atom feed — the user id inside the `Statistics: Posted by …`
footer, which the HTML converter must therefore read before discarding it. Only
topic ids are missing, which is why `7` is reserved rather than in use.

Nothing allocates a number, and that is the point:

- **Nothing can renumber.** An earlier proposal numbered posts by date plus an
  ordinal within the day. It needed a rule that ordinals are allocated at first
  sight and never reassigned — a rule that exists only because a rolling feed
  can present posts out of order, meaning the ordinal is not reliably
  chronological anyway. The friction came entirely from the naming scheme.
- **The numbers already sort by time.** phpBB assigns post ids sequentially.
- **One identifier, two worlds.** `viewtopic.php?p=489493` and `*8489493#` carry
  the same number, so a reference passes between the web forum and a BBC Micro
  in either direction. For a service whose purpose is joining those worlds, that
  seems worth more than a readable date.
- **Shorter.** Seven digits against ten or twelve, which at 75 baud is about
  half a second of typing saved on every jump.

Dates survive as an index rather than a naming scheme: `*3220260801#` shows
yesterday's posts without touching a menu, and a day page lists posts without
having to name them.

## Not a constraint

Page numbers have no practical length limit. Commstar transmits at least twenty
digits without truncating — see `viewdata-encoding.md`. The nine-digit Prestel
maximum belonged to Prestel's database, not to any terminal. Length is limited
only by typing time and by header space.
