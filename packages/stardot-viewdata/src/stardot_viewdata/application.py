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
from datetime import date, datetime
from pathlib import Path
from typing import Final

from sextile import keys
from sextile.addressing import PageAddress
from sextile.application import Arrival, PageRequest, Parting, Sextile, page
from sextile.page import Page, PageFrame
from sextile.templates import Menu, MenuItem, Prose
from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.composition import Align, Composition
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import fitted, rule
from sextile.viewdata.font import load_font
from sextile.viewdata.footer import FooterItem, Priority, render_footer
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

#: Named for the service rather than for the framework serving it, and
#: relative to the working directory -- so `serve` and `ingest` must be run
#: from the same place, which is the first thing that went wrong in practice.
DEFAULT_DATABASE_FILEPATH: Final = Path("stardot.sqlite")

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
        #  A caller arrives on the title frame once; `0` means the index, which
        #  is not the same page and never has been sent back to.
        super().__init__(name=SERVICE_NAME.title(), home="0", index="1")
        self._database_filepath = database_filepath
        self._repository = repository
        self._ours = repository is None

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

    def describe(self, address: PageAddress) -> str:
        """What to call a page where one is listed rather than shown.

        Only the pages whose numbers carry a field need saying here: the rest
        are titled where they are registered, and the framework reads those.
        "One post" is the right title in a list of *kinds* of page and the wrong
        one in a list of pages a reader has been to, which is the whole reason
        this override exists.

        Subjects and forum names are deliberately not looked up. A history frame
        lists nine pages, which would be nine queries for a label, and the page
        number beside each entry already says which post it is.
        """
        found = self.route(address)
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
        #  Everything else is what the page said it was when it was registered.
        return super().describe(address)

    # -- menus --------------------------------------------------------------

    @page("1", name="main", title="Main index", keywords=("MAIN", "INDEX", "HOME"))
    async def _main_index(self, request: PageRequest) -> Page:
        held = await self._read(lambda repository: repository.count_posts())
        items = [
            MenuItem.for_page(self, name)
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
        return self._menu(
            request.address,
            title=SERVICE_NAME,
            items=items,
            preamble=["Stardot, for users of Acorn computers.", f"{held} posts held."],
        )

    @page(
        "8",
        name="posts",
        title="Latest posts",
        detail="the newest first",
        keywords=("LATEST", "NEW", "POSTS"),
    )
    async def _latest_posts(self, request: PageRequest) -> Page:
        posts = await self._read(lambda repository: repository.latest_posts(limit=60))
        return self._posts_menu(request.address, "LATEST POSTS", posts)

    @page(
        "3",
        name="days",
        title="By day",
        detail="browse by date",
        keywords=("DAYS",),
    )
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

    @page("32{day:date}", name="day", title="One day")
    async def _day(self, request: PageRequest, day: date) -> Page:
        posts = await self._read(lambda repository: repository.posts_on(day))
        return self._posts_menu(request.address, _day_title(day), posts)

    @page(
        "4",
        name="forums",
        title="By forum",
        detail="browse by section",
        keywords=("FORUMS",),
    )
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

    @page("42{forum_id:int}", name="forum", title="One forum")
    async def _forum(self, request: PageRequest, forum_id: int) -> Page:
        posts = await self._read(lambda repository: repository.posts_in_forum(forum_id))
        #  Ask the archive rather than the post: a post first seen in a
        #  per-topic feed knows its forum's id but not its name, and the archive
        #  keeps whichever name any post supplied.
        forums = await self._read(lambda repository: repository.forums())
        named = {found_id: name for found_id, name, _ in forums}
        title = named.get(forum_id) or f"FORUM {forum_id}"
        return self._posts_menu(request.address, title, posts)

    @page(
        "5",
        name="contributors",
        title="By contributor",
        detail="browse by poster",
        keywords=("WHO", "USERS"),
    )
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

    @page("52{user_id:int}", name="contributor", title="One contributor")
    async def _contributor(self, request: PageRequest, user_id: int) -> Page:
        posts = await self._read(lambda repository: repository.posts_by_author(user_id))
        title = posts[0].author_name if posts else f"USER {user_id}"
        return self._posts_menu(request.address, title, posts)

    @page(
        "7",
        name="topics",
        title="By topic",
        detail="read whole threads",
        keywords=("TOPICS",),
    )
    async def _topics_index(self, request: PageRequest) -> Page:
        topics = await self._read(lambda repository: repository.topics(limit=60))
        if not topics:
            return Prose.of(
                "NO TOPICS held yet.",
                "Topics are known only for posts seen since the board's feed "
                "began carrying them. Older posts have none.",
                title="BY TOPIC",
                home=self.index,
            ).build(request.address)
        items = [
            MenuItem(
                title,
                f"{count} post{'' if count == 1 else 's'}",
                self.address_for("topic", topic_id=topic_id),
            )
            for topic_id, title, count in topics
        ]
        return self._menu(request.address, title="BY TOPIC", items=items)

    @page("72{topic_id:int}", name="topic", title="One topic")
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
        empty: str = "",
    ) -> Page:
        """A menu, dealt nine to a frame by the framework's template."""
        return Menu(
            title=title,
            entries=items,
            home=self.index,
            preamble=preamble or (),
            empty=empty,
        ).build(address)

    # -- content pages ------------------------------------------------------

    @page("82{post_id:int}", name="post", title="One post")
    async def _post(self, request: PageRequest, post_id: int) -> Page:
        post = await self._read(lambda repository: repository.post(post_id))
        if post is None:
            return Prose.of(
                f"Post {post_id} is NOT in the archive.",
                "This service holds what it has seen in the board's feed, "
                "which reaches back only a little way.",
                title="POST",
                home=self.index,
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

    @page("0", name="title")
    async def _title(self, request: PageRequest) -> Page:
        """The frame the line opens on: what this is, and how to get in.

        No page number in the header, because `*0#` is the back command and a
        number a reader cannot key is an instruction that misleads them.
        """
        held = await self._read(lambda repository: repository.count_posts())
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
            width=COLUMNS - 1,
            colour=BANNER_BACKGROUND,
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
        #  so that it reads as the second line and not a second title. The
        #  stripe behind it is a row where the word is three, which puts a band
        #  through its waist and leaves the rest on the frame's black: the same
        #  two colours as the name above, said more quietly.
        lettering.boxed(
            layout,
            SUBTITLE_ROW,
            SERVICE_KIND,
            load_font(SUBTITLE_FACE),
            BANNER_COLOUR,
            BANNER_BACKGROUND,
            rows=1,
            padding=2,
            spacing=Spacing.KERNED,
        )
        layout.draw(canvas)
        rule(canvas, 10)
        canvas.row(12).text("The Stardot forum for users of Acorn", Colour.WHITE)
        canvas.row(13).text("computers, as 40-column frames.", Colour.WHITE)
        canvas.row(15).text(f"{held} posts held.", Colour.GREEN)
        #  Each colour change costs a cell, which shows as a space -- so the
        #  attribute is the space, rather than being paid for on top of one.
        canvas.row(17).text("Key", Colour.WHITE).text("#", Colour.YELLOW).text(
            "for the main index.", Colour.WHITE
        )
        canvas.row(19).text("Key", Colour.WHITE).text("*91#", Colour.YELLOW).text(
            "for how to get about.", Colour.WHITE
        )
        return Page(
            frames=(
                PageFrame(
                    frame=canvas.frame,
                    choices={"1": self.address_for("main")},
                    moves=frozenset({NEXT_FRAME_KEY, CONVENTIONAL_NEXT_FRAME_KEY}),
                ),
            ),
            #  `#` is the one key a viewdata reader tries without being told, and
            #  a title frame is nothing but an invitation to press it.
            follows=self.address_for("main"),
        )

    @page(
        "91",
        name="help",
        title="How to get about",
        detail="the keys, and what they do",
        keywords=("HELP", "GUIDE", "KEYS"),
    )
    async def _help(self, request: PageRequest) -> Page:
        """How to get about, in two frames.

        Every key named here is one the service actually answers; a guide that
        drifts from the thing it describes is worse than none.
        """
        return self._guide(
            request.address,
            [
                [
                    ("1-9", "choose from a menu"),
                    ("0", "back to the main index"),
                    ("*nnn#", "go straight to a page"),
                    ("", ""),
                    ("W  S", "up and down the frames of"),
                    ("", "  one item"),
                    ("#", "the same as S"),
                    ("A  D", "back and forward through"),
                    ("", "  the items of a menu"),
                ],
                [
                    ("*0#", "back, through where you"),
                    ("", "  have been"),
                    ("*00#", "show this frame again"),
                    ("*09#", "fetch it afresh"),
                    ("*", "cancel a request being keyed"),
                    ("**", "cancel and begin again"),
                    ("DEL", "rub out a character"),
                    ("*90#", "ring off"),
                    ("", ""),
                    ("*93#", "every page and its number"),
                    ("*94#", "every word you can key"),
                ],
            ],
        )

    def _guide(self, address: PageAddress, batches: list[list[tuple[str, str]]]) -> Page:
        """A key on the left, what it does on the right."""
        frames = []
        for index, batch in enumerate(batches):
            canvas = Canvas()
            moving = _frame_moves(index, len(batches))
            draw_chrome(
                canvas,
                title="HOW TO GET ABOUT",
                page_number=address.frame_number(index),
                prompt=_prompt(moving, selecting=False),
            )
            for offset, (key, meaning) in enumerate(batch):
                row = canvas.row(CONTENT_FIRST_ROW + offset)
                if key:
                    row.text(f"{key:<7}", Colour.YELLOW)
                else:
                    row.skip(7)
                if meaning:
                    row.text(fitted(meaning, COLUMNS - 8), Colour.WHITE)
            frames.append(
                PageFrame(
                    frame=canvas.frame,
                    choices={"0": self.address_for("main")},
                    moves=_moves(moving),
                )
            )
        return Page(frames=tuple(frames))

    @page(
        "92",
        name="history",
        title="Where you have been",
        detail="this call, newest first",
        keywords=("HISTORY", "BEEN"),
    )
    async def _history(self, request: PageRequest) -> Page:
        """The framework's page, at this service's number."""
        return await self.history(request)

    @page(
        "94",
        name="names",
        title="Words you can key",
        detail="instead of a page number",
        keywords=("KEYWORDS", "WORDS"),
    )
    async def _names(self, request: PageRequest) -> Page:
        """The framework's page, at this service's number."""
        return await self.names(request)

    @page(
        "93",
        name="contents",
        title="Every page",
        detail="and the number that fetches it",
        keywords=("PAGES", "CONTENTS"),
    )
    async def _contents(self, request: PageRequest) -> Page:
        """The framework's page, at this service's number."""
        return await self.contents(request)

    @page("9", name="about", title="About this service", keywords=("ABOUT",))
    async def _about(self, request: PageRequest) -> Page:
        held = await self._read(lambda repository: repository.count_posts())
        return Prose.of(
            "A Viewdata service carrying posts from stardot.org.uk, for users "
            "of Acorn computers and emulators.",
            f"{held} posts held.",
            "Page numbers follow the board's own identifiers, so *82489493# "
            "here is post 489493 there.",
            "Served by Sextile, named after the star key on a viewdata keypad.",
            title=f"ABOUT {self.name.upper()}",
            home=self.index,
        ).build(request.address)

    #  Titled, and so listed: the contents page is a directory of numbers that
    #  do something rather than a menu of places to go, and a reader looking for
    #  how to ring off should find it there. 9 is the system namespace, where
    #  the second digit is a function, so *90# keeps its Prestel meaning.
    @page("90", name="logoff", title="Ring off", keywords=("BYE", "OFF"))
    async def _logoff(self, request: PageRequest) -> Page:
        return self._farewell(
            "GOODBYE",
            [f"Thank you for calling {self.name}.", "", "Ring off."],
        )

    async def timed_out(self, parting: Parting) -> Page:
        """Said in the service's own voice as an idle caller is released.

        Naming the page they were on, because the terminal keeps nothing and a
        reader who dials back in has no other way to pick up where they were.
        """
        return self._farewell(
            "RINGING OFF",
            [
                "No reply for some time, so the line",
                "has been released for somebody else.",
                "",
                f"You were reading *{parting.address}#.",
                "",
                f"Thank you for calling {self.name}. Do call",
                "again.",
            ],
        )

    def _farewell(self, title: str, lines: list[str]) -> Page:
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
                    fitted(line, COLUMNS - 1), Colour.WHITE
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
