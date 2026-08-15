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
from sextile.addressing import PageAddress, UnknownPageError, keyed
from sextile.application import Middleware, Next, Sextile
from sextile.builtin.guidance import GuideRow
from sextile.content.transliterate import transliterate
from sextile.declarations import Handler, PageInfo, PageRoute, page, routes_in, routes_on
from sextile.forms import Form, Suggest, draw_form
from sextile.handlers import standard_pages
from sextile.held import Held
from sextile.page import Page, PageFrame
from sextile.pages import farewell_page, menu_page, notice_page, prose_page
from sextile.requests import Neighbours, PageRequest, Parting
from sextile.routing import Converter, NoSuchRouteError, RouteError

__version__ = version("sextile")

#  The whole of it, and stated in one place: what is not named here is the
#  framework's own machinery. See docs/public-surface.md, which lists the
#  public submodules as well -- `layout`, `viewdata` and the rest are too
#  large to flatten into this list and are public as modules.
__all__ = [
    "Neighbours",
    "Converter",
    "Form",
    "GuideRow",
    "Handler",
    "Held",
    "Middleware",
    "Next",
    "NoSuchRouteError",
    "Page",
    "PageAddress",
    "PageFrame",
    "PageInfo",
    "PageRequest",
    "PageRoute",
    "Parting",
    "RouteError",
    "Sextile",
    "Suggest",
    "UnknownPageError",
    "__version__",
    "draw_form",
    "farewell_page",
    "handlers",
    "keyed",
    "keys",
    "menu_page",
    "notice_page",
    "page",
    "prose_page",
    "routes_in",
    "routes_on",
    "standard_pages",
    "transliterate",
]
