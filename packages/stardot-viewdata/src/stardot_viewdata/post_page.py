"""Drawing one post as a page, and the keys that move about it.

A post runs to several frames, and the reader moves two ways at once: up and
down the frames of this post, and sideways to its neighbours in whatever
sequence they arrived through. The vocabulary for both lives here, beside
the one page that uses all of it; the handler that fetches the post is in
`pages`.
"""

from collections.abc import Callable
from typing import Final

from sextile import Arrival, Page, PageAddress, Sextile, keys
from sextile.formatting import Prose
from sextile.layout import Drawn, Every, Flowing, PageLayout, Shortcut
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import fitted
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.typesetting import rows_for
from stardot_viewdata.html import parse_post_body
from stardot_viewdata.model import Post
from stardot_viewdata.store.repository import BOARD_TIMEZONE

#: Rows a post frame gives to its subject and byline before the body begins.
_POST_HEADING_ROWS: Final = 3

#  The four movement keys, and the conventional viewdata one. They are named in
#  sextile.keys, where the BBC's own cursor keys are mapped onto the same four
#  operations.
PREVIOUS_FRAME_KEY: Final = keys.PREVIOUS_FRAME
NEXT_FRAME_KEY: Final = keys.NEXT_FRAME
CONVENTIONAL_NEXT_FRAME_KEY: Final = keys.CONVENTIONAL_NEXT_FRAME
PREVIOUS_ITEM_KEY: Final = keys.PREVIOUS_ITEM
NEXT_ITEM_KEY: Final = keys.NEXT_ITEM


def post_page(
    app: Sextile,
    address: PageAddress,
    post: Post,
    arrival: Arrival,
    *,
    untitled: str,
) -> Page:
    """One post, divided between frames, with its heading on each of them.

    Args:
        app: The service, for the addresses its other pages answer to.
        address: The address this post answers to.
        post: The post itself.
        arrival: How the reader got here, which is what knows the posts either
            side of this one.
        untitled: What to head a post whose forum the archive never learned --
            one first seen in a per-topic feed -- since a frame has to say
            something.

    Returns:
        The page, however many frames the body needed.
    """
    return PageLayout(
        title=post.forum_name or untitled,
        home=app.address_for("main"),
        item="post",
        shortcuts=[*_about(app, post), *_neighbours(arrival)],
        parts=[
            #  On every frame: a reader three frames into a post should not
            #  have to go back to the first to see whose words these are.
            Every(Drawn(rows=_POST_HEADING_ROWS, draw=_heading_of(post))),
            Flowing(Prose(entries=rows_for(parse_post_body(post.content_html)))),
        ],
    ).build(address)


def _heading_of(post: Post) -> Callable[[Canvas, int], None]:
    """Draw a post's subject, and beneath it who wrote it and when."""

    def draw(canvas: Canvas, row: int) -> None:
        canvas.row(row).text(fitted(post.subject, COLUMNS - 1), Colour.YELLOW)
        canvas.row(row + 1).text(fitted(post.author_name, COLUMNS - 8), Colour.GREEN)
        canvas.right(row + 1, time_of(post), Colour.GREEN)

    return draw


def _about(app: Sextile, post: Post) -> list[Shortcut]:
    """The keys leading to what this post is filed under."""
    shortcuts = []
    if post.forum_id is not None:
        shortcuts.append(
            Shortcut(
                key="1",
                destination=app.address_for("forum", forum_id=post.forum_id),
                says="forum",
            )
        )
    if post.author_id is not None:
        shortcuts.append(
            Shortcut(
                key="2",
                destination=app.address_for("contributor", user_id=post.author_id),
                says="poster",
            )
        )
    shortcuts.append(
        Shortcut(
            key="3",
            destination=app.address_for(
                "day", day=post.published.astimezone(BOARD_TIMEZONE).date()
            ),
            says="day",
        )
    )
    if post.topic_id is not None:
        shortcuts.append(
            Shortcut(
                key="4",
                destination=app.address_for("topic", topic_id=post.topic_id),
                says="topic",
            )
        )
    return shortcuts


def _neighbours(arrival: Arrival) -> list[Shortcut]:
    """The keys leading to the posts either side of this one in its list.

    `arrow=True` because a reader may reach for the cursor keys instead, and on
    a post they mean what the letters mean.
    """
    shortcuts = []
    if arrival.preceding is not None:
        shortcuts.append(
            Shortcut(key=PREVIOUS_ITEM_KEY, destination=arrival.preceding, arrow=True)
        )
    if arrival.following is not None:
        shortcuts.append(
            Shortcut(key=NEXT_ITEM_KEY, destination=arrival.following, arrow=True)
        )
    return shortcuts


def time_of(post: Post) -> str:
    """When a post was made, on the board's own clock."""
    return f"{post.published.astimezone(BOARD_TIMEZONE):%H:%M}"


