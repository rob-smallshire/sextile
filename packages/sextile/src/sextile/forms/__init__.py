"""A field on a frame that a reader types into.

Everything else in this framework answers a keypress by going somewhere. A form
answers one by *changing what is on the screen without moving*.

The shape is deliberately narrow. A form owns some rows of a frame, says which
keys are typing rather than navigating, redraws its rows when the value changes,
and says where its digits lead as the value now stands. The session does the
remainder: it keeps the frame in step, sends the changed rows, and treats a digit
that leads somewhere exactly as it treats a digit on a menu -- so history,
sequences and the back key all go on working with nothing added.

The package is the contract and the two field types built on it:

- `base`: `Form`, the base a field type subclasses, `draw_form`, and `Lookup`.
- `type_ahead`: `TypeAhead`, a field with the best few matches beneath it.
- `fields`: `Field` and `FieldSet`, several fields with one live at a time.

All are re-exported here, so a service imports them from `sextile.forms`.
"""

from sextile.forms.base import Form, Lookup, draw_form
from sextile.forms.fields import Field, FieldSet, Footnote, SubmitHandler
from sextile.forms.type_ahead import SUGGESTIONS, TypeAhead

__all__ = [
    "SUGGESTIONS",
    "Field",
    "FieldSet",
    "Footnote",
    "Form",
    "Lookup",
    "SubmitHandler",
    "TypeAhead",
    "draw_form",
]
