# Glossary

The framework's terms, each with its current name and a plain definition. When
Phase 2 of the comprehensibility rework renames one, the old name is kept here
as "was X" so a reader coming from older code or docs can find it.

- **page** — what a handler returns: one or more frames sharing a page number.
- **frame** — one screenful, 24 rows of 40 cells; a page too long for one has
  several, keyed `a` to `z`.
- **part** — a piece of a page's body between the rules: a menu, some lines, a
  picture, a form. `layout.Part`.
- **entry** — one item in a sequence a formatter lays out, such as a line of a
  menu. `formatting.Entry`.
- **furniture** — the fixed structure a page is drawn into, around its parts:
  header, rules and footer. `layout.Furnishing`, `DEFAULT_FURNITURE`.
- **route** — a pattern bound to a handler, carrying the page's name and
  keywords. `PageRoute`.
- **pattern** — the page-number template a route matches: literal digits and
  named fields, such as `82{post_id:int}`.
- **address** — a page number a reader is at, resolved from a pattern.
  `PageAddress`.
- **keyword** — a word a reader keys in place of a number, `*MAIN#` for `*1#`;
  set by a route's `keywords=`.
- **choices vs moves** — choices are keys that lead somewhere, such as a menu's
  digits; moves are keys that page or step within where the reader already is,
  `W`/`A`/`S`/`D` and `#`.
- **sequence, neighbours** — the pages either side of this one in a run a menu
  offered, so a reader can step along without going back. `request.neighbours`
  is a `Neighbours(previous, next)` (was `Arrival(preceding, following)`).
- **shortcut** — a key present on every frame that leads to a fixed address.
  `layout.Shortcut`.
- **home vs index** — home is where a caller arrives when the line opens
  (`Sextile(home=...)`, page 1 by default; a service opening on a title frame
  sets its own). Index is where the `0` key goes from every frame
  (`Sextile(index=...)`, the same as home unless set apart). The footer word
  `index` is the label for that key.
- **session vs service state** — session state is one caller's own, lasting as
  long as the line is up (`request.session`); service state is shared across
  callers for the life of the service. Service state is `request.state`, a
  read-only view of what the lifespan opened, keyed by `StateKey`.
- **form** — rows of a frame a reader types into, a field with furniture around
  it. `forms.Form`, `forms.Field`.
