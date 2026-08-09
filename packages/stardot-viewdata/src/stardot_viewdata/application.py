"""Stardot, as a Viewdata service.

This is a Sextile application and nothing more: it says which page numbers
exist, what each of them shows, and where the keys lead. Everything about
connections, sessions, frames, control codes and routing belongs to the
framework, and everything about forums belongs here.

Menus are the shape most pages take. A reader selects with a single keypress, so
a menu offers at most nine choices on a frame and moving down goes to the next
nine. Digit 0 always returns to the main index: it is the one key a reader who
has lost their bearings can rely on.

Where the archive has nothing to show, the page says so. An empty menu with no
explanation looks like a fault, and on a service that deliberately answers
slowly a reader has no way to tell the difference.

The pages are ordinary functions and the service is a list of them. Nothing
here closes over anything: a page takes the archive from what the service holds
and the numbering from the service itself, both through the request it is
given.

The numbering is documented in docs/page-numbering.md. Its one rule worth
repeating here is that every identifier comes from Stardot -- post, forum, topic
and contributor ids are the board's own -- so nothing in this file allocates a
number, nothing can renumber, and a page number means the same thing on the web
forum as on a BBC Micro.
"""

import asyncio
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Final

from sextile import keys
from sextile.addressing import PageAddress, keyed
from sextile.application import Arrival, PageRequest, PageRoute, Parting, Sextile
from sextile.compass import ROWS, compass
from sextile.page import Page, PageFrame
from sextile.templates import CHOICES_PER_FRAME, HOME_KEY, Menu, MenuItem, Prose
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import fitted, rule
from sextile.viewdata.font import load_font
from sextile.viewdata.footer import (
    ROOM,
    FooterItem,
    Priority,
    movement,
    render_footer,
)
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.layout import draw_rows, paginate
from sextile.viewdata.lettering import Spacing
from stardot_viewdata.html import parse_post_body
from stardot_viewdata.model import Post
from stardot_viewdata.store.repository import BOARD_TIMEZONE, Repository

#: What this service is called, which is not what the framework is called.
SERVICE_NAME: Final = "STARDOT"

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

#: Named for the service rather than for the framework serving it, and
#: relative to the working directory -- so `serve` and `ingest` must be run
#: from the same place, which is the first thing that went wrong in practice.
DEFAULT_DATABASE_FILEPATH: Final = Path("stardot.sqlite")


#: What the archive is held under, in what the service holds.
ARCHIVE: Final = "archive"


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
_BEFORE: Final = "←"  # LEFTWARDS ARROW, G0 0x5B
_AFTER: Final = "→"  # RIGHTWARDS ARROW, G0 0x5D
_BETWEEN: Final = "―"  # HORIZONTAL BAR, G0 0x60

#  The footer is written in one colour, which costs a cell of the forty.
_FOOTER_ATTRIBUTE: Final = 1


# -- what a page reaches through the request ---------------------------------


def _archive(service: Mapping[str, object]) -> Repository:
    """The archive, out of what the service holds.

    A narrowing with a reason attached: what a service holds is typed as
    objects, because the framework cannot know what any service puts in it, and
    this is the one function that does know.
    """
    repository = service.get(ARCHIVE)
    if not isinstance(repository, Repository):
        raise RuntimeError("the archive is not open; the service was never started")
    return repository


def _service(request: PageRequest) -> Sextile:
    """The application a page belongs to, narrowed to the one it is."""
    app = request.application
    if not isinstance(app, Sextile):
        raise RuntimeError("this page was asked for outside a running service")
    return app


async def _read[T](request: PageRequest, query: Callable[[Repository], T]) -> T:
    """Ask the archive something, off the event loop.

    SQLite is synchronous, and a caller waiting on a query should not be every
    caller waiting on it.
    """
    return await asyncio.to_thread(query, _archive(request.service))


    # -- menus --------------------------------------------------------------


