"""Page numbers, and the references they name.

The first digit names a namespace and the second says what kind of page within
it, so the scheme has room to grow without renumbering anything:

    <root>          the namespace's index
    <root>1         search within it        (reserved, not yet built)
    <root>2<id>     one member of it

    1     service root        11  search everything
    3     days index          32<YYYYMMDD>   3220260802
    4     forums index    41 search   42<forum>  4253
    5     contributors    51 search   52<user>   5210058
    7     topics          71 search   72<topic>  7233387
    8     latest posts    81 search   82<post>   82489493
    9     system          90 logoff   91 status
    0, 2, 6             reserved

Because a page request is terminated by `#`, page numbers need not be
prefix-free -- `*8#` and `*82489493#` are unambiguously different -- so the
fields can vary in width and stay short.

Two deliberate irregularities. A namespace's index is the bare root and never
`<root>0`, because accepting both would give one page two numbers. And `9` is
the system namespace, where the second digit is a system function rather than a
content operation, so that `*90#` can keep its conventional Prestel meaning.

Every identifier comes from Stardot: post, forum and contributor ids all appear
in the Atom feed. Nothing here allocates a number, so nothing can renumber, and
a page number means the same thing on the web forum as on a BBC Micro. Topic ids
are not in the feed yet, which is why `72` is reserved rather than in use.
"""

from dataclasses import dataclass
from datetime import date
from typing import Final

_DATE_DIGITS: Final = 8
_FRAMES_PER_PAGE: Final = 26

#  The second digit selecting a member of a namespace, as opposed to its index
#  (0, unused) or a search within it (1, reserved).
_MEMBER: Final = "2"


class UnknownPageError(ValueError):
    """A page number that names nothing."""


@dataclass(frozen=True)
class MainIndex:
    """The service's front page."""


@dataclass(frozen=True)
class DaysIndex:
    """The index of days for which posts are held."""


@dataclass(frozen=True)
class Day:
    """Posts made on one day."""

    day: date


@dataclass(frozen=True)
class ForumsIndex:
    """The index of forums."""


@dataclass(frozen=True)
class Forum:
    """One forum, by its phpBB forum id."""

    forum_id: int


@dataclass(frozen=True)
class ContributorsIndex:
    """The index of contributors."""


@dataclass(frozen=True)
class Contributor:
    """One contributor, by their phpBB user id."""

    user_id: int


@dataclass(frozen=True)
class TopicsIndex:
    """The index of topics."""


@dataclass(frozen=True)
class Topic:
    """One topic, by its phpBB topic id."""

    topic_id: int


@dataclass(frozen=True)
class PostsIndex:
    """The latest posts."""


@dataclass(frozen=True)
class Post:
    """One post, by its phpBB post id."""

    post_id: int


@dataclass(frozen=True)
class About:
    """About the service."""


@dataclass(frozen=True)
class Logoff:
    """Disconnect, at the conventional Prestel page."""


PageRef = (
    MainIndex
    | DaysIndex
    | Day
    | ForumsIndex
    | Forum
    | ContributorsIndex
    | Contributor
    | TopicsIndex
    | Topic
    | PostsIndex
    | Post
    | About
    | Logoff
)

#  Named jumps. Prestel itself was almost entirely numeric, but other viewdata
#  services accepted keywords and there is no reason for our own server to be
#  bound by Prestel's database conventions. `*MAIN#` is easier to remember than
#  `*1#`, and costs nothing to offer alongside it.
_KEYWORDS: Final[dict[str, "PageRef"]] = {}


def parse_page_target(target: str) -> "PageRef":
    """The page a typed request names, whether by number or by keyword."""
    keyword = _KEYWORDS.get(target.strip().upper())
    if keyword is not None:
        return keyword
    return parse_page_number(target)


def keywords() -> dict[str, "PageRef"]:
    """The named jumps, for a page that wants to list them."""
    return dict(_KEYWORDS)


