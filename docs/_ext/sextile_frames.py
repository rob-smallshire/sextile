"""A Sphinx directive that draws a Viewdata frame as HTML, at build time.

`.. sextile-frame::` renders one frame of a service into the page, the same way
`sextile render --form html` does, so a documented frame is the frame the code
actually draws rather than a screenshot that goes stale. Two forms:

Options -- fetch a page from a service by its `module:name`::

    .. sextile-frame::
       :app: calendar_viewdata:app
       :page: "3"

Content body -- run a snippet that leaves a `frame` (a `Frame`) or a `page` (a
`Page`); `fetch(app, number)` is in scope. This is the form for anything that
needs a fixed clock or a hand-built frame::

    .. sextile-frame::

       from datetime import UTC, datetime
       from calendar_viewdata import build_application
       app = build_application(now=lambda: datetime(2026, 8, 1, tzinfo=UTC))
       frame = fetch(app, "3")

`:frame:` picks a frame other than the first; `:keys:` drives a session from the
page and renders what is on screen after; `:show-code:` also shows the snippet.
Anything that goes wrong is a build error, so a frame that stops rendering stops
the build.

The stylesheet and the Bedstead font are registered from the package and copied
into the build's `_static` when the build finishes.
"""

from __future__ import annotations

import asyncio
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util.docutils import SphinxDirective

from sextile.application import Sextile
from sextile.cli import load_application
from sextile.page import Page
from sextile.testing import connect
from sextile.viewdata.frame import Frame
from sextile.viewdata.html import render_html, stylesheet

if TYPE_CHECKING:
    from sphinx.application import Sphinx


def _fetch(app: Sextile, page: str = "1", *, frame: int = 0) -> Frame:
    """Fetch one frame of a page, opening and closing the service around it."""

    async def run() -> Frame:
        await app.startup()
        try:
            found = await app.fetch(page)
            if found is None:
                raise ValueError(f"{page!r} is not a page of the service")
            one = found.frame(frame)
            if one is None:
                raise ValueError(f"page {page!r} has no frame {frame}")
            return one.frame
        finally:
            await app.shutdown()

    return asyncio.run(run())


def _drive(app: Sextile, start: str, keys: str, frame: int) -> Frame:
    """Press keys from a page, and return the frame on screen after."""

    async def run() -> Frame:
        async with connect(app, start=start) as caller:
            await caller.press(keys)
            on_screen = caller.session.current_frame()
            if on_screen is None:
                raise ValueError(f"nothing on screen after keying {keys!r}")
            return on_screen

    return asyncio.run(run())


class SextileFrame(SphinxDirective):
    """Render one Viewdata frame into the page."""

    has_content = True
    option_spec = {  # noqa: RUF012 -- docutils reads this as a plain dict
        "app": directives.unchanged,
        "page": directives.unchanged,
        "frame": directives.nonnegative_int,
        "keys": directives.unchanged,
        "show-code": directives.flag,
    }

    def run(self) -> list[nodes.Node]:
        try:
            frame = self._frame()
        except Exception as error:
            raise self.severe(f"sextile-frame could not render: {error}") from error
        produced: list[nodes.Node] = []
        if "show-code" in self.options and self.content:
            source = "\n".join(self.content)
            produced.append(nodes.literal_block(source, source, language="python"))
        produced.append(nodes.raw("", render_html(frame), format="html"))
        return produced

    def _frame(self) -> Frame:
        if self.content:
            return self._from_snippet()
        return self._from_options()

    def _from_options(self) -> Frame:
        if "app" not in self.options or "page" not in self.options:
            raise ValueError("give :app: and :page:, or a snippet body")
        app = load_application(self.options["app"])
        index = self.options.get("frame", 0)
        keys = self.options.get("keys")
        if keys:
            return _drive(app, self.options["page"], keys, index)
        return _fetch(app, self.options["page"], frame=index)

    def _from_snippet(self) -> Frame:
        namespace: dict[str, Any] = {"fetch": _fetch}
        exec("\n".join(self.content), namespace)  # noqa: S102 -- the docs' own snippet
        frame = namespace.get("frame")
        if isinstance(frame, Frame):
            return frame
        page = namespace.get("page")
        if isinstance(page, Page):
            index = self.options.get("frame", 0)
            one = page.frame(index)
            if one is None:
                raise ValueError(f"the snippet's page has no frame {index}")
            return one.frame
        raise ValueError("the snippet must leave `frame` (a Frame) or `page` (a Page)")


def _copy_assets(app: Sphinx, exception: Exception | None) -> None:
    """Write the stylesheet and font into the build's _static once it finishes."""
    if exception is not None:
        return
    static = Path(app.outdir) / "_static"
    static.mkdir(parents=True, exist_ok=True)
    font = (files("sextile.viewdata") / "static" / "bedstead.woff2").read_bytes()
    (static / "bedstead.woff2").write_bytes(font)
    css = (
        '@font-face {\n'
        '  font-family: "Bedstead";\n'
        '  src: url("bedstead.woff2") format("woff2");\n'
        "}\n" + stylesheet()
    )
    (static / "viewdata.css").write_text(css, encoding="utf-8")


def setup(app: Sphinx) -> dict[str, Any]:
    """Register the directive, the stylesheet, and the asset copy."""
    app.add_directive("sextile-frame", SextileFrame)
    app.add_css_file("viewdata.css")
    app.connect("build-finished", _copy_assets)
    return {"version": "1.0", "parallel_read_safe": True, "parallel_write_safe": True}