async def _main_index(request: PageRequest) -> Page:
    app = _service(request)
    held = await _read(request, lambda repository: repository.count_posts())
    items = [
        MenuItem.for_page(app, name)
        for name in (
            "posts",
            "topics",
            "days",
            "forums",
            "contributors",
            "history",
            "help",
            "contents",
            "about",
        )
    ]
    return _menu(
        app,
        request.address,
        title=SERVICE_NAME,
        items=items,
        preamble=["Stardot, for users of Acorn computers.", f"{held} posts held."],
    )


async def _latest_posts(request: PageRequest) -> Page:
    app = _service(request)
    posts = await _read(request, lambda repository: repository.latest_posts(limit=60))
    return _posts_menu(app, request.address, posts)


async def _days_index(request: PageRequest) -> Page:
    app = _service(request)
    days = await _read(request, lambda repository: repository.days(limit=60))
    if not days:
        return _notice(app, request.address, None, ["NO POSTS held yet."])
    items = [
        MenuItem(
            _day_title(day),
            f"{count} post{'' if count == 1 else 's'}",
            app.address_for("day", day=day),
        )
        for day, count in days
    ]
    return _menu(app, request.address, items=items)


async def _day(request: PageRequest, day: date) -> Page:
    app = _service(request)
    posts = await _read(request, lambda repository: repository.posts_on(day))
    return _posts_menu(app, request.address, posts, _day_title(day))


async def _forums_index(request: PageRequest) -> Page:
    app = _service(request)
    forums = await _read(request, lambda repository: repository.forums())
    if not forums:
        return _notice(app, request.address, None, ["NO POSTS held yet."])
    items = [
        MenuItem(
            name,
            f"{count} post{'' if count == 1 else 's'}",
            app.address_for("forum", forum_id=forum_id),
        )
        for forum_id, name, count in forums
    ]
    return _menu(app, request.address, items=items)


async def _forum(request: PageRequest, forum_id: int) -> Page:
    app = _service(request)
    posts = await _read(request, lambda repository: repository.posts_in_forum(forum_id))
    #  Ask the archive rather than the post: a post first seen in a
    #  per-topic feed knows its forum's id but not its name, and the archive
    #  keeps whichever name any post supplied.
    forums = await _read(request, lambda repository: repository.forums())
    named = {found_id: name for found_id, name, _ in forums}
    title = named.get(forum_id) or f"FORUM {forum_id}"
    return _posts_menu(app, request.address, posts, title)


async def _contributors_index(request: PageRequest) -> Page:
    app = _service(request)
    contributors = await _read(request, lambda repository: repository.contributors())
    if not contributors:
        return _notice(app, request.address, None, ["NO POSTS held yet."])
    items = [
        MenuItem(
            name,
            f"{count} post{'' if count == 1 else 's'}",
            app.address_for("contributor", user_id=user_id),
        )
        for user_id, name, count in contributors
    ]
    return _menu(app, request.address, items=items)


async def _contributor(request: PageRequest, user_id: int) -> Page:
    app = _service(request)
    posts = await _read(request, lambda repository: repository.posts_by_author(user_id))
    title = posts[0].author_name if posts else f"USER {user_id}"
    return _posts_menu(app, request.address, posts, title)


async def _topics_index(request: PageRequest) -> Page:
    app = _service(request)
    topics = await _read(request, lambda repository: repository.topics(limit=60))
    if not topics:
        return Prose.of(
            "NO TOPICS held yet.",
            "Topics are known only for posts seen since the board's feed "
            "began carrying them. Older posts have none.",
            title=_headed(app, request.address),
            home=app.index,
        ).build(request.address)
    items = [
        MenuItem(
            title,
            f"{count} post{'' if count == 1 else 's'}",
            app.address_for("topic", topic_id=topic_id),
        )
        for topic_id, title, count in topics
    ]
    return _menu(app, request.address, items=items)


