"""Reading and writing the archive.

Deliberately synchronous. The queries are small and indexed, and wrapping SQLite
in an async facade would buy nothing but indirection; where a caller is on the
event loop it should reach this through ``asyncio.to_thread`` at the boundary,
which keeps the blocking explicit and in one place.

That means the connection is used from whichever worker thread ``to_thread``
happens to pick, so it is opened with ``check_same_thread=False`` and every
statement runs under a lock. SQLite itself is happy to be used this way provided
access is serialised, and serialising costs nothing at this scale.

Two decisions are baked into the schema rather than repeated at every call site:
instants are stored in UTC so that ordering by text is ordering by time, and a
post's London calendar date is computed once on the way in, because days are
London days and deriving that in SQL would be both slow and obscure.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from types import TracebackType
from typing import Final, Self
from zoneinfo import ZoneInfo

from sextile.model import Post

BOARD_TIMEZONE: Final = ZoneInfo("Europe/London")

_SCHEMA_FILEPATH: Final = Path(__file__).with_name("schema.sql")

_POST_COLUMNS: Final = (
    "post_id, forum_id, forum_name, author_id, author_name, "
    "subject, published, updated, url, content_html"
)


class Repository:
    """The archive of posts."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._connection.executescript(_SCHEMA_FILEPATH.read_text())

    @classmethod
    def open(cls, database_filepath: Path | str) -> Self:
        """The archive held in a file, created if it is not there."""
        path = Path(database_filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        return cls(sqlite3.connect(path, check_same_thread=False))

    @classmethod
    def in_memory(cls) -> Self:
        """A throwaway archive, for tests."""
        return cls(sqlite3.connect(":memory:", check_same_thread=False))

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exception_type: type[BaseException] | None,
        exception: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    # -- writing ------------------------------------------------------------

    def add_post(self, post: Post, *, now: datetime | None = None) -> bool:
        """Store a post, replacing an earlier copy of it.

        Returns whether the post was one we had not seen before, which is what
        distinguishes news from the feed simply showing us its window again.
        """
        seen_at = (now or datetime.now(UTC)).astimezone(UTC)
        with self._transaction() as cursor:
            known = cursor.execute(
                "SELECT first_seen FROM posts WHERE post_id = ?", (post.post_id,)
            ).fetchone()
            cursor.execute(
                f"INSERT OR REPLACE INTO posts ({_POST_COLUMNS}, local_date, first_seen) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    post.post_id,
                    post.forum_id,
                    post.forum_name,
                    post.author_id,
                    post.author_name,
                    post.subject,
                    _to_storage(post.published),
                    _to_storage(post.updated),
                    post.url,
                    post.content_html,
                    local_date(post.published).isoformat(),
                    #  An edit must not disturb when we first saw the post.
                    known["first_seen"] if known else _to_storage(seen_at),
                ),
            )
        return known is None

    # -- reading ------------------------------------------------------------

    def count_posts(self) -> int:
        row = self._one("SELECT COUNT(*) AS total FROM posts", ())
        return int(row["total"]) if row else 0

    def post(self, post_id: int) -> Post | None:
        row = self._one(f"SELECT {_POST_COLUMNS} FROM posts WHERE post_id = ?", (post_id,))
        return _to_post(row) if row else None

    def latest_posts(self, limit: int = 20) -> list[Post]:
        return self._posts(
            f"SELECT {_POST_COLUMNS} FROM posts ORDER BY published DESC LIMIT ?", (limit,)
        )

    def posts_on(self, day: date) -> list[Post]:
        """A day's posts, oldest first, because a day reads like a conversation."""
        return self._posts(
            f"SELECT {_POST_COLUMNS} FROM posts WHERE local_date = ? ORDER BY published",
            (day.isoformat(),),
        )

    def days(self, limit: int = 100) -> list[tuple[date, int]]:
        """The days with posts, newest first, each with how many."""
        rows = self._all(
            "SELECT local_date, COUNT(*) AS total FROM posts "
            "GROUP BY local_date ORDER BY local_date DESC LIMIT ?",
            (limit,),
        )
        return [(date.fromisoformat(row["local_date"]), int(row["total"])) for row in rows]

    def forums(self) -> list[tuple[int, str, int]]:
        """The forums seen, by id, with their post counts."""
        #  MAX picks a name over the empty string, because a post first seen in
        #  a per-topic feed knows its forum's id but not its name: the `rel=up`
        #  link there has an empty title. Whichever post supplies the name, the
        #  forum keeps it.
        rows = self._all(
            "SELECT forum_id, MAX(forum_name) AS forum_name, COUNT(*) AS total FROM posts "
            "WHERE forum_id IS NOT NULL GROUP BY forum_id ORDER BY forum_id",
            (),
        )
        return [(int(row["forum_id"]), row["forum_name"], int(row["total"])) for row in rows]

    def contributors(self) -> list[tuple[int, str, int]]:
        """The contributors seen, busiest first."""
        rows = self._all(
            "SELECT author_id, author_name, COUNT(*) AS total FROM posts "
            "WHERE author_id IS NOT NULL GROUP BY author_id "
            "ORDER BY total DESC, author_name",
            (),
        )
        return [(int(row["author_id"]), row["author_name"], int(row["total"])) for row in rows]

    def posts_in_forum(self, forum_id: int, limit: int = 50) -> list[Post]:
        return self._posts(
            f"SELECT {_POST_COLUMNS} FROM posts WHERE forum_id = ? "
            "ORDER BY published DESC LIMIT ?",
            (forum_id, limit),
        )

    def posts_by_author(self, author_id: int, limit: int = 50) -> list[Post]:
        return self._posts(
            f"SELECT {_POST_COLUMNS} FROM posts WHERE author_id = ? "
            "ORDER BY published DESC LIMIT ?",
            (author_id, limit),
        )

    # -- plumbing -----------------------------------------------------------

    def _posts(self, statement: str, parameters: tuple[object, ...]) -> list[Post]:
        return [_to_post(row) for row in self._all(statement, parameters)]

    def _all(self, statement: str, parameters: tuple[object, ...]) -> list[sqlite3.Row]:
        with self._lock:
            return self._connection.execute(statement, parameters).fetchall()

    def _one(self, statement: str, parameters: tuple[object, ...]) -> sqlite3.Row | None:
        with self._lock:
            row: sqlite3.Row | None = self._connection.execute(statement, parameters).fetchone()
        return row

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Cursor]:
        with self._lock, self._connection:
            cursor = self._connection.cursor()
            try:
                yield cursor
            finally:
                cursor.close()


def local_date(moment: datetime) -> date:
    """The board's calendar date for an instant."""
    return moment.astimezone(BOARD_TIMEZONE).date()


def _to_storage(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


def _to_post(row: sqlite3.Row) -> Post:
    return Post(
        post_id=int(row["post_id"]),
        forum_id=None if row["forum_id"] is None else int(row["forum_id"]),
        forum_name=row["forum_name"],
        author_id=None if row["author_id"] is None else int(row["author_id"]),
        author_name=row["author_name"],
        subject=row["subject"],
        published=datetime.fromisoformat(row["published"]),
        updated=datetime.fromisoformat(row["updated"]),
        url=row["url"],
        content_html=row["content_html"],
    )
