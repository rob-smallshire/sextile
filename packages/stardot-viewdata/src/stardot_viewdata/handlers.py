"""The Stardot service's page handlers, each declared beside its function.

Menus are the shape most pages take. A reader selects with a single keypress, so
a menu offers at most nine choices on a frame and moving down goes to the next
nine. Digit 0 always returns to the main index: it is the one key a reader who
has lost their bearings can rely on.

Where the archive has nothing to show, the page says so. An empty menu with no
explanation looks like a fault, and on a service that deliberately answers
slowly a reader has no way to tell the difference.

The pages are ordinary functions. Nothing here closes over anything: a page
takes the archive from what the service holds and the numbering from the
service itself, both through the request it is given. The `@router.page`
declaration above each is everything the service says about it, and the order
they are written in is the order the contents page lists them; the assembly
spreads `router` into the service.

The numbering is documented in docs/page-numbering.md. Its one rule worth
repeating here is that every identifier comes from Stardot -- post, forum, topic
and contributor ids are the board's own -- so nothing in this file allocates a
number, nothing can renumber, and a page number means the same thing on the web
forum as on a BBC Micro.
"""

import asyncio
from collections.abc import Callable
from datetime import date
from typing import Final

from sextile import (
    GuideRow,
    Page,
    PageRequest,
    PageRouter,
    StateKey,
    farewell_page,
    keyed,
    menu_page,
    notice_page,
    prose_page,
)
from sextile.formatting import MenuItem
from sextile.layout import (
    HOME_KEY,
    Custom,
    OnOneFrame,
    PageLayout,
    Shortcut,
)
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import ROWS
from stardot_viewdata.model import Post
from stardot_viewdata.post_page import (
    CONVENTIONAL_NEXT_FRAME_KEY,
    post_page,
    time_of,
)
from stardot_viewdata.store.repository import Repository
from stardot_viewdata.title_frame import draw_masthead

#: What this service is called, which is not what the framework is called.
SERVICE_NAME: Final = "STARDOT"

#: What the archive is held under, in what the service holds. A key rather
#: than a string, so every page narrows what it takes in the same call and a
#: mistyped key fails by name.
ARCHIVE: Final = StateKey[Repository]("archive")

#: The service's own pages, each declared beside its handler below. The assembly
#: spreads this into `Sextile(pages=...)`; declaration order is contents order.
router: Final = PageRouter()


async def _read[T](request: PageRequest, query: Callable[[Repository], T]) -> T:
    """Ask the archive something, off the event loop.

    SQLite is synchronous, and a caller waiting on a query should not be every
    caller waiting on it.
    """
    return await asyncio.to_thread(query, request.state[ARCHIVE])


@router.page("0")
async def title(request: PageRequest) -> Page:
    """The frame the line opens on: what this is, and how to get in.

    No page number in the header, because `*0#` is the back command and a
    number a reader cannot key is an instruction that misleads them.
    """
    app = request.app
    held = await _read(request, lambda repository: repository.count_posts())
    #  Both instructions are built from the pages they name and the keys this
    #  frame actually answers, so neither can come to say something the service
    #  no longer does. The words are the ones the pages were registered with,
    #  and the numbers are the ones the router would build.
    index, guide_item = app.menu_item("main"), app.menu_item("help")
    main_page, about = app.address_for("main"), app.address_for("help")

    def draw(canvas: Canvas, row: int) -> None:
        draw_masthead(canvas, SERVICE_NAME)
        canvas.row(row + 12).text("The Stardot forum for users of Acorn", Colour.WHITE)
        canvas.row(row + 13).text("computers and emulators.", Colour.WHITE)
        canvas.row(row + 15).text(f"{held} posts held.", Colour.GREEN)
        #  Each colour change costs a cell, which shows as a space -- so the
        #  attribute is the space, rather than being paid for on top of one.
        canvas.row(row + 17).text("Key", Colour.WHITE).text(
            CONVENTIONAL_NEXT_FRAME_KEY, Colour.YELLOW
        ).text(f"for the {index.text.lower()}.", Colour.WHITE)
        canvas.row(row + 19).text("Key", Colour.WHITE).text(
            keyed(about), Colour.YELLOW
        ).text(f"for {guide_item.text.lower()}.", Colour.WHITE)

    return PageLayout(
        #  None at all: a masthead is the whole frame.
        furniture=(),
        #  No `0` either: the opening frame is where a reader arrives, so there
        #  is no index to send them back to that they are not already at.
        home=None,
        #  `#` is the one key a viewdata reader tries without being told, and a
        #  title frame is nothing but an invitation to press it. Setting this
        #  answers that key as well as saying where it leads.
        next_page=main_page,
        shortcuts=[Shortcut(key="1", destination=main_page)],
        parts=[OnOneFrame(Custom(rows=ROWS, draw=draw))],
    ).build(request)