async def _topic(request: PageRequest, topic_id: int) -> Page:
    app = _service(request)
    posts = await _read(request, lambda repository: repository.posts_in_topic(topic_id))
    title = posts[0].topic_title if posts else f"TOPIC {topic_id}"
    return _posts_menu(app, request.address, posts, title)


def _headed(app: Sextile, address: PageAddress) -> str:
    """What goes at the top of a page: what it was registered as, shouted.

    A page that names itself where it is declared and again in its own chrome
    has two copies of its name to keep in step, and they do not stay in step.
    Pages whose heading is not their name -- a post's forum, a day's date --
    say so; the rest say nothing and get this.
    """
    return app.describe(address).upper()


def _posts_menu(
    app: Sextile, address: PageAddress, posts: list[Post], title: str | None = None
) -> Page:
    if not posts:
        return _notice(app, address, title, ["NO POSTS held for this page."])
    items = [
        MenuItem(
            post.subject,
            f"{post.author_name}  {_time_of(post)}",
            app.address_for("post", post_id=post.post_id),
        )
        for post in posts
    ]
    return _menu(app, address, title=title, items=items)


def _menu(
    app: Sextile,
    address: PageAddress,
    *,
    title: str | None = None,
    items: list[MenuItem],
    preamble: list[str] | None = None,
    empty: str = "",
) -> Page:
    """A menu, dealt nine to a frame by the framework's template."""
    return Menu(
        title=title if title is not None else _headed(app, address),
        entries=items,
        home=app.index,
        preamble=preamble or (),
        empty=empty,
    ).build(address)

# -- content pages ------------------------------------------------------


async def _post(request: PageRequest, post_id: int) -> Page:
    app = _service(request)
    post = await _read(request, lambda repository: repository.post(post_id))
    if post is None:
        return Prose.of(
            f"Post {post_id} is NOT in the archive.",
            "This service holds what it has seen in the board's feed, "
            "which reaches back only a little way.",
            title="POST",
            home=app.index,
        ).build(request.address)

    body_rows = CONTENT_ROWS - _POST_HEADING_ROWS
    pages = paginate(parse_post_body(post.content_html), body_rows)
    frames = []
    for index, rows in enumerate(pages):
        canvas = Canvas()
        moving = _frame_moves(index, len(pages))
        moving.update(_post_moves(request.arrival))
        draw_chrome(
            canvas,
            title=post.forum_name or SERVICE_NAME,
            page_number=request.address.frame_number(index),
            prompt=_prompt(moving, selecting=False),
        )
        canvas.row(CONTENT_FIRST_ROW).text(fitted(post.subject, COLUMNS - 1), Colour.YELLOW)
        byline = canvas.row(CONTENT_FIRST_ROW + 1)
        byline.text(fitted(post.author_name, COLUMNS - 8), Colour.GREEN)
        canvas.right(CONTENT_FIRST_ROW + 1, _time_of(post), Colour.GREEN)
        draw_rows(canvas, CONTENT_FIRST_ROW + _POST_HEADING_ROWS, rows)
        choices = _post_choices(app, post)
        choices.update(_neighbour_choices(request.arrival))
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


