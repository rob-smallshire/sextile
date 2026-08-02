"""The domain: what Sextile knows about a forum, independent of where it came from.

Nothing here mentions Atom, phpBB or HTTP. That is the seam a richer backend --
a phpBB extension, most likely -- slots into later without disturbing the
numbering, the renderer or the session layer.
"""

from dataclasses import dataclass
from datetime import datetime

REPLY_PREFIX = "Re: "


@dataclass(frozen=True)
class Post:
    """One post on the forum."""

    post_id: int
    """phpBB's own post id, which is also this post's page number."""

    forum_id: int | None
    """Absent in per-topic feeds, which carry no category naming the forum."""

    forum_name: str

    author_name: str
    author_id: int | None
    """phpBB's user id, absent when the poster has no profile link."""

    subject: str
    """The post's own title, as displayed, including any reply marker."""

    published: datetime
    updated: datetime

    url: str
    content_html: str
    """The post body as the feed supplied it, kept verbatim so the rendering
    pipeline can be re-run over real historical input."""

    @property
    def is_reply(self) -> bool:
        return self.subject.startswith(REPLY_PREFIX)

    @property
    def topic_title(self) -> str:
        """The subject with any reply marker removed, naming the thread."""
        return self.subject.removeprefix(REPLY_PREFIX)


@dataclass(frozen=True)
class Feed:
    """One retrieval of a feed, whatever slice of the board it covered."""

    title: str
    updated: datetime | None
    posts: tuple[Post, ...]
    problems: tuple[str, ...] = ()
    """Entries that could not be understood, described rather than discarded
    silently: a feed whose shape has changed should be visible, not invisible."""
