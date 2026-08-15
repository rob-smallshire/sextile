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

`:frame:` picks a frame other than the first; `:frames: a,b` renders several
frames of a page stacked, each captioned; `:keys:` drives a session from the page
and renders what is on screen after; `:show-code:` shows the snippet, and
`:hide-lines:` (an emphasize-lines-style spec) hides lines from what is shown
while still running them. Anything that goes wrong is a build error, so a frame
that stops rendering stops the build.

The stylesheet and the Bedstead font are registered from the package and copied
into the build's `_static` when the build finishes.
"""

from __future__ import annotations

import asyncio
from html import escape
from importlib.resources import files
from pathlib import Path
from typing import TYPE_CHECKING, Any

from docutils import nodes
from docutils.parsers.rst import directives
from sphinx.util import parselinenos
from sphinx.util.docutils import SphinxDirective

from sextile.application import Sextile
from sextile.cli import load_application
from sextile.page import Page
from sextile.testing import connect
from sextile.viewdata.frame import Frame
from sextile.viewdata.html import render_html, stylesheet

if TYPE_CHECKING:
    from sphinx.application import Sphinx


def _fetch_page(app: Sextile, page: str) -> Page:
    """Fetch a page, opening and closing the service around it."""

    async def run() -> Page:
        await app.startup()
        try:
            found = await app.fetch(page)
            if found is None:
                raise ValueError(f"{page!r} is not a page of the service")
            return found
        finally:
            await app.shutdown()

    return asyncio.run(run())


def _fetch(app: Sextile, page: str = "1", *, frame: int = 0) -> Frame:
    """Fetch one frame of a page, for a snippet that wants just the frame."""
    return _page_frame(_fetch_page(app, page), frame)


def _page_frame(page: Page, index: int) -> Frame:
    """One frame of an already-built page."""
    one = page.frame(index)
    if one is None:
        raise ValueError(f"the page has no frame {index}")
    return one.frame


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
        "frames": directives.unchanged,
        "keys": directives.unchanged,
        "show-code": directives.flag,
        "hide-lines": directives.unchanged,
    }

    def run(self) -> list[nodes.Node]:
        try:
            html = self._render()
        except Exception as error:
            raise self.severe(f"sextile-frame could not render: {error}") from error
        produced: list[nodes.Node] = []
        if "show-code" in self.options and self.content:
            source = self._shown_source()
            produced.append(nodes.literal_block(source, source, language="python"))
        produced.append(nodes.raw("", html, format="html"))
        return produced

    def _render(self) -> str:
        resolved = self._resolve()
        spec = self.options.get("frames")
        if spec:
            if not isinstance(resolved, Page):
                raise ValueError(":frames: needs a page, from `page` or `app` with :page:")
            return self._render_frames(resolved, spec)
        frame = resolved if isinstance(resolved, Frame) else _page_frame(resolved, self._index())
        return render_html(frame)

    def _render_frames(self, page: Page, spec: str) -> str:
        figures = []
        for letter in (part.strip() for part in spec.split(",") if part.strip()):
            frame = _page_frame(page, ord(letter) - ord("a"))
            figures.append(
                f'<figure class="viewdata-frame">'
                f"<figcaption>frame {escape(letter)}</figcaption>\n"
                f"{render_html(frame)}</figure>"
            )
        return "\n".join(figures)

    def _index(self) -> int:
        return self.options.get("frame", 0)

    def _shown_source(self) -> str:
        """The snippet as shown, with `:hide-lines:` removed but still executed.

        The lines hide from the reader without leaving the run, so an accumulating
        file can show only the lines a step adds while the whole of it draws the
        frame -- the shown code and the drawn frame cannot drift.
        """
        spec = self.options.get("hide-lines")
        hidden = set(parselinenos(spec, len(self.content))) if spec else set()
        return "\n".join(
            line for number, line in enumerate(self.content) if number not in hidden
        )

    def _resolve(self) -> Frame | Page:
        """The frame or page the directive draws, from its snippet or options."""
        if self.content:
            namespace: dict[str, Any] = {"fetch": _fetch}
            exec("\n".join(self.content), namespace)  # noqa: S102 -- the docs' own snippet
            frame = namespace.get("frame")
            if isinstance(frame, Frame):
                return frame
            page = namespace.get("page")
            if isinstance(page, Page):
                return page
            #  A snippet that is nothing but the lesson leaves `app`, and :page:
            #  says which page -- so the shown code carries no fetch scaffolding.
            app = namespace.get("app")
            if isinstance(app, Sextile) and "page" in self.options:
                return self._from_app(app)
            raise ValueError(
                "the snippet must leave `frame` or `page`, or define `app` with :page:"
            )
        if "app" not in self.options or "page" not in self.options:
            raise ValueError("give :app: and :page:, or a snippet body")
        return self._from_app(load_application(self.options["app"]))

    def _from_app(self, app: Sextile) -> Frame | Page:
        keys = self.options.get("keys")
        if keys:
            return _drive(app, self.options["page"], keys, self._index())
        return _fetch_page(app, self.options["page"])


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