async def _title(request: PageRequest) -> Page:
    """The frame the line opens on: what this is, and how to get in.

    No page number in the header, because `*0#` is the back command and a
    number a reader cannot key is an instruction that misleads them.
    """
    app = _service(request)
    held = await _read(request, lambda repository: repository.count_posts())
    canvas = Canvas()
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
        SERVICE_NAME,
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
    rule(canvas, 10)
    canvas.row(12).text("The Stardot forum for users of Acorn", Colour.WHITE)
    canvas.row(13).text("computers and emulators.", Colour.WHITE)
    canvas.row(15).text(f"{held} posts held.", Colour.GREEN)
    #  Both instructions are built from the pages they name and the keys
    #  this frame actually answers, so neither can come to say something
    #  the service no longer does. The words are the ones the pages were
    #  registered with, the numbers are the ones the router would build,
    #  and the key is the one in `moves` below.
    index, guide = MenuItem.for_page(app, "main"), MenuItem.for_page(app, "help")
    main, about = app.address_for("main"), app.address_for("help")
    moves = frozenset({NEXT_FRAME_KEY, CONVENTIONAL_NEXT_FRAME_KEY})
    #  Each colour change costs a cell, which shows as a space -- so the
    #  attribute is the space, rather than being paid for on top of one.
    canvas.row(17).text("Key", Colour.WHITE).text(
        CONVENTIONAL_NEXT_FRAME_KEY, Colour.YELLOW
    ).text(f"for the {index.text.lower()}.", Colour.WHITE)
    canvas.row(19).text("Key", Colour.WHITE).text(
        keyed(about), Colour.YELLOW
    ).text(f"for {guide.text.lower()}.", Colour.WHITE)
    return Page(
        frames=(
            PageFrame(
                frame=canvas.frame,
                choices={"1": main},
                moves=moves,
            ),
        ),
        #  `#` is the one key a viewdata reader tries without being told, and
        #  a title frame is nothing but an invitation to press it.
        follows=main,
    )


async def _help(request: PageRequest) -> Page:
    """How to get about, in two frames.

    Every key named here is one the service actually answers; a guide that
    drifts from the thing it describes is worse than none.
    """
    app = _service(request)
    #  Every key and every number here is the one the service actually
    #  answers, taken from the framework or from the router. The words are
    #  this page's own: a description in a table of keys is a paraphrase
    #  and cannot come to be untrue, but a number can, and did.
    moving = [
        (f"1-{CHOICES_PER_FRAME}", "choose from a menu"),
        (HOME_KEY, "back to the main index"),
        (keyed("<number>"), "go straight to a page"),
        (keyed("<keyword>"), "go to named page"),
        (keys.CONVENTIONAL_NEXT_FRAME, "next frame in series"),
        ("DEL", "rub out a character"),
    ]
    asking = [
        (keyed(keys.BACK), "back, through where you"),
        ("", "  have been"),
        (keyed(keys.REDISPLAY), "show this frame again"),
        (keyed(keys.REFRESH), "fetch it afresh"),
        ("", ""),
        (keyed(app.address_for("logoff")), "ring off"),
        ("", ""),
        (keyed(app.address_for("contents")), "every page and its number"),
        (keyed(app.address_for("names")), "every word you can key"),
    ]
    #  One column width for the whole guide, from the widest key in it, so
    #  the two frames line up with each other and neither is set by hand.
    column = max(len(key) for key, _ in moving + asking) + 1
    return _guide(
        app,
        request.address,
        [
            _drawn(_keys(moving, column), _compass),
            _keys(asking, column),
        ],
    )


def _guide(
    app: Sextile, address: PageAddress, drawings: list[Callable[[Canvas], None]]
) -> Page:
    """The guide's frames, each drawn its own way under the same chrome."""
    frames = []
    for index, draw in enumerate(drawings):
        canvas = Canvas()
        moving = _frame_moves(index, len(drawings))
        draw_chrome(
            canvas,
            title=_headed(app, address),
            page_number=address.frame_number(index),
            prompt=_prompt(moving, selecting=False),
        )
        draw(canvas)
        frames.append(
            PageFrame(
                frame=canvas.frame,
                choices={"0": app.address_for("main")},
                moves=_moves(moving),
            )
        )
    return Page(frames=tuple(frames))


def _drawn(*drawings: Callable[[Canvas], None]) -> Callable[[Canvas], None]:
    """Several things on one frame, drawn in the order they are given."""

    def draw(canvas: Canvas) -> None:
        for drawing in drawings:
            drawing(canvas)

    return draw


