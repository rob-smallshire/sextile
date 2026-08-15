"""A log of what has been read, and the two questions asked of it.

What is worth testing is the questions: what has been looked at lately, what
gets looked at most, and how many callers there have been. The writing is a
row in a table.
"""

from datetime import UTC, datetime, timedelta

import pytest

from sextile.page import PageAddress
from sextile.visits import SqliteVisits, Visits

NOON = datetime(2026, 8, 11, 12, 0, tzinfo=UTC)


@pytest.fixture
def log() -> Visits:
    return SqliteVisits.open(":memory:")


async def seen(
    log: Visits, page: str, *, caller: str = "a", at: datetime = NOON, found: bool = True
) -> None:
    await log.record(PageAddress(page), caller=caller, found=found, at=at)


class TestWhatHasBeenReadLately:
    async def test_the_newest_first(self, log: Visits) -> None:
        await seen(log, "1", at=NOON)
        await seen(log, "3", at=NOON + timedelta(minutes=1))
        assert [visit.page.digits for visit in await log.recent(9)] == ["3", "1"]

    async def test_a_page_read_twice_appears_once(self, log: Visits) -> None:
        #  A list of what has been looked at is a list of things, not of
        #  fetches: nine rows of the same page would tell a reader nothing.
        await seen(log, "1", at=NOON)
        await seen(log, "1", at=NOON + timedelta(minutes=1))
        assert len(await log.recent(9)) == 1

    async def test_and_it_is_the_last_time_that_counts(self, log: Visits) -> None:
        await seen(log, "1", at=NOON)
        await seen(log, "3", at=NOON + timedelta(minutes=1))
        await seen(log, "1", at=NOON + timedelta(minutes=2))
        assert [visit.page.digits for visit in await log.recent(9)] == ["1", "3"]

    async def test_a_prefix_is_a_namespace(self, log: Visits) -> None:
        #  Which is what a first digit already means in this numbering.
        await seen(log, "1")
        await seen(log, "3213133880")
        await seen(log, "3216088148")
        held = await log.recent(9, prefix="321")
        assert {visit.page.digits for visit in held} == {"3213133880", "3216088148"}

    async def test_a_page_that_was_not_there_is_left_out(self, log: Visits) -> None:
        #  Logged, but not read back: a number that answers nothing has no
        #  business on a list of somewhere to go.
        await seen(log, "99999", found=False)
        assert await log.recent(9) == []


class TestWhatIsReadMost:
    async def test_the_most_read_first(self, log: Visits) -> None:
        for _ in range(3):
            await seen(log, "1")
        await seen(log, "3")
        assert [visit.page.digits for visit in await log.popular(9)] == ["1", "3"]

    async def test_and_it_says_how_often(self, log: Visits) -> None:
        for _ in range(3):
            await seen(log, "1")
        assert (await log.popular(9))[0].times == 3

    async def test_a_window_leaves_out_what_is_older(self, log: Visits) -> None:
        await seen(log, "1", at=NOON - timedelta(days=2))
        await seen(log, "3", at=NOON)
        held = await log.popular(9, since=NOON - timedelta(days=1))
        assert [visit.page.digits for visit in held] == ["3"]


class TestHowManyCallers:
    async def test_distinct_callers_and_not_fetches(self, log: Visits) -> None:
        await seen(log, "1", caller="a")
        await seen(log, "3", caller="a")
        await seen(log, "1", caller="b")
        assert await log.callers() == 2

    async def test_over_a_window(self, log: Visits) -> None:
        await seen(log, "1", caller="a", at=NOON - timedelta(days=2))
        await seen(log, "1", caller="b", at=NOON)
        assert await log.callers(since=NOON - timedelta(days=1)) == 1


class TestWhatIsKept:
    """Thirty days by default, and a setting rather than a rule."""

    async def test_what_is_past_keeping_goes(self) -> None:
        log = SqliteVisits.open(":memory:", retention=timedelta(days=7))
        await seen(log, "1", at=NOON - timedelta(days=8))
        #  Trimmed on the next write, since a delete on every fetch is a write
        #  nobody asked for.
        await seen(log, "3", at=NOON)
        assert [visit.page.digits for visit in await log.recent(9)] == ["3"]

    async def test_and_what_is_not_stays(self) -> None:
        log = SqliteVisits.open(":memory:", retention=timedelta(days=7))
        await seen(log, "1", at=NOON - timedelta(days=6))
        await seen(log, "3", at=NOON)
        assert len(await log.recent(9)) == 2

    async def test_the_trimming_happens_once_a_day_and_not_once_a_page(self) -> None:
        #  Two writes in the same day, and the second does not pay for it.
        log = SqliteVisits.open(":memory:", retention=timedelta(days=7))
        await seen(log, "1", at=NOON - timedelta(days=8))
        await seen(log, "3", at=NOON)
        #  A row older than the window, written after the trim for that day has
        #  already run, survives until the next one.
        await seen(log, "5", at=NOON - timedelta(days=9))
        assert len(await log.recent(9)) == 2
