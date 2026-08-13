"""Drawing one post as a page, and the keys that move about it.

A post runs to several frames, and the reader moves two ways at once: up and
down the frames of this post, and sideways to its neighbours in whatever
sequence they arrived through. The vocabulary for both lives here, beside
the one page that uses all of it; the handler that fetches the post is in
`pages`.
"""

from typing import Final

from sextile import keys
from sextile.addressing import PageAddress
from sextile.application import Arrival, Sextile
from sextile.page import Page, PageFrame
from sextile.templates import HOME_KEY
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import fitted
from sextile.viewdata.footer import ROOM, FooterItem, Priority, movement, render_footer
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.layout import draw_rows, paginate
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
    """One post, dealt into frames, its keys built from what each frame offers.

    ``untitled`` heads a post whose forum the archive never learned -- one
    first seen in a per-topic feed -- since a frame has to say something.
    """
    body_rows = CONTENT_ROWS - _POST_HEADING_ROWS
    dealt = paginate(parse_post_body(post.content_html), body_rows)
    frames = []
    for index, rows in enumerate(dealt):
        canvas = Canvas()
        moving = frame_moves(index, len(dealt))
        moving.update(post_moves(arrival))
        draw_chrome(
            canvas,
            title=post.forum_name or untitled,
            page_number=address.frame_number(index),
            prompt=prompt(moving, selecting=False),
        )
        canvas.row(CONTENT_FIRST_ROW).text(fitted(post.subject, COLUMNS - 1), Colour.YELLOW)
        byline = canvas.row(CONTENT_FIRST_ROW + 1)
        byline.text(fitted(post.author_name, COLUMNS - 8), Colour.GREEN)
        canvas.right(CONTENT_FIRST_ROW + 1, time_of(post), Colour.GREEN)
        draw_rows(canvas, CONTENT_FIRST_ROW + _POST_HEADING_ROWS, rows)
        choices = _post_choices(app, post)
        choices.update(neighbour_choices(arrival))
        frames.append(PageFrame(frame=canvas.frame, choices=choices, moves=_moves(moving)))
    return Page(frames=tuple(frames))


def _post_choices(app: Sextile, post: Post) -> dict[str, PageAddress]:
    choices: dict[str, PageAddress] = {"0": app.address_for("main")}
    if post.forum_id is not None:
        choices["1"] = app.address_for("forum", forum_id=post.forum_id)
    if post.author_id is not None:
        choices["2"] = app.address_for("contributor", user_id=post.author_id)
    choices["3"] = app.address_for("day", day=post.published.astimezone(BOARD_TIMEZONE).date())
    if post.topic_id is not None:
        choices["4"] = app.address_for("topic", topic_id=post.topic_id)
    return choices


def time_of(post: Post) -> str:
    """When a post was made, on the board's own clock."""
    return f"{post.published.astimezone(BOARD_TIMEZONE):%H:%M}"


def frame_moves(index: int, total: int) -> dict[str, str]:
    """Moving up and down the frames of this page."""
    moves: dict[str, str] = {}
    if index > 0:
        moves[PREVIOUS_FRAME_KEY] = "up"
    if index + 1 < total:
        moves[NEXT_FRAME_KEY] = "down"
    return moves


def post_moves(arrival: Arrival) -> dict[str, str]:
    """Moving sideways between posts, when the reader arrived through a sequence."""
    moves: dict[str, str] = {}
    if arrival.preceding is not None:
        moves[PREVIOUS_ITEM_KEY] = "prev"
    if arrival.following is not None:
        moves[NEXT_ITEM_KEY] = "next"
    return moves


def _moves(moving: dict[str, str]) -> frozenset[str]:
    """The keys that move within this page rather than leaving it.

    `#` comes along wherever `S` does, so the conventional viewdata key keeps
    working for a reader who never learns the rest.
    """
    within = {key for key in moving if key in (PREVIOUS_FRAME_KEY, NEXT_FRAME_KEY)}
    if NEXT_FRAME_KEY in within:
        within.add(CONVENTIONAL_NEXT_FRAME_KEY)
    #  And the arrows a reader might press instead, which the framework knows
    #  the codes for and deliberately does not act on: what an arrow means is
    #  this page's business.
    return keys.with_arrows(within)


def neighbour_choices(arrival: Arrival) -> dict[str, PageAddress]:
    choices: dict[str, PageAddress] = {}
    if arrival.following is not None:
        choices[NEXT_ITEM_KEY] = arrival.following
    if arrival.preceding is not None:
        choices[PREVIOUS_ITEM_KEY] = arrival.preceding
    return keys.arrows_lead_where(choices)


def prompt(moving: dict[str, str], *, selecting: bool) -> str:
    """Name every key that does something here, and no key that does not.

    One item to a key, each saying in words what pressing it does, and each
    with a shorter way of saying it for when the row is tight. The footer then
    says as much as the row will hold: a page with keys to spare gets the
    sentence, and only the busiest page falls back to the short words.

    It used to pack a pair of keys into one item and label it with a noun --
    the frame keys as one item called "frame" -- which fitted the busiest page
    exactly and was then used on every page, including the ones with half a row
    going spare. A reader had to work out that the noun was what the keys moved
    through rather than what pressing them did.
    """
    items = []
    if selecting:
        items.append(FooterItem("1-9", "select", Priority.PRIMARY))
    items += movement(moving, item="post")
    if NEXT_FRAME_KEY in moving:
        #  Named so the conventional viewdata key is discoverable rather than
        #  merely working -- and the first thing off the row, since the key
        #  above it already says what it does.
        items.append(
            FooterItem(CONVENTIONAL_NEXT_FRAME_KEY, "next frame", Priority.REDUNDANT)
        )
    items.append(FooterItem(HOME_KEY, "index", Priority.ESSENTIAL))
    return render_footer(items, ROOM)