def _compass(canvas: Canvas) -> None:
    """Which way the four keys go, drawn rather than described.

    The framework's picture of the framework's own keys: a service drawing
    its own would be drawing the same thing, and would go on drawing it
    after the keys had moved. At the foot of the frame, under whatever the
    frame says in words.
    """
    compass(Composition(), CONTENT_FIRST_ROW + CONTENT_ROWS - ROWS).draw(canvas)


def _keys(
    rows: list[tuple[str, str]], column: int
) -> Callable[[Canvas], None]:
    """A key on the left, what it does on the right.

    Two cells go on attributes -- the yellow of the key and the white of
    what it does -- so what is left for the words is the row less the
    column and those two.
    """
    room = COLUMNS - column - 2

    def draw(canvas: Canvas) -> None:
        for offset, (key, meaning) in enumerate(rows):
            row = canvas.row(CONTENT_FIRST_ROW + offset)
            if key:
                row.text(f"{key:<{column}}", Colour.YELLOW)
            else:
                row.skip(column)
            if meaning:
                row.text(fitted(meaning, room), Colour.WHITE)

    return draw


async def _history(request: PageRequest) -> Page:
    """The framework's page, at this service's number."""
    return await _service(request).history(request)


async def _names(request: PageRequest) -> Page:
    """The framework's page, at this service's number."""
    app = _service(request)
    return await app.names(request)


async def _contents(request: PageRequest) -> Page:
    """The framework's page, at this service's number."""
    return await _service(request).contents(request)


async def _about(request: PageRequest) -> Page:
    app = _service(request)
    held = await _read(request, lambda repository: repository.count_posts())
    return Prose.of(
        "A Viewdata service carrying posts from stardot.org.uk, for users "
        "of Acorn computers and emulators.",
        f"{held} posts held.",
        "Page numbers follow the board's own identifiers, so *82489493# "
        "here is post 489493 there.",
        "Served by Sextile, named after the star key on a viewdata keypad.",
        title=f"ABOUT {app.name.upper()}",
        home=app.index,
    ).build(request.address)

#  Titled, and so listed: the contents page is a directory of numbers that
#  do something rather than a menu of places to go, and a reader looking for
#  how to ring off should find it there. 9 is the system namespace, where
#  the second digit is a function, so *90# keeps its Prestel meaning.


async def _logoff(request: PageRequest) -> Page:
    app = _service(request)
    return _farewell(
        app,
        "GOODBYE",
        [f"Thank you for calling {app.name}.", "", "Ring off."],
    )


def _ringing_off(app: Sextile, parting: Parting) -> Page:
    """Said in the service's own voice as an idle caller is released.

    Naming the page they were on, because the terminal keeps nothing and a
    reader who dials back in has no other way to pick up where they were.
    """
    return _farewell(
        app,
        "RINGING OFF",
        [
            "No reply for some time, so the line",
            "has been released for somebody else.",
            "",
            f"You were reading *{parting.address}#.",
            "",
            f"Thank you for calling {app.name}. Do call",
            "again.",
        ],
    )


def _farewell(app: Sextile, title: str, lines: list[str]) -> Page:
    """The last thing a caller sees, and the last thing this service draws.

    No chrome. A footer offering the index would be a lie on a page there is
    no coming back from, and the rows it and the rules occupy are exactly
    the ones the framework wants to leave blank: the reader is about to be
    talking to their modem, and the cursor is put below the last thing said.
    """
    canvas = Canvas()
    canvas.row(0).text(title, Colour.CYAN)
    for offset, line in enumerate(lines):
        if line:
            canvas.row(2 + offset).text(fitted(line, COLUMNS - 1), Colour.WHITE)
    return Page(frames=(PageFrame(frame=canvas.frame),), hang_up=True)


