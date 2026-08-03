"""Building the page a reference names.

Menus are the shape most pages take. A viewdata reader selects with a single
keypress, so a menu offers at most nine choices on a frame and `#` moves to the
next nine. Digit 0 always returns to the main index: it is the one key a reader
who has lost their bearings can rely on.

Where the archive has nothing to show, the page says so. An empty menu with no
explanation looks like a fault, and on a service that deliberately answers
slowly a reader has no way to tell the difference.
"""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Final

from sextile import keys
from sextile.content.html import parse_post_body
from sextile.model import Post
from sextile.pages import numbering
from sextile.pages.numbering import (
    About,
    Contributor,
    ContributorsIndex,
    Day,
    DaysIndex,
    Forum,
    ForumsIndex,
    Logoff,
    MainIndex,
    PageRef,
    PostsIndex,
    Topic,
    TopicsIndex,
)
from sextile.pages.page import Page, PageFrame
from sextile.store.repository import BOARD_TIMEZONE, Repository
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import (
    CONTENT_FIRST_ROW,
    CONTENT_ROWS,
    SERVICE_NAME,
    draw_chrome,
)
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.layout import draw_rows, paginate

#: A reader selects with one keypress, so nine is the most a frame can offer.
CHOICES_PER_FRAME: Final = 9

#: Each menu entry takes a line of its own plus a line of detail beneath.
_ROWS_PER_CHOICE: Final = 2

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

#  The G0 set has left, right and up arrows but no down arrow -- those three
#  are there for BBC BASIC and the line editor, not as a compass. So the two
#  horizontal arrows do duty as generic `previous` and `next` markers on both
#  axes, which needs no glyph the character set lacks.
_BEFORE: Final = "\u2190"  # LEFTWARDS ARROW, G0 0x5B
_AFTER: Final = "\u2192"  # RIGHTWARDS ARROW, G0 0x5D
_BETWEEN: Final = "\u2015"  # HORIZONTAL BAR, G0 0x60



@dataclass(frozen=True)
class Neighbours:
    """The posts either side of this one, in the sequence being read.

    Which sequence depends on how the reader arrived: a post reached from a
    day's index has that day's posts either side of it, one reached from a
    forum has that forum's. A post reached by typing its number has neither,
    and is offered neither.
    """

    following: PageRef | None = None
    preceding: PageRef | None = None


NO_NEIGHBOURS: Final = Neighbours()


@dataclass(frozen=True)
class MenuItem:
    """One selectable line of a menu."""

    text: str
    detail: str
    destination: PageRef


def resolve(
    reference: PageRef,
    repository: Repository,
    *,
    neighbours: Neighbours = NO_NEIGHBOURS,
) -> Page:
    """Build the page a reference names. Always returns something showable."""
    match reference:
        case MainIndex():
            return _main_index(repository)
        case PostsIndex():
            return _posts_menu(reference, "LATEST POSTS", repository.latest_posts(limit=60))
        case DaysIndex():
            return _days_menu(reference, repository)
        case Day(day):
            return _posts_menu(reference, _day_title(day), repository.posts_on(day))
        case ForumsIndex():
            return _forums_menu(reference, repository)
        case Forum(forum_id):
            return _forum_page(reference, forum_id, repository)
        case ContributorsIndex():
            return _contributors_menu(reference, repository)
        case Contributor(user_id):
            return _contributor_page(reference, user_id, repository)
        case numbering.Post(post_id):
            return _post_page(reference, post_id, repository, neighbours)
        case About():
            return _about(reference, repository)
        case Logoff():
            return _notice(
                reference, "GOODBYE", ["Thank you for calling Sextile.", "", "Ring off."]
            )
        case TopicsIndex() | Topic():
            return _notice(
                reference,
                "TOPICS",
                [
                    "Thread browsing is NOT AVAILABLE.",
                    "",
                    "The board's feed does not carry topic",
                    "identifiers, and the page that would",
                    "reveal them is disallowed to us by the",
                    "site's robots.txt.",
                    "",
                    "Posts may still be read by day, by",
                    "forum, and by contributor.",
                ],
            )


