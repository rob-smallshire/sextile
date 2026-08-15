"""A page as furniture and parts, laid out down as many frames as it takes.

The package is three subjects, each in its own module, re-exported here so a
service imports them all from `sextile.layout`:

- `parts`: the content between the rules -- `Drawable` and the wrappers that
  say which frames a part appears on, and `fill`, which walks them.
- `furniture`: the fixed bands round the content -- the header, the rules and
  the footer -- and `content_rows`, the rows they leave.
- `page`: `PageLayout`, which a service constructs and builds, and the
  `Shortcut` and home vocabulary it reads.

`footer` composes the prompt row and is used by both a `PageLayout` and a
service drawing a frame by hand; its names are re-exported here too.
"""

from sextile.layout.footer import (
    FOOTER_WIDTH,
    FooterItem,
    Priority,
    movement,
    render_footer,
)
from sextile.layout.furniture import (
    DEFAULT_FURNITURE,
    Edge,
    Footer,
    FrameContext,
    Furnishing,
    Header,
    Rule,
    content_rows,
)
from sextile.layout.page import (
    DEFAULT_HOME,
    HOME_KEY,
    DefaultHome,
    PageLayout,
    Shortcut,
)
from sextile.layout.parts import (
    CHOICES_PER_FRAME,
    Claim,
    Custom,
    Drawable,
    Flow,
    FrameBreak,
    OnEveryFrame,
    OnOneFrame,
    Part,
    Placed,
    Space,
)

__all__ = [
    "CHOICES_PER_FRAME",
    "DEFAULT_FURNITURE",
    "DEFAULT_HOME",
    "Claim",
    "Custom",
    "DefaultHome",
    "Drawable",
    "Edge",
    "FOOTER_WIDTH",
    "Flow",
    "Footer",
    "FooterItem",
    "FrameBreak",
    "FrameContext",
    "Furnishing",
    "HOME_KEY",
    "Header",
    "OnEveryFrame",
    "OnOneFrame",
    "PageLayout",
    "Part",
    "Placed",
    "Priority",
    "Rule",
    "Shortcut",
    "Space",
    "content_rows",
    "movement",
    "render_footer",
]