def _notice(
    app: Sextile,
    address: PageAddress,
    title: str | None,
    lines: list[str],
    *,
    hang_up: bool = False,
) -> Page:
    """A page that simply says something, with no choices but the way back."""
    canvas = Canvas()
    #  Through the same renderer as every other page, so a notice says what
    #  everything else says and degrades the same way.
    draw_chrome(
        canvas,
        title=title if title is not None else _headed(app, address),
        page_number=address.frame_number(0),
        prompt=_prompt({}, selecting=False),
    )
    for offset, line in enumerate(lines[:CONTENT_ROWS]):
        if line:
            canvas.row(CONTENT_FIRST_ROW + offset).text(
                fitted(line, COLUMNS - 1), Colour.WHITE
            )
    return Page(
        frames=(
            PageFrame(frame=canvas.frame, choices={"0": app.address_for("main")}),
        ),
        hang_up=hang_up,
    )

# -- when a page is not here --------------------------------------------


def _unknown_page(app: Sextile, target: str) -> Page:
    """Say so, in the service's own furniture, and leave the way back open."""
    canvas = Canvas()
    draw_chrome(
        canvas,
        title="UNKNOWN PAGE",
        page_number="",
        prompt="0 index, or key another page",
    )
    canvas.row(CONTENT_FIRST_ROW).text(f"*{target[:30]}# is NOT a page here.", Colour.WHITE)
    canvas.row(CONTENT_FIRST_ROW + 2).text("Try *1# for the main index.", Colour.WHITE)
    return Page(
        frames=(PageFrame(frame=canvas.frame, choices={"0": app.address_for("main")}),)
    )


#: What the service is made of, in the order the numbering runs. Everything
#: about a page is on one line of it: where it is, what builds it, what it is
#: called where it is listed rather than shown, and the words that reach it.
PAGES: Final = (
    PageRoute("0", _title, name="title"),
    PageRoute("1", _main_index, name="main", title="Main index",
              keywords=("MAIN", "INDEX", "HOME")),
    PageRoute("3", _days_index, name="days", title="By day",
              detail="browse by date", keywords=("DAYS",)),
    PageRoute("32{day:date}", _day, name="day", title="One day"),
    PageRoute("4", _forums_index, name="forums", title="By forum",
              detail="browse by section", keywords=("FORUMS",)),
    PageRoute("42{forum_id:int}", _forum, name="forum", title="One forum"),
    PageRoute("5", _contributors_index, name="contributors",
              title="By contributor", detail="browse by poster",
              keywords=("WHO", "USERS")),
    PageRoute("52{user_id:int}", _contributor, name="contributor",
              title="One contributor"),
    PageRoute("7", _topics_index, name="topics", title="By topic",
              detail="read whole threads", keywords=("TOPICS",)),
    PageRoute("72{topic_id:int}", _topic, name="topic", title="One topic"),
    PageRoute("8", _latest_posts, name="posts", title="Latest posts",
              detail="the newest first", keywords=("LATEST", "NEW", "POSTS")),
    PageRoute("82{post_id:int}", _post, name="post", title="One post"),
    PageRoute("9", _about, name="about", title="About this service",
              keywords=("ABOUT",)),
    #  Titled, and so listed: the contents page is a directory of numbers that
    #  do something rather than a menu of places to go, and a reader looking
    #  for how to ring off should find it there. 9 is the system namespace,
    #  where the second digit is a function, so *90# keeps its Prestel meaning.
    PageRoute("90", _logoff, name="logoff", title="Ring off",
              keywords=("BYE", "OFF")),
    PageRoute("91", _help, name="help", title="How to get about",
              detail="the keys, and what they do",
              keywords=("HELP", "GUIDE", "KEYS")),
    #  Three the framework builds, mapped into this service's numbering.
    PageRoute("92", _history, name="history", title="Where you have been",
              detail="this call, newest first", keywords=("HISTORY", "BEEN")),
    PageRoute("93", _contents, name="contents", title="Every page",
              detail="and the number that fetches it",
              keywords=("PAGES", "CONTENTS")),
    PageRoute("94", _names, name="names", title="Words you can key",
              detail="instead of a page number", keywords=("KEYWORDS", "WORDS")),
)


