"""What has been read, and how often.

A log of page fetches, and the two questions a service asks of one: what has
been looked at lately, and what gets looked at most. Both are the same shape on
every service, because a page number is the framework's own vocabulary -- so
the log, the middleware that writes it and the pages that read it are here, and
what a service adds is only its numbering.

**A protocol, and one implementation of it.** `Visits` is what the middleware
and the pages talk to; `SqliteVisits` is the one that keeps a file. It is the
same arrangement as every other impure edge in this framework: narrow enough to
fake in a test, and a service that wants its log somewhere else writes forty
lines rather than going without the pages.

**The record is the address.** `52<id>` is what the reader keyed, what the
router can parse back, and what `describe` can name -- so there is nothing else
to store and nothing that can come to disagree with it. A prefix filter is then
a namespace filter, which is what a first digit already means.

**The caller is a token, not an address.** Counting readers needs to know how
many and nothing else. A random token minted per connection answers that and
reveals nothing about who.

**A page that was not there is logged too.** A count of pages fetched that
quietly omitted the ones nobody could reach would be the wrong count, and the
numbers readers key wrongly are worth knowing. They are kept out of what is read
back: a page that does not exist does not belong on a list of popular ones.
"""

import asyncio
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final, Protocol, Self, runtime_checkable

from sextile.addressing import PageAddress

__all__ = [
    "KEPT",
    "SqliteVisits",
    "Visit",
    "Visits",
]

#: How long a visit is kept. Thirty days is what "lately" means; it is a setting
#: rather than a rule, since a service with more readers may want less of it.
KEPT: Final = timedelta(days=30)

_SCHEMA: Final = """
create table if not exists visits (
    at      text not null,
    caller  text not null,
    page    text not null,
    found   integer not null
);
create index if not exists visits_by_time on visits(at);
create index if not exists visits_by_page on visits(page, at);
"""


@dataclass(frozen=True)
class Visit:
    """One page, and what the log has to say about it."""

    page: PageAddress
    at: datetime
    """The last time it was fetched."""

    times: int = 1
    """How often, over whatever period was asked for."""


@runtime_checkable
class Visits(Protocol):
    """A log of what has been read.

    Every method is asynchronous, because the one implementation that keeps a
    file does its work in a thread and a page must not wait on a disk.
    """

    async def record(
        self, page: PageAddress, *, caller: str, found: bool, at: datetime | None = None
    ) -> None:
        """Note that a page was fetched."""

    async def recent(self, limit: int, *, prefix: str = "") -> Sequence[Visit]:
        """The pages fetched most recently, newest first, one entry apiece."""

    async def popular(
        self, limit: int, *, prefix: str = "", since: datetime | None = None
    ) -> Sequence[Visit]:
        """The pages fetched most often, the most read first."""

    async def callers(self, *, since: datetime | None = None) -> int:
        """How many distinct callers have been seen."""


class SqliteVisits:
    """The log, in a file of its own.

    A file of its own rather than a table in a service's own database, because
    a service's own database is often derived and rebuilt, whereas a log is the
    only copy of what it holds.
    """

    def __init__(self, connection: sqlite3.Connection, *, kept: timedelta = KEPT) -> None:
        self._connection = connection
        self._kept = kept
        self._trimmed: datetime | None = None

    @classmethod
    def open(cls, filepath: Path | str, *, kept: timedelta = KEPT) -> Self:
        connection = sqlite3.connect(filepath, check_same_thread=False)
        connection.executescript(_SCHEMA)
        connection.commit()
        return cls(connection, kept=kept)

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *unused: object) -> None:
        self.close()

    async def record(
        self, page: PageAddress, *, caller: str, found: bool, at: datetime | None = None
    ) -> None:
        when = at or datetime.now(UTC)
        await _in_a_thread(self._write, page, caller, found, when)

    def _write(
        self, page: PageAddress, caller: str, found: bool, when: datetime
    ) -> None:
        self._connection.execute(
            "insert into visits (at, caller, page, found) values (?, ?, ?, ?)",
            (when.isoformat(), caller, page.digits, int(found)),
        )
        self._trim(when)
        self._connection.commit()

    def _trim(self, when: datetime) -> None:
        """Drop what is past keeping, once a day rather than once a page.

        The delete is cheap and doing it on every fetch would still be a write
        nobody asked for. A day is short enough that the file has a ceiling and
        long enough that the cost disappears.
        """
        if self._trimmed is not None and self._trimmed.date() == when.date():
            return
        self._connection.execute(
            "delete from visits where at < ?", ((when - self._kept).isoformat(),)
        )
        self._trimmed = when

    async def recent(self, limit: int, *, prefix: str = "") -> Sequence[Visit]:
        return await _in_a_thread(self._recent, limit, prefix)

    def _recent(self, limit: int, prefix: str) -> list[Visit]:
        rows = self._connection.execute(
            "select page, max(at), count(*) from visits"
            " where found = 1 and page like ?"
            " group by page order by max(at) desc limit ?",
            (f"{prefix}%", limit),
        )
        return [_visit(row) for row in rows]

    async def popular(
        self, limit: int, *, prefix: str = "", since: datetime | None = None
    ) -> Sequence[Visit]:
        return await _in_a_thread(self._popular, limit, prefix, since)

    def _popular(
        self, limit: int, prefix: str, since: datetime | None
    ) -> list[Visit]:
        rows = self._connection.execute(
            "select page, max(at), count(*) from visits"
            " where found = 1 and page like ? and at >= ?"
            " group by page order by count(*) desc, max(at) desc limit ?",
            (f"{prefix}%", _from(since), limit),
        )
        return [_visit(row) for row in rows]

    async def callers(self, *, since: datetime | None = None) -> int:
        return await _in_a_thread(self._callers, since)

    def _callers(self, since: datetime | None) -> int:
        (count,) = self._connection.execute(
            "select count(distinct caller) from visits where at >= ?", (_from(since),)
        ).fetchone()
        return int(count)


def _visit(row: tuple[str, str, int]) -> Visit:
    page, at, times = row
    return Visit(page=PageAddress(page), at=datetime.fromisoformat(at), times=times)


def _from(since: datetime | None) -> str:
    """The start of a window, or the beginning of time."""
    return since.isoformat() if since is not None else ""


async def _in_a_thread[T](work: Callable[..., T], *given: object) -> T:
    """SQLite off the event loop, as every other query in this workspace is."""
    return await asyncio.to_thread(work, *given)