@router.page("1", name="main", title="Main index", keywords=("MAIN", "INDEX", "HOME"))
async def main_index(request: PageRequest) -> Page:
    """The index: what the service offers, and how many posts it holds."""
    app = request.app
    held = await _read(request, lambda repository: repository.count_posts())
    items = [
        app.menu_item(name)
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
    return menu_page(
        request,
        title=SERVICE_NAME,
        items=items,
        preamble=["Stardot, for users of Acorn computers.", f"{held} posts held."],
    )


@router.page("3", name="days", title="By day", detail="browse by date", keywords=("DAYS",))
async def days_index(request: PageRequest) -> Page:
    """The sixty most recent days posts were made on, the newest first."""
    app = request.app
    days = await _read(request, lambda repository: repository.days(limit=60))
    if not days:
        return notice_page(request, "NO POSTS held yet.")
    items = [
        MenuItem(
            day_title(day),
            f"{count} post{'' if count == 1 else 's'}",
            app.address_for("day", day=day),
        )
        for day, count in days
    ]
    return menu_page(request, items=items)


@router.page(
    "32{day:date}",
    name="day",
    title="One day",
    #  In a list of visited pages "One day" is the wrong words, naming the kind
    #  of page rather than the day. day_title is defined below this, so the
    #  label is deferred to a lambda rather than named directly.
    label=lambda day: day_title(day),
)
async def one_day(request: PageRequest, day: date) -> Page:
    """Every post held from one day, in the order they were published."""
    posts = await _read(request, lambda repository: repository.posts_on(day))
    return _posts_menu(request, posts, day_title(day))


@router.page("4", name="forums", title="By forum", detail="browse by section",
      keywords=("FORUMS",))
async def forums_index(request: PageRequest) -> Page:
    """The forums posts have been seen in, with how many are held from each."""
    app = request.app
    forums = await _read(request, lambda repository: repository.forums())
    if not forums:
        return notice_page(request, "NO POSTS held yet.")
    items = [
        MenuItem(
            name,
            f"{count} post{'' if count == 1 else 's'}",
            app.address_for("forum", forum_id=forum_id),
        )
        for forum_id, name, count in forums
    ]
    return menu_page(request, items=items)


@router.page("42{forum_id:int}", name="forum", title="One forum", label="Forum {forum_id}")
async def one_forum(request: PageRequest, forum_id: int) -> Page:
    """The newest posts held from one forum."""
    posts = await _read(request, lambda repository: repository.posts_in_forum(forum_id))
    #  Ask the archive rather than the post: a post first seen in a
    #  per-topic feed knows its forum's id but not its name, and the archive
    #  keeps whichever name any post supplied.
    forums = await _read(request, lambda repository: repository.forums())
    named = {found_id: name for found_id, name, _ in forums}
    title = named.get(forum_id) or f"FORUM {forum_id}"
    return _posts_menu(request, posts, title)


@router.page("5", name="contributors", title="By contributor", detail="browse by poster",
      keywords=("WHO", "USERS"))
async def contributors_index(request: PageRequest) -> Page:
    """Everyone who has posted, the most prolific first."""
    app = request.app
    contributors = await _read(request, lambda repository: repository.contributors())
    if not contributors:
        return notice_page(request, "NO POSTS held yet.")
    items = [
        MenuItem(
            name,
            f"{count} post{'' if count == 1 else 's'}",
            app.address_for("contributor", user_id=user_id),
        )
        for user_id, name, count in contributors
    ]
    return menu_page(request, items=items)


@router.page(
    "52{user_id:int}", name="contributor", title="One contributor", label="Contributor {user_id}"
)
async def one_contributor(request: PageRequest, user_id: int) -> Page:
    """The newest posts held from one contributor."""
    posts = await _read(request, lambda repository: repository.posts_by_author(user_id))
    title = posts[0].author_name if posts else f"USER {user_id}"
    return _posts_menu(request, posts, title)


@router.page("7", name="topics", title="By topic", detail="read whole threads",
      keywords=("TOPICS",))
async def topics_index(request: PageRequest) -> Page:
    """The sixty topics most recently posted to, the newest first.

    Topics are known only for posts seen since the board's feed began
    carrying them, which the page says where it has none to show.
    """
    app = request.app
    topics = await _read(request, lambda repository: repository.topics(limit=60))
    if not topics:
        return prose_page(
            request,
            "NO TOPICS held yet.",
            "Topics are known only for posts seen since the board's feed began "
            "carrying them. Older posts have none.",
        )
    items = [
        MenuItem(
            title,
            f"{count} post{'' if count == 1 else 's'}",
            app.address_for("topic", topic_id=topic_id),
        )
        for topic_id, title, count in topics
    ]
    return menu_page(request, items=items)


@router.page("72{topic_id:int}", name="topic", title="One topic", label="Topic {topic_id}")
async def one_topic(request: PageRequest, topic_id: int) -> Page:
    """Every post held from one topic."""
    posts = await _read(request, lambda repository: repository.posts_in_topic(topic_id))
    title = posts[0].topic_title if posts else f"TOPIC {topic_id}"
    return _posts_menu(request, posts, title)


@router.page("8", name="posts", title="Latest posts", detail="the newest first",
      keywords=("LATEST", "NEW", "POSTS"))
async def latest_posts(request: PageRequest) -> Page:
    """The sixty newest posts held, whatever forum or topic they are from."""
    posts = await _read(request, lambda repository: repository.latest_posts(limit=60))
    return _posts_menu(request, posts)


@router.page("82{post_id:int}", name="post", title="One post", label="Post {post_id}")
async def one_post(request: PageRequest, post_id: int) -> Page:
    """One post in full, or a notice where the archive has not seen it."""
    post = await _read(request, lambda repository: repository.post(post_id))
    if post is None:
        return prose_page(
            request,
            f"Post {post_id} is NOT in the archive.",
            "This service holds what it has seen in the board's feed, which "
            "reaches back only a little way.",
            title="POST",
        )
    return post_page(request, post, untitled=SERVICE_NAME)


@router.page("9", name="about", title="About this service", keywords=("ABOUT",))
async def about(request: PageRequest) -> Page:
    """What the service is, how much it holds, and how its numbering works."""
    app = request.app
    held = await _read(request, lambda repository: repository.count_posts())
    return prose_page(
        request,
        "A Viewdata service carrying posts from stardot.org.uk, for users of "
        "Acorn computers and emulators.",
        f"{held} posts held.",
        "Page numbers follow the board's own identifiers, so *82489493# here is "
        "post 489493 there.",
        "Served by Sextile, named after the star key on a viewdata keypad.",
        title=f"ABOUT {app.name.upper()}",
    )


#  Titled, and so listed: the contents page is a directory of numbers that
#  do something rather than a menu of places to go, and a reader looking
#  for how to ring off should find it there. 9 is the system namespace,
#  where the second digit is a function, so *90# keeps its Prestel meaning.
@router.page("90", name="logoff", title="Log off", keywords=("BYE", "OFF"))
async def logoff(request: PageRequest) -> Page:
    """The farewell frame, after which the line drops."""
    app = request.app
    return farewell_page(
        request, "GOODBYE", f"Thank you for calling {app.name}.", "", "Ring off."
    )


@router.page("91", name="help", title="How to get about",
      detail="the keys, and what they do", keywords=("HELP", "GUIDE", "KEYS"))
async def guide(request: PageRequest) -> Page:
    """How to get about: the framework's guide, with this service's own rows.

    Most of a guide is a description of the framework -- the keys, the two
    frames, the compass under the first -- and a description that drifts from
    what it describes is worse than none, so the framework builds it. What is
    left for a service is the rows only it can know, which here are the pages it
    keeps its own numbers for.
    """
    app = request.app
    return await app.guide_page(
        request,
        asking=[
            GuideRow(keyed(app.address_for("logoff")), "log off"),
            GuideRow(),
            GuideRow(keyed(app.address_for("contents")), "every page and its number"),
            GuideRow(keyed(app.address_for("keywords")), "every word you can key"),
        ],
    )


# -- the service's own voice, off any page number -----------------------------


def ringing_off(request: PageRequest) -> Page:
    """Said in the service's own voice as an idle caller is released.

    Naming the page they were on, because the terminal keeps nothing and a
    reader who dials back in has no other way to pick up where they were. The
    request is the page they were on.
    """
    app = request.app
    return farewell_page(
        request,
        "RINGING OFF",
        "No reply for some time, so the line",
        "has been released for somebody else.",
        "",
        f"You were reading *{request.address}#.",
        "",
        f"Thank you for calling {app.name}. Do call",
        "again.",
    )


def unknown_page(request: PageRequest, target: str) -> Page:
    """Say so, in the service's own furniture, and leave the way back open."""
    return notice_page(
        request,
        f"*{target[:30]}# is NOT a page here.",
        "",
        "Try *1# for the main index.",
        title="UNKNOWN PAGE",
        #  The notice answers no page of its own, so the number is hidden.
        numbered=False,
        #  The advice rides in the label: there is no key for "another page",
        #  only the command line. Shortened to "index" where the row is tight,
        #  the short form being first.
        home=Shortcut(
            key=HOME_KEY,
            destination=request.app.address_for("main"),
            label="index, or key another page",
        ),
    )


# -- the shapes the pages above share -----------------------------------------


def _posts_menu(
    request: PageRequest, posts: list[Post], title: str | None = None
) -> Page:
    if not posts:
        return notice_page(request, "NO POSTS held for this page.", title=title)
    items = [
        MenuItem(
            post.subject,
            f"{post.author_name}  {time_of(post)}",
            request.app.address_for("post", post_id=post.post_id),
        )
        for post in posts
    ]
    return menu_page(request, title=title, items=items)






def day_title(day: date) -> str:
    """A day as a menu names it, and as the history describes one."""
    return day.strftime("%a %d %b %Y").upper()