def build_application(
    database_filepath: Path | str = DEFAULT_DATABASE_FILEPATH,
    *,
    repository: Repository | None = None,
    pages: Sequence[PageRoute] = PAGES,
) -> Sextile:
    """Serve from an archive at ``database_filepath``, or from one already open.

    ``pages`` is the service's own list unless given another, which is what
    lets a test move a page and watch everything that names it follow -- the
    thing the old subclass-and-override could only do by pretending to be a
    different service.

    An archive passed in belongs to whoever passed it and is left open when the
    service stops. That is what a test wants, and what a caller holding the
    archive for some other purpose wants too -- and the lifespan is where that
    distinction now reads as one, rather than as two booleans on an object.
    """

    @asynccontextmanager
    async def lifespan(app: Sextile) -> AsyncIterator[Mapping[str, object]]:
        if repository is not None:
            yield {ARCHIVE: repository}
            return
        ours = await asyncio.to_thread(Repository.open, database_filepath)
        try:
            yield {ARCHIVE: ours}
        finally:
            await asyncio.to_thread(ours.close)

    app = Sextile(
        name=SERVICE_NAME.title(),
        #  A caller arrives on the title frame once; `0` means the index, which
        #  is not the same page and never has been sent back to.
        home="0",
        index="1",
        pages=pages,
        lifespan=lifespan,
    )

    @app.on_describe
    def better_words(address: PageAddress) -> str | None:
        """What to call a page where one is listed rather than shown.

        Only the pages whose numbers carry a field need saying here: the rest
        are titled where they are registered, and the framework reads those.
        "One post" is the right title in a list of *kinds* of page and the
        wrong one in a list of pages a reader has been to, which is the whole
        reason this exists. Returning None means the registration's own words
        will do.

        Subjects and forum names are deliberately not looked up. A history
        frame lists nine pages, which would be nine queries for a label, and
        the page number beside each entry already says which post it is.
        """
        found = app.route(address)
        if found is not None and found.params:
            match found.name, found.params:
                case "post", {"post_id": int() as post_id}:
                    return f"Post {post_id}"
                case "topic", {"topic_id": int() as topic_id}:
                    return f"Topic {topic_id}"
                case "forum", {"forum_id": int() as forum_id}:
                    return f"Forum {forum_id}"
                case "contributor", {"user_id": int() as user_id}:
                    return f"Contributor {user_id}"
                case "day", {"day": date() as day}:
                    return _day_title(day)
        return None

    @app.on_not_found
    async def unknown(target: str) -> Page:
        return _unknown_page(app, target)

    @app.on_timed_out
    async def released(parting: Parting) -> Page:
        return _ringing_off(app, parting)

    return app


# -- helpers ----------------------------------------------------------------


def _day_title(day: date) -> str:
    return day.strftime("%a %d %b %Y").upper()


def _time_of(post: Post) -> str:
    local: datetime = post.published.astimezone(BOARD_TIMEZONE)
    return local.strftime("%H:%M")


def _frame_moves(index: int, total: int) -> dict[str, str]:
    """Moving up and down the frames of this page."""
    moves: dict[str, str] = {}
    if index > 0:
        moves[PREVIOUS_FRAME_KEY] = "up"
    if index + 1 < total:
        moves[NEXT_FRAME_KEY] = "down"
    return moves


def _post_moves(arrival: Arrival) -> dict[str, str]:
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


def _neighbour_choices(arrival: Arrival) -> dict[str, PageAddress]:
    choices: dict[str, PageAddress] = {}
    if arrival.following is not None:
        choices[NEXT_ITEM_KEY] = arrival.following
    if arrival.preceding is not None:
        choices[PREVIOUS_ITEM_KEY] = arrival.preceding
    return keys.arrows_lead_where(choices)


def _prompt(moving: dict[str, str], *, selecting: bool) -> str:
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