def parse_page_number(number: str) -> PageRef:
    """The page a number names, or raise ``UnknownPageError``."""
    if not number or not number.isdigit() or not number.isascii():
        raise UnknownPageError(f"{number!r} is not a page number")

    root, rest = number[0], number[1:]

    match root:
        case "1" if not rest:
            return MainIndex()
        case "3" if not rest:
            return DaysIndex()
        case "4" if not rest:
            return ForumsIndex()
        case "5" if not rest:
            return ContributorsIndex()
        case "7" if not rest:
            return TopicsIndex()
        case "8" if not rest:
            return PostsIndex()
        case "9" if not rest:
            return About()
        case "9" if rest == "0":
            return Logoff()
        case "3" | "4" | "5" | "7" | "8":
            return _parse_member(number, root, rest)

    raise UnknownPageError(f"{number!r} is in a reserved or unallocated namespace")


def _parse_member(number: str, root: str, rest: str) -> PageRef:
    """A page below a namespace root, whose kind the second digit selects."""
    kind, identifier = rest[0], rest[1:]
    if kind != _MEMBER:
        #  0 is the index's formal spelling and is not accepted, since the bare
        #  root already names it; 1 is reserved for search; the rest are free.
        raise UnknownPageError(f"{number!r} selects an unallocated kind under {root}")
    if not identifier:
        raise UnknownPageError(f"{number!r} names no member")

    if root == "3":
        return _parse_day(number, identifier)
    value = _identifier(number, identifier)
    match root:
        case "4":
            return Forum(value)
        case "5":
            return Contributor(value)
        case "7":
            return Topic(value)
        case _:
            return Post(value)


def format_page_number(reference: PageRef) -> str:
    """The number naming a page."""
    match reference:
        case MainIndex():
            return "1"
        case DaysIndex():
            return "3"
        case Day(day):
            return f"32{day:%Y%m%d}"
        case ForumsIndex():
            return "4"
        case Forum(forum_id):
            return f"42{forum_id}"
        case ContributorsIndex():
            return "5"
        case Contributor(user_id):
            return f"52{user_id}"
        case TopicsIndex():
            return "7"
        case Topic(topic_id):
            return f"72{topic_id}"
        case PostsIndex():
            return "8"
        case Post(post_id):
            return f"82{post_id}"
        case About():
            return "9"
        case Logoff():
            return "90"


def frame_letter(index: int) -> str:
    """The letter naming a frame within a page, counting from ``a``.

    A user never types this: it identifies a continuation of a page that was too
    long for one screen, and appears only in the page number a frame displays.
    """
    if not 0 <= index < _FRAMES_PER_PAGE:
        raise ValueError(f"a page has at most {_FRAMES_PER_PAGE} frames, not frame {index}")
    return chr(ord("a") + index)


def _parse_day(number: str, digits: str) -> PageRef:
    if len(digits) != _DATE_DIGITS:
        raise UnknownPageError(f"{number!r} is not a day: expected {_DATE_DIGITS} date digits")
    try:
        return Day(date(int(digits[:4]), int(digits[4:6]), int(digits[6:])))
    except ValueError:
        raise UnknownPageError(f"{number!r} is not a real date") from None


def _identifier(number: str, rest: str) -> int:
    #  Stardot's identifiers never carry a leading zero, so accepting one would
    #  give a single page two different numbers.
    if rest.startswith("0"):
        raise UnknownPageError(f"{number!r} has a leading zero in its identifier")
    return int(rest)


_KEYWORDS.update(
    {
        "MAIN": MainIndex(),
        "INDEX": MainIndex(),
        "HOME": MainIndex(),
        "LATEST": PostsIndex(),
        "NEW": PostsIndex(),
        "POSTS": PostsIndex(),
        "DAYS": DaysIndex(),
        "FORUMS": ForumsIndex(),
        "WHO": ContributorsIndex(),
        "USERS": ContributorsIndex(),
        "TOPICS": TopicsIndex(),
        "ABOUT": About(),
        "HELP": About(),
        "BYE": Logoff(),
        "OFF": Logoff(),
    }
)
