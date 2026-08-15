# `sextile`

```{eval-rst}
.. automodule:: sextile
   :members:
   :show-inheritance:
   :exclude-members: Custom, Flow, OnOneFrame, PageLayout, Shortcut, TypeAhead, Form
```

`Custom`, `Flow`, `OnOneFrame`, `PageLayout` and `Shortcut` are documented on the
{py:mod}`sextile.layout` page, and `Form` and `TypeAhead` on the
{py:mod}`sextile.forms` page — their home modules — rather than a second time
here.

`Handler` is a type alias whose home module, `sextile.routing`, has no reference
page of its own, so it is documented here:

```{eval-rst}
.. py:currentmodule:: sextile.routing

.. py:type:: Handler

   A page handler: ``async (request: PageRequest) -> Page | None``. ``None``
   rather than a page means there is no such page, which the session shows
   differently from one it could not build.
```