# -- menus ------------------------------------------------------------------


def _main_index(repository: Repository) -> Page:
    held = repository.count_posts()
    items = [
        MenuItem("Latest posts", "the newest first", PostsIndex()),
        MenuItem("By day", "browse by date", DaysIndex()),
        MenuItem("By forum", "browse by section", ForumsIndex()),
        MenuItem("By contributor", "browse by poster", ContributorsIndex()),
        MenuItem("About this service", "", About()),
    ]
    return _menu(
        MainIndex(),
        title=SERVICE_NAME,
        items=items,
        preamble=["Stardot, for users of Acorn computers.", f"{held} posts held."],
    )


def _posts_menu(reference: PageRef, title: str, posts: list[Post]) -> Page:
    if not posts:
        return _notice(reference, title, ["NO POSTS held for this page."])
    items = [
        MenuItem(
            post.subject,
            f"{post.author_name}  {_time_of(post)}",
            numbering.Post(post.post_id),
        )
        for post in posts
    ]
    return _menu(reference, title=title, items=items)


def _days_menu(reference: PageRef, repository: Repository) -> Page:
    days = repository.days(limit=60)
    if not days:
        return _notice(reference, "BY DAY", ["NO POSTS held yet."])
    items = [
        MenuItem(_day_title(day), f"{count} post{'' if count == 1 else 's'}", Day(day))
        for day, count in days
    ]
    return _menu(reference, title="BY DAY", items=items)


def _forums_menu(reference: PageRef, repository: Repository) -> Page:
    forums = repository.forums()
    if not forums:
        return _notice(reference, "BY FORUM", ["NO POSTS held yet."])
    items = [
        MenuItem(name, f"{count} post{'' if count == 1 else 's'}", Forum(forum_id))
        for forum_id, name, count in forums
    ]
    return _menu(reference, title="BY FORUM", items=items)


def _contributors_menu(reference: PageRef, repository: Repository) -> Page:
    contributors = repository.contributors()
    if not contributors:
        return _notice(reference, "BY CONTRIBUTOR", ["NO POSTS held yet."])
    items = [
        MenuItem(name, f"{count} post{'' if count == 1 else 's'}", Contributor(user_id))
        for user_id, name, count in contributors
    ]
    return _menu(reference, title="BY CONTRIBUTOR", items=items)


def _forum_page(reference: PageRef, forum_id: int, repository: Repository) -> Page:
    posts = repository.posts_in_forum(forum_id)
    #  Ask the archive rather than the post: a post first seen in a per-topic
    #  feed knows its forum's id but not its name, and the archive keeps
    #  whichever name any post supplied.
    named = {found_id: name for found_id, name, _ in repository.forums()}
    title = named.get(forum_id) or f"FORUM {forum_id}"
    return _posts_menu(reference, title, posts)


def _contributor_page(reference: PageRef, user_id: int, repository: Repository) -> Page:
    posts = repository.posts_by_author(user_id)
    title = posts[0].author_name if posts else f"USER {user_id}"
    return _posts_menu(reference, title, posts)


def _menu(
    reference: PageRef,
    *,
    title: str,
    items: list[MenuItem],
    preamble: list[str] | None = None,
) -> Page:
    """Build a menu, dealing its items nine to a frame."""
    lead = preamble or []
    first_frame_capacity = (CONTENT_ROWS - len(lead) - (1 if lead else 0)) // _ROWS_PER_CHOICE
    per_frame = min(CHOICES_PER_FRAME, max(first_frame_capacity, 1))

    batches = [items[start : start + per_frame] for start in range(0, len(items), per_frame)] or [
        []
    ]
    frames = [
        _menu_frame(
            reference,
            index,
            title=title,
            batch=batch,
            preamble=lead,
            moving=_frame_moves(index, len(batches), more="more"),
        )
        for index, batch in enumerate(batches)
    ]
    return Page(reference=reference, frames=tuple(frames))


