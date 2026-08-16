"""Sextile: a framework for Prestel-style Viewdata services.

What a service is made of:

    from sextile import Page, PageRequest, PageRoute, Sextile

    async def main(request: PageRequest) -> Page:
        ...

    app = Sextile(pages=[PageRoute("1", main, name="main", keywords=("MAIN",))])

and `sextile serve your_module:app` answers calls on it. A page is a value and
a service is a list of them, so everything about a page is stated in one place
and registration order does not matter. Sessions, frames, control codes, page
numbering and the wire are the framework's; what the pages say is yours.

Named after the star key on a viewdata keypad.
"""

from importlib.metadata import version

from sextile import keys
from sextile.application import Sextile
from sextile.builtin.guidance import GuideRow
from sextile.content.transliterate import transliterate
from sextile.formatting import Lines, MenuItem, Prose
from sextile.forms import Form, TypeAhead, draw_form
from sextile.handlers import standard_pages
from sextile.layout import Custom, Flow, OnOneFrame, PageLayout, Shortcut
from sextile.middleware import CallNext, Middleware
from sextile.page import Page, PageAddress, PageFrame, UnknownPageError, keyed
from sextile.pages import farewell_page, menu_page, notice_page, prose_page, title_page
from sextile.requests import Neighbours, PageRequest
from sextile.routing import (
    DATE,
    INTEGER,
    Converter,
    Handler,
    NoSuchRouteError,
    PageRoute,
    PageRouter,
    RouteError,
    fixed_integer,
)
from sextile.state import StateKey

__version__ = version("sextile")

#  The whole of it, and stated in one place: what is not named here is the
#  framework's own machinery. See docs/public-surface.md, which lists the
#  public submodules as well -- `layout`, `viewdata` and the rest are too
#  large to flatten into this list and are public as modules.
__all__ = [
    "Neighbours",
    "DATE",
    "INTEGER",
    "CallNext",
    "Converter",
    "Custom",
    "Flow",
    "Form",
    "GuideRow",
    "Handler",
    "Lines",
    "MenuItem",
    "Middleware",
    "NoSuchRouteError",
    "OnOneFrame",
    "Page",
    "PageAddress",
    "PageFrame",
    "PageLayout",
    "PageRequest",
    "PageRoute",
    "PageRouter",
    "Prose",
    "RouteError",
    "Sextile",
    "Shortcut",
    "StateKey",
    "TypeAhead",
    "UnknownPageError",
    "__version__",
    "draw_form",
    "farewell_page",
    "fixed_integer",
    "handlers",
    "keyed",
    "keys",
    "menu_page",
    "notice_page",
    "prose_page",
    "standard_pages",
    "title_page",
    "transliterate",
]
