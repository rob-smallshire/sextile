"""The masthead the title frame opens on.

A stripe of colour with the service's name set in a mosaic face, the kind of
word under it in a lighter one, and a rule above and below -- the drawing
alone. The page that carries it, with the counts and the instructions, is in
`pages`.
"""

from typing import Final

from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.font import load_font
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.lettering import Spacing

#: The face the title frame's name is set in, and the row it starts on. Heavy
#: strokes and a solid top, which is what a title frame wants and what the
#: framework's own default face -- the shape a Beeb's ROM draws -- is not.
#: Three rows of the frame, the same as the double height it replaced.
BANNER_FACE: Final = "boldbash"
BANNER_ROW: Final = 2

#: The stripe the name is set on, in the colour the rules above and below it
#: are drawn in, so the three read as one piece of furniture. Yellow on blue is
#: what Ceefax used for a page's own name, and it is the strongest pair the
#: hardware has: there is no alpha black, so light on dark is the only choice,
#: and yellow is the brightest thing to put on the darkest.
BANNER_BACKGROUND: Final = Colour.BLUE
BANNER_COLOUR: Final = Colour.YELLOW

#: What the service is, under its name: a lighter face -- the shapes a Beeb's
#: own ROM draws -- so that it reads as a second line rather than a second
#: title, with a stripe a third its height behind it.
SERVICE_KIND: Final = "VIEWDATA"
SUBTITLE_FACE: Final = "acorn"
SUBTITLE_ROW: Final = 6

#: Cells of colour either side of that word, and the rows it takes. The stripe
#: is fitted to the word rather than either being told where the other is.
SUBTITLE_MARGIN: Final = 3
SUBTITLE_ROWS: Final = 3

#: The row of the rule that closes the masthead off from the page below it.
FOOT_RULE_ROW: Final = 10


def draw_masthead(canvas: Canvas, name: str) -> None:
    """The name on its stripe, the kind of service beneath, ruled off."""
    #  The rule sits on the top row rather than the second, so that the
    #  stripe has a blank row above it and below it and reads as a block.
    rule(canvas, 0)
    #  Set in a mosaic face rather than written: double height gives two
    #  rows and one size, and this is three rows and the size we chose.
    #  Kerned, because the row is only 78 blocks wide and the letters can
    #  afford to lean on each other. On a stripe of colour across the
    #  frame, with the composition working out where the stripe begins and
    #  where in it the letters go, up and down as well as along.
    face = load_font(BANNER_FACE)
    layout = Composition()
    stripe = layout.panel(
        BANNER_ROW,
        Align.LEFT,
        colour=BANNER_BACKGROUND,
        width=COLUMNS - 1,
        rows=lettering.rows_for(face),
    )
    lettering.place(
        layout,
        Align.CENTRE,
        name,
        face,
        BANNER_COLOUR,
        within=stripe,
        spacing=Spacing.KERNED,
    )
    #  What the service is, in the lighter face -- the Beeb's own shapes --
    #  so that it reads as the second line and not a second title. Two
    #  things that know nothing of each other: a stripe a row deep and a
    #  word three rows tall, both centred, so they line up without either
    #  being told where the other is. The composition sees that the middle
    #  row is coloured and colours the letters on it accordingly.
    lettering.place(
        layout,
        SUBTITLE_ROW,
        SERVICE_KIND,
        load_font(SUBTITLE_FACE),
        BANNER_COLOUR,
        spacing=Spacing.KERNED,
    )
    #  Fitted to the word after it is placed, so the colour reaches the
    #  same distance past it at both ends however the word is set.
    layout.panel(
        SUBTITLE_ROW + 1,
        colour=BANNER_BACKGROUND,
        around=range(SUBTITLE_ROW, SUBTITLE_ROW + SUBTITLE_ROWS),
        padding=SUBTITLE_MARGIN,
    )
    layout.draw(canvas)
    rule(canvas, FOOT_RULE_ROW)