def _menu_frame(
    reference: PageRef,
    index: int,
    *,
    title: str,
    batch: list[MenuItem],
    preamble: list[str],
    moving: dict[str, str],
) -> PageFrame:
    canvas = Canvas()
    number = f"{numbering.format_page_number(reference)}{numbering.frame_letter(index)}"
    draw_chrome(
        canvas,
        title=title,
        page_number=number,
        prompt=_prompt(moving, selecting=bool(batch)),
    )

    row = CONTENT_FIRST_ROW
    for line in preamble:
        canvas.row(row).text(_fitted(line, COLUMNS - 1), Colour.WHITE)
        row += 1
    if preamble:
        row += 1

    choices: dict[str, PageRef] = {"0": MainIndex()}
    for offset, item in enumerate(batch):
        digit = offset + 1
        choices[str(digit)] = item.destination
        canvas.row(row).text(f"{digit} ", Colour.YELLOW).text(
            _fitted(item.text, COLUMNS - 4), Colour.WHITE
        )
        row += 1
        if item.detail and row < CONTENT_FIRST_ROW + CONTENT_ROWS:
            canvas.row(row).skip(2).text(_fitted(item.detail, COLUMNS - 4), Colour.GREEN)
        row += 1

    return PageFrame(frame=canvas.frame, choices=choices, moves=_moves(moving))


# -- content pages ----------------------------------------------------------


def _post_page(
    reference: PageRef, post_id: int, repository: Repository, neighbours: Neighbours
) -> Page:
    post = repository.post(post_id)
    if post is None:
        return _notice(
            reference,
            "POST",
            [
                f"Post {post_id} is NOT in the archive.",
                "",
                "Sextile holds what it has seen in the",
                "board's feed, which reaches back only a",
                "little way.",
            ],
        )

    body_rows = CONTENT_ROWS - _POST_HEADING_ROWS
    pages = paginate(parse_post_body(post.content_html), body_rows)
    frames = []
    for index, rows in enumerate(pages):
        canvas = Canvas()
        number = f"{numbering.format_page_number(reference)}{numbering.frame_letter(index)}"
        moving = _frame_moves(index, len(pages), more="next frame")
        moving.update(_post_moves(neighbours))
        draw_chrome(
            canvas,
            title=post.forum_name or SERVICE_NAME,
            page_number=number,
            prompt=_prompt(moving, selecting=False),
        )
        canvas.row(CONTENT_FIRST_ROW).text(_fitted(post.subject, COLUMNS - 1), Colour.YELLOW)
        byline = canvas.row(CONTENT_FIRST_ROW + 1)
        byline.text(_fitted(post.author_name, COLUMNS - 8), Colour.GREEN)
        canvas.right(CONTENT_FIRST_ROW + 1, _time_of(post), Colour.GREEN)
        draw_rows(canvas, CONTENT_FIRST_ROW + _POST_HEADING_ROWS, rows)
        choices = _post_choices(post)
        choices.update(_neighbour_choices(neighbours))
        frames.append(
            PageFrame(frame=canvas.frame, choices=choices, moves=_moves(moving))
        )
    return Page(reference=reference, frames=tuple(frames))


def _post_choices(post: Post) -> dict[str, PageRef]:
    choices: dict[str, PageRef] = {"0": MainIndex()}
    if post.forum_id is not None:
        choices["1"] = Forum(post.forum_id)
    if post.author_id is not None:
        choices["2"] = Contributor(post.author_id)
    choices["3"] = Day(post.published.astimezone(BOARD_TIMEZONE).date())
    return choices


def _about(reference: PageRef, repository: Repository) -> Page:
    return _notice(
        reference,
        "ABOUT SEXTILE",
        [
            "A Viewdata service carrying posts from",
            "stardot.org.uk, for users of Acorn",
            "computers and emulators.",
            "",
            f"{repository.count_posts()} posts held.",
            "",
            "Page numbers follow the board's own",
            "identifiers, so *82489493# here is post",
            "489493 there.",
            "",
            "Named after the star key on a viewdata",
            "keypad.",
        ],
    )


