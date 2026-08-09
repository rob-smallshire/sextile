"""Sextile: a framework for Prestel-style Viewdata services.

What a service is made of:

    from sextile import Page, PageRequest, PageRoute, Sextile

    async def main(request: PageRequest) -> Page:
        ...

    app = Sextile(pages=[PageRoute("1", main, name="main", keywords=("MAIN",))])

and `sextile serve your_module:app` answers calls on it. A page is a value and
a service is a list of them, so everything about a page is said in one place
and the order things were registered in is nobody's business. Sessions, frames,
control codes, page numbering and the wire are the framework's; what the pages
say is yours.

Named after the star key on a viewdata keypad.
"""

from importlib.metadata import version

from sextile.addressing import PageAddress, UnknownPageError
from sextile.application import (
    Application,
    Arrival,
    Middleware,
    Next,
    PageInfo,
    PageRequest,
    PageRoute,
    Parting,
    Sextile,
    page,
)
from sextile.page import Page, PageFrame
from sextile.routing import Converter

__version__ = version("sextile")

__all__ = [
    "Application",
    "Arrival",
    "Converter",
    "Middleware",
    "Next",
    "PageInfo",
    "Parting",
    "Page",
    "PageAddress",
    "PageFrame",
    "PageRequest",
    "PageRoute",
    "Sextile",
    "UnknownPageError",
    "__version__",
    "page",
]
