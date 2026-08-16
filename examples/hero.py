"""Sextile's own title frame: the hero image for the READMEs and the docs.

A single furnished page drawn from block graphics and mosaic lettering, so it
renders the same on a BBC Micro as it does in the browser.

    uv run sextile render examples.hero:app --page 1              # to a terminal
    uv run sextile render examples.hero:app --page 1 --form html  # a web page
    uv run sextile serve examples.hero:app                        # then dial in
"""

import math
from collections.abc import Sequence

from sextile import (
    Custom,
    OnOneFrame,
    Page,
    PageLayout,
    PageRequest,
    PageRouter,
    Sextile,
    Shortcut,
    prose_page,
)
from sextile.layout import DEFAULT_FURNITURE, content_rows
from sextile.viewdata import lettering
from sextile.viewdata.blocks import block_runs
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font
from sextile.viewdata.lettering import Spacing, rows_needed

#: One line under the name. Rob's to change; a single constant so it changes once.
STRAPLINE = "Viewdata services in Python."

_FACE = load_font("boldbash")


def _sextile(across: int = 30, down: int = 24, thickness: float = 1.15) -> list[list[bool]]:
    """The astrological sextile: six spokes 60 degrees apart, drawn as blocks.

    Three lines through the centre give the six spokes; one is vertical, so the
    glyph reads as a star rather than an X with a bar.
    """
    centre_x, centre_y = (across - 1) / 2, (down - 1) / 2
    radius = min(across, down) / 2 - 0.5
    angles = [math.radians(degrees) for degrees in (30, 90, 150)]
    grid: list[list[bool]] = []
    for y in range(down):
        row = []
        for x in range(across):
            dx, dy = x - centre_x, y - centre_y
            reach = math.hypot(dx, dy)
            on_hub = reach < 1.4
            on_spoke = reach <= radius and any(
                abs(dx * math.sin(angle) - dy * math.cos(angle)) < thickness for angle in angles
            )
            row.append(on_hub or on_spoke)
        grid.append(row)
    return grid


_GLYPH: Sequence[Sequence[int]] = block_runs(_sextile())
_CONTENT_ROWS = len(content_rows(DEFAULT_FURNITURE))

router = PageRouter()


@router.page("1", name="title", title="SEXTILE")
async def title(request: PageRequest) -> Page:
    """The title frame: the sextile glyph, the name, and the strapline."""
    glyph_rows = len(_GLYPH)
    name_rows = rows_needed(_FACE)
    #  Centred down the twenty content rows, so the frame reads as a title, not
    #  a heading with a blank half beneath it.
    height = glyph_rows + name_rows + 3
    top = (_CONTENT_ROWS - height) // 2

    def draw(canvas: Canvas, row: int) -> None:
        layout = Composition()
        glyph_row = row + top
        layout.picture(glyph_row, Align.CENTRE, _GLYPH, Colour.YELLOW)
        name_row = glyph_row + glyph_rows + 1
        lettering.place(layout, name_row, "SEXTILE", _FACE, Colour.CYAN, spacing=Spacing.KERNED)
        layout.text(name_row + name_rows + 1, Align.CENTRE, STRAPLINE, Colour.WHITE)
        layout.draw(canvas)

    return PageLayout(
        title="SEXTILE",
        numbered=False,
        home=None,
        parts=[OnOneFrame(Custom(rows=_CONTENT_ROWS, draw=draw))],
        shortcuts=[Shortcut(key="1", destination=request.app.address_for("about"), label="about")],
    ).build(request)


@router.page("11", name="about", title="ABOUT SEXTILE")
async def about(request: PageRequest) -> Page:
    """What Sextile is, so the title frame's `1 about` leads somewhere real."""
    return prose_page(
        request,
        "Sextile is a framework for Prestel-style Viewdata services in Python.",
        "It owns the connection, the session, the page numbering and the frames "
        "on the wire; you write what the pages say.",
        "rob-smallshire.github.io/sextile",
    )


app = Sextile(name="Sextile", pages=[*router])