def _notice(reference: PageRef, title: str, lines: list[str]) -> Page:
    """A page that simply says something, with no choices but the way back."""
    canvas = Canvas()
    number = f"{numbering.format_page_number(reference)}{numbering.frame_letter(0)}"
    draw_chrome(canvas, title=title, page_number=number, prompt="0 for the main index")
    for offset, line in enumerate(lines[:CONTENT_ROWS]):
        if line:
            canvas.row(CONTENT_FIRST_ROW + offset).text(_fitted(line, COLUMNS - 1), Colour.WHITE)
    return Page(
        reference=reference,
        frames=(PageFrame(frame=canvas.frame, choices={"0": MainIndex()}),),
    )


# -- helpers ----------------------------------------------------------------


def _day_title(day: date) -> str:
    return day.strftime("%a %d %b %Y").upper()


def _time_of(post: Post) -> str:
    local: datetime = post.published.astimezone(BOARD_TIMEZONE)
    return local.strftime("%H:%M")


def _fitted(text: str, cells: int) -> str:
    fitted = text
    while cell_count(fitted) > cells:
        fitted = fitted[:-1]
    return fitted


# -- what a frame offers ----------------------------------------------------
#
#  A key a frame names must do something on that frame, and a key that would do
#  something should be named. So the prompt and the choices are built from the
#  same description of what is actually available here.


def _frame_moves(index: int, total: int, *, more: str) -> dict[str, str]:
    """Moving up and down the frames of this page."""
    del more  # the wording is now the same wherever it appears
    moves: dict[str, str] = {}
    if index > 0:
        moves[PREVIOUS_FRAME_KEY] = "up"
    if index + 1 < total:
        moves[NEXT_FRAME_KEY] = "down"
    return moves


def _post_moves(neighbours: Neighbours) -> dict[str, str]:
    """Moving sideways between posts, when the reader arrived through a sequence."""
    moves: dict[str, str] = {}
    if neighbours.preceding is not None:
        moves[PREVIOUS_ITEM_KEY] = "prev"
    if neighbours.following is not None:
        moves[NEXT_ITEM_KEY] = "next"
    return moves


def _moves(moving: dict[str, str]) -> frozenset[str]:
    """The keys that move within this page rather than leaving it.

    `#` comes along wherever `S` does, so the conventional viewdata key keeps
    working for a reader who never learns the rest.
    """
    keys = {key for key in moving if key in (PREVIOUS_FRAME_KEY, NEXT_FRAME_KEY)}
    if NEXT_FRAME_KEY in keys:
        keys.add(CONVENTIONAL_NEXT_FRAME_KEY)
    return frozenset(keys)


def _neighbour_choices(neighbours: Neighbours) -> dict[str, PageRef]:
    choices: dict[str, PageRef] = {}
    if neighbours.following is not None:
        choices[NEXT_ITEM_KEY] = neighbours.following
    if neighbours.preceding is not None:
        choices[PREVIOUS_ITEM_KEY] = neighbours.preceding
    return choices


def _prompt(moving: dict[str, str], *, selecting: bool) -> str:
    """Name every key that does something here, and no key that does not.

    At its longest -- both axes, or a menu with more frames either side -- this
    comes to exactly forty cells including its colour attribute. There is a test
    to that effect, because there is no room at all to spare.
    """
    parts = ["1-9 select"] if selecting else []
    parts.append(_axis(moving, PREVIOUS_FRAME_KEY, NEXT_FRAME_KEY, "frame"))
    parts.append(_axis(moving, PREVIOUS_ITEM_KEY, NEXT_ITEM_KEY, "post"))
    if NEXT_FRAME_KEY in moving:
        #  Named, so that the conventional viewdata key is discoverable rather
        #  than merely working.
        parts.append(f"{CONVENTIONAL_NEXT_FRAME_KEY} next")
    parts.append("0 menu")
    return ", ".join(part for part in parts if part)


def _axis(moving: dict[str, str], before: str, after: str, what: str) -> str:
    """One axis of movement, with an arrow beside each key that is available."""
    if before in moving and after in moving:
        return f"{_BEFORE}{before}{_BETWEEN}{after}{_AFTER} {what}"
    if after in moving:
        return f"{after}{_AFTER} {what}"
    if before in moving:
        return f"{_BEFORE}{before} {what}"
    return ""
