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

The numbering is documented in docs/page-numbering.md. Its one rule worth
repeating here is that every identifier comes from Stardot -- post, forum, topic
and contributor ids are the board's own -- so nothing in this file allocates a
number, nothing can renumber, and a page number means the same thing on the web
forum as on a BBC Micro.
"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Final

from sextile import keys
from sextile.addressing import PageAddress
from sextile.application import Arrival, PageRequest, Sextile
from sextile.content.html import parse_post_body
from sextile.model import Post
from sextile.page import Page, PageFrame
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
from sextile.viewdata.footer import FooterItem, Priority, render_footer
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.layout import draw_rows, paginate

DEFAULT_DATABASE_FILEPATH: Final = Path("sextile.sqlite")

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
_BEFORE: Final = "←"  # LEFTWARDS ARROW, G0 0x5B
_AFTER: Final = "→"  # RIGHTWARDS ARROW, G0 0x5D
_BETWEEN: Final = "―"  # HORIZONTAL BAR, G0 0x60

#  The footer is written in one colour, which costs a cell of the forty.
_FOOTER_ATTRIBUTE: Final = 1


@dataclass(frozen=True)
class MenuItem:
    """One selectable line of a menu."""

    text: str
    detail: str
    destination: PageAddress


class StardotApplication(Sextile):
    """The Stardot service: its pages, and where its keys lead."""

    def __init__(
        self,
        database_filepath: Path | str = DEFAULT_DATABASE_FILEPATH,
        *,
        repository: Repository | None = None,
    ) -> None:
        """Serve from an archive at ``database_filepath``, or from one already open.

        An archive passed in belongs to whoever passed it, and is left open when
        the application stops. That is what a test wants, and what a caller
        holding the archive for some other purpose wants too.
        """
        super().__init__()
        self._database_filepath = database_filepath
        self._repository = repository
        self._ours = repository is None
        self._register()

    # -- the archive --------------------------------------------------------

    @property
    def repository(self) -> Repository:
        if self._repository is None:
            raise RuntimeError("the archive is not open; the application was never started")
        return self._repository

    async def startup(self) -> None:
        if self._ours:
            self._repository = Repository.open(self._database_filepath)

    async def shutdown(self) -> None:
        if self._ours and self._repository is not None:
            self._repository.close()
            self._repository = None

    async def _read[T](self, query: Callable[[Repository], T]) -> T:
        """Ask the archive something, off the event loop.

        SQLite is synchronous, and a caller waiting on a query should not be
        every caller waiting on it.
        """
        repository = self.repository
        return await asyncio.to_thread(query, repository)

    # -- the numbering ------------------------------------------------------

    def _register(self) -> None:
        """Say which page numbers exist, and what answers them.

        The first digit names a namespace and the second says what kind of page
        within it, so the scheme has room to grow without renumbering anything.
        A namespace's index is the bare root and never `<root>0`, because
        accepting both would give one page two numbers.
        """
        self.page("1", name="main")(self._main_index)
        self.page("8", name="posts")(self._latest_posts)
        self.page("82{post_id:int}", name="post")(self._post)
        self.page("7", name="topics")(self._topics_index)
        self.page("72{topic_id:int}", name="topic")(self._topic)
        self.page("3", name="days")(self._days_index)
        self.page("32{day:date}", name="day")(self._day)
        self.page("4", name="forums")(self._forums_index)
        self.page("42{forum_id:int}", name="forum")(self._forum)
        self.page("5", name="contributors")(self._contributors_index)
        self.page("52{user_id:int}", name="contributor")(self._contributor)
        self.page("9", name="about")(self._about)
        #  9 is the system namespace, where the second digit is a system
        #  function rather than a content operation, so that *90# can keep its
        #  conventional Prestel meaning.
        self.page("90", name="logoff")(self._logoff)

        #  Named jumps. Prestel itself was almost entirely numeric, but other
        #  viewdata services accepted keywords and there is no reason for our
        #  own service to be bound by Prestel's database conventions.
        for keyword, route in (
            ("MAIN", "main"),
            ("INDEX", "main"),
            ("HOME", "main"),
            ("LATEST", "posts"),
            ("NEW", "posts"),
            ("POSTS", "posts"),
            ("DAYS", "days"),
            ("FORUMS", "forums"),
            ("WHO", "contributors"),
            ("USERS", "contributors"),
            ("TOPICS", "topics"),
            ("ABOUT", "about"),
            ("HELP", "about"),
            ("BYE", "logoff"),
            ("OFF", "logoff"),
        ):
            self.alias(keyword, self.address_for(route))

    # -- menus --------------------------------------------------------------

    async def _main_index(self, request: PageRequest) -> Page:
        held = await self._read(lambda repository: repository.count_posts())
        items = [
            MenuItem("Latest posts", "the newest first", self.address_for("posts")),
            MenuItem("By topic", "read whole threads", self.address_for("topics")),
            MenuItem("By day", "browse by date", self.address_for("days")),
            MenuItem("By forum", "browse by section", self.address_for("forums")),
            MenuItem("By contributor", "browse by poster", self.address_for("contributors")),
            MenuItem("About this service", "", self.address_for("about")),
        ]
        return self._menu(
            request.address,
            title=SERVICE_NAME,
            items=items,
            preamble=["Stardot, for users of Acorn computers.", f"{held} posts held."],
        )

    async def _latest_posts(self, request: PageRequest) -> Page:
        posts = await self._read(lambda repository: repository.latest_posts(limit=60))
        return self._posts_menu(request.address, "LATEST POSTS", posts)

    async def _days_index(self, request: PageRequest) -> Page:
        days = await self._read(lambda repository: repository.days(limit=60))
        if not days:
            return self._notice(request.address, "BY DAY", ["NO POSTS held yet."])
        items = [
            MenuItem(
                _day_title(day),
                f"{count} post{'' if count == 1 else 's'}",
                self.address_for("day", day=day),
            )
            for day, count in days
        ]
        return self._menu(request.address, title="BY DAY", items=items)

    async def _day(self, request: PageRequest, day: date) -> Page:
        posts = await self._read(lambda repository: repository.posts_on(day))
        return self._posts_menu(request.address, _day_title(day), posts)

    async def _forums_index(self, request: PageRequest) -> Page:
        forums = await self._read(lambda repository: repository.forums())
        if not forums:
            return self._notice(request.address, "BY FORUM", ["NO POSTS held yet."])
        items = [
            MenuItem(
                name,
                f"{count} post{'' if count == 1 else 's'}",
                self.address_for("forum", forum_id=forum_id),
            )
            for forum_id, name, count in forums
        ]
        return self._menu(request.address, title="BY FORUM", items=items)

    async def _forum(self, request: PageRequest, forum_id: int) -> Page:
        posts = await self._read(lambda repository: repository.posts_in_forum(forum_id))
        #  Ask the archive rather than the post: a post first seen in a
        #  per-topic feed knows its forum's id but not its name, and the archive
        #  keeps whichever name any post supplied.
        forums = await self._read(lambda repository: repository.forums())
        named = {found_id: name for found_id, name, _ in forums}
        title = named.get(forum_id) or f"FORUM {forum_id}"
        return self._posts_menu(request.address, title, posts)

    async def _contributors_index(self, request: PageRequest) -> Page:
        contributors = await self._read(lambda repository: repository.contributors())
        if not contributors:
            return self._notice(request.address, "BY CONTRIBUTOR", ["NO POSTS held yet."])
        items = [
            MenuItem(
                name,
                f"{count} post{'' if count == 1 else 's'}",
                self.address_for("contributor", user_id=user_id),
            )
            for user_id, name, count in contributors
        ]
        return self._menu(request.address, title="BY CONTRIBUTOR", items=items)

    async def _contributor(self, request: PageRequest, user_id: int) -> Page:
        posts = await self._read(lambda repository: repository.posts_by_author(user_id))
        title = posts[0].author_name if posts else f"USER {user_id}"
        return self._posts_menu(request.address, title, posts)

    async def _topics_index(self, request: PageRequest) -> Page:
        topics = await self._read(lambda repository: repository.topics(limit=60))
        if not topics:
            return self._notice(
                request.address,
                "BY TOPIC",
                [
                    "NO TOPICS held yet.",
                    "",
                    "Topics are known only for posts seen",
                    "since the board's feed began carrying",
                    "them. Older posts have none.",
                ],
            )
        items = [
            MenuItem(
                title,
                f"{count} post{'' if count == 1 else 's'}",
                self.address_for("topic", topic_id=topic_id),
            )
            for topic_id, title, count in topics
        ]
        return self._menu(request.address, title="BY TOPIC", items=items)

    async def _topic(self, request: PageRequest, topic_id: int) -> Page:
        posts = await self._read(lambda repository: repository.posts_in_topic(topic_id))
        title = posts[0].topic_title if posts else f"TOPIC {topic_id}"
        return self._posts_menu(request.address, title, posts)

    def _posts_menu(self, address: PageAddress, title: str, posts: list[Post]) -> Page:
        if not posts:
            return self._notice(address, title, ["NO POSTS held for this page."])
        items = [
            MenuItem(
                post.subject,
                f"{post.author_name}  {_time_of(post)}",
                self.address_for("post", post_id=post.post_id),
            )
            for post in posts
        ]
        return self._menu(address, title=title, items=items)

    def _menu(
        self,
        address: PageAddress,
        *,
        title: str,
        items: list[MenuItem],
        preamble: list[str] | None = None,
    ) -> Page:
        """Build a menu, dealing its items nine to a frame."""
        lead = preamble or []
        first_frame_capacity = (CONTENT_ROWS - len(lead) - (1 if lead else 0)) // _ROWS_PER_CHOICE
        per_frame = min(CHOICES_PER_FRAME, max(first_frame_capacity, 1))

        batches = [
            items[start : start + per_frame] for start in range(0, len(items), per_frame)
        ] or [[]]
        frames = [
            self._menu_frame(
                address,
                index,
                title=title,
                batch=batch,
                preamble=lead,
                moving=_frame_moves(index, len(batches)),
            )
            for index, batch in enumerate(batches)
        ]
        return Page(frames=tuple(frames))

    def _menu_frame(
        self,
        address: PageAddress,
        index: int,
        *,
        title: str,
        batch: list[MenuItem],
        preamble: list[str],
        moving: dict[str, str],
    ) -> PageFrame:
        canvas = Canvas()
        draw_chrome(
            canvas,
            title=title,
            page_number=address.frame_number(index),
            prompt=_prompt(moving, selecting=bool(batch)),
        )

        row = CONTENT_FIRST_ROW
        for line in preamble:
            canvas.row(row).text(_fitted(line, COLUMNS - 1), Colour.WHITE)
            row += 1
        if preamble:
            row += 1

        choices: dict[str, PageAddress] = {"0": self.address_for("main")}
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

    # -- content pages ------------------------------------------------------

    async def _post(self, request: PageRequest, post_id: int) -> Page:
        post = await self._read(lambda repository: repository.post(post_id))
        if post is None:
            return self._notice(
                request.address,
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
            moving = _frame_moves(index, len(pages))
            moving.update(_post_moves(request.arrival))
            draw_chrome(
                canvas,
                title=post.forum_name or SERVICE_NAME,
                page_number=request.address.frame_number(index),
                prompt=_prompt(moving, selecting=False),
            )
            canvas.row(CONTENT_FIRST_ROW).text(_fitted(post.subject, COLUMNS - 1), Colour.YELLOW)
            byline = canvas.row(CONTENT_FIRST_ROW + 1)
            byline.text(_fitted(post.author_name, COLUMNS - 8), Colour.GREEN)
            canvas.right(CONTENT_FIRST_ROW + 1, _time_of(post), Colour.GREEN)
            draw_rows(canvas, CONTENT_FIRST_ROW + _POST_HEADING_ROWS, rows)
            choices = self._post_choices(post)
            choices.update(_neighbour_choices(request.arrival))
            frames.append(PageFrame(frame=canvas.frame, choices=choices, moves=_moves(moving)))
        return Page(frames=tuple(frames))

    def _post_choices(self, post: Post) -> dict[str, PageAddress]:
        choices: dict[str, PageAddress] = {"0": self.address_for("main")}
        if post.forum_id is not None:
            choices["1"] = self.address_for("forum", forum_id=post.forum_id)
        if post.author_id is not None:
            choices["2"] = self.address_for("contributor", user_id=post.author_id)
        choices["3"] = self.address_for("day", day=post.published.astimezone(BOARD_TIMEZONE).date())
        if post.topic_id is not None:
            choices["4"] = self.address_for("topic", topic_id=post.topic_id)
        return choices

    async def _about(self, request: PageRequest) -> Page:
        held = await self._read(lambda repository: repository.count_posts())
        return self._notice(
            request.address,
            "ABOUT SEXTILE",
            [
                "A Viewdata service carrying posts from",
                "stardot.org.uk, for users of Acorn",
                "computers and emulators.",
                "",
                f"{held} posts held.",
                "",
                "Page numbers follow the board's own",
                "identifiers, so *82489493# here is post",
                "489493 there.",
                "",
                "Named after the star key on a viewdata",
                "keypad.",
            ],
        )

    async def _logoff(self, request: PageRequest) -> Page:
        return self._notice(
            request.address,
            "GOODBYE",
            ["Thank you for calling Sextile.", "", "Ring off."],
            hang_up=True,
        )

    def _notice(
        self,
        address: PageAddress,
        title: str,
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
            title=title,
            page_number=address.frame_number(0),
            prompt=_prompt({}, selecting=False),
        )
        for offset, line in enumerate(lines[:CONTENT_ROWS]):
            if line:
                canvas.row(CONTENT_FIRST_ROW + offset).text(
                    _fitted(line, COLUMNS - 1), Colour.WHITE
                )
        return Page(
            frames=(
                PageFrame(frame=canvas.frame, choices={"0": self.address_for("main")}),
            ),
            hang_up=hang_up,
        )

    # -- when a page is not here --------------------------------------------

    async def not_found(self, target: str) -> Page:
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
            frames=(PageFrame(frame=canvas.frame, choices={"0": self.address_for("main")}),)
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
    return frozenset(within)


def _neighbour_choices(arrival: Arrival) -> dict[str, PageAddress]:
    choices: dict[str, PageAddress] = {}
    if arrival.following is not None:
        choices[NEXT_ITEM_KEY] = arrival.following
    if arrival.preceding is not None:
        choices[PREVIOUS_ITEM_KEY] = arrival.preceding
    return choices


def _prompt(moving: dict[str, str], *, selecting: bool) -> str:
    """Name every key that does something here, and no key that does not.

    Composed as items with priorities rather than as a string, so that when the
    row will not hold them all the footer sheds what the reader can best spare.
    At its longest today it fills the row exactly, so the next axis added will
    need that.
    """
    items = []
    if selecting:
        items.append(FooterItem("1-9", "select", Priority.PRIMARY))
    for before, after, what in (
        (PREVIOUS_FRAME_KEY, NEXT_FRAME_KEY, "frame"),
        (PREVIOUS_ITEM_KEY, NEXT_ITEM_KEY, "post"),
    ):
        axis = _axis(moving, before, after)
        if axis:
            items.append(FooterItem(axis, what, Priority.SECONDARY))
    if NEXT_FRAME_KEY in moving:
        #  Named so the conventional viewdata key is discoverable rather than
        #  merely working -- and first to lose its label, since `S` already says
        #  the same thing.
        items.append(FooterItem(CONVENTIONAL_NEXT_FRAME_KEY, "next", Priority.REDUNDANT))
    items.append(FooterItem("0", "menu", Priority.ESSENTIAL))
    return render_footer(items, COLUMNS - _FOOTER_ATTRIBUTE)


def _axis(moving: dict[str, str], before: str, after: str) -> str:
    """One axis of movement, with an arrow beside each key that is available."""
    if before in moving and after in moving:
        return f"{_BEFORE}{before}{_BETWEEN}{after}{_AFTER}"
    if after in moving:
        return f"{after}{_AFTER}"
    if before in moving:
        return f"{_BEFORE}{before}"
    return ""
