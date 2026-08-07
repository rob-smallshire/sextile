"""Sextile: a framework for Prestel-style Viewdata services.

What a service is made of:

    from sextile import Page, PageRequest, Sextile

    app = Sextile()

    @app.page("1", name="main")
    async def main(request: PageRequest) -> Page:
        ...

    app.alias("MAIN", "1")

and `sextile serve your_module:app` answers calls on it. Sessions, frames,
control codes, page numbering and the wire are the framework's; what the pages
say is yours.

Named after the star key on a viewdata keypad.
"""

from importlib.metadata import version

from sextile.addressing import PageAddress, UnknownPageError
from sextile.application import Application, Arrival, PageRequest, Sextile
from sextile.page import Page, PageFrame
from sextile.routing import Converter

__version__ = version("sextile")

__all__ = [
    "Application",
    "Arrival",
    "Converter",
    "Page",
    "PageAddress",
    "PageFrame",
    "PageRequest",
    "Sextile",
    "UnknownPageError",
    "__version__",
]
