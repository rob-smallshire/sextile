"""What readers have been looking at, as pages a reader can look at.

Two of them, and both are menus rather than tables: every row is a page number,
so every row is somewhere to go. A list of what other people have been reading
that you cannot follow is a list that has been written at you.

Registered nowhere, like the history, the contents and the words. A service
maps them into its own numbering or does without.

**A page that no longer exists is left off.** A log is a record of what was
fetched and a menu is an offer, so the two are not the same list: a number that
answered last week and does not answer now belongs in one and not the other.
`describe` is asked, and a page the service will not name is not offered.
"""

from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from typing import Final

from sextile.addressing import PageAddress, keyed
from sextile.page import Page
from sextile.templates import CHOICES_PER_FRAME, Menu, MenuItem
from sextile.visits import Visit

RECENT_TITLE: Final = "Lately read"
POPULAR_TITLE: Final = "Most read"

_NOTHING_RECENT: Final = "Nothing has been read yet."
_NOTHING_POPULAR: Final = "Nothing has been read yet."

#: How long ago, in the largest unit that says something. A reader wants "an
#: hour ago" rather than "63 minutes ago", and "just now" rather than a figure
#: that will be wrong by the time the frame has finished arriving.
_AGES: Final = ((86400, "day"), (3600, "hour"), (60, "minute"))


def recent_page(
    *,
    address: PageAddress,
    visits: Sequence[Visit],
    describe: Callable[[PageAddress], str],
    home: PageAddress,
    title: str = RECENT_TITLE,
    now: datetime | None = None,
) -> Page:
    """What has been looked at lately, newest first."""
    when = now or datetime.now(UTC)
    return _menu(
        address=address,
        title=title,
        home=home,
        empty=_NOTHING_RECENT,
        entries=[
            (visit, _ago(when - visit.at.astimezone(UTC))) for visit in visits
        ],
        describe=describe,
    )


def popular_page(
    *,
    address: PageAddress,
    visits: Sequence[Visit],
    describe: Callable[[PageAddress], str],
    home: PageAddress,
    title: str = POPULAR_TITLE,
) -> Page:
    """What has been looked at most, the most read first."""
    return _menu(
        address=address,
        title=title,
        home=home,
        empty=_NOTHING_POPULAR,
        entries=[(visit, _times(visit.times)) for visit in visits],
        describe=describe,
    )


def _menu(
    *,
    address: PageAddress,
    title: str,
    home: PageAddress,
    empty: str,
    entries: Sequence[tuple[Visit, str]],
    describe: Callable[[PageAddress], str],
) -> Page:
    return Menu(
        title=title,
        entries=[
            MenuItem(
                text=named,
                detail=f"{keyed(visit.page)}  {said}",
                destination=visit.page,
            )
            for visit, said in entries
            if (named := describe(visit.page))
        ][:CHOICES_PER_FRAME],
        home=home,
        empty=empty,
    ).build(address)


def _ago(since: timedelta) -> str:
    """How long ago something happened, in one unit and plain words."""
    seconds = int(since.total_seconds())
    for size, unit in _AGES:
        if seconds >= size:
            how_many = seconds // size
            return f"{how_many} {unit}{'s' if how_many > 1 else ''} ago"
    return "just now"


def _times(count: int) -> str:
    return "read once" if count == 1 else f"read {count} times"
