"""Reading phpBB's Atom feed.

phpBB puts what Sextile needs in three awkward places, and this module knows
about all three so that nothing downstream has to:

- the **post id** is only in the entry's link, as `viewtopic.php?p=489493`;
- the **forum id** is only in the category's `scheme` URL;
- the **author's numeric id** is only in the `Statistics: Posted by ...` footer
  at the end of the post body -- markup the renderer later strips, so it has to
  be read here first.

An entry that cannot be understood is reported rather than dropped in silence:
a feed whose shape has changed should be noisy, not quietly empty.
"""

import re
from datetime import datetime
from typing import Final
from xml.etree import ElementTree

from sextile.model import Feed, Post

_ATOM: Final = "{http://www.w3.org/2005/Atom}"

#  phpBB joins the forum name and the subject with a bullet.
_TITLE_SEPARATOR: Final = " • "

_POST_ID: Final = re.compile(r"viewtopic\.php\?(?:[^\"#]*&(?:amp;)?)?p=(\d+)")
_FORUM_ID: Final = re.compile(r"viewforum\.php\?(?:[^\"#]*&(?:amp;)?)?f=(\d+)")
#  The profile link survives XML parsing with its ampersand still escaped,
#  because the body arrives inside a CDATA section.
_AUTHOR_ID: Final = re.compile(r"memberlist\.php\?[^\"]*?[?&](?:amp;)?u=(\d+)")


class FeedFormatError(ValueError):
    """A document that is not a usable Atom feed."""


def parse_feed(document: str) -> Feed:
    """Parse an Atom feed into posts."""
    try:
        root = ElementTree.fromstring(document)
    except ElementTree.ParseError as error:
        raise FeedFormatError(f"not well-formed XML: {error}") from error

    if root.tag != f"{_ATOM}feed":
        raise FeedFormatError(f"root element is {root.tag!r}, not an Atom feed")

    posts: list[Post] = []
    problems: list[str] = []
    for entry in root.findall(f"{_ATOM}entry"):
        try:
            posts.append(_parse_entry(entry))
        except FeedFormatError as error:
            problems.append(str(error))

    return Feed(
        title=_text(root, "title") or "",
        updated=_timestamp(root, "updated"),
        posts=tuple(posts),
        problems=tuple(problems),
    )


def _parse_entry(entry: ElementTree.Element) -> Post:
    url = _link(entry)
    content = _text(entry, "content") or ""
    forum_id, forum_name = _forum(entry)
    published = _timestamp(entry, "published") or _timestamp(entry, "updated")
    updated = _timestamp(entry, "updated") or published

    if published is None or updated is None:
        raise FeedFormatError(f"entry {url!r} has no timestamp")

    return Post(
        post_id=_post_id(entry, url),
        forum_id=forum_id,
        forum_name=forum_name,
        author_name=_author_name(entry),
        author_id=_author_id(content),
        subject=_subject(_text(entry, "title") or ""),
        published=published,
        updated=updated,
        url=url,
        content_html=content,
    )


def _post_id(entry: ElementTree.Element, url: str) -> int:
    #  The <id> element carries the same URL, so either will do; trying both
    #  costs nothing and tolerates a feed that fills in only one.
    for candidate in (url, _text(entry, "id") or ""):
        match = _POST_ID.search(candidate)
        if match:
            return int(match.group(1))
    raise FeedFormatError(f"entry {url or '<unknown>'!r} carries no post id")


def _forum(entry: ElementTree.Element) -> tuple[int | None, str]:
    """The forum a post belongs to, from whichever element says so.

    Board-wide and per-forum feeds carry a `<category>` naming the forum.
    Per-topic feeds carry none, but every entry now also has a
    `<link rel="up">` pointing at the forum, which is what fills that gap.
    The category is preferred where both are present, being the older and more
    specific of the two.
    """
    for found in (_forum_from_category(entry), _forum_from_up_link(entry)):
        if found[0] is not None:
            return found
    return None, ""


def _forum_from_category(entry: ElementTree.Element) -> tuple[int | None, str]:
    category = entry.find(f"{_ATOM}category")
    if category is None:
        return None, ""
    match = _FORUM_ID.search(category.get("scheme", ""))
    name = category.get("label") or category.get("term") or ""
    return (int(match.group(1)) if match else None), name


def _forum_from_up_link(entry: ElementTree.Element) -> tuple[int | None, str]:
    for link in entry.findall(f"{_ATOM}link"):
        if link.get("rel") != "up":
            continue
        #  It names the forum today; anything else is not to be mistaken for one.
        match = _FORUM_ID.search(link.get("href", ""))
        if match:
            return int(match.group(1)), link.get("title", "")
    return None, ""


def _author_name(entry: ElementTree.Element) -> str:
    author = entry.find(f"{_ATOM}author")
    if author is None:
        return ""
    return (author.findtext(f"{_ATOM}name") or "").strip()


def _author_id(content: str) -> int | None:
    match = _AUTHOR_ID.search(content)
    return int(match.group(1)) if match else None


def _subject(title: str) -> str:
    """The subject, with the forum name phpBB prepends removed.

    Split at the first separator: the forum name comes first, and a subject is
    free to contain a bullet of its own.
    """
    _, separator, subject = title.partition(_TITLE_SEPARATOR)
    return (subject if separator else title).strip()


def _link(entry: ElementTree.Element) -> str:
    link = entry.find(f"{_ATOM}link")
    return link.get("href", "") if link is not None else ""


def _text(element: ElementTree.Element, tag: str) -> str | None:
    found = element.find(f"{_ATOM}{tag}")
    return None if found is None else (found.text or "")


def _timestamp(element: ElementTree.Element, tag: str) -> datetime | None:
    text = _text(element, tag)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.strip())
    except ValueError:
        return None
